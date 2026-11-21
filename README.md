# Moodle Notificador

Painel e assistente de WhatsApp para alunos do **UniSenai PR**. Ele acompanha
os prazos de atividades no Moodle (AVA) e as faltas no Portal Educacional, sem
precisar abrir os dois sistemas toda hora.

Tudo roda no **GitHub Actions**, a cada 30 minutos. Não precisa de servidor.

## O que ele faz

- **Prazos do Moodle**: busca as atividades com data de entrega, verifica se
  cada uma já foi enviada e salva tudo em `eventos.json`.
- **Faltas do Portal Educacional (TOTVS)**: busca o total de faltas por
  disciplina e por mês, em todos os períodos, e também a **data, o horário e a
  situação de cada aula com falta**. Salva tudo em `faltas.json`.
- **Site (`index.html`)**: mostra os prazos agrupados por data, com busca, e um
  cartão de faltas por disciplina com:
  - barra de progresso até o limite de 20 faltas;
  - quantas horas ou dias de aula ainda dá para faltar;
  - faltas por mês;
  - **ao clicar no cartão**, uma janela com os dias em que houve falta e os
    detalhes de cada aula (horário, número da aula, situação e justificativa).
- **WhatsApp**: avisa quando aparece uma atividade nova no Moodle ou uma falta nova e responde a
  perguntas como *"quantas faltas eu tenho em Química?"*. As respostas são
  geradas por uma IA (OpenRouter) que usa só os dados de `eventos.json` e
  `faltas.json`.

## Como funciona

```
GitHub Actions (a cada 30 min)
 ├─ main.py    → Moodle             → eventos.json ─┐
 ├─ faltas.py  → Portal Educacional → faltas.json  ─┼─ commit no repositório → site (index.html)
 │                                   novidades.json ┘
 └─ whatsapp/run.js → envia os avisos de novidades.json e responde às mensagens recebidas
```

| Arquivo | Função |
|---|---|
| `main.py` | Faz login no Moodle, lista disciplinas e prazos e marca o que já foi enviado |
| `moodle.py` | Cliente HTTP do Moodle (login, sesskey, chamadas AJAX, status de envio) |
| `faltas.py` | Busca as faltas de todos os períodos e detecta faltas novas |
| `portal.py` | Cliente da API do Portal Educacional (TOTVS RM) |
| `novidades.py` | Registra o que mudou na execução atual, para o bot avisar no WhatsApp |
| `index.html` | O site (HTML, CSS e JS em um único arquivo, sem build) |
| `whatsapp/run.js` | Bot de execução curta: pareia, envia os avisos e responde às mensagens |
| `whatsapp/ia.js` | Monta o contexto e chama a IA pelo OpenRouter |
| `whatsapp/bot.js` | Versão antiga do bot como servidor Express (não é usada pelas Actions) |

## Configuração

### 1. Secrets do repositório

Em **Settings → Secrets and variables → Actions**, crie:

| Secret | Obrigatório | Descrição |
|---|---|---|
| `MOODLE_USER` | sim | Usuário do Moodle / Sistema Fiep |
| `MOODLE_PASSWORD` | sim | Senha do Moodle |
| `PORTAL_USER` | não | Usuário do Portal Educacional (se faltar, usa o do Moodle) |
| `PORTAL_PASSWORD` | não | Senha do Portal Educacional (se faltar, usa a do Moodle) |
| `WA_SESSION_KEY` | para o WhatsApp | Senha longa e aleatória que criptografa a sessão do WhatsApp |
| `WHATSAPP_OWNER` | para o WhatsApp | Seu número (quem recebe os avisos), com DDI e DDD, ex.: `5541999998888` |
| `OPENROUTER_API_KEY` | para a IA | Chave da [OpenRouter](https://openrouter.ai) |

### 2. Publicar o site

Ative o **GitHub Pages** em **Settings → Pages**, com a branch `main` e a pasta
`/ (root)`. O `index.html` lê o `eventos.json` e o `faltas.json` do próprio
repositório e se atualiza sozinho (prazos a cada minuto, faltas a cada 5
minutos).

### 3. Parear o WhatsApp (opcional)

Use um número **secundário** para o bot.

1. Vá em **Actions → Parear WhatsApp → Run workflow** e informe o número do bot
   (ex.: `5541999998888`).
2. Abra o log do passo *"Gerar código de pareamento"* e copie o código.
3. No celular do bot, vá em **WhatsApp → Aparelhos conectados → Conectar com
   número de telefone** e digite o código. Você tem 5 minutos.

A sessão fica salva no cache do Actions, criptografada com `WA_SESSION_KEY`.
Os logs só mostram contagens: nenhuma mensagem ou número aparece.

## Uso

- **Automático**: o workflow *Verificar Moodle* roda a cada 30 minutos.
- **Manual**: vá em **Actions → Verificar Moodle → Run workflow**. Marque
  *"Mandar uma mensagem de teste no WhatsApp"* para testar o bot.

### Rodar localmente

```bash
pip install -r requirements.txt

export MOODLE_USER="seu.usuario"
export MOODLE_PASSWORD="sua-senha"

python main.py     # atualiza eventos.json
python faltas.py   # atualiza faltas.json

python -m http.server 8000   # abra http://localhost:8000
```

Variáveis opcionais de `faltas.py`:

- `PORTAL_PERIODO`: força o período atual (ex.: `2026/2`);
- `PORTAL_ALIAS`: alias do Portal Educacional (padrão: `CorporeRM`).

## Regras de faltas

Os limites estão no começo da seção de faltas do `index.html` e do `whatsapp/ia.js`:

- limite de **20 faltas** por disciplina;
- cada falta vale **1 hora de aula**, e um dia de aula equivale a **4 faltas**;
- o cartão fica **laranja** quando restam 8 faltas ou menos (2 dias de aula) e
  **vermelho** quando o limite é atingido.

## Avisos

- Projeto pessoal, **não oficial**, sem ligação com o SENAI/FIEP. Ele usa as
  mesmas chamadas que o navegador faz, então pode parar de funcionar se os
  sistemas mudarem.
- `eventos.json` e `faltas.json` ficam no repositório. **Se o repositório for
  público, seus prazos e faltas também ficam públicos.**

## Licença

[MIT](LICENSE) © 2026 Erick Matheus
