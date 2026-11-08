"""
Arquivo temporário (não vai para o repositório) com o que mudou nesta
execução. O bot do WhatsApp lê esse arquivo para mandar os avisos.
"""

import json
from pathlib import Path

NOVIDADES_FILE = Path(__file__).resolve().parent / "novidades.json"


def adicionar(tipo, itens):
    dados = {}
    if NOVIDADES_FILE.exists():
        try:
            dados = json.loads(NOVIDADES_FILE.read_text(encoding="utf-8")) or {}
        except (ValueError, OSError):
            dados = {}

    dados.setdefault(tipo, []).extend(itens)
    NOVIDADES_FILE.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
