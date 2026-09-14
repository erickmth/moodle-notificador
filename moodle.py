
import os
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
                "Chrome/139.0.0.0 Safari/537.36"
            )
        })

    def login(self):
        """
        Realiza o login no Moodle usando a página de login.
        """

        if not self.username or not self.password:
            print("❌ MOODLE_USER ou MOODLE_PASSWORD não configurados.")
            return False

        try:
            login_url = urljoin(self.BASE_URL, "/login/index.php")

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
                print("❌ Formulário de login não encontrado.")
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

            for input_element in login_form.find_all("input"):
                name = input_element.get("name")

                if not name:
                    continue

                value = input_element.get("value", "")

                data[name] = value

            # Sobrescreve os campos de autenticação.
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

            final_url = login_response.url

            # Verificação básica de login.
            if "/login/" in final_url:
                soup = BeautifulSoup(
                    login_response.text,
                    "html.parser"
                )

                error = soup.select_one(
                    ".loginerrors, .alert-danger, .loginerror"
                )

                if error:
                    print("❌ Moodle recusou o login.")
                    return False

                # Se ainda está na página de login,
                # provavelmente a autenticação falhou.
                if "login/index.php" in final_url:
                    print("❌ Login não realizado.")
                    return False

            # Testamos uma página autenticada.
            test_response = self.session.get(
                urljoin(self.BASE_URL, "/my/"),
                timeout=30
            )

            test_response.raise_for_status()

            if "login/index.php" in test_response.url:
                print("❌ Sessão não autenticada.")
                return False

            print("✅ Login realizado com sucesso.")

            return True

        except requests.RequestException as error:
            print(f"❌ Erro de conexão com o Moodle: {error}")
            return False

        except Exception as error:
            print(f"❌ Erro durante o login: {error}")
            return False

    def get_courses(self):
        """
        Obtém as disciplinas disponíveis para o usuário.
        """

        try:
            url = urljoin(
                self.BASE_URL,
                "/my/"
            )

            response = self.session.get(
                url,
                timeout=30
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            courses = []

            # Procuramos links de cursos.
            for link in soup.find_all("a", href=True):

                href = link["href"]

                if "/course/view.php?id=" not in href:
                    continue

                name = link.get_text(
                    " ",
                    strip=True
                )

                if not name:
                    continue

                full_url = urljoin(
                    self.BASE_URL,
                    href
                )

                # Evita duplicados.
                if any(
                    course["url"] == full_url
                    for course in courses
                ):
                    continue

                courses.append({
                    "fullname": name,
                    "url": full_url
                })

            return courses

        except requests.RequestException as error:
            print(f"❌ Erro ao buscar disciplinas: {error}")
            return []

        except Exception as error:
            print(f"❌ Erro ao processar disciplinas: {error}")
            return []

    def get_calendar_events(self):
        """
        Obtém eventos do calendário do Moodle.

        Esta função será expandida usando os endpoints AJAX
        identificados no HAR.
        """

        try:
            url = urljoin(
                self.BASE_URL,
                "/calendar/view.php"
            )

            response = self.session.get(
                url,
                timeout=30
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            events = []

            # Eventos presentes diretamente no HTML.
            for event in soup.select(
                '[data-event-component="mod_assign"]'
            ):

                title = event.get(
                    "data-event-title"
                )

                if not title:
                    title = event.get_text(
                        " ",
                        strip=True
                    )

                link = event.find(
                    "a",
                    href=True
                )

                event_url = None

                if link:
                    event_url = urljoin(
                        self.BASE_URL,
                        link["href"]
                    )

                events.append({
                    "title": title,
                    "url": event_url,
                    "component": "mod_assign"
                })

            return events

        except requests.RequestException as error:
            print(f"❌ Erro ao acessar calendário: {error}")
            return []

        except Exception as error:
            print(f"❌ Erro ao processar calendário: {error}")
            return []
