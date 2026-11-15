"""Conversa com o Claude pela API da Anthropic e devolve JSON."""
import json
import re

from . import config
from .rede import chamar


def perguntar_json(sistema: str, pedido: str, modelo: str | None = None,
                   max_tokens: int = 4000, simulado: dict | None = None) -> dict:
    if config.SIMULAR:
        return simulado or {}
    resp = chamar(
        "POST", "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": config.ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": modelo or config.MODELO_CRIATIVO, "max_tokens": max_tokens,
              "system": sistema, "messages": [{"role": "user", "content": pedido}]},
        timeout=180,
    )
    texto = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    if resp.get("stop_reason") == "max_tokens":
        raise ValueError("A resposta do Claude foi cortada no meio (limite de tamanho).")
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError(f"Claude não devolveu JSON: {texto[:300]}")
    return json.loads(m.group(0))
