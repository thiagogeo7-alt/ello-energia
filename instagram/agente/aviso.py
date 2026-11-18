"""Ponte para scripts/alerta.py (avisos por e-mail para a equipe)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from alerta import enviar  # noqa: E402,F401
