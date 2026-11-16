"""Configurações lidas da ficha do cliente (clientes/<id>/) e dos segredos do GitHub.

Nada de senha ou token fica escrito no código.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # raiz do repositório
from nucleo import cliente as _cliente   # noqa: E402

CLIENTE = _cliente.carregar()
_cliente.aplicar_ambiente(CLIENTE)
IG = CLIENTE["instagram"]

# Limpa espaços e quebras de linha que às vezes vêm junto ao colar as chaves
for _n in ("IG_TOKEN", "ANTHROPIC_API_KEY", "FAL_KEY", "IG_USER_ID"):
    if os.getenv(_n):
        os.environ[_n] = os.environ[_n].strip().strip('"').strip("'")

RAIZ = Path(__file__).resolve().parent.parent          # pasta instagram/
PASTA_CLIENTE = _cliente.pasta(CLIENTE["id"])
MARCA = _cliente.marca_md(CLIENTE)
NOME = CLIENTE.get("nome", "")
NOME_CURTO = CLIENTE.get("nome_curto", NOME)

SIMULAR = os.getenv("SIMULAR", "0") == "1"

# Instagram (API com login do Instagram)
IG_TOKEN = os.getenv("IG_TOKEN", "")
IG_USER_ID = os.getenv("IG_USER_ID") or ""   # vem do segredo ou da ficha do cliente
# A Meta tem dois "endereços" de API conforme o tipo de token; o agente descobre sozinho qual usar.
IG_API_HOSTS = ["https://graph.instagram.com/v25.0", "https://graph.facebook.com/v25.0"]
IG_API = os.getenv("IG_API") or IG_API_HOSTS[0]

# Claude (API da Anthropic)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODELO_CRIATIVO = os.getenv("MODELO_CRIATIVO", "claude-sonnet-5-5")   # roteiros e legendas
MODELO_RAPIDO = os.getenv("MODELO_RAPIDO", "claude-haiku-5-5")       # respostas a comentários/DMs

# Vídeo com IA (fal.ai)
FAL_KEY = os.getenv("FAL_KEY", "")
# MODO_CENA: "imagem" = foto ultra-realista com movimento de câmera (~US$ 0,02 por Reels)
#            "video"  = vídeo de verdade com IA (Kling 3.0, ~US$ 0,56 por Reels)
MODO_CENA = os.getenv("MODO_CENA") or "imagem"
FAL_MODELO_IMAGEM = os.getenv("FAL_MODELO_IMAGEM", "fal-ai/flux/dev")
FAL_MODELO_VIDEO = os.getenv("FAL_MODELO_VIDEO", "fal-ai/kling-video/v3/standard/text-to-video")
VIDEO_SEGUNDOS = os.getenv("VIDEO_SEGUNDOS", "5")      # só a cena; a tela da marca é montada sem custo
VIDEO_COM_AUDIO = os.getenv("VIDEO_COM_AUDIO", "1") == "1"

# Estado (histórico, métricas, comentários já respondidos) fica no branch "dados"
DADOS_DIR = Path(os.getenv("DADOS_DIR", RAIZ / "dados-local"))
REPO = os.getenv("GITHUB_REPOSITORY", "thiagogeo7-alt/ello-energia")
DADOS_BRANCH = os.getenv("DADOS_BRANCH") or CLIENTE["branches"]["instagram"]
MIDIA_BRANCH = CLIENTE["branches"]["midia"]   # guarda só a mídia da publicação atual (não acumula histórico)
URL_MIDIA_BASE = f"https://raw.githubusercontent.com/{REPO}/{MIDIA_BRANCH}"

WHATSAPP = "".join(ch for ch in str(CLIENTE["whatsapp"].get("numero", "")) if ch.isdigit())
LINK_WHATSAPP = _cliente.link_whatsapp(CLIENTE, "")
# Link que já abre o WhatsApp com a mensagem escrita (e mostra que o contato veio do Instagram)
LINK_WHATSAPP_IG = _cliente.link_whatsapp(CLIENTE)
WHATSAPP_LEGIVEL = CLIENTE["whatsapp"].get("legivel") or WHATSAPP


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


# Reels de teste (Trial Reels): mostrados primeiro para quem NÃO segue a página.
# SS_PERFORMANCE = o Instagram libera para os seguidores automaticamente se o Reels for bem.
REELS_TESTE = (os.getenv("REELS_TESTE") or "sim").strip().lower() == "sim"
# Copiar cada Reels e carrossel para os Stories
COPIAR_STORIES = (os.getenv("COPIAR_STORIES") or "sim").strip().lower() == "sim"

# Textos do cliente usados nas automações
PALAVRA_CHAVE = str(IG.get("palavra_chave") or "QUERO").split()[0].upper()
OFERTA = IG.get("oferta") or "o atendimento é rápido"
TELA_FINAL = IG.get("tela_final") or {}
VIRADA_PADRAO = IG.get("virada_padrao") or "TEM JEITO!"
ARGUMENTOS = IG.get("argumentos") or []


def cores(texto: str) -> str:
    """Aplica as cores da marca do cliente a um HTML/CSS desenhado com as cores originais."""
    return _cliente.aplicar_cores(texto, CLIENTE)


def texto_whatsapp(modelo: str) -> str:
    return (modelo or "").replace("{link}", LINK_WHATSAPP_IG).replace("{whatsapp}", WHATSAPP_LEGIVEL)
