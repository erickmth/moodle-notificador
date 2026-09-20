const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion
} = require("@whiskeysockets/baileys");

const express = require("express");
const QRCode = require("qrcode");
const pino = require("pino");
const path = require("path");
const fs = require("fs");

const app = express();

app.use(express.json());

const PORT = process.env.PORT || 80;

const BOT_API_KEY = process.env.BOT_API_KEY;

const WHATSAPP_NUMBER = process.env.WHATSAPP_NUMBER;

const AUTH_DIR = path.join(
    __dirname,
    "auth"
);

let sock = null;

let qrCodeData = null;

let whatsappConnected = false;


/*
|--------------------------------------------------------------------------
| Verificação da API
|--------------------------------------------------------------------------
*/

function verificarApiKey(req, res, next) {

    if (!BOT_API_KEY) {

        return res.status(500).json({
            sucesso: false,
            erro: "BOT_API_KEY não configurada."
        });
    }

    const authorization =
        req.headers.authorization || "";

    const esperado =
        `Bearer ${BOT_API_KEY}`;

    if (authorization !== esperado) {

        return res.status(401).json({
            sucesso: false,
            erro: "Não autorizado."
        });
    }

    next();
}


/*
|--------------------------------------------------------------------------
| Formatação da mensagem
|--------------------------------------------------------------------------
*/

function criarMensagem(evento) {

    const nome =
        evento.nome ||
        "Nova atividade";

    const disciplina =
        evento.disciplina ||
        "Disciplina não identificada";

    const tipo =
        evento.tipo ||
        "Evento";

    let dataFormatada =
        "Data não informada";

    if (evento.timestamp) {

        const data =
            new Date(
                Number(evento.timestamp) * 1000
            );

        dataFormatada =
            new Intl.DateTimeFormat(
                "pt-BR",
                {
                    timeZone: "America/Sao_Paulo",
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit"
                }
            ).format(data);
    }

    let mensagem = "";

    mensagem += "📚 *Nova atividade no Moodle*\n\n";

    mensagem += `📝 ${nome}\n`;

    mensagem += `📖 Disciplina: ${disciplina}\n`;

    mensagem += `📅 Data: ${dataFormatada}\n`;

    mensagem += `📌 Tipo: ${tipo}\n`;

    if (evento.url) {

        mensagem += `\n🔗 ${evento.url}`;
    }

    return mensagem;
}


/*
|--------------------------------------------------------------------------
| Conexão WhatsApp
|--------------------------------------------------------------------------
*/

async function conectarWhatsApp() {

    console.log("");
    console.log("========================================");
    console.log("       BOT WHATSAPP MOODLE");
    console.log("========================================");
    console.log("");

    console.log(
        `📁 Diretório da sessão: ${AUTH_DIR}`
    );

    if (!fs.existsSync(AUTH_DIR)) {

        fs.mkdirSync(
            AUTH_DIR,
            {
                recursive: true
            }
        );
    }

    const {
        state,
        saveCreds
    } = await useMultiFileAuthState(
        AUTH_DIR
    );

    let version;

    try {

        const resultado =
            await fetchLatestBaileysVersion();

        version =
            resultado.version;

        console.log(
            `📱 Versão WhatsApp Web: ${version.join(".")}`
        );

    } catch (erro) {

        console.log(
            "⚠️ Não foi possível obter a versão mais recente do WhatsApp Web."
        );

        console.log(
            "Continuando com a versão padrão da biblioteca."
        );
    }

    const opcoes = {

        auth: state,

        logger: pino({
            level: "silent"
        }),

        browser: [
            "Moodle Notificador",
            "Chrome",
            "1.0.0"
        ],

        printQRInTerminal: false,

        markOnlineOnConnect: false
    };

    if (version) {

        opcoes.version = version;
    }

    sock =
        makeWASocket(opcoes);

    sock.ev.on(
        "creds.update",
        saveCreds
    );

    sock.ev.on(
        "connection.update",
        async (update) => {

            const {
                connection,
                lastDisconnect,
                qr
            } = update;

            if (qr) {

                qrCodeData = qr;

                whatsappConnected = false;

                console.log("");
                console.log(
                    "📱 Novo QR Code disponível."
                );

                console.log(
                    "Abra o endpoint /qr para visualizar."
                );

                console.log("");
            }

            if (connection === "open") {

                whatsappConnected = true;

                qrCodeData = null;

                console.log("");
                console.log(
                    "✅ WhatsApp conectado!"
                );

                console.log("");
            }

            if (connection === "close") {

                whatsappConnected = false;

                const statusCode =
                    lastDisconnect
                        ?.error
                        ?.output
                        ?.statusCode;

                const deveReconectar =
                    statusCode !==
                    DisconnectReason.loggedOut;

                console.log("");

                console.log(
                    "⚠️ Conexão WhatsApp encerrada."
                );

                console.log(
                    `Código: ${statusCode || "desconhecido"}`
                );

                if (deveReconectar) {

                    console.log(
                        "🔄 Tentando reconectar..."
                    );

                    setTimeout(
                        () => {
                            conectarWhatsApp()
                                .catch(
                                    (erro) => {
                                        console.error(
                                            "❌ Erro ao reconectar:",
                                            erro
                                        );
                                    }
                                );
                        },
                        5000
                    );

                } else {

                    console.log(
                        "❌ Sessão encerrada pelo WhatsApp."
                    );

                    console.log(
                        "Será necessário autenticar novamente."
                    );
                }
            }
        }
    );
}


/*
|--------------------------------------------------------------------------
| Health check
|--------------------------------------------------------------------------
*/

app.get(
    "/",
    (req, res) => {

        res.json({
            sucesso: true,
            servico: "Moodle WhatsApp Bot",
            whatsapp_conectado:
                whatsappConnected,
            qr_disponivel:
                Boolean(qrCodeData)
        });
    }
);


/*
|--------------------------------------------------------------------------
| Status
|--------------------------------------------------------------------------
*/

app.get(
    "/status",
    (req, res) => {

        res.json({
            sucesso: true,
            whatsapp_conectado:
                whatsappConnected,
            qr_disponivel:
                Boolean(qrCodeData)
        });
    }
);


/*
|--------------------------------------------------------------------------
| QR Code
|--------------------------------------------------------------------------
*/

app.get(
    "/qr",
    async (req, res) => {

        if (whatsappConnected) {

            return res.send(`
                <!DOCTYPE html>
                <html lang="pt-BR">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>WhatsApp conectado</title>
                </head>

                <body style="
                    font-family: Arial, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    background: #f5f5f5;
                ">

                    <div style="
                        background: white;
                        padding: 40px;
                        border-radius: 20px;
                        text-align: center;
                        box-shadow: 0 10px 40px rgba(0,0,0,.08);
                    ">

                        <h1>WhatsApp conectado</h1>

                        <p>
                            O bot já está conectado ao WhatsApp.
                        </p>

                    </div>

                </body>
                </html>
            `);
        }

        if (!qrCodeData) {

            return res.status(404).send(`
                <!DOCTYPE html>
                <html lang="pt-BR">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <meta http-equiv="refresh" content="5">
                    <title>QR Code</title>
                </head>

                <body style="
                    font-family: Arial, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    background: #f5f5f5;
                ">

                    <div style="
                        background: white;
                        padding: 40px;
                        border-radius: 20px;
                        text-align: center;
                        box-shadow: 0 10px 40px rgba(0,0,0,.08);
                    ">

                        <h1>QR Code ainda não disponível</h1>

                        <p>
                            Aguarde alguns segundos...
                        </p>

                        <p>
                            A página será atualizada automaticamente.
                        </p>

                    </div>

                </body>
                </html>
            `);
        }

        try {

            const imagem =
                await QRCode.toDataURL(
                    qrCodeData
                );

            res.send(`
                <!DOCTYPE html>

                <html lang="pt-BR">

                <head>

                    <meta charset="UTF-8">

                    <meta
                        name="viewport"
                        content="width=device-width, initial-scale=1.0"
                    >

                    <meta
                        http-equiv="refresh"
                        content="10"
                    >

                    <title>Conectar WhatsApp</title>

                </head>

                <body style="
                    font-family: Arial, sans-serif;
                    background: #f5f5f5;
                    margin: 0;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                ">

                    <div style="
                        background: white;
                        padding: 35px;
                        border-radius: 20px;
                        text-align: center;
                        max-width: 420px;
                        width: calc(100% - 40px);
                        box-shadow: 0 10px 40px rgba(0,0,0,.08);
                    ">

                        <h1>
                            Conectar WhatsApp
                        </h1>

                        <p>
                            Abra o WhatsApp no celular,
                            entre em Dispositivos conectados
                            e escaneie o QR Code.
                        </p>

                        <img
                            src="${imagem}"
                            alt="QR Code do WhatsApp"
                            style="
                                width: 300px;
                                max-width: 100%;
                                height: auto;
                                margin-top: 20px;
                            "
                        >

                        <p style="
                            color: #666;
                            margin-top: 20px;
                        ">
                            A página atualiza automaticamente.
                        </p>

                    </div>

                </body>

                </html>
            `);

        } catch (erro) {

            console.error(
                "Erro ao gerar QR Code:",
                erro
            );

            res.status(500).json({
                sucesso: false,
                erro: "Não foi possível gerar o QR Code."
            });
        }
    }
);


/*
|--------------------------------------------------------------------------
| Enviar notificação
|--------------------------------------------------------------------------
*/

app.post(
    "/notify",
    verificarApiKey,
    async (req, res) => {

        try {

            if (!whatsappConnected) {

                return res.status(503).json({
                    sucesso: false,
                    erro: "WhatsApp ainda não está conectado."
                });
            }

            if (!WHATSAPP_NUMBER) {

                return res.status(500).json({
                    sucesso: false,
                    erro: "WHATSAPP_NUMBER não configurado."
                });
            }

            const evento =
                req.body;

            if (!evento || typeof evento !== "object") {

                return res.status(400).json({
                    sucesso: false,
                    erro: "Evento inválido."
                });
            }

            const mensagem =
                criarMensagem(evento);

            const numero =
                WHATSAPP_NUMBER
                    .replace(/\D/g, "");

            const jid =
                `${numero}@s.whatsapp.net`;

            console.log("");
            console.log(
                "📨 Enviando notificação..."
            );

            console.log(
                `Para: ${numero}`
            );

            console.log(
                `Evento: ${evento.nome || "Sem nome"}`
            );

            const resultado =
                await sock.sendMessage(
                    jid,
                    {
                        text: mensagem
                    }
                );

            console.log(
                "✅ Mensagem enviada."
            );

            return res.json({
                sucesso: true,
                mensagem: "Notificação enviada.",
                id:
                    resultado?.key?.id || null
            });

        } catch (erro) {

            console.error(
                "❌ Erro ao enviar mensagem:",
                erro
            );

            return res.status(500).json({
                sucesso: false,
                erro: "Erro ao enviar mensagem."
            });
        }
    }
);


/*
|--------------------------------------------------------------------------
| Inicialização HTTP
|--------------------------------------------------------------------------
*/

app.listen(
    PORT,
    "0.0.0.0",
    () => {

        console.log("");
        console.log(
            `🌐 Servidor HTTP iniciado na porta ${PORT}`
        );

        console.log(
            `📡 Endpoint: /notify`
        );

        console.log(
            `📱 QR Code: /qr`
        );

        console.log("");
    }
);


/*
|--------------------------------------------------------------------------
| Inicialização WhatsApp
|--------------------------------------------------------------------------
*/

conectarWhatsApp()
    .catch(
        (erro) => {

            console.error(
                "❌ Erro ao iniciar WhatsApp:",
                erro
            );

            process.exit(1);
        }
    );
