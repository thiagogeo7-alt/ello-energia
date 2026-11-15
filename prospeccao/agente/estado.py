"""CRM do agente de prospecção.

Fica no branch "prospeccao-dados" do repositório, que é recriado a cada gravação (sem histórico,
para o repositório não crescer). Como o repositório é público:
- resumo.json         -> só números e eventos sem dados pessoais (alimenta o painel);
- crm.enc             -> todos os contatos, CRIPTOGRAFADOS com PAINEL_SENHA;
- interessados.enc    -> interessados e reuniões, criptografados (o painel abre com a senha).
"""
import base64
import json
import os
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

SENHA = (os.getenv("PAINEL_SENHA") or "").strip()
ITER = 200_000
BRANCH = "prospeccao-dados"
REPO = os.getenv("GITHUB_REPOSITORY", "thiagogeo7-alt/ello-energia")
MAX_CONTATOS = int(os.getenv("MAX_CONTATOS", "6000"))

STATUS_ATIVOS = {"novo", "enviado", "lembrete1", "lembrete2"}


def agora() -> datetime:
    return datetime.now(timezone.utc)


def iso(d: datetime | None = None) -> str:
    return (d or agora()).isoformat(timespec="seconds")


# ---------- Criptografia (AES-GCM + PBKDF2, compatível com o navegador) ----------

def _chave(salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(SENHA.encode())


def cifrar(obj) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_chave(salt)).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode(), None)
    b = lambda x: base64.b64encode(x).decode()
    return json.dumps({"v": 1, "iter": ITER, "salt": b(salt), "iv": b(iv), "dados": b(ct)})


def decifrar(texto: str):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    o = json.loads(texto)
    d = lambda k: base64.b64decode(o[k])
    return json.loads(AESGCM(_chave(d("salt"))).decrypt(d("iv"), d("dados"), None))


# ---------- Carregar / salvar ----------

def carregar() -> dict:
    p = config.PASTA
    crm = {"contatos": {}, "bloqueados": [], "eventos": [], "envios_por_dia": {}, "buscas_google": {},
           "consultas_feitas": [], "custos": [], "cnpj_competencia": ""}
    if (p / "crm.enc").exists():
        if not SENHA:
            raise SystemExit("Cadastre o segredo PAINEL_SENHA: ele protege os contatos (LGPD).")
        crm.update(decifrar((p / "crm.enc").read_text()))
    elif (p / "crm-simulado.json").exists():
        crm.update(json.loads((p / "crm-simulado.json").read_text()))
    return crm


def _resumo(crm: dict) -> dict:
    cont = list(crm["contatos"].values())
    por_status = Counter(c["status"] for c in cont)
    por_seg = {}
    for c in cont:
        s = por_seg.setdefault(c.get("segmento") or "outros", Counter())
        s["total"] += 1
        s[c["status"]] += 1
        if c.get("enviados"):
            s["contatados"] += 1
        if c.get("respostas"):
            s["responderam"] += 1
    limite = agora() - timedelta(days=60)
    return {
        "atualizado_em": iso(),
        "total_contatos": len(cont),
        "com_email": sum(1 for c in cont if c.get("email")),
        "por_status": dict(por_status),
        "por_segmento": {k: dict(v) for k, v in por_seg.items()},
        "por_fonte": dict(Counter(c.get("fonte", "?") for c in cont)),
        "envios_por_dia": {d: n for d, n in crm["envios_por_dia"].items()
                           if d >= limite.date().isoformat()},
        "eventos": crm["eventos"][-200:],
        "buscas_google": crm["buscas_google"],
        "custos": crm["custos"][-500:],
        "bloqueados": len(crm["bloqueados"]),
        "cnpj_competencia": crm.get("cnpj_competencia", ""),
    }


def _interessados(crm: dict) -> list:
    saida = []
    for c in crm["contatos"].values():
        if c["status"] in ("interessado", "reuniao") or any(r.get("classe") == "pergunta" for r in c.get("respostas", [])):
            saida.append({k: c.get(k) for k in ("empresa", "email", "telefone", "segmento", "status", "site", "bairro")}
                         | {"ultima_resposta": (c.get("respostas") or [{}])[-1]})
    return saida


def podar(crm: dict) -> None:
    """Mantém a base num tamanho saudável: descarta primeiro os 'novos' mais antigos sem e-mail de site."""
    cont = crm["contatos"]
    excesso = len(cont) - MAX_CONTATOS
    if excesso <= 0:
        return
    candidatos = sorted((c for c in cont.values() if c["status"] == "novo"),
                        key=lambda c: (c.get("fonte") == "site", c.get("criado", "")))
    for c in candidatos[:excesso]:
        cont.pop(c["id"], None)


def evento(crm: dict, tipo: str, segmento: str = "", detalhe: str = "") -> None:
    crm["eventos"].append({"data": iso(), "tipo": tipo, "segmento": segmento, "detalhe": detalhe[:120]})
    crm["eventos"] = crm["eventos"][-1000:]


def salvar(crm: dict) -> None:
    crm.pop("_idx", None)
    podar(crm)
    p = config.PASTA
    p.mkdir(parents=True, exist_ok=True)
    (p / "resumo.json").write_text(json.dumps(_resumo(crm), ensure_ascii=False, indent=1), encoding="utf-8")
    if SENHA:
        (p / "crm.enc").write_text(cifrar(crm))
        (p / "interessados.enc").write_text(cifrar(_interessados(crm)))
    else:
        (p / "crm-simulado.json").write_text(json.dumps(crm, ensure_ascii=False))   # só em testes locais
    enviar_github()


def enviar_github() -> None:
    """Recria o branch prospeccao-dados com os arquivos atuais (sem acumular histórico)."""
    if config.SIMULAR or not os.getenv("GITHUB_TOKEN"):
        print("[local] dados de prospecção não enviados ao GitHub")
        return
    url = f"https://x-access-token:{os.environ['GITHUB_TOKEN']}@github.com/{REPO}"
    with tempfile.TemporaryDirectory() as tmp:
        for nome in ("resumo.json", "crm.enc", "interessados.enc"):
            f = config.PASTA / nome
            if f.exists():
                Path(tmp, nome).write_bytes(f.read_bytes())

        def git(*a):
            subprocess.run(["git", "-C", tmp, *a], check=True)
        git("init", "-q")
        git("checkout", "-q", "-b", BRANCH)
        git("add", "-A")
        git("-c", "user.name=Agente ELLO", "-c", "user.email=agente@users.noreply.github.com",
            "commit", "-q", "-m", f"Prospecção {iso()}")
        git("push", "-q", "-f", url, f"HEAD:{BRANCH}")
