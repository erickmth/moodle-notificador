import re
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

    def __init__(self, username, password):
        self.username = username
        self.password = password

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })

        self.sesskey = None

    # ==========================================================
    # LOGIN
    # ==========================================================

    def login(self):

        print("Acessando página de login do Sistema Fiep...")

        login_page_url = self.BASE_URL + self.LOGIN_PAGE

        response = self.session.get(
            login_page_url,
            timeout=30
        )

        print(f"Página de login carregada: HTTP {response.status_code}")

        response.raise_for_status()

        print("Enviando autenticação para o Sistema Fiep...")

        payload = {
            "_key": "badiumview.factory.theme.fiep.app.login.service.exec",
            "_operation": "ws",
            "username": self.username,
            "password": self.password,
        }

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": self.BASE_URL,
            "Referer": login_page_url,
            "X-Requested-With": "XMLHttpRequest",
        }

        response = self.session.post(
            self.BASE_URL + self.LOGIN_SERVICE,
            json=payload,
            headers=headers,
            timeout=30
        )

        print(f"Resposta do login: HTTP {response.status_code}")

        response.raise_for_status()

        try:
            data = response.json()
        except Exception:
            raise RuntimeError(
                "A resposta do login não retornou JSON válido."
            )

        if data.get("status") != "accept":
            raise RuntimeError(
                f"Login recusado pelo Sistema Fiep: {data}"
            )

        print("✅ Login aceito pelo Sistema Fiep.")

        message = data.get("message") or {}

        urlgoback = message.get(
            "urlgoback",
            self.BASE_URL + "/my/"
        )

        print("Redirecionando para o Moodle...")

        authenticated = self.session.get(
            urlgoback,
            timeout=30
        )

        print(
            f"Página autenticada: HTTP "
            f"{authenticated.status_code}"
        )

        authenticated.raise_for_status()

        print(f"URL final: {authenticated.url}")

        if "/my/" not in authenticated.url:
            raise RuntimeError(
                "O redirecionamento não chegou à página autenticada do Moodle."
            )

        print("✅ Sessão Moodle autenticada.")

        self.sesskey = self._extract_sesskey(
            authenticated.text
        )

        if not self.sesskey:
            raise RuntimeError(
                "Não foi possível encontrar o sesskey."
            )

        print("✅ Sesskey encontrado.")

        return True

    # ==========================================================
    # EXTRAIR SESSKEY
    # ==========================================================

    def _extract_sesskey(self, html):

        patterns = [
            r'M\.cfg\.sesskey\s*=\s*[\'"]([^\'"]+)',
            r'"sesskey"\s*:\s*"([^"]+)"',
            r"'sesskey'\s*:\s*'([^']+)'",
            r'name=["\']sesskey["\']\s+value=["\']([^"\']+)',
            r'sesskey=([^&"\']+)',
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                re.IGNORECASE
            )

            if match:
                return match.group(1)

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        input_element = soup.find(
            "input",
            {
                "name": "sesskey"
            }
        )

        if input_element:
            return input_element.get("value")

        return None

    # ==========================================================
    # AJAX MOODLE
    # ==========================================================

    def _ajax_request(self, methodname, args):

        if not self.sesskey:
            raise RuntimeError(
                "Sesskey não disponível."
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
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list) or not data:
            raise RuntimeError(
                f"Resposta inesperada do Moodle: {data}"
            )

        result = data[0]

        if result.get("error"):
            raise RuntimeError(
                f"Erro no Moodle: {result}"
            )

        return result.get("data")

    # ==========================================================
    # DISCIPLINAS
    # ==========================================================

    def get_courses(self):

        methodname = (
            "core_course_get_enrolled_courses_by_timeline_classification"
        )

        args = {
            "offset": 0,
            "limit": 0,
            "classification": "allincludinghidden",
            "sort": "fullname",
            "customfieldname": "",
            "customfieldvalue": "",
        }

        data = self._ajax_request(
            methodname,
            args
        )

        if not data:
            return []

        return data.get(
            "courses",
            []
        )

    # ==========================================================
    # EVENTOS
    # ==========================================================

    def get_calendar_events(self):

        methodname = (
            "core_calendar_get_action_events_by_timesort"
        )

        args = {
            "timesortfrom": 0,
            "limitnum": 50,
            "limittononsuspendedevents": True,
        }

        data = self._ajax_request(
            methodname,
            args
        )

        if not data:
            return []

        return data.get(
            "events",
            []
        )

    # ==========================================================
    # PREPARAR EVENTOS
    # ==========================================================

    def get_normalized_events(self):

        events = self.get_calendar_events()

        normalized = []

        for event in events:

            event_id = event.get("id")

            name = (
                event.get("name")
                or event.get("formattedtime")
                or "Evento sem nome"
            )

            course_name = (
                event.get("course")
                or event.get("coursename")
                or ""
            )

            timestart = event.get(
                "timestart"
            )

            timesort = event.get(
                "timesort"
            )

            url = (
                event.get("url")
                or event.get("urltoevent")
                or ""
            )

            event_type = (
                event.get("eventtype")
                or event.get("modulename")
                or event.get("component")
                or ""
            )

            normalized_event = {
                "id": str(event_id) if event_id else "",
                "nome": name,
                "disciplina": course_name,
                "timestamp": timestart,
                "timesort": timesort,
                "tipo": event_type,
                "url": url,
            }

            normalized.append(
                normalized_event
            )

        return normalized

    # ==========================================================
    # TESTE COMPLETO
    # ==========================================================

    def test(self):

        print()
        print("=" * 50)
        print("          NOTIFICADOR MOODLE")
        print("=" * 50)

        print()
        print("Consultando Moodle...")

        self.login()

        print()
        print("Moodle autenticado com sucesso.")

        # ------------------------------------------------------
        # CURSOS
        # ------------------------------------------------------

        print()
        print("Consultando disciplinas...")

        courses = self.get_courses()

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

        # ------------------------------------------------------
        # EVENTOS
        # ------------------------------------------------------

        print()
        print("Consultando eventos do calendário...")

        events = self.get_normalized_events()

        print(
            f"📅 Eventos encontrados: "
            f"{len(events)}"
        )

        for event in events:

            print()
            print(
                f"   📝 {event['nome']}"
            )

            print(
                f"      ID: {event['id']}"
            )

            print(
                f"      Disciplina: "
                f"{event['disciplina'] or 'Não identificada'}"
            )

            print(
                f"      Tipo: "
                f"{event['tipo'] or 'Não identificado'}"
            )

            print(
                f"      Timestamp: "
                f"{event['timestamp']}"
            )

            if event["url"]:
                print(
                    f"      URL: "
                    f"{event['url']}"
                )

        print()
        print("=" * 50)
        print("Fim da verificação.")
        print("=" * 50)
