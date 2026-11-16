"""Ficha do cliente: lê clientes/<id>/ e prepara as configurações antes de os agentes começarem.

Qual cliente roda é decidido pela variável de ambiente CLIENTE (padrão: "ello").

Segredos (tokens, senhas) nunca ficam nos arquivos. No GitHub, o workflow entrega todos os segredos
e variáveis de uma vez (SEGREDOS_JSON / VARIAVEIS_JSON) e aqui pegamos só os do cliente, pelo prefixo
definido na ficha (ex.: "PADARIA_IG_TOKEN" vira IG_TOKEN para o cliente "padaria").
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import yaml

RAIZ_REPO = Path(__file__).resolve().parent.parent
PASTA_CLIENTES = RAIZ_REPO / "clientes"

# Segredos que pertencem a cada cliente: nunca usamos o de outro cliente no lugar.
SEGREDOS_DO_CLIENTE = ["IG_TOKEN", "IG_USER_ID", "PAINEL_SENHA", "SMTP_SENHA", "SMTP_USUARIO", "GOOGLE_MAPS_KEY"]
# Segredos que podem ser da agência (pagos por nós e embutidos no preço) se o cliente não tiver o próprio.
SEGREDOS_COMPARTILHAVEIS = ["ANTHROPIC_API_KEY", "FAL_KEY"]

# Ficha → variável de ambiente que o código dos agentes já entende. Uma variável do GitHub com o mesmo
# nome (e o prefixo do cliente) tem prioridade sobre a ficha.
MAPA_AMBIENTE = {
    "IG_USER_ID": ("instagram", "ig_user_id"),
    "MODO_CENA": ("instagram", "modo_cena"),
    "REELS_TESTE": ("instagram", "reels_teste"),
    "COPIAR_STORIES": ("instagram", "copiar_stories"),
    "EMAIL_REMETENTE": ("prospeccao", "email_remetente"),
    "NOME_REMETENTE": ("prospeccao", "nome_remetente"),
    "SMTP_HOST": ("prospeccao", "smtp_host"),
    "IMAP_HOST": ("prospeccao", "imap_host"),
    "LINK_AGENDA": ("prospeccao", "link_agenda"),
    "RODAPE_EMPRESA": ("prospeccao", "rodape_empresa"),
    "LIMITE_DIA": ("prospeccao", "limite_dia"),
    "BUSCAS_GOOGLE_POR_MES": ("prospeccao", "buscas_google_mes"),
    "MUNICIPIO_RECEITA": ("prospeccao", "municipio_receita"),
    "LINK_SITE": (None, "site"),
    "CIDADE": (None, "cidade"),
    "UF": (None, "uf"),
}


def id_atual() -> str:
    return (os.getenv("CLIENTE") or "ello").strip().lower()


def pasta(cid: str | None = None) -> Path:
    return PASTA_CLIENTES / (cid or id_atual())


def _texto(v) -> str:
    if v is True:
        return "sim"
    if v is False:
        return "nao"
    return "" if v is None else str(v)


def carregar_prefixo(cid: str) -> str:
    """Prefixo padrão dos segredos no GitHub: nome da pasta em maiúsculas + "_" (a ELLO não tem prefixo)."""
    return "" if cid == "ello" else re.sub(r"[^A-Z0-9]", "_", cid.upper()) + "_"


def carregar(cid: str | None = None) -> dict:
    """Lê a ficha do cliente e completa o que estiver faltando com padrões seguros."""
    cid = cid or id_atual()
    arq = pasta(cid) / "cliente.yaml"
    if not arq.exists():
        raise SystemExit(f"Cliente '{cid}' não encontrado: falta o arquivo {arq.relative_to(RAIZ_REPO)}.")
    c = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
    c["id"] = cid
    c.setdefault("nome_curto", c.get("nome", cid))
    c.setdefault("prefixo_segredos", carregar_prefixo(cid))
    br = c.setdefault("branches", {})
    br.setdefault("instagram", f"dados-{cid}")
    br.setdefault("midia", f"midia-{cid}")
    br.setdefault("prospeccao", f"prospeccao-dados-{cid}")
    c.setdefault("cores", {})
    c.setdefault("whatsapp", {})
    c.setdefault("instagram", {})
    c.setdefault("prospeccao", {})
    return c


def ligado(c: dict, agente: str) -> bool:
    return _texto((c.get(agente) or {}).get("ligado", "nao")).strip().lower() == "sim"


def todos() -> list[str]:
    return sorted(p.name for p in PASTA_CLIENTES.iterdir()
                  if p.is_dir() and not p.name.startswith(("_", ".")) and (p / "cliente.yaml").exists())


def _json_env(nome: str) -> dict:
    try:
        return json.loads(os.getenv(nome) or "{}") or {}
    except json.JSONDecodeError:
        return {}


def aplicar_ambiente(c: dict) -> None:
    """Coloca no ambiente só os segredos e opções DESTE cliente."""
    p = c["prefixo_segredos"]
    segredos = _json_env("SEGREDOS_JSON")
    variaveis = _json_env("VARIAVEIS_JSON")
    no_github = bool(segredos)   # rodando no GitHub com a lista completa de segredos

    for nome in SEGREDOS_DO_CLIENTE:
        if no_github:
            # Sempre sobrescreve: se o cliente não tiver o segredo, fica vazio (nunca o de outro cliente).
            os.environ[nome] = segredos.get(p + nome, "")
        elif p and os.getenv(p + nome):
            os.environ[nome] = os.environ[p + nome]
    for nome in SEGREDOS_COMPARTILHAVEIS:
        valor = segredos.get(p + nome) or segredos.get(nome) or os.getenv(p + nome) or os.getenv(nome) or ""
        if valor:
            os.environ[nome] = valor

    for nome, (secao, chave) in MAPA_AMBIENTE.items():
        if nome in SEGREDOS_DO_CLIENTE and os.getenv(nome):
            continue   # IG_USER_ID cadastrado como segredo vence a ficha
        do_github = variaveis.get(p + nome)
        valor = do_github if do_github else _texto((c.get(secao) or {}).get(chave) if secao else c.get(chave))
        if valor:
            os.environ[nome] = valor
    os.environ["CLIENTE"] = c["id"]


def marca_md(c: dict) -> str:
    arq = pasta(c["id"]) / "marca.md"
    return arq.read_text(encoding="utf-8") if arq.exists() else ""


def segmentos(c: dict) -> dict:
    arq = pasta(c["id"]) / "segmentos.yaml"
    return (yaml.safe_load(arq.read_text(encoding="utf-8")) or {}) if arq.exists() else {}


def arquivo_marca(c: dict, relativo: str, padrao: Path | None = None) -> Path | None:
    """Arquivo da pasta do cliente (logo, trilha...), ou o padrão do produto se o cliente não tiver."""
    if relativo:
        arq = pasta(c["id"]) / relativo
        if arq.exists():
            return arq
    return padrao if padrao and padrao.exists() else None


# Cores da ELLO usadas no desenho original dos vídeos e carrosséis. Cada cliente troca pelas suas.
CORES_ORIGINAIS = {
    "escuro": "#0A1A33", "fundo": "#0B1626", "fundo_brilho": "#1B3A5E", "marinho": "#0E2240",
    "destaque": "#F5B731", "destaque_claro": "#F5CF4A", "destaque_carrossel": "#F5A524",
    "secundaria": "#2D6DB0", "secundaria_clara": "#4D9BEA", "azul_carrossel": "#2F5BEA",
    "alerta": "#D92D2D", "botao_carrossel": "#1FAF5B",
}


def _rgb(h: str) -> str:
    h = h.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def aplicar_cores(texto: str, c: dict) -> str:
    """Troca as cores originais do desenho pelas cores do cliente (sem mudar nada para a ELLO)."""
    cores = c.get("cores") or {}
    for chave, original in CORES_ORIGINAIS.items():
        nova = str(cores.get(chave) or original)
        if nova.upper() == original.upper():
            continue
        texto = re.sub(re.escape(original), nova, texto, flags=re.IGNORECASE)
        texto = texto.replace(f"rgba({_rgb(original)},", f"rgba({_rgb(nova)},")
    return texto


def link_whatsapp(c: dict, mensagem: str | None = None) -> str:
    from urllib.parse import quote
    numero = re.sub(r"\D", "", str((c.get("whatsapp") or {}).get("numero", "")))
    msg = mensagem if mensagem is not None else (c.get("whatsapp") or {}).get("mensagem_instagram", "")
    return f"https://wa.me/{numero}" + (f"?text={quote(msg, safe='!')}" if msg else "")
