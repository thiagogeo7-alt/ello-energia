"""Coleta de contatos de empresas: Google Maps + e-mail público do site, e base aberta de CNPJ da Receita."""
import csv
import io
import re
import time
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from . import config, estado
from .rede import ErroAPI, chamar
from .segmentos import SEGMENTOS, segmento_por_cnae

BAIRROS = ["Centro", "Cambuí", "Taquaral", "Barão Geraldo", "Sousas", "Castelo", "Guanabara",
           "Nova Campinas", "Ouro Verde", "Campos Elíseos", "Jardim Proença", "Bonfim",
           "Vila Industrial", "Swift", "Parque Prado", "Chapadão", "Botafogo", "São Bernardo",
           "Vila Itapura", "Jardim do Trevo", "Parque Industrial", "Jardim Aurélia", "Bosque",
           "Mansões Santo Antônio", "Jardim Garcia", "Vila Nova", "Jardim Nova Europa", "DIC"]

DOMINIOS_IGNORAR = ("instagram.com", "facebook.com", "linktr.ee", "wa.me", "whatsapp.com", "ifood.com",
                    "google.com", "goo.gl", "youtube.com", "tiktok.com", "linkedin.com", "twitter.com", "x.com")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LIXO = ("example", "exemplo", "sentry", "wixpress", "@2x", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
        "seudominio", "seuemail", "email@", "domain.com", "noreply", "no-reply", "godaddy", "u003e")
UA = {"User-Agent": "Mozilla/5.0 (compatible; ELLO-prospeccao/1.0; +https://thiagogeo7-alt.github.io/ello-energia/)"}


# ---------- Utilidades ----------

def _indice_emails(crm: dict) -> set:
    return {c["email"].lower() for c in crm["contatos"].values() if c.get("email")}


def adicionar(crm: dict, idc: str, email: str, empresa: str, segmento: str, fonte: str, **extra) -> bool:
    email = (email or "").strip().lower().rstrip(".")
    if not email or idc in crm["contatos"] or email in crm["bloqueados"]:
        return False
    if email in crm.setdefault("_idx", _indice_emails(crm)):
        return False
    crm["contatos"][idc] = {"id": idc, "email": email, "empresa": (empresa or "").strip()[:120],
                            "segmento": segmento, "fonte": fonte, "status": "novo", "criado": estado.iso(),
                            "enviados": [], "respostas": [], **{k: v for k, v in extra.items() if v}}
    crm["_idx"].add(email)
    return True


def emails_do_site(url: str) -> list[str]:
    """Procura e-mails públicos na página inicial e nas páginas de contato do site."""
    if not url or any(d in url for d in DOMINIOS_IGNORAR):
        return []
    dominio = urlparse(url).netloc.replace("www.", "")
    achados: list[str] = []
    paginas = [url, urljoin(url, "/contato"), urljoin(url, "/contato/"), urljoin(url, "/fale-conosco"),
               urljoin(url, "/contact")]
    for pg in paginas:
        try:
            r = requests.get(pg, headers=UA, timeout=10, allow_redirects=True)
        except requests.RequestException:
            continue
        if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", ""):
            continue
        texto = r.text.replace("[at]", "@").replace("(at)", "@").replace(" arroba ", "@")
        for e in EMAIL_RE.findall(texto):
            e = e.lower().strip(".")
            if any(x in e for x in LIXO) or e in achados:
                continue
            achados.append(e)
        if achados:
            break
        time.sleep(0.5)
    # Prefere e-mails do próprio domínio do site
    achados.sort(key=lambda e: (dominio not in e, len(e)))
    return achados[:2]


# ---------- Google Maps (Places API) ----------

def _buscar_google(consulta: str) -> list[dict]:
    cab = {"Content-Type": "application/json", "X-Goog-Api-Key": config.GOOGLE_MAPS_KEY,
           "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.websiteUri,"
                               "places.nationalPhoneNumber,places.businessStatus"}
    r = chamar("POST", "https://places.googleapis.com/v1/places:searchText", headers=cab,
               json={"textQuery": consulta, "languageCode": "pt-BR", "regionCode": "BR", "pageSize": 20})
    return r.get("places", [])


def coletar_google(crm: dict, max_buscas: int | None = None) -> int:
    config.exigir("GOOGLE_MAPS_KEY")
    mes = date.today().strftime("%Y-%m")
    usadas = crm["buscas_google"].get(mes, 0)
    disponiveis = min(max_buscas or 250, config.BUSCAS_GOOGLE_POR_MES - usadas)
    if disponiveis <= 0:
        print(f"Cota mensal de buscas no Google já usada ({usadas}). Nada a fazer até o mês que vem.")
        return 0
    feitas = set(crm["consultas_feitas"])
    fila = [f"{termo} em {bairro}, {config.CIDADE} {config.UF}"
            for bairro in BAIRROS for s in SEGMENTOS.values() for termo in s["buscas"]]
    fila = [q for q in fila if q not in feitas]
    if not fila:   # tudo já buscado: recomeça o ciclo
        crm["consultas_feitas"], fila = [], [f"{t} em {b}, {config.CIDADE} {config.UF}"
                                             for b in BAIRROS for s in SEGMENTOS.values() for t in s["buscas"]]
    termo_seg = {t: k for k, s in SEGMENTOS.items() for t in s["buscas"]}
    novos = 0
    for consulta in fila[:disponiveis]:
        termo = consulta.split(" em ")[0]
        if config.SIMULAR:
            lugares = [{"id": f"sim-{abs(hash(consulta)) % 10**8}", "displayName": {"text": f"{termo.title()} Exemplo"},
                        "websiteUri": "", "formattedAddress": f"Rua Teste, {config.CIDADE}"}]
        else:
            try:
                lugares = _buscar_google(consulta)
            except ErroAPI as e:
                print(f"Google recusou a busca: {e}")
                break
        crm["buscas_google"][mes] = crm["buscas_google"].get(mes, 0) + 1
        crm["consultas_feitas"].append(consulta)
        for lg in lugares:
            if lg.get("businessStatus") not in (None, "OPERATIONAL"):
                continue
            site = lg.get("websiteUri", "")
            emails = ["contato@exemplo-simulado.com.br"] if config.SIMULAR else emails_do_site(site)
            if not emails:
                continue
            endereco = lg.get("formattedAddress", "")
            bairro = endereco.split(" - ")[1].split(",")[0] if " - " in endereco else ""
            if adicionar(crm, f"g:{lg['id']}", emails[0], lg.get("displayName", {}).get("text", ""),
                         termo_seg.get(termo, "comercio"), "site", site=site,
                         telefone=lg.get("nationalPhoneNumber", ""), bairro=bairro):
                novos += 1
    estado.evento(crm, "coleta_google", detalhe=f"{novos} contatos novos")
    print(f"Google: {disponiveis} buscas, {novos} contatos novos com e-mail.")
    return novos


# ---------- Base aberta de CNPJ (Receita Federal) ----------

def _competencia_recente() -> str:
    hoje = date.today()
    for i in range(0, 4):
        y, m = hoje.year, hoje.month - i
        while m <= 0:
            y, m = y - 1, m + 12
        comp = f"{y}-{m:02d}"
        try:
            r = requests.get(f"{config.RECEITA_BASE}/{comp}/", timeout=30, headers=UA)
            if r.status_code == 200 and "Estabelecimentos" in r.text:
                return comp
        except requests.RequestException:
            pass
    raise ErroAPI("Não encontrei a base de CNPJ da Receita. Ajuste a variável RECEITA_BASE.")


def _baixar(url: str, destino: Path) -> Path:
    with requests.get(url, stream=True, timeout=120, headers=UA) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for parte in r.iter_content(1 << 20):
                f.write(parte)
    return destino


def _linhas_zip(arq: Path):
    with zipfile.ZipFile(arq) as z:
        for nome in z.namelist():
            with z.open(nome) as f:
                yield from csv.reader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def coletar_cnpj(crm: dict, max_novos: int = 2500, pasta_tmp: str = "/tmp/cnpj") -> int:
    """Lê os 10 arquivos de Estabelecimentos, filtra Campinas + ativas + CNAE dos segmentos + com e-mail,
    e cruza com Empresas para pegar a razão social e excluir empresários individuais (MEI)."""
    comp = _competencia_recente()
    if crm.get("cnpj_competencia") == comp:
        print(f"Base de CNPJ {comp} já foi processada.")
        return 0
    tmp = Path(pasta_tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    achados, contagem_email = {}, {}
    for i in range(10):
        arq = _baixar(f"{config.RECEITA_BASE}/{comp}/Estabelecimentos{i}.zip", tmp / f"est{i}.zip")
        for row in _linhas_zip(arq):
            if len(row) < 28 or row[20] != config.MUNICIPIO_RECEITA or row[5] != "02":
                continue
            email = row[27].strip().lower()
            seg = segmento_por_cnae(row[11])
            if not email or not seg:
                continue
            contagem_email[email] = contagem_email.get(email, 0) + 1
            achados[row[0]] = {"cnpj": row[0] + row[1] + row[2], "fantasia": row[4], "email": email,
                               "segmento": seg, "cnae": row[11], "bairro": row[17].title(),
                               "telefone": f"({row[21]}) {row[22]}" if row[22] else ""}
        arq.unlink()
        print(f"Estabelecimentos{i}: {len(achados)} candidatos até agora")
    # E-mails repetidos em várias empresas costumam ser do escritório de contabilidade: descarta
    achados = {k: v for k, v in achados.items() if contagem_email[v["email"]] <= 2
               and not any(x in v["email"] for x in ("contab", "contador", "fiscal@", "dp@"))}
    razao = {}
    for i in range(10):
        arq = _baixar(f"{config.RECEITA_BASE}/{comp}/Empresas{i}.zip", tmp / f"emp{i}.zip")
        for row in _linhas_zip(arq):
            if row and row[0] in achados:
                razao[row[0]] = (row[1], row[2])   # razão social, natureza jurídica
        arq.unlink()
    novos = 0
    for basico, v in achados.items():
        rs, natureza = razao.get(basico, ("", ""))
        if natureza == "2135":   # empresário individual (MEI): e-mail costuma ser pessoal, não contatamos
            continue
        nome = v["fantasia"] or rs
        if adicionar(crm, f"cnpj:{v['cnpj']}", v["email"], nome.title(), v["segmento"], "cnpj",
                     cnae=v["cnae"], bairro=v["bairro"], telefone=v["telefone"]):
            novos += 1
            if novos >= max_novos:
                break
    crm["cnpj_competencia"] = comp
    estado.evento(crm, "coleta_cnpj", detalhe=f"{novos} contatos novos (base {comp})")
    print(f"CNPJ {comp}: {novos} contatos novos.")
    return novos
