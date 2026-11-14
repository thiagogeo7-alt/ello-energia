"""Atualiza as métricas do que já foi publicado e resume o que funcionou."""
from datetime import datetime, timedelta, timezone

from . import instagram


def pontuacao(m: dict) -> float:
    """Peso maior para o que faz o Instagram distribuir mais: compartilhar e salvar."""
    if not m:
        return 0.0
    return (m.get("views", 0) * 0.1 + m.get("reach", 0) * 0.2 + m.get("likes", 0)
            + m.get("comments", 0) * 3 + m.get("saved", 0) * 4 + m.get("shares", 0) * 5)


def atualizar_metricas(estado: dict, dias: int = 30) -> None:
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    for p in estado["publicacoes"]:
        if not p.get("media_id"):
            continue
        try:
            data = datetime.fromisoformat(p["data"])
        except (KeyError, ValueError):
            continue
        if data < limite:
            continue
        m = instagram.metricas(p["media_id"], reel=p.get("tipo") == "reel")
        if m:
            p["metricas"] = m
            p["pontuacao"] = pontuacao(m)


def resumo_para_claude(estado: dict, tipo: str) -> str:
    pubs = [p for p in estado["publicacoes"] if p.get("tipo") == tipo and p.get("metricas")]
    if not pubs:
        return "Ainda não há histórico com métricas. Explore temas variados do guia da marca."
    pubs.sort(key=lambda p: p.get("pontuacao", 0), reverse=True)

    def linha(p):
        m = p["metricas"]
        return (f"- tema: {p.get('tema')} | gancho: {p.get('gancho')} | "
                f"views {m.get('views', '-')}, alcance {m.get('reach', '-')}, "
                f"compart. {m.get('shares', '-')}, salvos {m.get('saved', '-')}, coment. {m.get('comments', '-')}")

    melhores = "\n".join(linha(p) for p in pubs[:5])
    piores = "\n".join(linha(p) for p in pubs[-3:]) if len(pubs) > 5 else "(poucos dados)"
    recentes = ", ".join(p.get("tema", "") for p in estado["publicacoes"][-8:])
    return (f"MELHORES publicações:\n{melhores}\n\nPIORES publicações:\n{piores}\n\n"
            f"Temas usados recentemente (não repetir igual): {recentes}")
