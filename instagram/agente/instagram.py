"""Cliente da API do Instagram (login pelo Instagram, sem Página do Facebook)."""
import os
import json
import time

from . import config
from .rede import ErroAPI, chamar


def detectar_api() -> str:
    """Testa o token nos dois endereços da Meta e fica com o que responder."""
    if config.SIMULAR or os.getenv("IG_API"):
        return config.IG_API
    erros = []
    for host in config.IG_API_HOSTS:
        try:
            r = chamar("GET", f"{host}/{config.IG_USER_ID}", tentativas=1,
                       params={"fields": "username", "access_token": config.IG_TOKEN})
            config.IG_API = host
            print(f"Conectado como @{r.get('username')} via {host.split('/')[2]}")
            return host
        except ErroAPI as e:
            erros.append(str(e))
    raise ErroAPI("O token não funcionou em nenhum endereço da Meta:\n" + "\n".join(erros))


def _get(caminho: str, **params) -> dict:
    params["access_token"] = config.IG_TOKEN
    return chamar("GET", f"{config.IG_API}/{caminho}", params=params)


_ID_CACHE = {}


def uid() -> str:
    """ID da conta: usa o segredo IG_USER_ID ou descobre pelo token."""
    return config.IG_USER_ID


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


def publicar_reel(video_url: str, legenda: str, capa_url: str | None = None, teste: bool | None = None) -> str:
    """teste=True publica como Reels de teste (vai primeiro para quem não segue a página)."""
    teste = config.REELS_TESTE if teste is None else teste
    if config.SIMULAR:
        print(f"[simulação] publicaria Reel{' de teste' if teste else ''}: {video_url}")
        return "SIM_REEL_123"
    dados = {"media_type": "REELS", "video_url": video_url, "caption": legenda, "share_to_feed": "true"}
    if capa_url:
        dados["cover_url"] = capa_url
    if teste:
        dados["trial_params"] = json.dumps({"graduation_strategy": "SS_PERFORMANCE"})
    try:
        container = _post(f"{uid()}/media", **dados)["id"]
    except ErroAPI as e:
        if "trial_params" not in dados:
            raise
        print(f"Aviso: Reels de teste recusado ({e}); publicando como Reels normal")
        dados.pop("trial_params")
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


def publicar_story(midia_url: str, video: bool) -> str:
    """Publica uma foto ou vídeo nos Stories (somem em 24 h)."""
    if config.SIMULAR:
        print(f"[simulação] publicaria Story: {midia_url}")
        return "SIM_STORY_123"
    campo = "video_url" if video else "image_url"
    container = _post(f"{uid()}/media", media_type="STORIES", **{campo: midia_url})["id"]
    _aguardar_container(container, limite_s=600 if video else 180)
    return _post(f"{uid()}/media_publish", creation_id=container)["id"]


def copiar_para_stories(midia_url: str, video: bool) -> str | None:
    """Cópia nos Stories sem atrapalhar a publicação principal se algo falhar."""
    if not config.COPIAR_STORIES:
        return None
    try:
        sid = publicar_story(midia_url, video)
        print(f"Copiado para os Stories: {sid}")
        return sid
    except Exception as e:
        print(f"Aviso: não consegui copiar para os Stories ({e})")
        return None


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


def permalink(media_id: str) -> str:
    if config.SIMULAR:
        return "https://www.instagram.com/p/SIMULADO/"
    try:
        return _get(media_id, fields="permalink").get("permalink", "")
    except ErroAPI:
        return ""


# ---------- Comentários ----------

def comentarios(media_id: str) -> list[dict]:
    if config.SIMULAR:
        return [{"id": "C1", "text": "Quanto custa pra entrar?", "username": "maria_cps", "timestamp": "2026-11-14T15:00:00+0000"},
                {"id": "C2", "text": "🔥🔥", "username": "joao", "timestamp": "2026-11-14T15:05:00+0000"},
                {"id": "C3", "text": "ECONOMIZAR", "username": "ana.campinas", "timestamp": "2026-11-14T15:06:00+0000"}]
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
    try:
        return _get(f"{uid()}/conversations", platform="instagram", fields=campos, limit=limite).get("data", [])
    except ErroAPI:
        return _get("me/conversations", platform="instagram", fields=campos, limit=limite).get("data", [])


def meu_id() -> str:
    return config.IG_USER_ID


_destinos_cache: list | None = None


def _destinos_mensagem() -> list[tuple[str, str]]:
    """Onde a Meta aceita envio de mensagens: o próprio perfil do Instagram e, pelo Facebook,
    a Página ligada a ele (com o token da Página)."""
    global _destinos_cache
    if _destinos_cache is not None:
        return _destinos_cache
    destinos = [(f"{config.IG_API}/{config.IG_USER_ID}/messages", config.IG_TOKEN)]
    try:
        paginas = _get("me/accounts", fields="id,access_token,instagram_business_account").get("data", [])
        for pg in paginas:
            if (pg.get("instagram_business_account") or {}).get("id") == config.IG_USER_ID and pg.get("access_token"):
                destinos.insert(0, (f"{config.IG_API}/{pg['id']}/messages", pg["access_token"]))
    except Exception as e:
        print(f"Aviso: não consegui listar a Página do Facebook ({e})")
    destinos.append((f"{config.IG_API}/me/messages", config.IG_TOKEN))
    _destinos_cache = destinos
    return destinos


def _enviar(corpo: dict) -> None:
    ultimo = None
    for url, token in _destinos_mensagem():
        try:
            chamar("POST", url, params={"access_token": token}, json=corpo)
            return
        except ErroAPI as e:
            ultimo = e
    raise ultimo or ErroAPI("Nenhum destino aceitou a mensagem")


def enviar_mensagem(usuario_id: str, texto: str) -> None:
    if config.SIMULAR:
        print(f"[simulação] enviaria DM para {usuario_id}: {texto}")
        return
    _enviar({"recipient": {"id": usuario_id}, "message": {"text": texto}})


def resposta_privada(comentario_id: str, texto: str) -> None:
    """Manda uma DM para quem comentou (permitido até 7 dias depois do comentário)."""
    if config.SIMULAR:
        print(f"[simulação] mandaria DM para o autor do comentário {comentario_id}: {texto[:60]}…")
        return
    _enviar({"recipient": {"comment_id": comentario_id}, "message": {"text": texto}})


# ---------- Token ----------

def renovar_token() -> dict:
    """Renova o token de longa duração (vale ~60 dias a partir da renovação)."""
    return chamar("GET", "https://graph.instagram.com/refresh_access_token",
                  params={"grant_type": "ig_refresh_token", "access_token": config.IG_TOKEN})


def apagar(media_id: str) -> dict:
    """Apaga uma publicação (Reels, carrossel, foto). Não tem volta."""
    if config.SIMULAR:
        print(f"[simulação] apagaria a publicação {media_id}")
        return {"success": True}
    return chamar("DELETE", f"{config.IG_API}/{media_id}", params={"access_token": config.IG_TOKEN})
