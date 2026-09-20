import json
import re
import requests
from bs4 import BeautifulSoup


class MoodleClient:

    BASE_URL = "https://ava.fiep.digital"

    def __init__(self, username, password):
        self.username = username
        self.password = password

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7,es;q=0.6",
        })

        self.sesskey = None

    # ==========================================================
    # LOGIN
    # ==========================================================

    def login(self):

        print("Acessando página de login...")

        login_url = f"{self.BASE_URL}/login/index.php"

        response = self.session.get(
            login_url,
            timeout=30
        )

        response.raise_for_status()

        print(f"Página de login carregada: HTTP {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")

        login_token = ""

        token_input = soup.find(
            "input",
            {
                "name": "logintoken"
            }
        )

        if token_input:
            login_token = token_input.get("value", "")

        print(
            "Logintoken encontrado."
            if login_token
            else "Logintoken não encontrado."
        )

        # ======================================================
        # ENVIA LOGIN
        # ======================================================

        payload = {
            "username": self.username,
            "password": self.password,
        }

        if login_token:
            payload["logintoken"] = login_token

        print("Enviando login...")

        response = self.session.post(
            login_url,
            data=payload,
            allow_redirects=True,
            timeout=30
        )

        response.raise_for_status()

        print(
            f"Resposta após login: HTTP {response.status_code}"
        )

        # ======================================================
        # VERIFICA SE CONTINUOU NA PÁGINA DE LOGIN
        # ======================================================

        final_url = response.url.lower()

        if "/login/index.php" in final_url:

            soup = BeautifulSoup(response.text, "html.parser")

            login_error = soup.select_one(
                ".loginerrors"
            )

            if login_error:
                erro = login_error.get_text(
                    " ",
                    strip=True
                )

                print(
                    f"❌ Moodle recusou o login: {erro}"
                )

            else:

                print(
                    "❌ O Moodle continuou na página de login."
                )

            return False

        # ======================================================
        # ACESSA UMA PÁGINA AUTENTICADA
        # ======================================================

        print("Login aparentemente realizado.")

        print("Acessando página autenticada...")

        authenticated_url = (
            f"{self.BASE_URL}/my/"
        )

        authenticated_response = self.session.get(
            authenticated_url,
            timeout=30
        )

        authenticated_response.raise_for_status()

        print(
            "Página autenticada:"
            f" HTTP {authenticated_response.status_code}"
        )

        html = authenticated_response.text

        # ======================================================
        # VERIFICA SE VOLTOU PARA LOGIN
        # ======================================================

        if "/login/index.php" in authenticated_response.url.lower():

            print(
                "❌ A sessão não ficou autenticada."
            )

            return False

        # ======================================================
        # EXTRAI SESSKEY
        # ======================================================

        self.sesskey = self._extract_sesskey(
            html
        )

        if not self.sesskey:

            print(
                "❌ Não foi possível encontrar o sesskey."
            )

            # Diagnóstico seguro.
            # NÃO mostra cookies, senha ou tokens.

            print(
                f"URL final: {authenticated_response.url}"
            )

            if "M.cfg" in html:
                print(
                    "M.cfg foi encontrado no HTML, "
                    "mas o sesskey não foi extraído."
                )
            else:
                print(
                    "M.cfg não apareceu no HTML."
                )

            return False

        print(
            "Sesskey encontrado com sucesso."
        )

        return True

    # ==========================================================
    # EXTRAI SESSKEY
    # ==========================================================

    def _extract_sesskey(self, html):

        # Moodle normalmente entrega:
        #
        # M.cfg = {"wwwroot":"...",
        #          "sesskey":"XXXXXXXXXX", ...}

        patterns = [

            # Formato normal
            r'M\.cfg\s*=\s*\{.*?"sesskey"\s*:\s*"([^"]+)"',

            # Caso exista whitespace diferente
            r'M\.cfg\s*=\s*\{.*?["\']sesskey["\']\s*:\s*["\']([^"\']+)["\']',

            # Busca independente do M.cfg
            r'["\']sesskey["\']\s*:\s*["\']([^"\']+)["\']',

            # Possível atributo HTML
            r'data-sesskey\s*=\s*["\']([^"\']+)["\']',

            # Input
            r'name=["\']sesskey["\'][^>]*value=["\']([^"\']+)["\']',

            # Ordem invertida
            r'value=["\']([^"\']+)["\'][^>]*name=["\']sesskey["\']',
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html,
                flags=re.IGNORECASE | re.DOTALL
            )

            if match:

                sesskey = match.group(1).strip()

                if sesskey:
                    return sesskey

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
            f"{self.BASE_URL}"
            f"/lib/ajax/service.php"
        )

        params = {
            "sesskey": self.sesskey,
            "info": methodname,
        }

        payload = [
            {
                "index": 0,
                "methodname": methodname,
                "args": args,
            }
        ]

        headers = {
            "Accept": (
                "application/json, "
                "text/javascript, */*; q=0.01"
            ),
            "Content-Type": "application/json",
            "Origin": self.BASE_URL,
            "Referer": (
                f"{self.BASE_URL}/my/courses.php"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }

        response = self.session.post(
            url,
            params=params,
            json=payload,
            headers=headers,
            timeout=30
        )

        print(
            f"AJAX {methodname}: "
            f"HTTP {response.status_code}"
        )

        response.raise_for_status()

        try:

            result = response.json()

        except ValueError:

            print(
                "❌ Moodle retornou algo que "
                "não é JSON."
            )

            print(
                response.text[:1000]
            )

            raise

        return result

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

        result = self._ajax_request(
            methodname,
            args
        )

        if not result:
            return []

        first = result[0]

        if first.get("error"):

            print(
                "❌ Erro no Moodle ao buscar disciplinas:"
            )

            print(
                json.dumps(
                    first,
                    ensure_ascii=False,
                    indent=2
                )[:3000]
            )

            return []

        data = first.get("data", {})

        if isinstance(data, str):

            try:
                data = json.loads(data)

            except json.JSONDecodeError:

                print(
                    "❌ Resposta de cursos "
                    "não pôde ser interpretada."
                )

                return []

        if not isinstance(data, dict):
            return []

        courses = data.get(
            "courses",
            []
        )

        return courses

    # ==========================================================
    # EVENTOS DO CALENDÁRIO
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

        result = self._ajax_request(
            methodname,
            args
        )

        if not result:
            return []

        first = result[0]

        if first.get("error"):

            print(
                "❌ Erro no Moodle ao buscar eventos:"
            )

            print(
                json.dumps(
                    first,
                    ensure_ascii=False,
                    indent=2
                )[:3000]
            )

            return []

        data = first.get(
            "data",
            {}
        )

        if isinstance(data, str):

            try:
                data = json.loads(data)

            except json.JSONDecodeError:

                print(
                    "❌ Resposta de calendário "
                    "não pôde ser interpretada."
                )

                return []

        if not isinstance(data, dict):
            return []

        events = data.get(
            "events",
            []
        )

        return events
