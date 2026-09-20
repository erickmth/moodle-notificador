import os
import re
import json
import requests
from bs4 import BeautifulSoup


class MoodleClient:

    BASE_URL = "https://ava.fiep.digital"

    LOGIN_PAGE = (
        "/theme/badiumview/controller.php"
        "?_key=badiumview.factory.theme.fiep.app.login.index"
        "&_operation=apppage"
    )

    LOGIN_SERVICE = "/theme/badiumview/controller.php"

    def __init__(self, username=None, password=None):

        self.username = username or os.getenv("MOODLE_USER")
        self.password = password or os.getenv("MOODLE_PASSWORD")

        if not self.username:
            raise ValueError("MOODLE_USER não foi informado.")

        if not self.password:
            raise ValueError("MOODLE_PASSWORD não foi informado.")

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        })

        self.sesskey = None

    # ==========================================================
    # LOGIN
    # ==========================================================

    def login(self):

        print("\nAcessando página de login do Sistema Fiep...")

        login_page_url = self.BASE_URL + self.LOGIN_PAGE

        response = self.session.get(
            login_page_url,
            timeout=30
        )

        print(f"Página de login carregada: HTTP {response.status_code}")

        if response.status_code != 200:
            print("❌ Não foi possível carregar a página de login.")
            return False

        # ------------------------------------------------------
        # O AVA usa a camada BadiumView do Sistema Fiep.
        #
        # O JavaScript real do site envia:
        #
        # {
        #   "_key": "badiumview.factory.theme.fiep.app.login.service.exec",
        #   "_operation": "ws",
        #   "username": "...",
        #   "password": "..."
        # }
        # ------------------------------------------------------

        payload = {
            "_key": "badiumview.factory.theme.fiep.app.login.service.exec",
            "_operation": "ws",
            "username": self.username,
            "password": self.password,
        }

        print("Enviando autenticação para o Sistema Fiep...")

        response = self.session.post(
            self.BASE_URL + self.LOGIN_SERVICE,
            json=payload,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": self.BASE_URL,
                "Referer": login_page_url,
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=30,
        )

        print(f"Resposta do login: HTTP {response.status_code}")

        if response.status_code != 200:
            print("❌ O servidor recusou a requisição de login.")
            print(f"URL: {response.url}")
            return False

        try:
            data = response.json()
        except ValueError:
            print("❌ A resposta do login não é um JSON válido.")
            print(response.text[:500])
            return False

        status = data.get("status")

        if status != "accept":

            print("❌ Login não aceito pelo Sistema Fiep.")

            message = data.get("message")

            if isinstance(message, dict):
                message = message.get("error") or message

            if message:
                print(f"Mensagem do servidor: {message}")

            return False

        print("✅ Login aceito pelo Sistema Fiep.")

        message = data.get("message", {})

        if isinstance(message, dict):
            urlgoback = message.get("urlgoback")
        else:
            urlgoback = None

        if not urlgoback:
            urlgoback = self.BASE_URL + "/my/"

        print("Redirecionando para o Moodle...")

        authenticated_response = self.session.get(
            urlgoback,
            timeout=30,
            allow_redirects=True,
        )

        print(
            f"Página autenticada: HTTP "
            f"{authenticated_response.status_code}"
        )

        print(f"URL final: {authenticated_response.url}")

        if authenticated_response.status_code != 200:
            print("❌ Não foi possível acessar o Moodle autenticado.")
            return False

        # ------------------------------------------------------
        # Agora precisamos encontrar o sesskey da sessão Moodle.
        # ------------------------------------------------------

        html = authenticated_response.text

        self.sesskey = self._extract_sesskey(html)

        if not self.sesskey:

            print("❌ Login ocorreu, mas o sesskey não foi encontrado.")
            print("Isso significa que a sessão Moodle ainda não está disponível.")

            return False

        print("✅ Sessão Moodle autenticada.")
        print("✅ Sesskey encontrado.")

        return True

    # ==========================================================
    # EXTRAÇÃO DO SESSKEY
    # ==========================================================

    def _extract_sesskey(self, html):

        if not html:
            return None

        # ------------------------------------------------------
        # Formatos comuns do Moodle
        # ------------------------------------------------------

        patterns = [

            r'M\.cfg\.sesskey\s*=\s*["\']([^"\']+)["\']',

            r'"sesskey"\s*:\s*"([^"]+)"',

            r"'sesskey'\s*:\s*'([^']+)'",

            r'name=["\']sesskey["\']\s+value=["\']([^"\']+)["\']',

            r'name=["\']sesskey["\'][^>]+value=["\']([^"\']+)["\']',

            r'[?&]sesskey=([A-Za-z0-9]+)',

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                re.IGNORECASE
            )

            if match:

                sesskey = match.group(1)

                if sesskey:
                    return sesskey

        # ------------------------------------------------------
        # Tentativa adicional utilizando BeautifulSoup
        # ------------------------------------------------------

        try:

            soup = BeautifulSoup(
                html,
                "html.parser"
            )

            # Inputs
            for element in soup.find_all(
                "input",
                attrs={"name": "sesskey"}
            ):

                value = element.get("value")

                if value:
                    return value

        except Exception:
            pass

        return None

    # ==========================================================
    # REQUISIÇÃO AJAX DO MOODLE
    # ==========================================================

    def _ajax_request(self, methodname, args):

        if not self.sesskey:

            raise RuntimeError(
                "Sesskey não disponível. "
                "Faça login antes de chamar o Moodle."
            )

        url = (
            f"{self.BASE_URL}/lib/ajax/service.php"
            f"?sesskey={self.sesskey}"
            f"&info={methodname}"
        )

        payload = [
            {
                "index": 0,
                "methodname": methodname,
                "args": args,
            }
        ]

        response = self.session.post(
            url,
            json=payload,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/json",
                "Origin": self.BASE_URL,
                "Referer": self.BASE_URL + "/my/",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=30,
        )

        if response.status_code != 200:

            raise RuntimeError(
                f"Moodle AJAX retornou HTTP {response.status_code}"
            )

        try:
            data = response.json()

        except ValueError:

            raise RuntimeError(
                "Resposta do Moodle AJAX não é JSON válido."
            )

        # ------------------------------------------------------
        # Moodle normalmente retorna uma lista:
        #
        # [
        #   {
        #       "error": false,
        #       "data": ...
        #   }
        # ]
        # ------------------------------------------------------

        if not isinstance(data, list) or not data:

            raise RuntimeError(
                "Resposta inesperada do Moodle AJAX."
            )

        result = data[0]

        if result.get("error"):

            message = result.get(
                "exception",
                "Erro desconhecido"
            )

            raise RuntimeError(
                f"Moodle AJAX: {message}"
            )

        return result.get("data")

    # ==========================================================
    # DISCIPLINAS
    # ==========================================================

    def get_courses(self):

        print("\nConsultando disciplinas...")

        args = {
            "offset": 0,
            "limit": 0,
            "classification": "allincludinghidden",
            "sort": "fullname",
            "customfieldname": "",
            "customfieldvalue": "",
        }

        data = self._ajax_request(
            "core_course_get_enrolled_courses_by_timeline_classification",
            args
        )

        if not data:

            print("⚠️ Nenhuma disciplina encontrada.")
            return []

        courses = []

        # ------------------------------------------------------
        # Moodle pode devolver estrutura com courses
        # ------------------------------------------------------

        if isinstance(data, dict):

            if "courses" in data:
                courses = data["courses"]

            elif "items" in data:
                courses = data["items"]

        elif isinstance(data, list):

            courses = data

        print(
            f"📚 Disciplinas encontradas: "
            f"{len(courses)}"
        )

        return courses

    # ==========================================================
    # EVENTOS DO CALENDÁRIO
    # ==========================================================

    def get_calendar_events(self):

        print("\nConsultando eventos do calendário...")

        args = {
            "timesortfrom": 0,
            "limitnum": 50,
            "limittononsuspendedevents": True,
        }

        data = self._ajax_request(
            "core_calendar_get_action_events_by_timesort",
            args
        )

        if not data:

            print("📅 Eventos encontrados: 0")
            return []

        events = []

        if isinstance(data, dict):

            if "events" in data:
                events = data["events"]

            elif "items" in data:
                events = data["items"]

        elif isinstance(data, list):

            events = data

        print(
            f"📅 Eventos encontrados: "
            f"{len(events)}"
        )

        return events

    # ==========================================================
    # TESTE COMPLETO
    # ==========================================================

    def test(self):

        print("=" * 50)
        print("          NOTIFICADOR MOODLE")
        print("=" * 50)

        print("\nConsultando Moodle...")

        if not self.login():

            print("\n❌ Não foi possível acessar o Moodle.")
            return False

        print("\nMoodle autenticado com sucesso.")

        # ------------------------------------------------------
        # Disciplinas
        # ------------------------------------------------------

        try:

            courses = self.get_courses()

            for course in courses:

                if not isinstance(course, dict):
                    continue

                fullname = course.get(
                    "fullname",
                    "Disciplina sem nome"
                )

                course_id = course.get(
                    "id",
                    "?"
                )

                print(
                    f"   • {fullname} "
                    f"(ID: {course_id})"
                )

        except Exception as e:

            print(
                f"❌ Erro ao consultar disciplinas: {e}"
            )

        # ------------------------------------------------------
        # Eventos
        # ------------------------------------------------------

        try:

            events = self.get_calendar_events()

            for event in events:

                if not isinstance(event, dict):
                    continue

                name = (
                    event.get("name")
                    or event.get("title")
                    or "Evento sem nome"
                )

                print(
                    f"   • {name}"
                )

        except Exception as e:

            print(
                f"❌ Erro ao consultar calendário: {e}"
            )

        print("\n" + "=" * 50)
        print("Fim da verificação.")
        print("=" * 50)

        return True
