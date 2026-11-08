"""
Cliente do Portal Educacional (TOTVS RM) do SESI/SENAI PR.

Fluxo usado pelo próprio portal:
  1. POST  TOTVSEducacional/Login                {user, password, alias}
  2. GET   TOTVSEducacional/Contexto/ContextoComFoto   (um contexto por período)
  3. POST  TOTVSEducacional/Contexto/Selecao     (seleciona o período)
  4. GET   TOTVSEducacional/FaltaEtapa           (faltas do período selecionado)
"""

import re

import requests


class PortalError(Exception):
    pass


class PortalClient:

    BASE_URL = "https://alunos.sesisenaipr.org.br"
    API = BASE_URL + "/FrameHTML/RM/API/TOTVSEducacional/"
    LOGIN_PAGE = BASE_URL + "/FrameHTML/Web/App/Edu/PortalEducacional/login/"
    APP_PAGE = BASE_URL + "/FrameHTML/Web/App/Edu/PortalEducacional/"

    def __init__(self, username, password, alias="CorporeRM"):
        self.username = username
        self.password = password
        self.alias = alias

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Origin": self.BASE_URL,
            "Referer": self.APP_PAGE,
        })

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    def _json(self, response, contexto):
        if response.status_code in (401, 403):
            raise PortalError(
                f"{contexto}: acesso negado (HTTP {response.status_code})."
            )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            raise PortalError(
                f"{contexto}: resposta não é JSON "
                f"(HTTP {response.status_code}, "
                f"{response.headers.get('Content-Type')})."
            )

    def _get(self, metodo):
        r = self.session.get(self.API + metodo, timeout=30)
        return self._json(r, f"GET {metodo}")

    def _post(self, metodo, corpo):
        r = self.session.post(self.API + metodo, json=corpo, timeout=30)
        return self._json(r, f"POST {metodo}")

    @staticmethod
    def _mensagens(dados):
        if not isinstance(dados, dict):
            return []
        msgs = dados.get("messages") or dados.get("$messages") or []
        return [
            (m.get("detail") or m.get("message") or str(m))
            if isinstance(m, dict) else str(m)
            for m in msgs
        ]

    @staticmethod
    def _data(dados):
        if isinstance(dados, dict) and "data" in dados:
            return dados["data"]
        return dados

    @staticmethod
    def _encontrar_chave(dados):
        """A chave do login pode vir em 'value', 'data' ou 'data.value'."""
        if isinstance(dados, str):
            return dados or None
        if not isinstance(dados, dict):
            return None
        for campo in ("value", "Value", "key", "Key", "data", "Data"):
            valor = dados.get(campo)
            if isinstance(valor, str) and valor:
                return valor
            if isinstance(valor, dict):
                interna = PortalClient._encontrar_chave(valor)
                if interna:
                    return interna
        return None

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login(self):
        print("Acessando página de login do Portal Educacional...")
        r = self.session.get(self.LOGIN_PAGE, timeout=30)
        print(f"Página de login carregada: HTTP {r.status_code}")

        print("Enviando autenticação para o portal...")
        r = self.session.post(
            self.API + "Login",
            json={
                "user": self.username,
                "password": self.password,
                "alias": self.alias,
            },
            headers={"Referer": self.LOGIN_PAGE},
            timeout=30,
        )
        print(f"Resposta do login: HTTP {r.status_code}")
        dados = self._json(r, "Login")

        erros = self._mensagens(dados)
        if erros:
            raise PortalError("Login recusado: " + " | ".join(erros))

        chave = self._encontrar_chave(dados)

        if not chave:
            print("⚠️ Login sem chave; tentando seguir só com os cookies.")
            print("Portal autenticado (sem AutoLoginPortal).")
            return

        # O portal abre "#/main?key=<chave>" e troca essa chave pela
        # sessão chamando user/AutoLoginPortal.
        r = self.session.get(
            self.BASE_URL + "/FrameHTML/RM/API/user/AutoLoginPortal",
            params={"key": chave},
            timeout=30,
        )
        print(f"Ativação da sessão: HTTP {r.status_code}")
        dados = self._json(r, "AutoLoginPortal")
        if isinstance(dados, dict) and dados.get("Excessao"):
            raise PortalError(f"AutoLoginPortal recusado: {dados.get('Excessao')}")

        print("Portal autenticado.")

    # ------------------------------------------------------------------
    # Períodos e contexto
    # ------------------------------------------------------------------
    def get_contextos(self):
        dados = self._data(self._get("Contexto/ContextoComFoto"))
        if isinstance(dados, dict):
            dados = [dados]
        if not isinstance(dados, list):
            raise PortalError("ContextoComFoto retornou um formato inesperado.")
        validos = [c for c in dados if isinstance(c, dict) and c.get("IDPERLET")]
        if not validos:
            amostra = dados[0] if dados else {}
            chaves = list(amostra.keys())[:10] if isinstance(amostra, dict) else amostra
            raise PortalError(
                f"Nenhum período encontrado em ContextoComFoto (amostra: {chaves})."
            )
        return validos

    def selecionar_contexto(self, ctx):
        corpo = {
            "CodColigada": ctx.get("CODCOLIGADA"),
            "CodFilial": ctx.get("CODFILIAL"),
            "CodTipoCurso": ctx.get("CODTIPOCURSO"),
            "IdContextoAluno": ctx.get("IDCONTEXTOALUNO"),
            "IdHabilitacaoFilial": ctx.get("IDHABILITACAOFILIAL"),
            "IdPerlet": ctx.get("IDPERLET"),
            "RA": ctx.get("RA"),
            "AcessoDadosAcademicos": ctx.get("ACESSODADOSACADEMICOS") == "S",
            "AcessoDadosFinanceiros": ctx.get("ACESSODADOSFINANCEIROS") == "S",
        }
        dados = self._post("Contexto/Selecao", corpo)
        erros = self._mensagens(dados)
        if erros:
            raise PortalError("Seleção de período recusada: " + " | ".join(erros))

    # ------------------------------------------------------------------
    # Faltas
    # ------------------------------------------------------------------
    @staticmethod
    def _numero(valor):
        if valor is None or valor == "":
            return None
        try:
            return float(str(valor).replace(",", "."))
        except ValueError:
            return None

    def get_faltas(self):
        dados = self._data(self._get("FaltaEtapa"))
        linhas = dados.get("FaltasEtapa", []) if isinstance(dados, dict) else dados
        linhas = linhas or []

        disciplinas = []
        for linha in linhas:
            etapas = []
            total = None

            # Colunas no formato "1 - Mês 1", "25 - Total de Faltas"...
            colunas = []
            for chave, valor in linha.items():
                m = re.match(r"^\s*(\d+)\s*-\s*(.+)$", str(chave))
                if m:
                    colunas.append((int(m.group(1)), m.group(2).strip(), valor))

            for _, nome, valor in sorted(colunas):
                if "total" in nome.lower():
                    total = self._numero(valor)
                else:
                    etapas.append({"etapa": nome, "faltas": self._numero(valor)})

            if total is None:
                total = sum(e["faltas"] or 0 for e in etapas)

            nome = (linha.get("Disciplina") or linha.get("DISCIPLINA") or "").strip()

            disciplinas.append({
                "codigo": linha.get("CODDISC"),
                "disciplina": nome or "Disciplina sem nome",
                "situacao": linha.get("Situação") or linha.get("Situacao"),
                "total": int(total) if float(total).is_integer() else total,
                "percentual": self._numero(linha.get("PERCENTUAL")),
                "situacao_faltas": linha.get("SITUACAOFALTAS"),
                "etapas": etapas,
            })

        disciplinas.sort(key=lambda d: d["disciplina"].lower())
        return disciplinas

    def get_faltas_todos_periodos(self):
        """Retorna {codperlet: {"curso": ..., "disciplinas": [...]}}."""
        resultado = {}
        for ctx in self.get_contextos():
            periodo = str(ctx.get("CODPERLET") or ctx.get("IDPERLET"))
            curso = (ctx.get("NOMECURSO") or "").strip()
            print(f"📆 Período {periodo} ({curso})...")

            self.selecionar_contexto(ctx)
            disciplinas = self.get_faltas()
            for d in disciplinas:
                d["curso"] = curso

            atual = resultado.setdefault(periodo, {
                "curso": curso,
                "inicio": str(ctx.get("DTINICIO") or "")[:10] or None,
                "disciplinas": [],
            })
            atual["disciplinas"].extend(disciplinas)
            print(f"   {len(disciplinas)} disciplina(s).")

        return resultado
