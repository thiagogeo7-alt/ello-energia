"""Memória do agente: o que já publicou, métricas e o que já respondeu.

Fica em um JSON no branch "dados" do repositório (separado do site).
"""
import json
from datetime import datetime, timezone

from . import config

ARQUIVO = config.DADOS_DIR / "estado.json"

PADRAO = {
    "publicacoes": [],          # [{data, tipo, tema, gancho, prompt, legenda, media_id, metricas}]
    "comentarios_respondidos": [],
    "mensagens_respondidas": [],
    "leads": [],                # pessoas que demonstraram interesse (vai para o painel)
    "custos": [],               # [{data, servico, usd}]
}


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def carregar() -> dict:
    if ARQUIVO.exists():
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        for k, v in PADRAO.items():
            dados.setdefault(k, type(v)())
        return dados
    return json.loads(json.dumps(PADRAO))


def salvar(dados: dict) -> None:
    config.DADOS_DIR.mkdir(parents=True, exist_ok=True)
    # Mantém as listas de IDs respondidos num tamanho razoável
    for k in ("comentarios_respondidos", "mensagens_respondidas"):
        dados[k] = dados[k][-3000:]
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
