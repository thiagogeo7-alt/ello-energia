"""Gera o vídeo do Reels com IA (Kling 3.0 via fal.ai)."""
import time

from . import config
from .rede import ErroAPI, chamar

PRECO_USD_POR_SEGUNDO = {True: 0.112, False: 0.084}   # com / sem áudio (Kling 3.0 Standard)


CUSTO_IMAGEM_USD = 0.02   # Flux dev, retrato 9:16


def custo_estimado() -> float:
    if config.MODO_CENA == "imagem":
        return CUSTO_IMAGEM_USD
    return round(int(config.VIDEO_SEGUNDOS) * PRECO_USD_POR_SEGUNDO[config.VIDEO_COM_AUDIO], 2)


def _fila(modelo: str, entrada: dict, limite_s: int = 900) -> dict:
    """Envia um pedido para a fila da fal.ai e espera o resultado."""
    cab = {"Authorization": f"Key {config.FAL_KEY}", "Content-Type": "application/json"}
    pedido = chamar("POST", f"https://queue.fal.run/{modelo}", headers=cab, json=entrada)
    inicio = time.time()
    while time.time() - inicio < limite_s:
        st = chamar("GET", pedido["status_url"], headers=cab)
        if st.get("status") == "COMPLETED":
            return chamar("GET", pedido["response_url"], headers=cab)
        if st.get("status") in ("FAILED", "ERROR"):
            raise ErroAPI(f"fal.ai falhou: {st}")
        time.sleep(5)
    raise ErroAPI("A fal.ai demorou demais para responder.")


def gerar_imagem(prompt: str) -> str:
    """Foto ultra-realista vertical; devolve a URL."""
    if config.SIMULAR:
        print(f"[simulação] geraria imagem: {prompt[:90]}…")
        return "https://exemplo.com/imagem-simulada.jpg"
    r = _fila(config.FAL_MODELO_IMAGEM, {
        "prompt": prompt, "image_size": "portrait_16_9", "num_images": 1,
        "num_inference_steps": 28, "enable_safety_checker": True,
    }, limite_s=300)
    imgs = r.get("images") or []
    if not imgs:
        raise ErroAPI(f"fal.ai não devolveu imagem: {r}")
    return imgs[0]["url"]


def gerar_cena(prompt_video: str, prompt_imagem: str) -> str:
    return gerar_imagem(prompt_imagem) if config.MODO_CENA == "imagem" else gerar(prompt_video)


def gerar(prompt: str, limite_s: int = 900) -> str:
    """Devolve a URL pública do vídeo .mp4 gerado."""
    if config.SIMULAR:
        print(f"[simulação] geraria vídeo ({config.VIDEO_SEGUNDOS}s): {prompt[:90]}…")
        return "https://exemplo.com/video-simulado.mp4"

    cab = {"Authorization": f"Key {config.FAL_KEY}", "Content-Type": "application/json"}
    pedido = chamar("POST", f"https://queue.fal.run/{config.FAL_MODELO_VIDEO}", headers=cab, json={
        "prompt": prompt,
        "duration": str(config.VIDEO_SEGUNDOS),
        "aspect_ratio": "9:16",
        "generate_audio": config.VIDEO_COM_AUDIO,
        "negative_prompt": "text, captions, watermark, logo, subtitles, blurry, distorted faces, extra fingers",
    })
    status_url, resposta_url = pedido["status_url"], pedido["response_url"]

    inicio = time.time()
    while time.time() - inicio < limite_s:
        st = chamar("GET", status_url, headers=cab)
        if st.get("status") == "COMPLETED":
            resultado = chamar("GET", resposta_url, headers=cab)
            url = (resultado.get("video") or {}).get("url")
            if not url:
                raise ErroAPI(f"fal.ai não devolveu vídeo: {resultado}")
            return url
        if st.get("status") in ("FAILED", "ERROR"):
            raise ErroAPI(f"fal.ai falhou ao gerar o vídeo: {st}")
        time.sleep(15)
    raise ErroAPI("O vídeo demorou demais para ficar pronto.")
