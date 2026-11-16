"""Diz ao GitHub para quais clientes um agente deve rodar agora.

Uso: python nucleo/lista.py instagram|prospeccao [cliente|todos]
Imprime: lista=[{"cliente": "ello", "dados": "...", ...}]   (formato de saída do GitHub Actions)

- "todos" (ou vazio, nas execuções agendadas): só os clientes com o agente "ligado: sim" na ficha.
- Um cliente específico: roda para ele mesmo que esteja desligado (útil para testes).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nucleo import cliente  # noqa: E402


def main() -> None:
    agente = sys.argv[1]
    pedido = (sys.argv[2] if len(sys.argv) > 2 else "").strip().lower() or "todos"
    ids = cliente.todos() if pedido == "todos" else [pedido]
    lista = []
    for cid in ids:
        c = cliente.carregar(cid)
        if pedido == "todos" and not cliente.ligado(c, agente):
            continue
        lista.append({"cliente": cid, "dados": c["branches"]["instagram"], "midia": c["branches"]["midia"],
                      "prospeccao": c["branches"]["prospeccao"],
                      "previa": "previa-" if cid == "ello" else f"previa-{cid}-"})
    print("lista=" + json.dumps(lista, ensure_ascii=False))
    print(f"Clientes para '{agente}': {[x['cliente'] for x in lista] or 'nenhum'}", file=sys.stderr)


if __name__ == "__main__":
    main()
