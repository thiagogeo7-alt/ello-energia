"""Chamadas HTTP com novas tentativas e mensagens de erro legíveis."""
import time

import requests


class ErroAPI(RuntimeError):
    pass


def chamar(metodo: str, url: str, tentativas: int = 3, **kwargs) -> dict:
    kwargs.setdefault("timeout", 60)
    ultimo = None
    for i in range(tentativas):
        try:
            r = requests.request(metodo, url, **kwargs)
        except requests.RequestException as e:
            ultimo = str(e)
        else:
            if r.status_code < 400:
                return r.json() if r.content else {}
            ultimo = f"HTTP {r.status_code}: {r.text[:500]}"
            if r.status_code < 500 and r.status_code != 429:
                break   # erro do pedido: repetir não adianta
        time.sleep(2 ** (i + 1))
    raise ErroAPI(f"{metodo} {url.split('?')[0]} falhou — {ultimo}")
