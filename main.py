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

            values = params.get(
                "id"
            )

            if not values:
                return None

            return int(
                values[0]
            )

        except Exception:

            return None

    def _pagina_atividade(self, url):

        """
        Baixa o HTML da página da atividade.
        Funciona mesmo quando os web services estão bloqueados.
        """

        if not url:
            return None

        response = self.session.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        return response.text

    def _extrair_status_do_html(self, html):

        """
        Analisa o HTML da página da atividade do tipo 'assign'
        e tenta determinar se a tarefa já foi enviada.

        Retorna True, False ou None (quando não dá pra saber).
        """

        if not html:
            return None

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # Remove scripts e estilos para não confundir o texto.
        for tag in soup(["script", "style"]):
            tag.decompose()

        texto = soup.get_text(
            " ",
            strip=True
        ).lower()

        # ------------------------------------------------------------
        # 1) Sinais FORTES de que JÁ foi enviado.
        # ------------------------------------------------------------
        positivos = [
            "situação da entrega: enviado",
            "situacao da entrega: enviado",
            "status da entrega: enviado",
            "status da submissão: enviado",
            "status da submissao: enviado",
            "enviado para avaliação",
            "enviado para avaliacao",
            "submetido para avaliação",
            "submetido para avaliacao",
            "esta tarefa foi enviada",
            "tarefa enviada",
            "foi enviado",
            "foi enviada",
            "enviado com sucesso",
            "submissão enviada",
            "submissao enviada",
            "entrega enviada",
            "entregue",
            "recebido",
        ]

        for termo in positivos:

            if termo in texto:
                return True

        # ------------------------------------------------------------
        # 2) Sinais FORTES de que NÃO foi enviado.
        # ------------------------------------------------------------
        negativos = [
            "situação da entrega: nada foi enviado",
            "situacao da entrega: nada foi enviado",
            "situação da entrega: nenhum envio",
            "situacao da entrega: nenhum envio",
            "status da entrega: nada foi enviado",
            "nenhuma tentativa",
            "nada foi enviado",
            "nenhum envio",
            "não enviado",
            "nao enviado",
            "não submetido",
            "nao submetido",
            "nenhuma submissão",
            "nenhuma submissao",
            "envie sua tarefa",
            "enviar tarefa",
            "adicionar tarefa",
            "adicionar entrega",
            "faça o envio",
            "faca o envio",
            "você ainda não enviou",
            "voce ainda nao enviou",
            "ainda não enviou",
            "ainda nao enviou",
        ]

        for termo in negativos:

            if termo in texto:
                return False

        # ------------------------------------------------------------
        # 3) Procura elementos específicos do Moodle.
        # ------------------------------------------------------------
        # Tabela "Situação da entrega"
        for tabela in soup.find_all("table"):

            cabecalho = tabela.get_text(
                " ",
                strip=True
            ).lower()

            if "situação da entrega" in cabecalho \
                    or "situacao da entrega" in cabecalho \
                    or "status da entrega" in cabecalho:

                conteudo = cabecalho

                if "enviado" in conteudo \
                        or "entregue" in conteudo:

                    return True

                if "nada foi enviado" in conteudo \
                        or "nenhum envio" in conteudo \
                        or "não enviado" in conteudo \
                        or "nao enviado" in conteudo:

                    return False

        # Blocos comuns de status no Moodle (badges)
        for seletor in [
            ".submissionstatussubmitted",
            ".submissionstatus-submitted",
            "div[class*='submissionstatus']",
        ]:

            try:

                elemento = soup.select_one(seletor)

            except Exception:

                elemento = None

            if elemento:

                texto_elemento = elemento.get_text(
                    " ",
                    strip=True
                ).lower()

                if "enviado" in texto_elemento \
                        or "submitted" in texto_elemento:

                    return True

                if "nada" in texto_elemento \
                        or "nenhum" in texto_elemento:

                    return False

        # ------------------------------------------------------------
        # 4) Não deu pra saber.
        # ------------------------------------------------------------
        return None

    def is_assignment_submitted(self, event):

        """
        Verifica se uma atividade do tipo 'assign' já foi enviada.

        Usa scraping da própria página da atividade, porque
        os web services do Moodle da Fiep estão bloqueados.
        """

        url = event.get(
            "url",
            ""
        )

        print()
        print(f"   🔗 URL da atividade: {url}")

        if not url:

            print("   ⚠️ Evento sem URL.")
            return False

        # Só faz sentido checar entregas de 'assign'.
        if "/mod/assign/" not in url:

            print("   ℹ️ Não é uma atividade mod_assign.")
            return False

        try:

            html = self._pagina_atividade(url)

        except Exception as erro:

            print(
                f"   ❌ Erro ao baixar a página da atividade: "
                f"{erro}"
            )

            return False

        status = self._extrair_status_do_html(html)

        print(
            f"   📌 Status detectado no HTML: "
            f"{status}"
        )

        if status is True:

            return True

        if status is False:

            return False

        # ------------------------------------------------------------
        # Se chegou aqui, o HTML não trouxe uma resposta clara.
        # Tenta uma última análise heurística.
        # ------------------------------------------------------------
        soup = BeautifulSoup(html, "html.parser")

        texto = soup.get_text(" ", strip=True).lower()

        # Se aparecer "enviado" em algum lugar e não tiver
        # nenhuma negação perto, assume enviado.
        if "enviado" in texto:

            if "não enviado" not in texto \
                    and "nao enviado" not in texto \
                    and "nada foi enviado" not in texto:

                print(
                    "   ⚠️ Ambíguo, mas 'enviado' presente. "
                    "Assumindo enviado."
                )

                return True

        print("   ⚠️ Não foi possível determinar o status.")
        return False

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

    client.login()

    eventos = client.get_normalized_events()

    for evento in eventos:

        tipo = str(evento.get("tipo") or "").lower()

        if tipo != "due":
            continue

        print()
        print("=" * 70)
        print(evento.get("nome"))
        print("=" * 70)

        client.is_assignment_submitted(evento)
