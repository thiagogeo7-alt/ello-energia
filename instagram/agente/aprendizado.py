"""Atualiza as métricas do que já foi publicado e resume o que funcionou."""
from datetime import datetime, timedelta, timezone

from . import instagram


def pontuacao(m: dict, leads: int = 0) -> float:
    """Peso maior para o que traz cliente (leads) e para o que faz o Instagram distribuir (compartilhar, salvar)."""
    if not m and not leads:
        return 0.0
    m = m or {}
    return (m.get("views", 0) * 0.1 + m.get("reach", 0) * 0.2 + m.get("likes", 0)
            + m.get("comments", 0) * 3 + m.get("saved", 0) * 4 + m.get("shares", 0) * 5 + leads * 15)


def atualizar_metricas(estado: dict, dias: int = 30) -> None:
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    for p in estado["publicacoes"]:
        if not p.get("media_id") or p.get("removido"):
            continue
        try:
            data = datetime.fromisoformat(p["data"])
        except (KeyError, ValueError):
            continue
        if data < limite:
            continue
        m = instagram.metricas(p["media_id"], reel=p.get("tipo") == "reel")
        if m.get("removido"):
            p["removido"] = True
            continue
        if m:
            p["metricas"] = m
            p["pontuacao"] = pontuacao(m, p.get("leads", 0))
    estado["metricas_atualizadas_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


def estado_agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atualizar_metricas_do_dia(estado: dict) -> None:
    """Uma vez por dia (pelas respostas, que rodam com frequência): mantém os números do painel e do
    aprendizado frescos mesmo nos dias sem publicação. Nunca derruba as respostas."""
    try:
        ultima = datetime.fromisoformat(estado.get("metricas_atualizadas_em", "2000-01-01T00:00:00+00:00"))
        if datetime.now(timezone.utc) - ultima < timedelta(hours=20):
            return
        atualizar_metricas(estado)
        seguidores = instagram.conta().get("followers_count")
        if isinstance(seguidores, int):
            estado.setdefault("seguidores", []).append({"data": estado_agora(), "total": seguidores})
            estado["seguidores"] = estado["seguidores"][-120:]
        print("Métricas das publicações e seguidores atualizados.")
    except Exception as e:
        print(f"Aviso: não consegui atualizar as métricas ({e})")


def resumo_para_claude(estado: dict, tipo: str) -> str:
    pubs = [p for p in estado["publicacoes"] if p.get("tipo") == tipo and p.get("metricas")]
    if not pubs:
        return "Ainda não há histórico com métricas. Explore temas variados do guia da marca.\n" + recentes_texto(estado)
    pubs.sort(key=lambda p: p.get("pontuacao", 0), reverse=True)

    def linha(p):
        m = p["metricas"]
        return (f"- tema: {p.get('tema')} | gancho: {p.get('gancho')} | "
                f"views {m.get('views', '-')}, alcance {m.get('reach', '-')}, "
                f"compart. {m.get('shares', '-')}, salvos {m.get('saved', '-')}, coment. {m.get('comments', '-')}, "
                f"interessados {p.get('leads', 0)}")

    melhores = "\n".join(linha(p) for p in pubs[:5])
    piores = "\n".join(linha(p) for p in pubs[-3:]) if len(pubs) > 5 else "(poucos dados)"
    return (f"MELHORES publicações:\n{melhores}\n\nPIORES publicações:\n{piores}\n\n" + recentes_texto(estado))


def recentes_texto(estado: dict) -> str:
    recentes = "; ".join(f"{p.get('tema', '')}" + (f" ({p['publico']})" if p.get("publico") else "")
                         for p in estado["publicacoes"][-8:])
    return f"Posts recentes (NÃO repetir tema nem tipo de negócio): {recentes}"
