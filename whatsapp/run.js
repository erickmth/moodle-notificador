/*
 * Bot de WhatsApp de execução curta, feito para rodar no GitHub Actions.
 *
 *   node run.js pair   -> gera o código de pareamento para o número do bot
 *   node run.js        -> conecta, manda os avisos novos, responde as
 *                         mensagens recebidas desde a última execução e sai
 *
 * Os logs do Actions são públicos neste repositório, por isso nenhuma
 * mensagem, número ou resposta é impressa: só contagens.
 */

const fs = require("fs");
const path = require("path");
const pino = require("pino");
const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    Browsers
} = require("@whiskeysockets/baileys");

const { responder, escreverAviso, MODELO } = require("./ia");

const AUTH_DIR = path.join(__dirname, "auth");
const ESTADO_FILE = path.join(AUTH_DIR, "estado-bot.json");
const NOVIDADES_FILE = path.join(__dirname, "..", "novidades.json");

const MODO = process.argv[2] === "pair" ? "pair" : "run";
const DONO = (process.env.WHATSAPP_OWNER || "").replace(/\D/g, "");
const NUMERO_BOT = (process.env.WHATSAPP_BOT_NUMBER || "").replace(/\D/g, "");

const ESPERA_OFFLINE_MS = 20_000;     // tempo para chegarem as mensagens pendentes
const LIMITE_PAREAMENTO_MS = 5 * 60_000;
const MAX_IDADE_MENSAGEM_S = 24 * 3600;
const MAX_HISTORICO = 12;

const esperar = ms => new Promise(r => setTimeout(r, ms));
const logger = pino({ level: "silent" });

/* ------------------------------------------------------------------ */
/* Estado do bot (vai junto com a sessão, criptografado)               */
/* ------------------------------------------------------------------ */
function lerEstado() {
    try {
        return JSON.parse(fs.readFileSync(ESTADO_FILE, "utf-8"));
    } catch {
        return { ultimoTimestamp: 0, respondidas: [], historico: [] };
    }
}

function salvarEstado(estado) {
    estado.respondidas = estado.respondidas.slice(-200);
    estado.historico = estado.historico.slice(-MAX_HISTORICO);
    fs.mkdirSync(AUTH_DIR, { recursive: true });
    fs.writeFileSync(ESTADO_FILE, JSON.stringify(estado, null, 2));
}

/* ------------------------------------------------------------------ */
/* Conexão                                                             */
/* ------------------------------------------------------------------ */
async function conectar({ aoAbrir, aoMensagem }) {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }));

    return new Promise((resolve, reject) => {
        let pedidoCodigo = false;

        const iniciar = () => {
            const sock = makeWASocket({
                version,
                auth: state,
                logger,
                browser: Browsers.macOS("Chrome"),
                printQRInTerminal: false,
                markOnlineOnConnect: false,
                syncFullHistory: false
            });

            sock.ev.on("creds.update", saveCreds);
            if (aoMensagem) sock.ev.on("messages.upsert", aoMensagem);

            sock.ev.on("connection.update", async ({ connection, lastDisconnect, qr }) => {
                if (qr && MODO === "pair" && !pedidoCodigo && !state.creds.registered) {
                    pedidoCodigo = true;
                    try {
                        const codigo = await sock.requestPairingCode(NUMERO_BOT);
                        const formatado = codigo.match(/.{1,4}/g).join("-");
                        console.log("");
                        console.log("==============================================");
                        console.log(`  CÓDIGO DE PAREAMENTO:  ${formatado}`);
                        console.log("==============================================");
                        console.log("No celular do número do bot: WhatsApp > Aparelhos conectados >");
                        console.log("Conectar um aparelho > Conectar com número de telefone.");
                        console.log("");
                    } catch (erro) {
                        reject(new Error(`Falha ao pedir o código de pareamento: ${erro.message}`));
                    }
                }

                if (connection === "open") {
                    console.log("✅ Conectado ao WhatsApp.");
                    try {
                        resolve(await aoAbrir(sock));
                    } catch (erro) {
                        reject(erro);
                    }
                }

                if (connection === "close") {
                    const codigo = lastDisconnect?.error?.output?.statusCode;
                    if (codigo === DisconnectReason.restartRequired) {
                        console.log("Reiniciando conexão após o pareamento...");
                        iniciar();
                    } else if (codigo === DisconnectReason.loggedOut) {
                        reject(new Error("Sessão desconectada no celular. Rode o pareamento de novo."));
                    } else if (!sock.__encerrado) {
                        reject(new Error(`Conexão fechada (código ${codigo ?? "?"}).`));
                    }
                }
            });
        };

        iniciar();
    });
}

/* ------------------------------------------------------------------ */
/* Identificação das mensagens do dono                                 */
/* ------------------------------------------------------------------ */
function ehDoDono(chave) {
    if (!DONO) return false;
    const candidatos = [chave.remoteJid, chave.remoteJidAlt, chave.senderPn, chave.participant, chave.participantAlt];
    const alvos = new Set([DONO, ...jidsDono.map(j => j.split("@")[0].split(":")[0])]);
    return candidatos.some(j => typeof j === "string" && alvos.has(j.split("@")[0].split(":")[0]));
}

/*
 * Descobre o endereço real do dono no WhatsApp. Muitos números do Brasil
 * estão registrados sem o 9 extra (ex.: 55 41 9xxxx-xxxx vira 55 41 xxxx-xxxx),
 * e mensagem enviada para o formato errado não chega.
 */
let jidsDono = [];
async function resolverDono(sock) {
    const candidatos = [DONO];
    const m = DONO.match(/^55(\d{2})9(\d{8})$/);
    if (m) candidatos.push(`55${m[1]}${m[2]}`);
    const m2 = DONO.match(/^55(\d{2})(\d{8})$/);
    if (m2) candidatos.push(`55${m2[1]}9${m2[2]}`);

    for (const numero of candidatos) {
        try {
            const [r] = await sock.onWhatsApp(numero);
            if (r?.exists) {
                jidsDono = [r.jid, ...(r.lid ? [r.lid] : [])];
                const variante = numero === DONO ? "como cadastrado" : "variante com/sem o 9";
                console.log(`Número do dono encontrado no WhatsApp (${variante}).`);
                return r.jid;
            }
        } catch (erro) {
            console.log(`Não consegui consultar o número (${erro.message}).`);
        }
    }
    console.log(`⚠️ Número do dono não encontrado no WhatsApp (${DONO.length} dígitos; ` +
        `${DONO.startsWith("55") ? "começa com 55" : "SEM o 55 no início"}). Confira o secret WHATSAPP_OWNER.`);
    return `${DONO}@s.whatsapp.net`;
}

function textoDaMensagem(msg) {
    const m = msg.message || {};
    return (
        m.conversation ||
        m.extendedTextMessage?.text ||
        m.ephemeralMessage?.message?.conversation ||
        m.ephemeralMessage?.message?.extendedTextMessage?.text ||
        ""
    ).trim();
}

async function encerrar(sock) {
    sock.__encerrado = true;
    await esperar(3000); // dá tempo de salvar as credenciais
    sock.end(undefined);
}

/* ------------------------------------------------------------------ */
/* Modos                                                               */
/* ------------------------------------------------------------------ */
async function parear() {
    if (!NUMERO_BOT) throw new Error("Informe o número do bot (WHATSAPP_BOT_NUMBER).");

    const { state } = await useMultiFileAuthState(AUTH_DIR);
    if (state.creds.registered) {
        console.log("Já existe uma sessão pareada. Apague o cache para parear de novo.");
        return;
    }

    const limite = setTimeout(() => {
        console.error("⏰ Tempo esgotado: o código não foi usado em 5 minutos.");
        process.exit(1);
    }, LIMITE_PAREAMENTO_MS);

    await conectar({
        aoAbrir: async sock => {
            clearTimeout(limite);
            if (DONO) {
                await esperar(5000); // deixa a sessão nova terminar de sincronizar
                await sock.sendMessage(await resolverDono(sock), {
                    text: "👋 Oi! Sou seu assistente de prazos e faltas. A partir de agora te aviso aqui quando aparecer atividade ou falta nova, e você pode me perguntar o que quiser sobre isso."
                });
            }
            salvarEstado({ ...lerEstado(), ultimoTimestamp: Math.floor(Date.now() / 1000) });
            await encerrar(sock);
        }
    });
    console.log("✅ Pareamento concluído e sessão salva.");
}

async function executar() {
    const { state } = await useMultiFileAuthState(AUTH_DIR);
    if (!state.creds.registered) {
        console.log("ℹ️ WhatsApp ainda não pareado. Rode o workflow \"Parear WhatsApp\".");
        return;
    }
    if (!DONO) {
        console.log("ℹ️ WHATSAPP_OWNER não configurado; nada a fazer.");
        return;
    }

    const estado = lerEstado();
    const recebidas = new Map();
    const agoraS = Math.floor(Date.now() / 1000);

    const aoMensagem = ({ messages }) => {
        for (const msg of messages) {
            if (!msg.message || msg.key.fromMe || !ehDoDono(msg.key)) continue;
            const ts = Number(msg.messageTimestamp || 0);
            if (ts <= estado.ultimoTimestamp || ts < agoraS - MAX_IDADE_MENSAGEM_S) continue;
            if (estado.respondidas.includes(msg.key.id)) continue;
            const texto = textoDaMensagem(msg);
            if (texto) recebidas.set(msg.key.id, { msg, texto, ts });
        }
    };

    await conectar({
        aoMensagem,
        aoAbrir: async sock => {
            const destino = await resolverDono(sock);

            if (process.env.WA_TESTE === "1") {
                await sock.sendMessage(destino, { text: "✅ Teste do bot: se você está lendo isto, os avisos estão chegando! Pode me mandar uma pergunta sobre prazos ou faltas." });
                console.log("📨 Mensagem de teste enviada.");
            }

            // 1. Avisos de atividades e faltas novas
            let novidades = {};
            try { novidades = JSON.parse(fs.readFileSync(NOVIDADES_FILE, "utf-8")); } catch { }
            const qtdNovidades = (novidades.atividades?.length || 0) + (novidades.faltas?.length || 0);
            if (qtdNovidades > 0) {
                const aviso = await escreverAviso(novidades);
                await sock.sendMessage(destino, { text: aviso });
                estado.historico.push({ role: "assistant", content: aviso });
                console.log(`📣 Aviso enviado (${qtdNovidades} novidade(s)).`);
            } else {
                console.log("Sem novidades para avisar.");
            }

            // 2. Espera as mensagens recebidas enquanto o bot estava desligado
            await esperar(ESPERA_OFFLINE_MS);
            const pendentes = [...recebidas.values()].sort((a, b) => a.ts - b.ts);
            console.log(`💬 Mensagens para responder: ${pendentes.length} (modelo: ${MODELO})`);

            for (const { msg, texto, ts } of pendentes) {
                let resposta;
                try {
                    await sock.sendPresenceUpdate("composing", msg.key.remoteJid).catch(() => { });
                    resposta = await responder(texto, estado.historico);
                } catch (erro) {
                    console.log(`Falha na IA: ${erro.message}`);
                    resposta = "Desculpa, não consegui pensar numa resposta agora 😕 Tenta de novo daqui a pouco.";
                }
                await sock.sendMessage(msg.key.remoteJid, { text: resposta }, { quoted: msg });
                estado.historico.push({ role: "user", content: texto }, { role: "assistant", content: resposta });
                estado.respondidas.push(msg.key.id);
                estado.ultimoTimestamp = Math.max(estado.ultimoTimestamp, ts);
            }

            salvarEstado(estado);
            await encerrar(sock);
        }
    });
    console.log("Fim da execução do WhatsApp.");
}

(MODO === "pair" ? parear() : executar())
    .then(() => process.exit(0))
    .catch(erro => {
        console.error(`❌ ${erro.message}`);
        process.exit(1);
    });
