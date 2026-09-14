from moodle import MoodleClient


def main():
    print("=" * 50)
    print("          NOTIFICADOR MOODLE")
    print("=" * 50)
    print()

    client = MoodleClient()

    print("Consultando Moodle...")
    print()

    # Tenta fazer login
    if not client.login():
        print()
        print("❌ Não foi possível acessar o Moodle.")
        return

    print()
    print("Buscando disciplinas...")
    print()

    # Busca as disciplinas
    cursos = client.get_courses()

    print(f"📚 Disciplinas encontradas: {len(cursos)}")
    print()

    if cursos:
        for curso in cursos:
            print(f"- {curso['fullname']}")

            if curso.get("url"):
                print(f"  {curso['url']}")

            print()
    else:
        print("⚠️ Nenhuma disciplina encontrada.")
        print()

    print("Buscando eventos do calendário...")
    print()

    # Busca eventos
    eventos = client.get_calendar_events()

    print(f"📅 Eventos encontrados: {len(eventos)}")
    print()

    if eventos:
        for evento in eventos:
            print(f"- {evento['title']}")

            if evento.get("url"):
                print(f"  {evento['url']}")

            print()
    else:
        print("Nenhum evento encontrado.")
        print()

    print("=" * 50)
    print("       VERIFICAÇÃO CONCLUÍDA")
    print("=" * 50)


if __name__ == "__main__":
    main()
