"""Testes A/B dos Reels: o agente varia de propósito um elemento por vez e mede o que funciona melhor.

Testes em andamento:
- gancho: o estilo da frase que aparece no 1º segundo (pergunta, número, provocação, história).
- horario: a faixa de horário da publicação (17h, 19h ou 21h, horário de Brasília).

Como escolhe: enquanto alguma variante tiver menos de MIN_AMOSTRAS posts maduros, usa a menos testada
(equilíbrio). Depois, usa a vencedora em 70% das vezes e continua explorando as outras em 30%, para
perceber se o público mudou de gosto.

Como mede: pontuação de cada post (alcance, salvos, compartilhamentos, comentários e interessados, ver
aprendizado.pontuacao), só de posts com pelo menos DIAS_MADURO dias, para comparar números já assentados.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

BRASILIA = timezone(timedelta(hours=-3))
MIN_AMOSTRAS = 3
DIAS_MADURO = 3
PARTE_EXPLORACAO = 0.3

TESTES = {
    "gancho": {
        "nome": "Estilo do gancho (1º segundo)",
        "variantes": {
            "pergunta": "Abra com uma PERGUNTA direta sobre a dor do público (ex.: \"SUA CONTA PASSOU DE R$ 500?\").",
            "numero": "Abra com um NÚMERO concreto e verdadeiro do guia da marca (ex.: \"ATÉ 50% MENOS NA CONTA\").",
            "provocacao": "Abra com uma frase PROVOCATIVA que contrarie uma crença comum (ex.: \"PLACA SOLAR? NÃO PRECISA\").",
            "historia": "Abra com o começo de uma HISTÓRIA curta e humana (ex.: \"A PADARIA DO SEU JOÃO...\").",
        },
    },
    "horario": {
        "nome": "Horário da publicação",
        "variantes": {"17": "17h às 18h59", "19": "19h às 20h59", "21": "21h em diante"},
    },
}


def _data(texto: str):
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None


def faixa_horario(momento: datetime | None = None) -> str:
    """Faixa do horário de Brasília em que o post saiu."""
    h = (momento or datetime.now(BRASILIA)).astimezone(BRASILIA).hour
    return "21" if h >= 21 else "19" if h >= 19 else "17"


def _reels(estado: dict) -> list[dict]:
    return [p for p in estado.get("publicacoes", []) if p.get("tipo") == "reel"]


def _maduros(estado: dict) -> list[dict]:
    limite = datetime.now(timezone.utc) - timedelta(days=DIAS_MADURO)
    return [p for p in _reels(estado) if (d := _data(p.get("data", ""))) and d <= limite]


def resultados(estado: dict, teste: str) -> dict:
    """{variante: {"posts": n, "media": pontuação média, "interessados": soma}} só com posts maduros."""
    res = {v: {"posts": 0, "soma": 0.0, "interessados": 0} for v in TESTES[teste]["variantes"]}
    for p in _maduros(estado):
        v = (p.get("testes") or {}).get(teste)
        if v in res:
            res[v]["posts"] += 1
            res[v]["soma"] += float(p.get("pontuacao") or 0)
            res[v]["interessados"] += int(p.get("leads") or 0)
    for r in res.values():
        r["media"] = round(r["soma"] / r["posts"], 1) if r["posts"] else None
        del r["soma"]
    return res


def vencedora(estado: dict, teste: str) -> str | None:
    """A variante com maior média, só quando todas já têm o mínimo de posts maduros."""
    res = resultados(estado, teste)
    if any(r["posts"] < MIN_AMOSTRAS for r in res.values()):
        return None
    return max(res, key=lambda v: res[v]["media"] or 0)


def _menos_testada(estado: dict, teste: str, desempate: int) -> str:
    """Variante com menos posts (contando também os recentes, ainda não maduros)."""
    contagem = {v: 0 for v in TESTES[teste]["variantes"]}
    for p in _reels(estado):
        v = (p.get("testes") or {}).get(teste)
        if v in contagem:
            contagem[v] += 1
    menor = min(contagem.values())
    candidatas = [v for v, n in contagem.items() if n == menor]
    return candidatas[desempate % len(candidatas)]


def escolher(estado: dict, teste: str, semente: int | None = None) -> str:
    """Variante para o próximo Reels. Com a mesma `semente` e o mesmo estado, a escolha é sempre igual
    (importante para o horário, que é conferido várias vezes no mesmo dia)."""
    n = len(_reels(estado)) if semente is None else semente
    venc = vencedora(estado, teste)
    if venc and random.Random(n * 31 + len(teste)).random() >= PARTE_EXPLORACAO:
        return venc
    return _menos_testada(estado, teste, n)


def instrucao_gancho(variante: str) -> str:
    return TESTES["gancho"]["variantes"].get(variante, "")


def resumo_texto(estado: dict) -> str:
    """Resumo legível dos testes (vai no relatório semanal e no aprendizado do roteirista)."""
    linhas = []
    for chave, t in TESTES.items():
        res = resultados(estado, chave)
        venc = vencedora(estado, chave)
        partes = [f"{v}: {r['posts']} post(s), média {r['media'] if r['media'] is not None else '—'}, "
                  f"{r['interessados']} interessado(s)" for v, r in res.items()]
        situacao = f"vencedora até agora: {venc}" if venc else \
            f"ainda coletando (mínimo de {MIN_AMOSTRAS} posts com {DIAS_MADURO}+ dias por variante)"
        linhas.append(f"- {t['nome']} — {situacao}\n    " + "\n    ".join(partes))
    return "\n".join(linhas)
