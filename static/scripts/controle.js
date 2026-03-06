const socket = io();

function getOrdemSelecionada() {
    const select = document.getElementById("ordem_select");
    if (!select) return null;
    const codigo = (select.value || "").trim();
    return codigo || null;
}

function atualizarMetaUI() {
    const select = document.getElementById("ordem_select");
    const metaInput = document.getElementById("meta_ordem");
    if (!select || !metaInput) return;

    const opt = select.options[select.selectedIndex];
    const meta = opt ? opt.getAttribute("data-meta") : null;

    if (!select.value) {
        metaInput.value = "";
        metaInput.placeholder = "Selecione uma OP";
        return;
    }

    metaInput.value = meta || 0;
}

document.addEventListener("DOMContentLoaded", () => {
    const select = document.getElementById("ordem_select");
    if (select) {
        select.addEventListener("change", atualizarMetaUI);
        atualizarMetaUI();
    }
});

// Envia comandos simples (start/restart/stop)
function enviarComando(comando) {
    if (comando === 'Start') {
        const ordemCodigo = getOrdemSelecionada();
        if (!ordemCodigo) {
            mostrarPopup(
                'Selecione uma Ordem de Produção antes de iniciar.',
                '#b91c1c',
                3500
            );
            return;
        }

    }

    const payload = {
        tipo: 'comando',
        mensagem: comando
    };

    if (comando === 'Start') {
        payload.ordem = getOrdemSelecionada();
    }

    if (comando === 'Restart') {
        const ordemCodigo = getOrdemSelecionada();
        if (!ordemCodigo) {
            payload.ordem = null;
        } else {
            payload.ordem = ordemCodigo;
        }
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
    const status = data.status;
    const elemento = document.getElementById('status-indicador');
    if (status === "ON") {
        elemento.textContent = 'Ligada 🟢';
        elemento.style.color = '#22c55e';
        elemento.style.borderColor = 'rgba(34,197,94,0.7)';
        elemento.style.background = 'rgba(34,197,94,0.12)';
    } else if (status === "OFF") {
        elemento.textContent = 'Desligada 🔴';
        elemento.style.color = '#f97373';
        elemento.style.borderColor = 'rgba(248,113,113,0.7)';
        elemento.style.background = 'rgba(248,113,113,0.12)';
    } else if (status === "ARMED") {
        elemento.textContent = 'Armada 🟡';
        elemento.style.color = '#f59e0b';
        elemento.style.borderColor = 'rgba(245,158,11,0.7)';
        elemento.style.background = 'rgba(245,158,11,0.12)';
    }
});

function atualizarStatus(data) {

    const el = document.getElementById("status")

    if (data.status === 'sucesso') {
        el.style.color = "#4ade80"
        setStatus(data.mensagem || "Mensagem enviada com sucesso")
    } else {
        el.style.color = "#f97373"
        setStatus("Erro ao enviar comando")
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

let statusTimer = null

function setStatus(msg){

    const el = document.getElementById("status")

    el.textContent = `Status: ${msg}`

    if(statusTimer)
        clearTimeout(statusTimer)

    statusTimer = setTimeout(()=>{
        el.textContent = ""
    },5000)

}