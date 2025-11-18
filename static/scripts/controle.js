const socket = io();

// Envia comandos simples (start/restart/stop)
function enviarComando(comando) {
    let valorInteiro = null;

    if (comando === 'Start') {
        const input = document.getElementById('valor-inteiro');
        const bruto = input.value.trim();
        const numero = Number(bruto);

        if (
            bruto === '' ||
            Number.isNaN(numero) ||
            !Number.isInteger(numero) ||
            numero <= 0
        ) {
            mostrarPopup(
                'Informe um número inteiro válido maior que zero antes de iniciar o sistema.',
                '#b91c1c',
                4200
            );
            input.focus();
            return;
        }

        valorInteiro = numero;
    }

    const payload = {
        tipo: 'comando',
        mensagem: comando
    };

    if (comando === 'Start' && valorInteiro !== null) {
        payload.valor_inteiro = valorInteiro;
    }

    fetch('/enviar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        atualizarStatus(data);
        if (comando === 'Restart') {
            if (typeof bloquearCampos === 'function') bloquearCampos(false);
            if (typeof bloquearBotoes === 'function') bloquearBotoes(false);
        }
    })
    .catch(() => mostrarErro());
}

socket.on('atualiza_status_producao', data => {
    const elemento = document.getElementById('status-indicador');
    if (data.status === true) {
        elemento.textContent = 'Ligada 🟢';
        elemento.style.color = '#22c55e';
        elemento.style.borderColor = 'rgba(34,197,94,0.7)';
        elemento.style.background = 'rgba(34,197,94,0.12)';
    } else {
        elemento.textContent = 'Desligada 🔴';
        elemento.style.color = '#f97373';
        elemento.style.borderColor = 'rgba(248,113,113,0.7)';
        elemento.style.background = 'rgba(248,113,113,0.12)';
    }
});

function atualizarStatus(data) {
    const statusDiv = document.getElementById('status');

    if (data.status === 'sucesso') {
        statusDiv.textContent = data.mensagem || "✅ Mensagem enviada com sucesso.";
        statusDiv.style.color = "#4ade80";
    } else {
        statusDiv.textContent = "❌ Erro ao enviar.";
        statusDiv.style.color = "#f97373";
    }
}

function mostrarErro() {
    const status = document.getElementById('status');
    status.textContent = "❌ Erro na comunicação com o servidor.";
    status.style.color = "#f97373";
}

async function checarPing() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);

    try {
        const resp = await fetch("/ping", { signal: controller.signal });
        clearTimeout(timeout);

        if (!resp.ok) throw new Error(resp.status);

        console.log("Servidor ok, recarregando...");
        location.reload();
    } catch (e) {
        console.warn("Servidor indisponível, tentando novamente...");
        setTimeout(checarPing, 1000);
    }
}

socket.on("disconnect", () => {
    console.warn("Socket.IO desconectado, iniciando checagem...");
    checarPing();
});

socket.on("connect", () => {
    console.log("Socket.IO reconectado!");
});

function validarAlocacao() {
    const selects = document.querySelectorAll('select[id^="posto_"]');
    const usados = new Set();

    for (const sel of selects) {
        const valor = sel.value;
        if (!valor) continue;

        if (usados.has(valor)) {
            alert("O mesmo funcionário não pode ser atribuído a mais de um posto.");
            return false;
        }
        usados.add(valor);
    }

    return true;
}

function mostrarPopup(mensagem, cor = '#333', duracao_ms = 3000) {
    const popup = document.getElementById('popup-aviso');
    popup.textContent = mensagem;
    popup.style.backgroundColor = cor;
    popup.style.display = 'block';

    setTimeout(() => {
        popup.style.display = 'none';
    }, duracao_ms);
}

socket.on('aviso_lista_func', data => {
    mostrarPopup(data.mensagem, data.cor, data.tempo);
});

socket.on('alerta_geral', data => {
    mostrarPopup(data.mensagem, data.cor, data.tempo);
});