"""Cliente da API do Instagram (login pelo Instagram, sem Página do Facebook)."""
import time

from . import config
from .rede import ErroAPI, chamar


def _get(caminho: str, **params) -> dict:
    params["access_token"] = config.IG_TOKEN
    return chamar("GET", f"{config.IG_API}/{caminho}", params=params)


_ID_CACHE = {}


def uid() -> str:
    """ID da conta: usa o segredo IG_USER_ID ou descobre pelo token."""
    if config.IG_USER_ID and config.IG_USER_ID != "me":
        return config.IG_USER_ID
    if "id" not in _ID_CACHE:
        _ID_CACHE["id"] = meu_id()
    return _ID_CACHE["id"]


def _post(caminho: str, **dados) -> dict:
    dados["access_token"] = config.IG_TOKEN
    return chamar("POST", f"{config.IG_API}/{caminho}", data=dados)


# ---------- Publicação ----------

def _aguardar_container(container_id: str, limite_s: int = 600) -> None:
    inicio = time.time()
    while time.time() - inicio < limite_s:
        st = _get(container_id, fields="status_code,status")
        codigo = st.get("status_code")
        if codigo == "FINISHED":
            return
        if codigo in ("ERROR", "EXPIRED"):
            raise ErroAPI(f"Instagram recusou a mídia: {st}")
        time.sleep(15)
    raise ErroAPI("Instagram demorou demais para processar a mídia.")


def publicar_reel(video_url: str, legenda: str, capa_url: str | None = None) -> str:
    if config.SIMULAR:
        print(f"[simulação] publicaria Reel: {video_url}")
        return "SIM_REEL_123"
    dados = {"media_type": "REELS", "video_url": video_url, "caption": legenda, "share_to_feed": "true"}
    if capa_url:
        dados["cover_url"] = capa_url
    container = _post(f"{uid()}/media", **dados)["id"]
    _aguardar_container(container)
    return _post(f"{uid()}/media_publish", creation_id=container)["id"]


def publicar_carrossel(imagens_url: list[str], legenda: str) -> str:
    if config.SIMULAR:
        print(f"[simulação] publicaria carrossel com {len(imagens_url)} imagens")
        return "SIM_CARROSSEL_123"
    filhos = []
    for url in imagens_url:
        filhos.append(_post(f"{uid()}/media", image_url=url, is_carousel_item="true")["id"])
    for f in filhos:
        _aguardar_container(f, limite_s=180)
    pai = _post(f"{uid()}/media", media_type="CAROUSEL",
                children=",".join(filhos), caption=legenda)["id"]
    _aguardar_container(pai, limite_s=180)
    return _post(f"{uid()}/media_publish", creation_id=pai)["id"]


# ---------- Leitura e métricas ----------

def minhas_publicacoes(limite: int = 25) -> list[dict]:
    if config.SIMULAR:
        return [{"id": "SIM_REEL_1", "caption": "Teste", "media_type": "VIDEO",
                 "timestamp": "2026-11-10T21:00:00+0000", "comments_count": 2, "like_count": 30}]
    campos = "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count"
    return _get(f"{uid()}/media", fields=campos, limit=limite).get("data", [])


def metricas(media_id: str, reel: bool = True) -> dict:
    """Alcance, visualizações, curtidas, comentários, salvos e compartilhamentos."""
    if config.SIMULAR:
        return {"reach": 1200, "views": 2100, "likes": 80, "comments": 6, "saved": 14, "shares": 9}
    nomes = ["reach", "likes", "comments", "saved", "shares", "views"] if reel \
        else ["reach", "likes", "comments", "saved", "shares"]
    try:
        dados = _get(f"{media_id}/insights", metric=",".join(nomes)).get("data", [])
    except ErroAPI as e:
        print(f"Aviso: sem métricas para {media_id}: {e}")
        return {}
    return {m["name"]: (m.get("values") or [{}])[0].get("value", 0) for m in dados}


# ---------- Comentários ----------

def comentarios(media_id: str) -> list[dict]:
    if config.SIMULAR:
        return [{"id": "C1", "text": "Quanto custa pra entrar?", "username": "maria_cps", "timestamp": "2026-11-14T15:00:00+0000"},
                {"id": "C2", "text": "🔥🔥", "username": "joao", "timestamp": "2026-11-14T15:05:00+0000"}]
    campos = "id,text,username,timestamp,replies{id,username}"
    return _get(f"{media_id}/comments", fields=campos, limit=50).get("data", [])


def responder_comentario(comentario_id: str, texto: str) -> None:
    if config.SIMULAR:
        print(f"[simulação] responderia comentário {comentario_id}: {texto}")
        return
    _post(f"{comentario_id}/replies", message=texto)


# ---------- Mensagens diretas ----------

def conversas(limite: int = 20) -> list[dict]:
    if config.SIMULAR:
        return [{"id": "T1", "messages": {"data": [
            {"id": "M1", "message": "Oi, minha conta vem 600 reais, dá pra economizar?",
             "from": {"id": "U1", "username": "carlos"}, "created_time": "2026-11-14T15:10:00+0000"}]}}]
    campos = "id,updated_time,messages.limit(5){id,message,from,created_time}"
    return _get("me/conversations", platform="instagram", fields=campos, limit=limite).get("data", [])


def meu_id() -> str:
    if config.SIMULAR:
        return "EU"
    return _get("me", fields="user_id,username").get("user_id", "")


def enviar_mensagem(usuario_id: str, texto: str) -> None:
    if config.SIMULAR:
        print(f"[simulação] enviaria DM para {usuario_id}: {texto}")
        return
    chamar("POST", f"{config.IG_API}/me/messages",
           headers={"Authorization": f"Bearer {config.IG_TOKEN}"},
           json={"recipient": {"id": usuario_id}, "message": {"text": texto}})


# ---------- Token ----------

def renovar_token() -> dict:
    """Renova o token de longa duração (vale ~60 dias a partir da renovação)."""
    return chamar("GET", "https://graph.instagram.com/refresh_access_token",
                  params={"grant_type": "ig_refresh_token", "access_token": config.IG_TOKEN})
