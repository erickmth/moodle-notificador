import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from portal import PortalClient

BASE_DIR = Path(__file__).resolve().parent
FALTAS_FILE = BASE_DIR / "faltas.json"

FUSO = timezone(timedelta(hours=-3))  # America/Sao_Paulo


def escolher_periodo_atual(periodos):
    """Período mais recente que já começou (ou o mais recente, se nenhum)."""
    hoje = datetime.now(FUSO).strftime("%Y-%m-%d")
    nomes = sorted(periodos)
    iniciados = [
        p for p in nomes
        if periodos[p].get("inicio") and periodos[p]["inicio"] <= hoje
    ]
    if iniciados:
        return max(iniciados, key=lambda p: periodos[p]["inicio"])
    return nomes[-1] if nomes else None


def main():
    print()
    print("=" * 50)
    print(" FALTAS - PORTAL EDUCACIONAL")
    print("=" * 50)

    usuario = os.getenv("PORTAL_USER") or os.getenv("MOODLE_USER")
    senha = os.getenv("PORTAL_PASSWORD") or os.getenv("MOODLE_PASSWORD")

    if not usuario or not senha:
        print("❌ PORTAL_USER / PORTAL_PASSWORD não configurados.")
        raise SystemExit(1)

    origem = "PORTAL_*" if os.getenv("PORTAL_USER") else "MOODLE_* (reaproveitado)"
    print(f"🔑 Credenciais: {origem}")

    client = PortalClient(
        usuario,
        senha,
        alias=os.getenv("PORTAL_ALIAS", "CorporeRM"),
    )
    client.login()

    periodos = client.get_faltas_todos_periodos()
    atual = os.getenv("PORTAL_PERIODO") or escolher_periodo_atual(periodos)

    dados = {
        "atualizado_em": datetime.now(FUSO).isoformat(timespec="seconds"),
        "periodo_atual": atual,
        "periodos": periodos,
    }

    with open(FALTAS_FILE, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")

    print()
    print(f"💾 {FALTAS_FILE.name} salvo. Período atual: {atual}")
    for periodo, info in periodos.items():
        print(f"\n📚 {periodo}")
        for d in info["disciplinas"]:
            pct = d["percentual"]
            pct_txt = f"{pct:g}%" if pct is not None else "-"
            print(f"   {d['total']:>3} faltas ({pct_txt:>5})  {d['disciplina']}")


if __name__ == "__main__":
    main()
