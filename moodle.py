import re
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
            {"name": "sesskey"}
        )

        if input_element:
            return input_element.get("value")

        return None

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

        try:
            data = response.json()

        except Exception as erro:
            raise RuntimeError(
                f"O Moodle não retornou JSON válido: {erro}"
            )

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

    def _extrair_assign_id(self, url):

        if not url:
            return None

        try:

            parsed = urlparse(url)

            parametros = parse_qs(
                parsed.query
            )

            valores = parametros.get(
                "id"
            )

            if valores:

                valor = valores[0]

                if valor.isdigit():
                    return int(valor)

        except Exception as erro:

            print(
                f"⚠️ Não foi possível extrair "
                f"o ID da atividade: {erro}"
            )

        return None

    def get_submission_status(
        self,
        assign_id
    ):
        """
        Consulta o status da entrega de uma
        atividade do tipo Assignment.

        O Moodle utiliza:
            mod_assign_get_submission_status

        assignid = ID da instância da atividade.
        userid = 0 significa usuário atual.
        """

        if not assign_id:
            raise ValueError(
                "assign_id não informado."
            )

        methodname = (
            "mod_assign_get_submission_status"
        )

        args = {
            "assignid": int(assign_id),
            "userid": 0,
        }

        return self._ajax_request(
            methodname,
            args
        )

    def verificar_entrega(
        self,
        evento
    ):
        """
        Retorna informações sobre a entrega.

        resultado:

        {
            "consultado": True,
            "enviado": True/False,
            "status": "...",
            "motivo": "..."
        }
        """

        url = evento.get(
            "url",
            ""
        )

        assign_id = self._extrair_assign_id(
            url
        )

        if not assign_id:

            return {
                "consultado": False,
                "enviado": False,
                "status": "sem_assign_id",
                "motivo": (
                    "Não foi possível encontrar "
                    "o ID da atividade na URL."
                ),
            }

        print(
            f"      🔎 Consultando entrega "
            f"da atividade {assign_id}..."
        )

        try:

            data = self.get_submission_status(
                assign_id
            )

            if not data:

                return {
                    "consultado": True,
                    "enviado": False,
                    "status": "sem_dados",
                    "motivo": (
                        "Moodle não retornou dados "
                        "da submissão."
                    ),
                }

            return self._interpretar_status_entrega(
                data
            )

        except Exception as erro:

            print(
                f"      ⚠️ Falha ao consultar entrega: "
                f"{type(erro).__name__}: {erro}"
            )

            return {
                "consultado": False,
                "enviado": False,
                "status": "erro_consulta",
                "motivo": str(erro),
            }

    def _interpretar_status_entrega(
        self,
        data
    ):
        """
        Interpreta a resposta do
        mod_assign_get_submission_status.

        Não considera apenas a existência de
        uma submissão como suficiente.

        O objetivo é identificar se a atividade
        realmente foi enviada.
        """

        status = data.get("status")

        if not isinstance(
            status,
            dict
        ):
            status = {}


        submission = status.get(
            "submission"
        )


        if not isinstance(
            submission,
            dict
        ):
            submission = None


        lastattempt = data.get(
            "lastattempt"
        )

        if not isinstance(
            lastattempt,
            dict
        ):
            lastattempt = {}


        last_submission = lastattempt.get(
            "submission"
        )

        if not isinstance(
            last_submission,
            dict
        ):
            last_submission = None


        /*
         * O Moodle pode fornecer o estado
         * em submission ou lastattempt.
         */
        status_text = (
            status.get("status")
            or data.get("status")
            if isinstance(data.get("status"), str)
            else None
        )


        if not status_text:
            status_text = (
                lastattempt.get("status")
                or ""
            )


        /*
         * Algumas versões retornam o status
         * diretamente no objeto submission.
         */
        if not status_text and submission:

            status_text = (
                submission.get("status")
                or ""
            )


        if not status_text and last_submission:

            status_text = (
                last_submission.get("status")
                or ""
            )


        status_text = str(
            status_text
        ).lower().strip()


        /*
         * Estados conhecidos de submissão.
         */
        estados_enviados = {
            "submitted",
            "graded",
            "returned",
        }


        estados_nao_enviados = {
            "draft",
            "new",
            "",
        }


        if status_text in estados_enviados:

            return {
                "consultado": True,
                "enviado": True,
                "status": status_text,
                "motivo": (
                    "Moodle indica que a "
                    "atividade foi enviada."
                ),
            }


        if status_text in estados_nao_enviados:

            return {
                "consultado": True,
                "enviado": False,
                "status": (
                    status_text
                    or "new"
                ),
                "motivo": (
                    "Moodle indica que a "
                    "atividade ainda não foi enviada."
                ),
            }


        /*
         * Algumas respostas podem possuir
         * campos adicionais.
         *
         * Tentamos identificar um envio
         * efetivo sem assumir que apenas a
         * existência de "submission" significa
         * que foi entregue.
         */
        if submission:

            attempt = submission.get(
                "attempt"
            )

            if (
                attempt is not None
                and str(attempt).isdigit()
                and int(attempt) >= 0
            ):

                submission_status = str(
                    submission.get(
                        "status",
                        ""
                    )
                ).lower().strip()

                if submission_status in estados_enviados:

                    return {
                        "consultado": True,
                        "enviado": True,
                        "status": submission_status,
                        "motivo": (
                            "Submissão identificada "
                            "como enviada."
                        ),
                    }


        /*
         * Se não conseguimos interpretar com
         * segurança, mantemos a atividade no
         * painel.
         */
        return {
            "consultado": True,
            "enviado": False,
            "status": (
                status_text
                or "desconhecido"
            ),
            "motivo": (
                "Status não reconhecido com "
                "segurança; atividade mantida."
            ),
        }

    def get_normalized_events(
        self,
        consultar_entregas=True
    ):

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

        /*
         * Agora filtramos somente os prazos
         * reais das atividades.
         */
        eventos_due = [
            evento
            for evento in normalized
            if str(
                evento.get("tipo", "")
            ).lower() == "due"
        ]


        if not consultar_entregas:

            return eventos_due


        print()
        print(
            "Verificando quais atividades "
            "já foram entregues..."
        )


        eventos_pendentes = []

        for evento in eventos_due:

            print()
            print(
                f"   📝 {evento['nome']}"
            )

            print(
                f"      Disciplina: "
                f"{evento['disciplina'] or 'Não identificada'}"
            )

            print(
                f"      URL: "
                f"{evento['url'] or 'Não disponível'}"
            )


            /*
             * Só atividades mod_assign podem
             * usar essa consulta.
             */
            url_lower = str(
                evento.get("url", "")
            ).lower()


            if "/mod/assign/" not in url_lower:

                print(
                    "      ℹ️ Atividade não é "
                    "mod_assign."
                )

                print(
                    "      → Mantida no painel."
                )

                evento["entrega_consultada"] = False
                evento["entregue"] = False

                eventos_pendentes.append(
                    evento
                )

                continue


            resultado =
                self.verificar_entrega(
                    evento
                )


            evento["entrega_consultada"] = (
                resultado["consultado"]
            )

            evento["entregue"] = (
                resultado["enviado"]
            )

            evento["status_entrega"] = (
                resultado["status"]
            )


            if resultado["enviado"]:

                print(
                    "      ✅ Já entregue."
                )

                print(
                    "      → Removida do painel."
                )

                continue


            print(
                "      ⏳ Ainda pendente."
            )

            print(
                f"      Status: "
                f"{resultado['status']}"
            )

            eventos_pendentes.append(
                evento
            )


        return eventos_pendentes

    def test(self):

        print()

        print("=" * 50)

        print(
            "          NOTIFICADOR MOODLE"
        )

        print("=" * 50)

        print()

        print(
            "Consultando Moodle..."
        )

        self.login()

        print()

        print(
            "Moodle autenticado com sucesso."
        )

        print()

        print(
            "Consultando disciplinas..."
        )

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
                f"   • {fullname} | "
                f"{shortname} | "
                f"ID: {course_id}"
            )


        print()

        print(
            "Consultando eventos do calendário..."
        )

        events = self.get_normalized_events(
            consultar_entregas=True
        )


        print()

        print(
            f"📅 Atividades pendentes: "
            f"{len(events)}"
        )


        for event in events:

            print()

            print(
                f"   📝 {event['nome']}"
            )

            print(
                f"      ID: "
                f"{event['id']}"
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
                f"      Status entrega: "
                f"{event.get('status_entrega', 'Não consultado')}"
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

        print(
            "Fim da verificação."
        )

        print("=" * 50)
