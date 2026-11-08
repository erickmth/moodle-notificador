/*
 * Assistente (OpenRouter) que conhece as atividades do Moodle e as faltas.
 * Os dados vêm de eventos.json e faltas.json, na raiz do repositório.
 */

const fs = require("fs");
const path = require("path");

const RAIZ = path.join(__dirname, "..");
const FUSO = "America/Sao_Paulo";
const LIMITE_FALTAS = 20;
const FALTAS_POR_DIA = 4;

const MODELO = process.env.OPENROUTER_MODEL || "openrouter/free";
const NOME = process.env.NOME_ALUNO || "Erick";

function lerJSON(arquivo, padrao) {
    try {
        return JSON.parse(fs.readFileSync(path.join(RAIZ, arquivo), "utf-8"));
    } catch {
        return padrao;
    }
}

function formatarData(timestamp) {
    return new Intl.DateTimeFormat("pt-BR", {
        timeZone: FUSO, weekday: "short", day: "2-digit", month: "2-digit",
        hour: "2-digit", minute: "2-digit"
    }).format(new Date(Number(timestamp) * 1000));
}

/* Resumo em texto dos dados atuais, usado como contexto da IA. */
function montarContexto() {
    const agora = Date.now() / 1000;

    const eventos = lerJSON("eventos.json", [])
        .filter(e => String(e.tipo || "").toLowerCase() === "due")
        .filter(e => !e.enviado && Number(e.timestamp) > agora)
        .sort((a, b) => a.timestamp - b.timestamp);

    const linhasAtividades = eventos.length
        ? eventos.map(e => `- ${e.nome} | ${e.disciplina || "?"} | prazo ${formatarData(e.timestamp)}`).join("\n")
        : "- Nenhuma atividade pendente.";

    const faltas = lerJSON("faltas.json", null);
    let linhasFaltas = "- Dados de faltas indisponíveis.";
    if (faltas && faltas.periodos) {
        const atual = faltas.periodo_atual;
        const discs = faltas.periodos[atual]?.disciplinas || [];
        linhasFaltas = discs.length
            ? discs.map(d => {
                const restam = Math.max(0, LIMITE_FALTAS - (d.total || 0));
                return `- ${d.disciplina}: ${d.total} de ${LIMITE_FALTAS} faltas, pode faltar mais ${restam} h (${Math.floor(restam / FALTAS_POR_DIA)} dia(s) de aula)`;
            }).join("\n")
            : "- Nenhuma disciplina com faltas no período.";
        linhasFaltas = `Período ${atual}:\n` + linhasFaltas;
    }

    const hoje = new Intl.DateTimeFormat("pt-BR", {
        timeZone: FUSO, weekday: "long", day: "2-digit", month: "2-digit",
        year: "numeric", hour: "2-digit", minute: "2-digit"
    }).format(new Date());

    return `Agora: ${hoje} (horário de Brasília).

ATIVIDADES PENDENTES NO MOODLE (AVA):
${linhasAtividades}

FALTAS (limite de ${LIMITE_FALTAS} faltas por disciplina; cada falta = 1 hora de aula; um dia de aula = ${FALTAS_POR_DIA} faltas):
${linhasFaltas}`;
}

const INSTRUCOES = `Você é o assistente acadêmico do ${NOME}, aluno de Engenharia Mecatrônica no UniSenai PR, conversando pelo WhatsApp.
Seu papel é informar sobre atividades do Moodle (prazos de entrega) e faltas por disciplina, usando SOMENTE os dados fornecidos abaixo.
Regras:
- Responda em português, de forma curta, simpática e direta, no estilo de mensagem de WhatsApp.
- Use a formatação do WhatsApp (*negrito*, listas com •) e poucos emojis.
- Nunca invente atividades, datas, notas ou números de faltas. Se a informação não estiver nos dados, diga que não sabe.
- Se perguntarem algo fora do tema (atividades, prazos, faltas, organização de estudos), responda brevemente e lembre que você cuida dos prazos e das faltas.
- Os dados são atualizados automaticamente a cada 30 minutos, aproximadamente.`;

async function chamarIA(mensagens) {
    const chave = process.env.OPENROUTER_API_KEY;
    if (!chave) throw new Error("OPENROUTER_API_KEY não configurada.");

    const resposta = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: {
            "Authorization": `Bearer ${chave}`,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/erickmth/moodle-notificador",
            "X-Title": "Moodle Notificador"
        },
        body: JSON.stringify({
            model: MODELO,
            messages: mensagens,
            max_tokens: 700,
            temperature: 0.4
        }),
        signal: AbortSignal.timeout(90_000)
    });

    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok) {
        throw new Error(`OpenRouter HTTP ${resposta.status}: ${dados?.error?.message || "erro"}`);
    }

    const texto = dados?.choices?.[0]?.message?.content?.trim();
    if (!texto) throw new Error("OpenRouter retornou resposta vazia.");
    return texto;
}

/* Responde uma mensagem do aluno, com o histórico recente da conversa. */
async function responder(pergunta, historico = []) {
    return chamarIA([
        { role: "system", content: `${INSTRUCOES}\n\nDADOS ATUAIS:\n${montarContexto()}` },
        ...historico,
        { role: "user", content: pergunta }
    ]);
}

/* Texto padrão caso a IA esteja indisponível. */
function avisoPadrao(novidades) {
    const partes = [];

    for (const a of novidades.atividades || []) {
        partes.push(`📚 *Nova atividade:* ${a.nome}\n📖 ${a.disciplina || "Disciplina não identificada"}\n📅 Prazo: ${a.timestamp ? formatarData(a.timestamp) : "não informado"}${a.url ? `\n🔗 ${a.url}` : ""}`);
    }
    for (const f of novidades.faltas || []) {
        const restam = Math.max(0, LIMITE_FALTAS - f.total);
        partes.push(`⚠️ *Falta nova:* ${f.disciplina}\n+${f.novas} falta(s), total ${f.total} de ${LIMITE_FALTAS}. Pode faltar mais ${restam} h.`);
    }

    return partes.join("\n\n");
}

/* Mensagem de aviso escrita pela IA, com os links sempre incluídos no final. */
async function escreverAviso(novidades) {
    const padrao = avisoPadrao(novidades);
    try {
        const texto = await chamarIA([
            { role: "system", content: `${INSTRUCOES}\n\nDADOS ATUAIS:\n${montarContexto()}` },
            {
                role: "user",
                content: `Escreva UMA mensagem curta avisando o ${NOME} sobre estas novidades detectadas agora. ` +
                    `Destaque prazos e quantas faltas ainda pode ter. Não inclua links.\n\n` +
                    JSON.stringify(novidades, null, 2)
            }
        ]);
        const links = (novidades.atividades || [])
            .filter(a => a.url)
            .map(a => `🔗 ${a.nome}: ${a.url}`)
            .join("\n");
        return links ? `${texto}\n\n${links}` : texto;
    } catch (erro) {
        console.log(`IA indisponível para o aviso (${erro.message}); usando texto padrão.`);
        return padrao;
    }
}

module.exports = { responder, escreverAviso, montarContexto, MODELO };
