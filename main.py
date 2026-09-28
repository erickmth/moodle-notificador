import os
from moodle import MoodleClient

client = MoodleClient(
    username=os.getenv("MOODLE_USER"),
    password=os.getenv("MOODLE_PASSWORD")
)
client.login()

# Teste 1: get_submission_status direto com o cmid da URL
try:
    data = client.get_submission_status(1293219)
    print("✅ get_submission_status com cmid funcionou")
    print(data)
except Exception as e:
    print("❌ get_submission_status falhou:", e)

# Teste 2: pegar o HTML da página da atividade
resp = client.session.get(
    "https://ava.fiep.digital/mod/assign/view.php?id=1293219",
    timeout=30
)
print("HTTP:", resp.status_code)
print("Tem 'enviado' no HTML?", "enviado" in resp.text.lower())
print("Tem 'submetido' no HTML?", "submetido" in resp.text.lower())
print("Tem 'submission' no HTML?", "submission" in resp.text.lower())
print("Trecho:", resp.text[:500])
