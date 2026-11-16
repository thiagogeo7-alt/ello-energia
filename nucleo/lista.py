"""Diz ao GitHub para quais clientes um agente deve rodar agora.

Uso: python nucleo/lista.py instagram|prospeccao [cliente|todos] [reels|carrossel]
Imprime: lista=[{"cliente": "ello", "dados": "...", ...}]   (formato de saída do GitHub Actions)

- "todos" (ou vazio, nas execuções agendadas): só os clientes com o agente "ligado: sim" na ficha.
- Um cliente específico: roda para ele mesmo que esteja desligado (útil para testes).
- Ritmo do plano (só nas execuções automáticas): instagram.reels_por_mes (15 ou 8) e
  instagram.carrosseis_por_semana (2 ou 1) na ficha do cliente.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nucleo import cliente  # noqa: E402


def no_ritmo(c: dict, tarefa: str) -> bool:
    """O plano do cliente prevê esta publicação hoje? (horário de Brasília)"""
    hoje = datetime.now(timezone.utc) - timedelta(hours=3)
    ig = c.get("instagram") or {}
    if tarefa == "reels":   # o agendamento roda nos dias ímpares (~15 por mês)
        return int(ig.get("reels_por_mes") or 15) >= 15 or hoje.day % 4 == 1   # 8 por mês: dias 1, 5, 9...
    if tarefa == "carrossel":   # o agendamento roda terça e quinta
        return int(ig.get("carrosseis_por_semana") or 2) >= 2 or hoje.weekday() == 1   # 1 por semana: terça
    return True


def main() -> None:
    agente = sys.argv[1]
    pedido = (sys.argv[2] if len(sys.argv) > 2 else "").strip().lower() or "todos"
    tarefa = sys.argv[3] if len(sys.argv) > 3 else ""
    ids = cliente.todos() if pedido == "todos" else [pedido]
    lista = []
    for cid in ids:
        c = cliente.carregar(cid)
        if pedido == "todos" and (not cliente.ligado(c, agente) or not no_ritmo(c, tarefa)):
            continue
        lista.append({"cliente": cid, "dados": c["branches"]["instagram"], "midia": c["branches"]["midia"],
                      "prospeccao": c["branches"]["prospeccao"],
                      "previa": "previa-" if cid == "ello" else f"previa-{cid}-"})
    print("lista=" + json.dumps(lista, ensure_ascii=False))
    print(f"Clientes para '{agente}': {[x['cliente'] for x in lista] or 'nenhum'}", file=sys.stderr)


if __name__ == "__main__":
    main()
