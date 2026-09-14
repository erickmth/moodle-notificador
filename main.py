
from moodle import MoodleClient


def main():
    print("=" * 40)
    print("       NOTIFICADOR MOODLE")
    print("=" * 40)
    print()

    client = MoodleClient()

    print("Consultando Moodle...")
    
    if not client.login():
        print("❌ Não foi possível acessar o Moodle.")
        return

    print("✅ Login realizado.")
    
    cursos = client.get_courses()

    print(f"\nDisciplinas encontradas: {len(cursos)}")

    for curso in cursos:
        print(f"- {curso['fullname']}")

    print("\nVerificação concluída.")


if __name__ == "__main__":
    main()
