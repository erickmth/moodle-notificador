import re
import json
from urllib.parse import urlparse, parse_qs

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

    def login(self):
        print("Acessando página de login do Sistema Fiep...")

        login_page_url = self.BASE_URL + self.LOGIN_PAGE

        response = self.session.get(
            login_page_url,
            timeout=30
        )

        print(
            f"Página de login carregada: "
            f"HTTP {response.status_code}"
        )

        response.raise_for_status()

        print("Enviando autenticação para o Sistema Fiep...")

        payload = {
            "_key": (
                "badiumview.factory.theme.fiep."
                "app.login.service.exec"
            ),
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

        print(
            f"Resposta do login: "
            f"HTTP {response.status_code}"
        )

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
            f"Página autenticada: "
            f"HTTP {authenticated.status_code}"
        )

        authenticated.raise_for_status()

        print(
            f"URL final: "
            f"{authenticated.url}"
        )

        if "/my/" not in authenticated.url:

            raise RuntimeError(
                "O redirecionamento não chegou à "
                "página autenticada do Moodle."
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

            return input_element.get(
                "value"
            )

        return None

    def _ajax_request(
        self,
        methodname,
        args
    ):

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

    def get_courses(self):

        methodname = (
            "core_course_get_enrolled_courses_by_"
            "timeline_classification"
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

    def _extract_cmid_from_url(self, url):

        if not url:
            return None

        try:

            parsed = urlparse(url)

            params = parse_qs(
                parsed.query
            )

            values = params.get("id")

            if not values:
                return None

            return int(
                values[0]
            )

        except Exception:

            return None

    def get_course_module(self, cmid):

        if not cmid:
            return None

        methodname = "core_course_get_module"

        args = {
            "id": int(cmid),
            "sectionreturn": 0,
        }

        print()
        print(
            f"      🔎 Consultando módulo "
            f"CMID {cmid}..."
        )

        try:

            data = self._ajax_request(
                methodname,
                args
            )

        except Exception as erro:

            print(
                f"      ❌ Erro ao consultar módulo: "
                f"{erro}"
            )

            return None

        print(
            "      📦 Resposta do módulo:"
        )

        try:

            print(
                json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2
                )
            )

        except Exception:

            print(
                repr(data)
            )

        if not data:
            return None

        if isinstance(
            data,
            dict
        ):

            if isinstance(
                data.get("cm"),
                dict
            ):

                return data.get("cm")

            if isinstance(
                data.get("coursemodule"),
                dict
            ):

                return data.get(
                    "coursemodule"
                )

            return data

        return None

    def get_submission_status(
        self,
        assignid
    ):

        if not assignid:
            return None

        methodname = (
            "mod_assign_get_submission_status"
        )

        args = {
            "assignid": int(assignid),
            "userid": 0,
        }

        print()
        print("=" * 70)
        print(
            "RESPOSTA BRUTA DO STATUS DA ENTREGA"
        )
        print(
            f"Assignment ID: {assignid}"
        )
        print(
            f"Arguments: {args}"
        )
        print("=" * 70)

        try:

            data = self._ajax_request(
                methodname,
                args
            )

        except Exception as erro:

            print(
                f"❌ ERRO AO CONSULTAR STATUS: "
                f"{erro}"
            )

            print("=" * 70)

            return None

        try:

            print(
                json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2
                )
            )

        except Exception:

            print(
                repr(data)
            )

        print("=" * 70)
        print(
            "FIM DA RESPOSTA"
        )
        print("=" * 70)

        return data

    def _get_submission_state(
        self,
        data
    ):

        if not isinstance(
            data,
            dict
        ):

            return None

        possible_objects = []

        lastattempt = data.get(
            "lastattempt"
        )

        if isinstance(
            lastattempt,
            dict
        ):

            possible_objects.append(
                lastattempt
            )

            submission = lastattempt.get(
                "submission"
            )

            if isinstance(
                submission,
                dict
            ):

                possible_objects.append(
                    submission
                )

        status = data.get(
            "status"
        )

        if isinstance(
            status,
            dict
        ):

            possible_objects.append(
                status
            )

            submission = status.get(
                "submission"
            )

            if isinstance(
                submission,
                dict
            ):

                possible_objects.append(
                    submission
                )

        submission = data.get(
            "submission"
        )

        if isinstance(
            submission,
            dict
        ):

            possible_objects.append(
                submission
            )

        for obj in possible_objects:

            for key in (
                "status",
                "workflowstate",
                "state",
            ):

                value = obj.get(
                    key
                )

                if isinstance(
                    value,
                    str
                ):

                    value = value.lower().strip()

                    if value:

                        return value

        return None

    def is_assignment_submitted(
        self,
        event
    ):

        url = event.get(
            "url",
            ""
        )

        cmid = self._extract_cmid_from_url(
            url
        )

        print()
        print(
            f"   🔗 URL da atividade: {url}"
        )

        print(
            f"   🆔 CMID encontrado: {cmid}"
        )

        if not cmid:

            print(
                "   ⚠️ Não foi possível identificar "
                "o CMID."
            )

            return False

        module = self.get_course_module(
            cmid
        )

        if not module:

            print(
                "   ⚠️ Não foi possível obter "
                "os dados do módulo."
            )

            return False

        modname = (
            module.get("modname")
            or module.get("modulename")
            or ""
        )

        modname = str(
            modname
        ).lower()

        assignid = (
            module.get("instance")
            or module.get("instanceid")
        )

        print(
            f"   🧩 Tipo do módulo: "
            f"{modname or 'não identificado'}"
        )

        print(
            f"   🆔 Instance: "
            f"{assignid or 'não identificado'}"
        )

        if modname != "assign":

            print(
                "   ℹ️ Não é uma atividade "
                "mod_assign."
            )

            return False

        if not assignid:

            print(
                "   ⚠️ Não foi possível encontrar "
                "o instance ID da atividade."
            )

            return False

        data = self.get_submission_status(
            assignid
        )

        if not data:

            print(
                "   ⚠️ Moodle não retornou "
                "dados de submissão."
            )

            return False

        state = self._get_submission_state(
            data
        )

        print()
        print(
            f"   📌 Estado identificado: "
            f"{state or 'NÃO IDENTIFICADO'}"
        )

        return state in (
            "submitted",
            "graded",
            "returned",
        )

    def get_normalized_events(self):

        events = self.get_calendar_events()

        normalized = []

        for event in events:

            event_id = event.get(
                "id"
            )

            name = (
                event.get("name")
                or event.get("formattedtime")
                or "Evento sem nome"
            )

            course = event.get(
                "course"
            )

            if isinstance(
                course,
                dict
            ):

                course_id = course.get(
                    "id"
                )

                course_name = (
                    course.get("fullname")
                    or course.get("fullnamedisplay")
                    or course.get("shortname")
                    or ""
                )

            else:

                course_id = None

                course_name = (
                    event.get("coursename")
                    or course
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
                "id": (
                    str(event_id)
                    if event_id
                    else ""
                ),
                "nome": name,
                "disciplina": course_name,
                "curso_id": course_id,
                "timestamp": timestart,
                "timesort": timesort,
                "tipo": event_type,
                "url": url,
            }

            normalized.append(
                normalized_event
            )

        return normalized

    def test_submission(
        self
    ):

        print()
        print("=" * 70)
        print(
            "       DIAGNÓSTICO DE ENTREGA MOODLE"
        )
        print("=" * 70)

        self.login()

        print()
        print(
            "Consultando eventos do calendário..."
        )

        events = self.get_normalized_events()

        print(
            f"📅 Total de eventos: "
            f"{len(events)}"
        )

        due_events = []

        for event in events:

            event_type = str(
                event.get("tipo")
                or ""
            ).lower()

            if event_type == "due":

                due_events.append(
                    event
                )

        print(
            f"📋 Eventos due encontrados: "
            f"{len(due_events)}"
        )

        if not due_events:

            print(
                "❌ Nenhum evento due encontrado."
            )

            return

        print()

        for index, event in enumerate(
            due_events,
            start=1
        ):

            print(
                "=" * 70
            )

            print(
                f"ATIVIDADE {index}"
            )

            print(
                "=" * 70
            )

            print(
                f"Nome: {event.get('nome')}"
            )

            print(
                f"Disciplina: "
                f"{event.get('disciplina')}"
            )

            print(
                f"ID do evento: "
                f"{event.get('id')}"
            )

            print(
                f"URL: "
                f"{event.get('url')}"
            )

            print()

            submitted = self.is_assignment_submitted(
                event
            )

            print()

            if submitted:

                print(
                    "🟢 RESULTADO: "
                    "ATIVIDADE IDENTIFICADA COMO ENVIADA"
                )

            else:

                print(
                    "🟡 RESULTADO: "
                    "ATIVIDADE NÃO FOI IDENTIFICADA COMO ENVIADA"
                )

            print()

        print(
            "=" * 70
        )

        print(
            "Fim do diagnóstico."
        )

        print(
            "=" * 70
        )


if __name__ == "__main__":

    import os

    username = os.getenv(
        "MOODLE_USER"
    )

    password = os.getenv(
        "MOODLE_PASSWORD"
    )

    if not username:

        raise RuntimeError(
            "MOODLE_USER não configurado."
        )

    if not password:

        raise RuntimeError(
            "MOODLE_PASSWORD não configurado."
        )

    client = MoodleClient(
        username=username,
        password=password
    )

    client.test_submission()
