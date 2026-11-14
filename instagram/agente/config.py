"""Configurações lidas das variáveis de ambiente (segredos do GitHub).

Nada de senha ou token fica escrito no código.
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent          # pasta instagram/
MARCA = (RAIZ / "marca.md").read_text(encoding="utf-8")

SIMULAR = os.getenv("SIMULAR", "0") == "1"

# Instagram (API com login do Instagram)
IG_TOKEN = os.getenv("IG_TOKEN", "")
IG_USER_ID = os.getenv("IG_USER_ID", "me")
IG_API = "https://graph.instagram.com/v25.0"

# Claude (API da Anthropic)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODELO_CRIATIVO = os.getenv("MODELO_CRIATIVO", "claude-sonnet-5-5")   # roteiros e legendas
MODELO_RAPIDO = os.getenv("MODELO_RAPIDO", "claude-haiku-5-5")       # respostas a comentários/DMs

# Vídeo com IA (fal.ai)
FAL_KEY = os.getenv("FAL_KEY", "")
FAL_MODELO_VIDEO = os.getenv("FAL_MODELO_VIDEO", "fal-ai/kling-video/v3/standard/text-to-video")
VIDEO_SEGUNDOS = os.getenv("VIDEO_SEGUNDOS", "5")      # só a cena; a tela da marca é montada sem custo
VIDEO_COM_AUDIO = os.getenv("VIDEO_COM_AUDIO", "1") == "1"

# Estado (histórico, métricas, comentários já respondidos) fica no branch "dados"
DADOS_DIR = Path(os.getenv("DADOS_DIR", RAIZ / "dados-local"))
REPO = os.getenv("GITHUB_REPOSITORY", "thiagogeo7-alt/ello-energia")
DADOS_BRANCH = os.getenv("DADOS_BRANCH", "dados")
MIDIA_BRANCH = "midia"   # guarda só a mídia da publicação atual (não acumula histórico)
URL_MIDIA_BASE = f"https://raw.githubusercontent.com/{REPO}/{MIDIA_BRANCH}"

WHATSAPP = "5519995621927"
LINK_WHATSAPP = f"https://wa.me/{WHATSAPP}"


def exigir(*nomes: str) -> None:
    """Para a execução com mensagem clara se faltar algum segredo."""
    if SIMULAR:
        return
    faltando = [n for n in nomes if not os.getenv(n)]
    if faltando:
        raise SystemExit(
            "Faltam segredos no GitHub: " + ", ".join(faltando)
            + ". Cadastre em Settings → Secrets and variables → Actions."
        )
