import os

from moodle import MoodleClient


def main():

    username = os.getenv("MOODLE_USER")
    password = os.getenv("MOODLE_PASSWORD")

    if not username:
        print("❌ MOODLE_USER não configurado.")
        return

    if not password:
        print("❌ MOODLE_PASSWORD não configurado.")
        return

    client = MoodleClient(
        username=username,
        password=password
    )

    client.test()


if __name__ == "__main__":
    main()
