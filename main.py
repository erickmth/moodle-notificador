import json
import os
from pathlib import Path

from moodle import MoodleClient


# Garante que o arquivo fique na raiz do repositório,
# independentemente do diretório de onde o Python for executado.
BASE_DIR = Path(__file__).resolve().parent
HISTORICO_FILE = BASE_DIR / "eventos.json"


def carregar_historico():

    if not HISTORICO_FILE.exists():

        print(
            "ℹ️ Arquivo eventos.json ainda não existe."
        )

        return []

    try:

        with open(
            HISTORICO_FILE,
            "r",
            encoding="utf-8"
        ) as arquivo:

            dados = json.load(arquivo)

            if isinstance(dados, list):

                return dados

            print(
                "⚠️ eventos.json não contém uma lista válida."
            )

            return []

    except json.JSONDecodeError:

        print(
            "⚠️ eventos.json está vazio ou possui JSON inválido."
        )

        return []

    except Exception as erro:

        print(
            f"⚠️ Não foi possível ler o histórico: "
            f"{erro}"
        )

        return []


def salvar_historico(eventos):

    try:

        with open(
            HISTORICO_FILE,
            "w",
            encoding="utf-8"
        ) as arquivo:

            json.dump(
                eventos,
                arquivo,
                ensure_ascii=False,
                indent=2
            )

            arquivo.write("\n")

        print(
            f"💾 Histórico salvo em: "
            f"{HISTORICO_FILE}"
        )

        print(
            f"💾 Total de eventos no histórico: "
            f"{len(eventos)}"
        )

    except Exception as erro:

        print(
            f"❌ Erro ao salvar eventos.json: "
            f"{erro}"
        )

        raise


def criar_chave_evento(evento):

    if evento.get("id"):

        return f"id:{evento['id']}"

    return "|".join([
        evento.get("nome", ""),
        evento.get("disciplina", ""),
        str(evento.get("timestamp", "")),
        evento.get("url", ""),
    ])


def main():

    print()
    print("=" * 50)
    print("          NOTIFICADOR MOODLE")
    print("=" * 50)

    print()
    print(
        f"📁 Arquivo de histórico: "
        f"{HISTORICO_FILE}"
    )

    username = os.getenv("MOODLE_USER")
    password = os.getenv("MOODLE_PASSWORD")

    if not username:

        print(
            "❌ MOODLE_USER não configurado."
        )

        return

    if not password:

        print(
            "❌ MOODLE_PASSWORD não configurado."
        )

        return

    client = MoodleClient(
        username=username,
        password=password
    )

    try:

        print()
        print("Consultando Moodle...")

        client.login()

        print()
        print(
            "Moodle autenticado com sucesso."
        )

        print()
        print("Consultando disciplinas...")

        courses = client.get_courses()

        print(
            f"📚 Disciplinas encontradas: "
            f"{len(courses)}"
        )

        for course in courses:

            fullname = course.get(
                "fullname",
                "Sem nome"
            )

            shortname = course.get(
                "shortname",
                ""
            )

            course_id = course.get(
                "id",
                ""
            )

            print(
                f"   • {fullname}"
                f" | {shortname}"
                f" | ID: {course_id}"
            )

        print()
        print(
            "Consultando eventos do calendário..."
        )

        eventos = client.get_normalized_events()

        print(
            f"📅 Eventos encontrados: "
            f"{len(eventos)}"
        )

        historico = carregar_historico()

        print()
        print(
            f"🗂️ Eventos já registrados: "
            f"{len(historico)}"
        )

        chaves_historico = {
            criar_chave_evento(evento)
            for evento in historico
        }

        novos_eventos = []

        for evento in eventos:

            chave = criar_chave_evento(evento)

            if chave not in chaves_historico:

                novos_eventos.append(
                    evento
                )

        print(
            f"🆕 Novos eventos encontrados: "
            f"{len(novos_eventos)}"
        )

        if novos_eventos:

            print()
            print("=" * 50)
            print("          NOVOS EVENTOS")
            print("=" * 50)

            for evento in novos_eventos:

                print()
                print(
                    f"🆕 {evento['nome']}"
                )

                print(
                    f"   📚 Disciplina: "
                    f"{evento['disciplina'] or 'Não identificada'}"
                )

                print(
                    f"   🆔 ID: "
                    f"{evento['id']}"
                )

                print(
                    f"   📅 Timestamp: "
                    f"{evento['timestamp']}"
                )

                print(
                    f"   🔗 URL: "
                    f"{evento['url'] or 'Não disponível'}"
                )

        else:

            print()
            print(
                "ℹ️ Nenhum evento novo."
            )

        # Recria o histórico usando a chave do evento.
        # Isso evita duplicações.
        historico_por_chave = {}

        for evento in historico:

            chave = criar_chave_evento(
                evento
            )

            historico_por_chave[chave] = evento

        # Adiciona/atualiza os eventos encontrados
        # nesta execução.
        for evento in eventos:

            chave = criar_chave_evento(
                evento
            )

            historico_por_chave[chave] = evento

        novo_historico = list(
            historico_por_chave.values()
        )

        salvar_historico(
            novo_historico
        )

        # Confirma que o arquivo realmente existe
        # depois da gravação.
        if HISTORICO_FILE.exists():

            tamanho = HISTORICO_FILE.stat().st_size

            print(
                f"✅ eventos.json confirmado."
            )

            print(
                f"📦 Tamanho do arquivo: "
                f"{tamanho} bytes"
            )

        else:

            raise RuntimeError(
                "eventos.json não foi criado após "
                "a tentativa de salvamento."
            )

    except Exception as erro:

        print()
        print("=" * 50)
        print("❌ ERRO")
        print("=" * 50)

        print(
            f"{type(erro).__name__}: {erro}"
        )

        raise

    print()
    print("=" * 50)
    print("Fim da verificação.")
    print("=" * 50)


if __name__ == "__main__":
    main()
