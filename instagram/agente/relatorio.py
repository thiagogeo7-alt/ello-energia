"""Relatório semanal de estratégia: números da semana + o que funcionou + o que fazer na próxima.

Roda toda segunda de manhã (Despertador). Manda por e-mail para a equipe e guarda no estado
(o painel mostra o último). Rodado à mão, gera um relatório novo mesmo que já exista um na semana.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import requests

from . import aprendizado, aviso, claude, config, estado, experimentos, instagram

BRASILIA = timezone(timedelta(hours=-3))
DIAS = 7

SISTEMA = f"""Você é o estrategista de crescimento do Instagram da ELLO Energia (energia solar compartilhada,
Campinas). Escreve o relatório semanal para o dono, que é leigo em tecnologia e em marketing:
português do Brasil simples, direto, sem jargão (explique termos como "alcance" em poucas palavras quando usar).

Regras:
- Use SOMENTE os números fornecidos. Nunca invente números, causas certas ou promessas de resultado.
- Conta nova tem números pequenos: avalie tendência e aprendizado, não "fracasso".
- Os testes A/B só têm conclusão quando o próprio resumo disser "vencedora"; antes disso, diga que ainda estão coletando.
- As recomendações para o agente devem ser coisas que um agente automático pode fazer (temas, formatos,
  ganchos, horários, legendas, chamadas para ação). As recomendações para a equipe são ações humanas
  (gravar um vídeo, responder pessoalmente um interessado, parceria com perfil local, pedir avaliação a cliente).
- Respeite o guia da marca abaixo.

Guia da marca (resumo):
{config.MARCA[:2500]}

Responda SOMENTE com JSON."""

PEDIDO = """Dados da semana ({periodo}):

CONTA
{conta}

PUBLICAÇÕES DA SEMANA
{posts}

INTERESSADOS (pessoas que pediram o WhatsApp ou demonstraram interesse): {leads_semana} nesta semana
(total desde o início: {leads_total})

TESTES A/B EM ANDAMENTO (Reels)
{testes}

PROSPECÇÃO POR E-MAIL
{prospeccao}

{historico}

Devolva JSON:
{{
  "manchete": "uma frase resumindo a semana",
  "o_que_aconteceu": "2 a 4 frases com os principais números e a tendência",
  "funcionou": ["até 3 itens, cada um com o post (código) ou o número que comprova"],
  "nao_funcionou": ["até 3 itens"],
  "testes_ab": "1 a 3 frases sobre os testes",
  "acoes_agente": ["3 ajustes concretos que o agente vai priorizar na próxima semana"],
  "acoes_equipe": ["2 ações humanas simples para a equipe nesta semana"]
}}"""

SIMULADO = {
    "manchete": "Semana de teste: o agente postou no ritmo e começou a medir o que funciona.",
    "o_que_aconteceu": "Simulação.", "funcionou": ["Simulação"], "nao_funcionou": ["Simulação"],
    "testes_ab": "Ainda coletando.", "acoes_agente": ["Simulação"] * 3, "acoes_equipe": ["Simulação"] * 2,
}


def _data(texto: str):
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None


def _semana_iso(momento: datetime) -> str:
    a, s, _ = momento.astimezone(BRASILIA).isocalendar()
    return f"{a}-S{s:02d}"


def _seguidores_ha(est: dict, dias: int) -> int | None:
    """Seguidores registrados há cerca de `dias` dias (fotografia diária feita pelas respostas)."""
    alvo = datetime.now(timezone.utc) - timedelta(days=dias)
    melhor = None
    for f in est.get("seguidores", []):
        d = _data(f.get("data", ""))
        if d and d <= alvo + timedelta(hours=12):
            melhor = f.get("total")
    return melhor


def _prospeccao(anterior: dict) -> tuple[str, dict]:
    """Lê o resumo público do agente de prospecção (branch prospeccao-dados)."""
    if config.SIMULAR:
        dados = {"total_contatos": 2500, "por_status": {"enviado": 40, "respondeu": 2, "interessado": 1},
                 "envios_por_dia": {datetime.now(BRASILIA).strftime("%Y-%m-%d"): 10}}
    else:
        try:
            r = requests.get(f"https://raw.githubusercontent.com/{config.REPO}/prospeccao-dados/resumo.json",
                             timeout=30)
            dados = r.json() if r.ok else {}
        except (requests.RequestException, ValueError):
            dados = {}
    if not dados:
        return "sem dados da prospecção nesta semana", {}
    desde = (datetime.now(BRASILIA) - timedelta(days=DIAS)).strftime("%Y-%m-%d")
    atual = {"empresas na base": dados.get("total_contatos", 0),
             "e-mails enviados na semana": sum(v for d, v in (dados.get("envios_por_dia") or {}).items() if d > desde)}
    atual.update({f"situação '{k}'": v for k, v in (dados.get("por_status") or {}).items()})
    linhas = []
    for k, v in atual.items():
        antes = anterior.get(k)
        variacao = f" ({v - antes:+d} desde o último relatório)" if isinstance(v, int) and isinstance(antes, int) \
            and "semana" not in k else ""
        linhas.append(f"- {k}: {v}{variacao}")
    return "\n".join(linhas), atual


def _texto_email(r: dict, periodo: str, conta_linhas: str, posts_linhas: str) -> str:
    def lista(itens):
        return "\n".join(f"  • {i}" for i in itens or []) or "  • —"
    return (f"{r.get('manchete', '')}\n\nPeríodo: {periodo}\n\n"
            f"O QUE ACONTECEU\n{r.get('o_que_aconteceu', '')}\n\n"
            f"O QUE FUNCIONOU\n{lista(r.get('funcionou'))}\n\n"
            f"O QUE NÃO FUNCIONOU\n{lista(r.get('nao_funcionou'))}\n\n"
            f"TESTES A/B\n{r.get('testes_ab', '')}\n\n"
            f"O AGENTE VAI PRIORIZAR NA PRÓXIMA SEMANA\n{lista(r.get('acoes_agente'))}\n\n"
            f"SUGESTÕES PARA A EQUIPE\n{lista(r.get('acoes_equipe'))}\n\n"
            f"—\nNÚMEROS DA CONTA\n{conta_linhas}\n\nPUBLICAÇÕES DA SEMANA\n{posts_linhas}\n")


def executar(agendado: bool = False) -> dict | None:
    config.exigir("ANTHROPIC_API_KEY")
    est = estado.carregar()
    agora = datetime.now(timezone.utc)
    semana = _semana_iso(agora)
    if agendado and any(x.get("semana") == semana for x in est.get("relatorios", [])):
        print(f"Relatório da semana {semana} já foi enviado. Nada a fazer.")
        return None

    aprendizado.atualizar_metricas(est)   # números frescos de todos os posts
    anterior = (est.get("relatorios") or [{}])[-1]

    # Conta
    info = instagram.conta()
    totais = instagram.metricas_conta(DIAS)
    seguidores = info.get("followers_count")
    if isinstance(seguidores, int):
        est.setdefault("seguidores", []).append({"data": estado.agora(), "total": seguidores})
    antes = _seguidores_ha(est, DIAS) or anterior.get("conta", {}).get("seguidores")
    nomes = {"reach": "contas alcançadas", "views": "visualizações", "profile_views": "visitas ao perfil",
             "website_clicks": "cliques no link do perfil", "accounts_engaged": "contas que interagiram",
             "total_interactions": "interações"}
    conta_linhas = [f"- seguidores: {seguidores if seguidores is not None else '—'}"
                    + (f" ({seguidores - antes:+d} em {DIAS} dias)" if isinstance(seguidores, int)
                       and isinstance(antes, int) else " (primeira medição)")]
    for k, nome in nomes.items():
        if k in totais:
            ant = (anterior.get("conta") or {}).get(k)
            var = f" (semana anterior: {ant})" if ant is not None else ""
            conta_linhas.append(f"- {nome} nos últimos {DIAS} dias: {totais[k]}{var}")
    conta_txt = "\n".join(conta_linhas)

    # Posts da semana
    inicio = agora - timedelta(days=DIAS)
    da_semana = [p for p in est["publicacoes"]
                 if not p.get("removido") and (d := _data(p.get("data", ""))) and d >= inicio]
    estado.refs_por_media(est)   # garante o código (R1, C1...) nos posts antigos
    posts_linhas = []
    for p in sorted(da_semana, key=lambda x: x.get("pontuacao") or 0, reverse=True):
        m = p.get("metricas") or {}
        t = p.get("testes") or {}
        teste = f" | teste: gancho {t.get('gancho')}, {t.get('horario')}h" if t else ""
        posts_linhas.append(
            f"- {p.get('ref', '?')} {('Reels' if p.get('tipo') == 'reel' else 'Carrossel')} \"{p.get('tema', '')}\""
            + (f" ({p.get('publico') or p.get('formato')})" if p.get("publico") or p.get("formato") else "")
            + f": visualiz. {m.get('views', '—')}, alcance "
            f"{m.get('reach', '—')}, salvos {m.get('saved', '—')}, compart. {m.get('shares', '—')}, coment. "
            f"{m.get('comments', '—')}, interessados {p.get('leads', 0)}, pontuação {p.get('pontuacao', 0)}{teste}")
    posts_txt = "\n".join(posts_linhas) or "- nenhuma publicação nesta semana"

    leads_total = est.get("total_leads", 0)
    leads_semana = sum(1 for l in est.get("leads", []) if (d := _data(l.get("data", ""))) and d >= inicio)
    prosp_txt, prosp = _prospeccao(anterior.get("prospeccao") or {})
    periodo = (f"{inicio.astimezone(BRASILIA):%d/%m} a {agora.astimezone(BRASILIA):%d/%m/%Y}")

    r = claude.perguntar_json(SISTEMA, PEDIDO.format(
        periodo=periodo, conta=conta_txt, posts=posts_txt, leads_semana=leads_semana, leads_total=leads_total,
        testes=experimentos.resumo_texto(est), prospeccao=prosp_txt,
        historico=aprendizado.resumo_para_claude(est, "reel")), max_tokens=2500, simulado=SIMULADO)

    texto = _texto_email(r, periodo, conta_txt, posts_txt)
    print(texto)
    aviso.enviar(f"Relatório semanal ({periodo}): {r.get('manchete', '')[:70]}", texto)

    registro = {"data": estado.agora(), "semana": semana, "periodo": periodo,
                "conta": {"seguidores": seguidores, **totais}, "prospeccao": prosp,
                "leads_semana": leads_semana, "relatorio": r}
    est.setdefault("relatorios", []).append(registro)
    est["relatorios"] = est["relatorios"][-12:]
    estado.registrar(est, "relatorio", r.get("manchete", "")[:120])
    estado.salvar(est)
    return registro


if __name__ == "__main__":   # uso: python -m agente.relatorio
    print(json.dumps(executar(os.getenv("AGENDADO") == "1"), ensure_ascii=False, indent=1)[:2000])
