"""Escreve os e-mails de prospecção com o Claude (em lote, para sair barato), com modelos de reserva."""
import json

from . import claude, config
from .segmentos import SEGMENTO_PADRAO, SEGMENTOS

_INSTRUCOES_SEG = "\n".join(f"- Segmento {s['nome']}: {s['instrucao'].strip()}"
                            for s in SEGMENTOS.values() if s.get("instrucao"))

SISTEMA = f"""Você escreve e-mails de prospecção B2B para a {config.NOME}, em português do Brasil.
Objetivo: conseguir uma resposta ou uma conversa rápida. Tom: humano, direto, respeitoso, sem cara de spam.

Regras:
- No máximo 90 palavras no corpo. Parágrafos curtos. Texto simples, sem negrito, sem emojis.
- Personalize com o nome da empresa e o tipo de negócio. Nunca invente fatos sobre a empresa.
- Benefício central: {" ".join(str(config.P.get("beneficio_central") or "").split())}.
{(config.P.get("regras") or "").strip()}
- Termine com UMA pergunta simples de sim/não (ex.: "{config.P.get("pergunta_final_exemplo") or "Faz sentido conversarmos 15 minutos?"}").
- Não coloque links no primeiro e-mail. Não use palavras como "grátis!!!", "promoção", "imperdível".
- Assunto curto (até 6 palavras), em minúsculas, natural, sem ponto de exclamação.
{_INSTRUCOES_SEG}
- Não escreva assinatura nem rodapé: eles são adicionados automaticamente.

Fatos da marca que você pode usar:
{config.MARCA[:2500]}

Responda SOMENTE com JSON."""

TIPOS = {
    "inicial": "primeiro contato",
    "lembrete1": "1º lembrete, 3 dias depois, sem resposta: bem curto (até 50 palavras), retomando a pergunta",
    "lembrete2": "último lembrete, 7 dias depois: até 40 palavras, educado, dizendo que não vai insistir mais",
}

_PADRAO = {
    "inicial": ("contato - {empresa}", "Olá, tudo bem?\n\nSou da " + config.NOME + ". Ajudamos {tipo} a crescer.\n\n"
                "No caso de vocês, {angulo}.\n\nFaz sentido conversarmos 15 minutos?"),
    "lembrete1": ("re: contato - {empresa}", "Olá! Passando para saber se viu minha mensagem. Posso te explicar em 15 minutos?"),
    "lembrete2": ("re: contato - {empresa}", "Olá! Esta é minha última mensagem. Se precisarem, é só responder este e-mail. Obrigado!"),
}
MODELOS = {t: ((config.P.get("modelos") or {}).get(t, {}).get("assunto") or _PADRAO[t][0],
               (config.P.get("modelos") or {}).get(t, {}).get("corpo") or _PADRAO[t][1]) for t in _PADRAO}


def _modelo(c: dict, tipo: str) -> dict:
    seg = SEGMENTOS.get(c.get("segmento") or "", SEGMENTOS.get(SEGMENTO_PADRAO) or {"nome": "empresas", "angulo": ""})
    empresa = c.get("empresa") or "sua empresa"
    a, b = MODELOS[tipo]
    fmt = {"empresa": empresa, "tipo": seg["nome"].lower(), "angulo": seg["angulo"]}
    return {"assunto": a.format(**fmt).lower(), "corpo": b.format(**fmt)}


def escrever(lote: list[tuple[dict, str]]) -> list[dict]:
    """lote = [(contato, tipo)]; devolve [{assunto, corpo}] na mesma ordem."""
    if not lote:
        return []
    itens = [{"n": i, "empresa": c.get("empresa") or "", "segmento": SEGMENTOS.get(c.get("segmento"), {}).get("nome", ""),
              "angulo": SEGMENTOS.get(c.get("segmento"), {}).get("angulo", ""), "bairro": c.get("bairro", ""),
              "tipo": TIPOS[t], "assunto_anterior": (c.get("enviados") or [{}])[0].get("assunto", "")}
             for i, (c, t) in enumerate(lote)]
    pedido = ("Escreva um e-mail para cada item. Para lembretes, use como assunto 're: ' + assunto_anterior.\n"
              + json.dumps(itens, ensure_ascii=False, indent=1)
              + '\n\nDevolva {"emails": [{"n": 0, "assunto": "...", "corpo": "..."}, ...]}')
    try:
        r = claude.perguntar_json(SISTEMA, pedido, modelo=config.MODELO_RAPIDO, max_tokens=6000,
                                  simulado={"emails": [dict(n=i, **_modelo(c, t)) for i, (c, t) in enumerate(lote)]})
        por_n = {e["n"]: e for e in r.get("emails", []) if e.get("assunto") and e.get("corpo")}
    except Exception as e:
        print(f"Aviso: Claude falhou ao escrever ({e}); usando modelos prontos.")
        por_n = {}
    return [por_n.get(i) or _modelo(c, t) for i, (c, t) in enumerate(lote)]
