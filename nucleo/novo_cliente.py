"""Cria a pasta de um cliente novo (clientes/<id>/) a partir do modelo, com rascunho feito por IA.

Uso (o workflow "Produto - Novo cliente" chama isto com os dados do formulário):
  python nucleo/novo_cliente.py --id clinica-sorriso --nome "Clínica Sorriso" --cidade Campinas --uf SP \
      --whatsapp 5519999999999 --site https://... --descricao "o que a empresa faz, para quem, diferenciais" \
      --vende-para-empresas nao

Sem ANTHROPIC_API_KEY (ou com SIMULAR=1), cria só a ficha básica a partir do modelo.
O cliente nasce DESLIGADO (ligado: nao). Revise os arquivos, faça o teste e só então ligue.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nucleo import cliente  # noqa: E402

MODELO_IA = os.getenv("MODELO_CRIATIVO") or "claude-sonnet-5-5"


def _slug(t: str) -> str:
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:30]


def _legivel(numero: str) -> str:
    n = re.sub(r"\D", "", numero)
    if n.startswith("55"):
        n = n[2:]
    if len(n) == 11:
        return f"({n[:2]}) {n[2:7]}-{n[7:]}"
    if len(n) == 10:
        return f"({n[:2]}) {n[2:6]}-{n[6:]}"
    return numero


def texto_do_site(url: str, limite: int = 6000) -> str:
    """Lê o texto visível da página inicial do cliente (ajuda a IA a acertar o tom e os fatos)."""
    if not url:
        return ""
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        t = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", r.text)
        t = html.unescape(re.sub(r"<[^>]+>", " ", t))
        return re.sub(r"\s+", " ", t).strip()[:limite]
    except requests.RequestException as e:
        print(f"Aviso: não consegui ler o site ({e})")
        return ""


def perguntar_claude(sistema: str, pedido: str, max_tokens: int = 8000) -> dict:
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=300, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
        "content-type": "application/json"},
        json={"model": MODELO_IA, "max_tokens": max_tokens, "system": sistema,
              "messages": [{"role": "user", "content": pedido}]})
    r.raise_for_status()
    texto = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError(f"A IA não devolveu JSON: {texto[:300]}")
    return json.loads(m.group(0))


SISTEMA = """Você é estrategista de marketing digital de pequenas e médias empresas brasileiras.
Vai preparar a configuração de dois agentes automáticos para um cliente novo:
(1) Instagram: Reels de 20-30 s feitos com IA (formatos diálogo, explicativo com desenhos e reação),
carrosséis educativos, Stories e respostas automáticas que levam para o WhatsApp quando a pessoa comenta
uma palavra-chave; (2) Prospecção B2B por e-mail (só se o cliente vende para empresas).

Use SOMENTE fatos da descrição e do site. Não invente números, prêmios, clientes ou preços.
Inclua nas regras as restrições éticas do setor quando existirem (ex.: saúde: CFM/CFO proíbem
promessa de resultado e "antes e depois"; advocacia: OAB proíbe captação ativa de clientela, então
NÃO faça prospecção ativa; financeiro: sem promessa de rentabilidade).
Português do Brasil. Responda SOMENTE com JSON válido."""

PEDIDO = """Cliente novo:
- Nome: {nome}
- Cidade: {cidade}/{uf}
- WhatsApp: {whatsapp}
- Site: {site}
- Vende para empresas (B2B)? {b2b}
- Descrição dada pelo dono: {descricao}

Texto do site (pode estar vazio):
{site_texto}

Devolva este JSON:
{{
  "marca_md": "guia da marca completo em Markdown, no MESMO formato do modelo abaixo",
  "nome_curto": "nome curto (até 12 letras)",
  "palavra_chave": "UMA palavra em MAIÚSCULAS para comentar (ex.: QUERO, AGENDAR)",
  "oferta": "o presente oferecido em troca do contato, em minúsculas (ex.: 'a primeira avaliação é gratuita')",
  "mensagem_instagram": "mensagem que já vem escrita no WhatsApp quando a pessoa clica",
  "dm_palavra_chave": "direct enviado a quem comenta a palavra-chave, 3 parágrafos curtos, termina com '👉 {{link}}'",
  "dm_padrao": "frase curta convidando para o WhatsApp",
  "tela_final": {{"titulo_1": "até 12 letras MAIÚSCULAS", "titulo_2": "até 10 letras MAIÚSCULAS", "subtitulo": "até 28 letras MAIÚSCULAS",
                  "slogan": "frase curta", "ganhe_1": "até 30 letras", "ganhe_2": "até 20 letras, termina com a palavra em destaque"}},
  "rodape_carrossel": "o que a empresa faz · cidade",
  "exemplo_explicativo": "passo → passo → passo do serviço",
  "exemplo_reacao": "situação de emoção forte ligada ao problema",
  "ambientes": "6 a 9 ambientes onde o público vive o problema",
  "argumentos": ["7 argumentos de venda diferentes, cada um 'Rótulo: explicação curta'"],
  "cores": {{"escuro": "#hex", "destaque": "#hex", "secundaria": "#hex"}} (se o site deixar claro; senão {{}}),
  "prospeccao": {{
     "beneficio_central": "uma frase", "resumo_oferta": "uma linha", "pedido_interessado": "o que pedir a quem tem interesse",
     "pergunta_final_exemplo": "pergunta de sim/não", "regras": "regras extras em linhas começando com '- '",
     "segmentos": {{"chave_sem_espaco": {{"nome": "...", "buscas": ["termos do Google Maps"], "cnae": ["prefixos CNAE"], "angulo": "por que faz sentido para eles"}}}}
  }} (ou null se o cliente não vende para empresas ou o setor proíbe prospecção ativa)
}}

Modelo do guia da marca:
{modelo_marca}"""


def criar(a: argparse.Namespace) -> Path:
    cid = _slug(a.id or a.nome)
    destino = cliente.PASTA_CLIENTES / cid
    if destino.exists():
        raise SystemExit(f"Já existe um cliente com o nome '{cid}'. Escolha outro.")
    modelo = cliente.PASTA_CLIENTES / "_modelo"
    shutil.copytree(modelo, destino)

    c = yaml.safe_load((destino / "cliente.yaml").read_text(encoding="utf-8"))
    numero = re.sub(r"\D", "", a.whatsapp or "")
    if numero and not numero.startswith("55"):
        numero = "55" + numero
    c.update({"nome": a.nome, "nome_curto": a.nome.split()[0][:12], "cidade": a.cidade, "uf": a.uf.upper(),
              "site": a.site or ""})
    c["whatsapp"].update({"numero": numero, "legivel": _legivel(numero)})
    c["instagram"]["rodape_carrossel"] = f"{a.nome} · {a.cidade}"
    c["prospeccao"]["rodape_empresa"] = f"{a.nome} · {a.cidade}/{a.uf.upper()}"
    c["prospeccao"]["nome_remetente"] = f"Equipe | {a.nome}"

    b2b = (a.vende_para_empresas or "nao").lower().startswith("s")
    if os.getenv("ANTHROPIC_API_KEY") and os.getenv("SIMULAR") != "1":
        print("Pedindo à IA o rascunho da marca…")
        r = perguntar_claude(SISTEMA, PEDIDO.format(
            nome=a.nome, cidade=a.cidade, uf=a.uf, whatsapp=_legivel(numero), site=a.site or "-",
            b2b="sim" if b2b else "não", descricao=a.descricao or "-", site_texto=texto_do_site(a.site) or "-",
            modelo_marca=(modelo / "marca.md").read_text(encoding="utf-8")))
        (destino / "marca.md").write_text(r.get("marca_md") or "", encoding="utf-8")
        ig = c["instagram"]
        c["nome_curto"] = r.get("nome_curto") or c["nome_curto"]
        for k in ("palavra_chave", "oferta", "dm_palavra_chave", "dm_padrao", "rodape_carrossel",
                  "exemplo_explicativo", "exemplo_reacao", "ambientes", "argumentos"):
            if r.get(k):
                ig[k] = r[k]
        ig["tela_final"].update({k: v for k, v in (r.get("tela_final") or {}).items() if v})
        if r.get("mensagem_instagram"):
            c["whatsapp"]["mensagem_instagram"] = r["mensagem_instagram"]
        for k, v in (r.get("cores") or {}).items():
            if isinstance(v, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
                c["cores"][k] = v
        pr = r.get("prospeccao") if b2b else None
        if pr:
            for k in ("beneficio_central", "resumo_oferta", "pedido_interessado", "pergunta_final_exemplo", "regras"):
                if pr.get(k):
                    c["prospeccao"][k] = pr[k]
            if pr.get("segmentos"):
                (destino / "segmentos.yaml").write_text(
                    "# Rascunho feito por IA: revise os termos de busca e os CNAEs.\n"
                    + yaml.safe_dump(pr["segmentos"], allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    else:
        print("Sem chave da IA (ou em simulação): criei só a ficha básica. Complete marca.md à mão.")
    if not b2b:
        c["prospeccao"]["ligado"] = "nao"
        c["prospeccao"]["observacao"] = "Cliente vende para consumidor final: só o agente de Instagram."

    cabecalho = (f"# Ficha do cliente {a.nome}. Criada automaticamente: REVISE antes de ligar.\n"
                 f"# Segredos no GitHub com o prefixo {cliente.carregar_prefixo(cid)} (ex.: {cliente.carregar_prefixo(cid)}IG_TOKEN)\n\n")
    (destino / "cliente.yaml").write_text(
        cabecalho + yaml.safe_dump(c, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    print(f"Cliente criado em clientes/{cid}/")
    return destino


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--id", default="")
    p.add_argument("--nome", required=True)
    p.add_argument("--cidade", required=True)
    p.add_argument("--uf", required=True)
    p.add_argument("--whatsapp", default="")
    p.add_argument("--site", default="")
    p.add_argument("--descricao", default="")
    p.add_argument("--vende-para-empresas", default="nao")
    criar(p.parse_args())


if __name__ == "__main__":
    main()
