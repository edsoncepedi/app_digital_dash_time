// Função para validar o código do produto (prototipado como "PTT01" até "PTT30")
function verificaCodQrPrototipo(code) {
    if (code.length === 10) {
        const dia = parseInt(code.slice(0, 3), 10);
        const cp = code.slice(3, 5);
        const prot = parseInt(code.slice(5, 7), 10);
        const sn = parseInt(code.slice(7, 10), 10);

        return (
            !isNaN(dia) && dia >= 1 && dia <= 366 &&
            cp === "CP" &&
            !isNaN(prot) && prot >= 1 && prot <= 99 &&
            !isNaN(sn) && sn >= 1 && sn <= 999
        );
    }
    return false;
}

// Função para validar o código do palete (prototipado como "PLT01" até "PLT26")
function verificaCodQrPalete(code) {
    if (code.length === 5) {
        const tag = code.slice(0, 3);
        const num = parseInt(code.slice(3), 10);
        return tag === "PLT" && !isNaN(num) && num > 0 && num <= 26;
    }
    return false;
}
// Função utilitária para exibir mensagens no <div id="resposta"> com cor personalizada
function mostrarResposta(mensagem, cor) {
    const respostaDiv = document.getElementById("resposta");
    respostaDiv.textContent = mensagem;
    respostaDiv.style.color = cor;
}

// Conexão com o servidor Socket.IO
const socket = io();

socket.on("connect", () => {
    mostrarResposta("", "green");
    document.getElementById("produto").value = "";
    document.getElementById("palete").value = "";
});

socket.emit('pagina_associacao_connect');

socket.on('atualiza_status_producao', data => {
  const elemento = document.getElementById('status-indicador');
  if (data.status === true) {
    elemento.textContent = 'Ligada 🟢'; // Mostra status positivo com emoji verde
    elemento.style.color = 'green';        // Muda a cor do texto para verde
  } else {
    elemento.textContent = 'Desligada 🔴'; // Mostra status negativo com emoji vermelho
    elemento.style.color = 'red';             // Muda a cor do texto para vermelho
  }
  });

// Receber código do produto e preencher o campo automaticamente
socket.on('add_produto_impresso', data => {
const inputProduto = document.getElementById('produto');
inputProduto.value = data.codigo;
mostrarResposta("Código de produto recebido!", "green");
checkAndAdvance();
});

socket.on('add_palete_lido', data => {
const inputPalete = document.getElementById('palete');
inputPalete.value = data.codigo;
mostrarResposta("Código de palete recebido!", "green");
checkAndAdvance();
});

socket.on('aviso_ao_operador_assoc', data => {
    mostrarPopup(data.mensagem, data.cor, data.tempo);
});

socket.on('alerta_geral', data => {
    mostrarPopup(data.mensagem, data.cor, data.tempo);
});

function mostrarPopup(mensagem, cor = '#333', duracao_ms = 3000) {
    const popup = document.getElementById('popup-aviso');
    popup.textContent = mensagem;
    popup.style.backgroundColor = cor;
    popup.style.display = 'block';

    setTimeout(() => {
        popup.style.display = 'none';
    }, duracao_ms);
}

socket.on('palete_recebido', data => {
    const palete = document.getElementById("palete").value.trim();
    if (verificaCodQrPalete(palete)) {
        socket.emit('campo_palete', { palete: true });
    }else {
        socket.emit('campo_palete', { palete: false });
    }
});

// Função principal que lida com a navegação e envio após validação
async function checkAndAdvance() {
    // Captura os valores dos campos
    const produto = document.getElementById("produto").value.trim();
    const palete = document.getElementById("palete").value.trim();

    // Se ambos os códigos forem válidos, envia para o backend
    if (verificaCodQrPrototipo(produto) && verificaCodQrPalete(palete)) {
        try {
            const response = await fetch("/associacao/submit", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ produto, palete }) // Dados enviados como JSON
            });

            const resposta = await response.text();
            const respostaDiv = document.getElementById("resposta");

            // Analisa a resposta recebida do servidor
            // Se a resposta for um Sucesso
            if (resposta.includes("Sucesso")) {
                // Mostra o aviso de concluído no Front
                respostaDiv.textContent = resposta;
                respostaDiv.style.color = "green";

                const inputProduto = document.getElementById('produto');

                // Limpando os campos
                document.getElementById("produto").value = "";
                document.getElementById("palete").value = "";

            // Se o palete já estiver vinculado
            } else if (resposta.includes("ERRO: PALETE JÁ VINCULADO")) {
                // Mostra a mensagem de erro
                respostaDiv.textContent = resposta;
                respostaDiv.style.color = "red";
                // Limpa o campo de palete e manda o cursor para o campo de palete novamente
                document.getElementById("palete").value = "";
                document.getElementById("palete").focus();
            // Para qualquer outro erro de associação.
            } else {
                // Mostra a mensagem de erro
                respostaDiv.textContent = resposta;
                respostaDiv.style.color = "red";
                // Limpa os campos e inicia novamente
                document.getElementById("produto").value = "";
                document.getElementById("palete").value = "";
                document.getElementById("palete").disabled = true
            }
        } catch (error) {
            // Captura erro de rede ou problema na requisição
            const respostaDiv = document.getElementById("resposta");
            respostaDiv.textContent = "Erro ao enviar dados: " + error;
            respostaDiv.style.color = "red";
        }
    }
}

let servidorIndisponivel = false;

async function checarPing() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000); // 1 segundo de limite

    try {
        const resp = await fetch("/ping", { signal: controller.signal });
        clearTimeout(timeout);

        if (!resp.ok) throw new Error(resp.status);

        console.log("Servidor ok, recarregando...");
        location.reload(); // só recarrega quando o servidor está realmente no ar
    } catch (e) {
        console.warn("Servidor indisponível, tentando novamente...");

        if (!servidorIndisponivel) {
            servidorIndisponivel = true;
            mostrarPopup("Servidor indisponível. Tentando se reconectar!", "#dc3545", 9999999);
        }

        setTimeout(checarPing, 1000); // tenta de novo em 1s
    }
}

// quando desconectar, ativa monitoramento
socket.on("disconnect", () => {
    console.warn("Socket.IO desconectado, iniciando checagem...");
    checarPing();
});

// quando reconectar, cancela monitoramento
socket.on("connect", () => {
    console.log("Socket.IO reconectado!");
});