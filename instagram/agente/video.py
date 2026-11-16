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


CUSTO_TRILHA_USD = 0.01   # CassetteAI: US$ 0,02 por minuto de música


def gerar_trilha(prompt: str, segundos: int = 30) -> str:
    """Música instrumental nova para cada Reels; devolve a URL do áudio."""
    if config.SIMULAR:
        print(f"[simulação] geraria trilha: {prompt[:80]}…")
        return ""
    r = _fila("CassetteAI/music-generator", {"prompt": prompt, "duration": max(10, min(180, int(segundos)))},
              limite_s=180)
    url = (r.get("audio_file") or {}).get("url")
    if not url:
        raise ErroAPI(f"fal.ai não devolveu a trilha: {r}")
    return url


# Vozes realistas (MiniMax Speech-02 HD, com reforço de português). Se falhar, usa Kokoro pt-BR.
VOZES = {
    "Calm_Woman": "mulher adulta, voz calma e acolhedora",
    "Wise_Woman": "mulher madura/idosa, voz serena",
    "Lively_Girl": "mulher jovem, voz animada",
    "Friendly_Person": "voz simpática e neutra (boa para narrador)",
    "Casual_Guy": "homem jovem, descontraído",
    "Patient_Man": "homem adulto, voz calma",
    "Deep_Voice_Man": "homem com voz grave",
    "Elegant_Man": "homem maduro, voz elegante",
}
VOZES_MASCULINAS = {"Casual_Guy", "Patient_Man", "Deep_Voice_Man", "Elegant_Man"}
CUSTO_FALA_USD_POR_1000 = 0.10


def gerar_fala(texto: str, voz: str = "Friendly_Person") -> str:
    """Fala em português com voz realista; devolve a URL do áudio."""
    if config.SIMULAR:
        print(f"[simulação] geraria fala ({voz}): {texto[:60]}…")
        return ""
    voz = voz if voz in VOZES else "Friendly_Person"
    try:
        r = _fila("fal-ai/minimax/speech-02-hd", {
            "text": texto, "language_boost": "Portuguese",
            "voice_setting": {"voice_id": voz, "speed": 1.05, "vol": 1, "pitch": 0},
        }, limite_s=180)
        url = (r.get("audio") or {}).get("url")
        if url:
            return url
        raise ErroAPI(f"sem áudio: {r}")
    except Exception as e:
        print(f"Aviso: voz MiniMax falhou ({e}); usando Kokoro")
        r = _fila("fal-ai/kokoro/brazilian-portuguese",
                  {"prompt": texto, "voice": "pm_alex" if voz in VOZES_MASCULINAS else "pf_dora"}, limite_s=180)
        url = (r.get("audio") or {}).get("url")
        if not url:
            raise ErroAPI(f"fal.ai não devolveu a fala: {r}")
        return url


# Cenas em vídeo de verdade (MiniMax H3 Max Turbo, imagem → vídeo, 768p)
MODELO_VIDEO_CENA = "minimax/h3-max-turbo/image-to-video"
PRECO_VIDEO_CENA_USD_S = 0.04


def duracao_audio(url: str) -> float:
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", url],
                       capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def animar_imagem(imagem_url: str, prompt: str, segundos: float, audio_url: str | None = None) -> str:
    """Transforma a foto da cena num vídeo com movimento real; com audio_url, sincroniza a boca com a fala."""
    if config.SIMULAR:
        print(f"[simulação] animaria a cena ({segundos:.1f}s): {prompt[:70]}…")
        return imagem_url
    entrada = {"prompt": prompt, "image_url": imagem_url, "duration": round(max(2.0, min(8.0, segundos)), 1),
               "resolution": "768P", "prompt_expansion_mode": "balanced"}
    if audio_url:
        entrada["target_audio_url"] = audio_url
    r = _fila(MODELO_VIDEO_CENA, entrada, limite_s=900)
    url = (r.get("video") or {}).get("url")
    if not url:
        raise ErroAPI(f"fal.ai não devolveu o vídeo da cena: {r}")
    return url
