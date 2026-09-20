import os
from datetime import datetime

from moodle import MoodleClient


def format_timestamp(timestamp):

    if not timestamp:
        return "Sem data"

    try:

        timestamp = int(timestamp)

        data = datetime.fromtimestamp(
            timestamp
        )

        return data.strftime(
            "%d/%m/%Y %H:%M"
        )

    except Exception:

        return str(timestamp)


def main():

    print("=" * 50)
    print("          NOTIFICADOR MOODLE")
    print("=" * 50)

    username = os.getenv(
        "MOODLE_USER"
    )

    password = os.getenv(
        "MOODLE_PASSWORD"
    )

    if not username or not password:

        print(
            "❌ MOODLE_USER ou MOODLE_PASSWORD "
            "não configurados."
        )

        return

    print()
    print("Consultando Moodle...")
    print()

    client = MoodleClient(
        username=username,
        password=password
    )

    # ======================================================
    # LOGIN
    # ======================================================

    if not client.login():

        print()
        print(
            "❌ Não foi possível acessar o Moodle."
        )

        return

    print()
    print(
        "✅ Login realizado com sucesso."
    )

    # ======================================================
    # DISCIPLINAS
    # ======================================================

    print()
    print(
        "Buscando disciplinas..."
    )

    courses = client.get_courses()

    print()
    print(
        f"📚 Disciplinas encontradas: "
        f"{len(courses)}"
    )

    if courses:

        print()

        for course in courses:

            course_id = course.get(
                "id",
                "?"
            )

            fullname = course.get(
                "fullname",
                "Sem nome"
            )

            shortname = course.get(
                "shortname",
                ""
            )

            print(
                f"• {fullname}"
            )

            if shortname:
                print(
                    f"  Código: {shortname}"
                )

            print(
                f"  ID: {course_id}"
            )

            print()

    else:

        print(
            "⚠️ Nenhuma disciplina encontrada."
        )

    # ======================================================
    # EVENTOS
    # ======================================================

    print()
    print(
        "Buscando eventos do calendário..."
    )

    events = client.get_calendar_events()

    print()
    print(
        f"📅 Eventos encontrados: "
        f"{len(events)}"
    )

    if events:

        print()

        for event in events:

            name = event.get(
                "name",
                event.get(
                    "title",
                    "Sem nome"
                )
            )

            event_type = event.get(
                "eventtype",
                ""
            )

            component = event.get(
                "modulename",
                event.get(
                    "component",
                    ""
                )
            )

            timestart = event.get(
                "timestart",
                event.get(
                    "timesort",
                    ""
                )
            )

            url = event.get(
                "url",
                ""
            )

            print(
                f"• {name}"
            )

            if event_type:
                print(
                    f"  Tipo: {event_type}"
                )

            if component:
                print(
                    f"  Módulo: {component}"
                )

            if timestart:
                print(
                    f"  Data: "
                    f"{format_timestamp(timestart)}"
                )

            if url:
                print(
                    f"  URL: {url}"
                )

            print()

    else:

        print(
            "⚠️ Nenhum evento encontrado."
        )

    print()
    print("=" * 50)
    print("              FINALIZADO")
    print("=" * 50)


if __name__ == "__main__":
    main()
