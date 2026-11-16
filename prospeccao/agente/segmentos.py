"""Segmentos de prospecção: vêm do arquivo clientes/<id>/segmentos.yaml de cada cliente."""
from . import config

SEGMENTOS = {k: {"nome": v.get("nome", k), "buscas": list(v.get("buscas") or []),
                 "cnae": [str(x) for x in (v.get("cnae") or [])], "angulo": v.get("angulo", ""),
                 "instrucao": v.get("instrucao", "")}
             for k, v in (config.SEGMENTOS or {}).items()}
SEGMENTO_PADRAO = next(iter(SEGMENTOS), None)


def segmento_por_cnae(cnae: str) -> str | None:
    """Escolhe o segmento pelo CNAE principal (o prefixo mais específico vence)."""
    melhor, tam = None, 0
    for chave, s in SEGMENTOS.items():
        for p in s["cnae"]:
            if cnae.startswith(p) and len(p) > tam:
                melhor, tam = chave, len(p)
    return melhor
