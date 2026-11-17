"""Diz ao GitHub para quais clientes um agente deve rodar agora.

Uso: python nucleo/lista.py instagram|prospeccao [cliente|todos] [reels|carrossel]
Imprime: lista=[{"cliente": "ello", "dados": "...", ...}]   (formato de saída do GitHub Actions)

- "todos" (ou vazio, nas execuções agendadas): só os clientes com o agente "ligado: sim" na ficha.
- Um cliente específico: roda para ele mesmo que esteja desligado (útil para testes).
- Ritmo do plano (só nas execuções automáticas): instagram.reels_por_mes (15 ou 8) e
  instagram.carrosseis_por_semana (2 ou 1) na ficha do cliente.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nucleo import cliente  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "instagram"))
import agenda  # noqa: E402  (regras de dia/horário/uma vez por dia, as mesmas do agente)


def _estado(branch: str) -> dict:
    """Lê o estado.json do cliente direto do branch de dados (sem baixar o resto)."""
    try:
        subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", branch], check=True,
                       capture_output=True, timeout=60)
        return json.loads(subprocess.run(["git", "show", "FETCH_HEAD:estado.json"], check=True,
                                         capture_output=True, timeout=30).stdout or b"{}")
    except (subprocess.SubprocessError, ValueError, OSError):
        return {}


def no_ritmo(c: dict, tarefa: str) -> bool:
    """Execuções automáticas: é dia previsto no plano, está no horário e ainda não publicou hoje?"""
    if tarefa not in agenda.REGRAS:
        return True
    agora = datetime.now(agenda.BRASILIA)
    ig = c.get("instagram") or {}
    if tarefa == "reels" and int(ig.get("reels_por_mes") or 15) < 15 and agora.day % 4 != 1:
        return False   # plano de 8 Reels por mês: dias 1, 5, 9, 13...
    if tarefa == "carrossel" and int(ig.get("carrosseis_por_semana") or 2) < 2 and agora.weekday() != 1:
        return False   # plano de 1 carrossel por semana: terça
    rodar, motivo = agenda.decidir(tarefa, _estado(c["branches"]["instagram"]), agora)
    print(f"{c['id']}: {'publicar' if rodar else 'pular'} ({motivo})", file=sys.stderr)
    return rodar


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
