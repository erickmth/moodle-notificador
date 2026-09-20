from moodle import MoodleClient


def main():
    print("=" * 50)
    print("          NOTIFICADOR MOODLE")
    print("=" * 50)
    print()

    client = MoodleClient()

    print("Consultando Moodle...")
    print()

    # =========================================================
    # LOGIN
    # =========================================================

    if not client.login():
        print()
        print(
            "❌ Não foi possível acessar o Moodle."
        )
        return

    # =========================================================
    # DISCIPLINAS
    # =========================================================

    print()
    print("Buscando disciplinas...")
    print()

    cursos = client.get_courses()

    print()
    print(
        f"📚 Disciplinas encontradas: "
        f"{len(cursos)}"
    )
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

    # =========================================================
    # CALENDÁRIO
    # =========================================================

    print(
        "Buscando eventos do calendário..."
    )
    print()

    eventos = client.get_calendar_events()

    print()
    print(
        f"📅 Eventos encontrados: "
        f"{len(eventos)}"
    )
    print()

    if eventos:

        for evento in eventos:

            nome = (
                evento.get("name")
                or evento.get("title")
                or "Sem nome"
            )

            print(
                f"- {nome}"
            )

            # Curso associado
            course = evento.get(
                "course"
            )

            if course:
                print(
                    f"  Curso: {course}"
                )

            # Data/timestamp
            timestart = evento.get(
                "timestart"
            )

            if timestart:
                print(
                    f"  Timestamp: {timestart}"
                )

            # URL
            url = evento.get(
                "url"
            )

            if url:
                print(
                    f"  URL: {url}"
                )

            # Tipo do módulo
            modulename = evento.get(
                "modulename"
            )

            if modulename:
                print(
                    f"  Módulo: {modulename}"
                )

            print()

    else:

        print(
            "Nenhum evento encontrado."
        )

    # =========================================================
    # FINAL
    # =========================================================

    print("=" * 50)
    print("       VERIFICAÇÃO CONCLUÍDA")
    print("=" * 50)


if __name__ == "__main__":
    main()
