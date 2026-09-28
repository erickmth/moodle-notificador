import os
from moodle import MoodleClient

client = MoodleClient(
    username=os.getenv("MOODLE_USER"),
    password=os.getenv("MOODLE_PASSWORD")
)
client.login()

# Pré-banca (que você JÁ enviou)
urls = {
    "PRE-BANCA (enviada)": "https://ava.fiep.digital/mod/assign/view.php?id=1298240",
    "AULA 4 (não enviada)": "https://ava.fiep.digital/mod/assign/view.php?id=1293219",
    "AULA 5 (não enviada)": "https://ava.fiep.digital/mod/assign/view.php?id=1294653",
}

from bs4 import BeautifulSoup

for nome, url in urls.items():
    print("=" * 70)
    print(nome)
    print("=" * 70)

    html = client._pagina_atividade(url)
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    # Procura a tabela de status de entrega
    for tabela in soup.find_all("table"):
        texto = tabela.get_text(" ", strip=True)
        if "entrega" in texto.lower() or "submiss" in texto.lower():
            print(">>> TABELA ENCONTRADA:")
            print(texto[:800])
            print()

    # Procura qualquer coisa com "submissionstatus"
    for el in soup.select("[class*='submission']"):
        cls = " ".join(el.get("class", []))
        txt = el.get_text(" ", strip=True)
        if txt:
            print(f">>> [{cls}] {txt[:200]}")

    print()
