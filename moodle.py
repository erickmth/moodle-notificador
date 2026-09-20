import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class MoodleClient:
    BASE_URL = "https://ava.fiep.digital"

    def __init__(self):
        self.username = os.getenv("MOODLE_USER")
        self.password = os.getenv("MOODLE_PASSWORD")

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Accept-Language": (
                "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
            )
        })

        self.sesskey = None

    def login(self):
        """
        Realiza o login no Moodle e extrai o sesskey
        da página autenticada.
        """

        if not self.username or not self.password:
            print(
                "❌ MOODLE_USER ou MOODLE_PASSWORD "
                "não configurados."
            )
            return False

        try:
            login_url = urljoin(
                self.BASE_URL,
                "/login/index.php"
            )

            print("Acessando página de login...")

            response = self.session.get(
                login_url,
                timeout=30
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            login_form = soup.find("form")

            if not login_form:
                print(
                    "❌ Formulário de login não encontrado."
                )
                return False

            login_action = login_form.get("action")

            if not login_action:
                login_action = login_url
            else:
                login_action = urljoin(
                    self.BASE_URL,
                    login_action
                )

            data = {}

            for input_element in login_form.find_all(
                "input"
            ):
                name = input_element.get("name")

                if not name:
                    continue

                data[name] = input_element.get(
                    "value",
                    ""
                )

            data["username"] = self.username
            data["password"] = self.password

            print("Enviando login...")

            login_response = self.session.post(
                login_action,
                data=data,
                timeout=30,
                allow_redirects=True
            )

            login_response.raise_for_status()

            # Se o Moodle ainda redirecionou para o login,
            # a autenticação não foi concluída.
            if "/login/" in login_response.url:
                print(
                    "❌ Login não realizado."
                )
                return False

            # A resposta do login normalmente já é uma
            # página autenticada e contém M.cfg.sesskey.
            self.sesskey = self._extract_sesskey(
                login_response.text
            )

            # Caso a resposta do login não contenha o sesskey,
            # acessamos /my/ e procuramos novamente.
            if not self.sesskey:

                my_url = urljoin(
                    self.BASE_URL,
                    "/my/"
                )

                print(
                    "Sesskey não encontrado na resposta "
                    "do login. Acessando página autenticada..."
                )

                my_response = self.session.get(
                    my_url,
                    timeout=30
                )

                my_response.raise_for_status()

                if "/login/" in my_response.url:
                    print(
                        "❌ Sessão não autenticada."
                    )
                    return False

                self.sesskey = self._extract_sesskey(
                    my_response.text
                )

            if not self.sesskey:
                print(
                    "❌ Não foi possível encontrar o sesskey."
                )
                return False

            print(
                "✅ Login realizado com sucesso."
            )

            print(
                "✅ Sessão Moodle obtida."
            )

            return True

        except requests.RequestException as error:
            print(
                f"❌ Erro de conexão com o Moodle: {error}"
            )
            return False

        except Exception as error:
            print(
                f"❌ Erro durante o login: {error}"
            )
            return False

    def _extract_sesskey(self, html):
        """
        Extrai M.cfg.sesskey do HTML do Moodle.

        O HAR mostra que o Moodle disponibiliza o valor
        dentro de:

        M.cfg = {..., "sesskey":"...", ...}
        """

        if not html:
            return None

        # Forma principal observada no HAR.
        patterns = [
            r'M\.cfg\s*=\s*\{.*?"sesskey"\s*:\s*"([^"]+)"',
            r'"sesskey"\s*:\s*"([^"]+)"',
            r"'sesskey'\s*:\s*'([^']+)'",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                html,
                re.DOTALL
            )

            if match:
                value = match.group(1)

                if value:
                    return value

        # Algumas páginas podem carregar o valor
        # através de atributos HTML.
        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        for element in soup.find_all(
            attrs={"data-sesskey": True}
        ):
            value = element.get(
                "data-sesskey"
            )

            if value:
                return value

        # Campo hidden como fallback.
        element = soup.find(
            "input",
            attrs={"name": "sesskey"}
        )

        if element:
            value = element.get("value")

            if value:
                return value

        return None

    def _ajax_request(
        self,
        methodname,
        args
    ):
        """
        Executa uma chamada AJAX do Moodle.

        Endpoint identificado no HAR:
        /lib/ajax/service.php
        """

        if not self.sesskey:
            raise RuntimeError(
                "Sesskey não disponível."
            )

        url = urljoin(
            self.BASE_URL,
            "/lib/ajax/service.php"
        )

        payload = [
            {
                "index": 0,
                "methodname": methodname,
                "args": args
            }
        ]

        params = {
            "sesskey": self.sesskey,
            "info": methodname
        }

        headers = {
            "Accept": (
                "application/json, "
                "text/javascript, */*; q=0.01"
            ),
            "Content-Type": "application/json",
            "Origin": self.BASE_URL,
            "Referer": urljoin(
                self.BASE_URL,
                "/my/courses.php"
            ),
            "X-Requested-With": "XMLHttpRequest"
        }

        response = self.session.post(
            url,
            params=params,
            json=payload,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        try:
            return response.json()

        except ValueError:
            print(
                "❌ Moodle retornou uma resposta "
                "que não é JSON."
            )

            print(
                f"HTTP {response.status_code}"
            )

            return None

    def get_courses(self):
        """
        Busca as disciplinas através do método AJAX
        utilizado pelo próprio Moodle.

        Método identificado no HAR:
        core_course_get_enrolled_courses_by_timeline_classification
        """

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
            "customfieldvalue": ""
        }

        print(
            "Consultando API AJAX de disciplinas..."
        )

        try:
            result = self._ajax_request(
                methodname,
                args
            )

            if result is None:
                return []

            if not isinstance(result, list):
                print(
                    "⚠️ Resposta AJAX inesperada."
                )
                return []

            courses = []

            for item in result:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                if item.get("error"):

                    print(
                        "❌ Moodle retornou erro "
                        "na consulta de disciplinas."
                    )

                    exception = item.get(
                        "exception"
                    )

                    message = item.get(
                        "message"
                    )

                    if exception:
                        print(
                            f"   Exceção: {exception}"
                        )

                    if message:
                        print(
                            f"   Mensagem: {message}"
                        )

                    continue

                data = item.get("data")

                if not data:
                    continue

                if isinstance(
                    data,
                    str
                ):
                    try:
                        data = json.loads(data)

                    except json.JSONDecodeError:
                        continue

                if not isinstance(
                    data,
                    dict
                ):
                    continue

                raw_courses = data.get(
                    "courses",
                    []
                )

                if not isinstance(
                    raw_courses,
                    list
                ):
                    continue

                for course in raw_courses:

                    if not isinstance(
                        course,
                        dict
                    ):
                        continue

                    course_id = course.get(
                        "id"
                    )

                    fullname = course.get(
                        "fullname"
                    )

                    if not fullname:
                        continue

                    course_url = None

                    if course_id:
                        course_url = (
                            f"{self.BASE_URL}"
                            f"/course/view.php?id="
                            f"{course_id}"
                        )

                    courses.append({
                        "id": course_id,
                        "fullname": fullname,
                        "url": course_url
                    })

            # Remove duplicados.
            unique_courses = []
            seen = set()

            for course in courses:

                identifier = (
                    course.get("id"),
                    course.get("fullname")
                )

                if identifier in seen:
                    continue

                seen.add(identifier)

                unique_courses.append(
                    course
                )

            return unique_courses

        except requests.RequestException as error:
            print(
                f"❌ Erro na API AJAX: {error}"
            )
            return []

        except Exception as error:
            print(
                f"❌ Erro ao processar disciplinas: {error}"
            )
            return []

    def get_calendar_events(self):
        """
        Busca eventos do calendário através do AJAX
        do Moodle.

        Método identificado no HAR:
        core_calendar_get_action_events_by_timesort
        """

        methodname = (
            "core_calendar_get_action_events_by_timesort"
        )

        args = {
            "timesortfrom": 0,
            "limitnum": 50,
            "limittononsuspendedevents": True
        }

        print(
            "Consultando API AJAX do calendário..."
        )

        try:
            result = self._ajax_request(
                methodname,
                args
            )

            if result is None:
                return []

            if not isinstance(
                result,
                list
            ):
                return []

            events = []

            for item in result:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                if item.get("error"):

                    print(
                        "❌ Moodle retornou erro "
                        "ao consultar calendário."
                    )

                    exception = item.get(
                        "exception"
                    )

                    message = item.get(
                        "message"
                    )

                    if exception:
                        print(
                            f"   Exceção: {exception}"
                        )

                    if message:
                        print(
                            f"   Mensagem: {message}"
                        )

                    continue

                data = item.get(
                    "data"
                )

                if not data:
                    continue

                if isinstance(
                    data,
                    str
                ):
                    try:
                        data = json.loads(data)

                    except json.JSONDecodeError:
                        continue

                if not isinstance(
                    data,
                    dict
                ):
                    continue

                raw_events = data.get(
                    "events",
                    []
                )

                if not isinstance(
                    raw_events,
                    list
                ):
                    continue

                for event in raw_events:

                    if not isinstance(
                        event,
                        dict
                    ):
                        continue

                    events.append(
                        event
                    )

            return events

        except requests.RequestException as error:
            print(
                f"❌ Erro no calendário AJAX: {error}"
            )
            return []

        except Exception as error:
            print(
                f"❌ Erro ao processar calendário: {error}"
            )
            return []
