import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import novidades
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


def registrar_faltas_novas(dados):
    """Compara com o faltas.json anterior e lista as faltas que aumentaram."""
    if not FALTAS_FILE.exists():
        return  # Primeira execução: nada para comparar.

    try:
        anterior = json.loads(FALTAS_FILE.read_text(encoding="utf-8"))
    except ValueError:
        return

    def por_disciplina(info):
        return {
            (d.get("codigo") or d.get("disciplina")): d
            for d in (info or {}).get("disciplinas", [])
        }

    novas = []
    for periodo, info in dados["periodos"].items():
        antes = por_disciplina(anterior.get("periodos", {}).get(periodo))
        if not antes:
            continue  # Período novo: não avisa tudo de uma vez.
        for chave, d in por_disciplina(info).items():
            total_antes = (antes.get(chave) or {}).get("total") or 0
            total = d.get("total") or 0
            if total > total_antes:
                novas.append({
                    "periodo": periodo,
                    "disciplina": d.get("disciplina"),
                    "novas": total - total_antes,
                    "total": total,
                })

    if novas:
        print(f"🆕 Disciplinas com falta nova: {len(novas)}")
        novidades.adicionar("faltas", novas)


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

    registrar_faltas_novas(dados)

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
