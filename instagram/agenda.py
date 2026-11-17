"""Decide se uma execução AGENDADA deve publicar agora (só biblioteca padrão, roda em segundos).

Por que existe: o agendador do GitHub às vezes atrasa ou pula execuções. Por isso o workflow tenta
várias vezes ao longo do dia, e este verificador garante que só a primeira tentativa do dia publica.

Uso: python agenda.py reels|carrossel caminho/do/estado.json
Imprime "rodar=true" ou "rodar=false" (formato de saída do GitHub Actions).
"""
import json
import sys
from datetime import datetime, timedelta, timezone

BRASILIA = timezone(timedelta(hours=-3))

# tarefa: (é dia de publicar?, a partir de que hora de Brasília, tipo gravado no estado)
REGRAS = {
    "reels": (lambda d: d.day % 2 == 1, 17, "reel"),              # dias ímpares, a partir das 17h
    "carrossel": (lambda d: d.weekday() in (1, 3), 12, "carrossel"),  # terça e quinta, a partir das 12h
}


def _data_brasilia(texto: str):
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")).astimezone(BRASILIA).date()
    except ValueError:
        return None


def decidir(tarefa: str, estado: dict, agora: datetime) -> tuple[bool, str]:
    e_dia, hora_minima, tipo = REGRAS[tarefa]
    if not e_dia(agora):
        return False, "hoje não é dia desta publicação"
    if agora.hour < hora_minima:
        return False, f"ainda não são {hora_minima}h"
    hoje = agora.date()
    for p in estado.get("publicacoes", []):
        if p.get("tipo") == tipo and _data_brasilia(p.get("data", "")) == hoje:
            return False, "já foi publicado hoje"
    return True, "é dia, está no horário e ainda não foi publicado hoje"


def main() -> None:
    tarefa, arquivo = sys.argv[1], sys.argv[2]
    try:
        estado = json.load(open(arquivo, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        estado = {}
    rodar, motivo = decidir(tarefa, estado, datetime.now(BRASILIA))
    print(f"rodar={'true' if rodar else 'false'}")
    print(f"{tarefa}: {'PUBLICAR' if rodar else 'pular'} ({motivo})", file=sys.stderr)


if __name__ == "__main__":
    main()
