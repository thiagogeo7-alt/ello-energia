"""Memória do agente: o que já publicou, métricas, custos e o que já respondeu.

Fica no branch "dados" do repositório (separado do site). Como o repositório é público:
- estado.json  -> tudo que NÃO é dado pessoal (publicações, métricas, custos, contagens);
- leads.enc    -> contatos de interessados, CRIPTOGRAFADOS com a senha PAINEL_SENHA (LGPD).
"""
import base64
import json
import os
from datetime import datetime, timezone

from . import config

ARQUIVO = config.DADOS_DIR / "estado.json"
ARQUIVO_LEADS = config.DADOS_DIR / "leads.enc"
SENHA = (os.getenv("PAINEL_SENHA") or "").strip()
ITERACOES = 200_000

PADRAO = {
    "publicacoes": [],          # [{data, tipo, tema, gancho, legenda, media_id, permalink, metricas}]
    "comentarios_respondidos": [],
    "mensagens_respondidas": [],
    "leads": [],                # só em memória; salvo criptografado em leads.enc
    "custos": [],               # [{data, servico, usd}]
    "acoes": [],                # linha do tempo para o painel: [{data, tipo, detalhe}]
}


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def proximo_ref(est: dict, tipo: str) -> str:
    """Código curto do próximo post: R1, R2... para Reels e C1, C2... para carrosséis."""
    letra = "R" if tipo == "reel" else "C"
    return f"{letra}{sum(1 for p in est['publicacoes'] if p.get('tipo') == tipo) + 1}"


def refs_por_media(est: dict) -> dict:
    """media_id → código do post (inclui os posts antigos, numerados na ordem em que saíram)."""
    cont, refs = {}, {}
    for p in est["publicacoes"]:
        letra = "R" if p.get("tipo") == "reel" else "C"
        cont[letra] = cont.get(letra, 0) + 1
        p.setdefault("ref", f"{letra}{cont[letra]}")
        if p.get("media_id"):
            refs[p["media_id"]] = p["ref"]
    return refs


def registrar(est: dict, tipo: str, detalhe: str = "") -> None:
    """Adiciona um item à linha do tempo do painel (sem dados pessoais)."""
    est["acoes"].append({"data": agora(), "tipo": tipo, "detalhe": detalhe[:140]})


# ---------- Criptografia dos leads (AES-GCM + PBKDF2, compatível com o navegador) ----------

def _chave(salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERACOES).derive(SENHA.encode())


def _cifrar(dados: list) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_chave(salt)).encrypt(iv, json.dumps(dados, ensure_ascii=False).encode(), None)
    b = lambda x: base64.b64encode(x).decode()
    return json.dumps({"v": 1, "iter": ITERACOES, "salt": b(salt), "iv": b(iv), "dados": b(ct)})


def _decifrar(texto: str) -> list:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    o = json.loads(texto)
    d = lambda k: base64.b64decode(o[k])
    return json.loads(AESGCM(_chave(d("salt"))).decrypt(d("iv"), d("dados"), None))


# ---------- Carregar e salvar ----------

def carregar() -> dict:
    if ARQUIVO.exists():
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    else:
        dados = {}
    for k, v in PADRAO.items():
        dados.setdefault(k, type(v)())
    dados["leads"] = []
    dados["_total_anterior"] = dados.get("total_leads", 0)
    if SENHA and ARQUIVO_LEADS.exists():
        try:
            dados["leads"] = _decifrar(ARQUIVO_LEADS.read_text())
        except Exception as e:
            print(f"Aviso: não consegui abrir leads.enc ({e}). A senha PAINEL_SENHA mudou?")
    dados["_leads_iniciais"] = len(dados["leads"])
    return dados


def salvar(dados: dict) -> None:
    config.DADOS_DIR.mkdir(parents=True, exist_ok=True)
    for k in ("comentarios_respondidos", "mensagens_respondidas"):
        dados[k] = dados[k][-3000:]
    dados["acoes"] = dados["acoes"][-500:]

    publico = {k: v for k, v in dados.items() if k != "leads" and not k.startswith("_")}
    novos = len(dados["leads"]) - dados.get("_leads_iniciais", 0)
    publico["total_leads"] = dados.get("_total_anterior", 0) + novos
    publico["atualizado_em"] = agora()
    ARQUIVO.write_text(json.dumps(publico, ensure_ascii=False, indent=2), encoding="utf-8")

    if dados["leads"]:
        if SENHA:
            ARQUIVO_LEADS.write_text(_cifrar(dados["leads"]))
        else:
            print("Aviso: cadastre o segredo PAINEL_SENHA para guardar os leads com segurança.")
