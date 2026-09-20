from moodle import MoodleClient


def main():
    print("=" * 50)
    print("          NOTIFICADOR MOODLE")
    print("=" * 50)
    print()

    client = MoodleClient()

    print("Consultando Moodle...")
    print()

    if not client.login():
        print()
        print("❌ Não foi possível acessar o Moodle.")
        return

    print()
    print("Buscando disciplinas...")
    print()

    cursos = client.get_courses()

    print()
    print(f"📚 Disciplinas encontradas: {len(cursos)}")
    print()

    if cursos:
        for curso in cursos:
            print(
                f"- [{curso.get('id')}] "
                f"{curso.get('fullname')}"
            )

            if curso.get("url"):
                print(
                    f"  {curso.get('url')}"
                )

            print()
    else:
        print(
            "⚠️ Nenhuma disciplina encontrada."
        )

    print("Buscando eventos do calendário...")
    print()

    eventos = client.get_calendar_events()

    print()
    print(
        f"📅 Eventos encontrados: {len(eventos)}"
    )
    print()

    if eventos:
        for evento in eventos:

            name = (
                evento.get("name")
                or evento.get("title")
                or "Sem nome"
            )

            print(f"- {name}")

            course = evento.get(
                "course"
            )

            if course:
                print(
                    f"  Curso: {course}"
                )

            timestart = evento.get(
                "timestart"
            )

            if timestart:
                print(
                    f"  Timestamp: {timestart}"
                )

            url = evento.get(
                "url"
            )

            if url:
                print(
                    f"  URL: {url}"
                )

            print()
    else:
        print(
            "Nenhum evento encontrado."
        )

    print("=" * 50)
    print("       VERIFICAÇÃO CONCLUÍDA")
    print("=" * 50)


if __name__ == "__main__":
    main()
