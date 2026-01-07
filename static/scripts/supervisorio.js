/* ===================== CONFIG ===================== */
window.NUM_POSTOS = window.NUM_POSTOS ?? 3;
let meta_prod = 100;
let currentProd = 0; // guarda produção atual

// Mapeamento DINÂMICO: estado da máquina -> título do card
// Estados esperados: 0=IDLE, 1=BS, 2=BT1, 3=BT2, 4=BD
const DEFAULT_STATE_TITLES = {
  0: "Arrival",   // IDLE
  1: "Preparo",   // BS
  2: "Montagem",  // BT1
  3: "Espera"     // BT2
};
// Se quiser sobrescrever: window.STATE_TITLES = { ... }
/* ================================================== */

// Helpers de estado
const stateIndex = (s) => (s && typeof s==='object' && 'value' in s) ? s.value : s;
const stateName  = (s) => ['IDLE','BS','BT1','BT2','BD'][stateIndex(s)] || 'IDLE';
const titleFor   = (s) => (window.STATE_TITLES || DEFAULT_STATE_TITLES)[stateIndex(s)] || 'Arrival';
const titleClass = (title) => {
  title = (title || '').toLowerCase();
  if(title.startsWith('espe'))  return 'espera';
  if(title.startsWith('mont'))  return 'montagem';
  if(title.startsWith('prep'))  return 'preparo';
  return 'arrival';
};
const fmtSec = (v) => (v==null || Number.isNaN(v)) ? '--' : (typeof v==='number' ? v.toFixed(2)+'s' : v);

// Constrói um card de posto
function buildCard(n){
  const el = document.createElement('div');
  el.className = 'card posto';
  el.id = `posto_${n}`;
  const initialTitle = 'Arrival';
  el.innerHTML = `
    <div class="tag ${titleClass(initialTitle)}" id="p${n}-tag">
      <div class="head" id="p${n}-head">${initialTitle}</div>
    </div>
    <div style="height:56px"></div>

    <div class="posto-label">Posto ${n}</div>

    <div class="row"><span>Produto:</span><span id="p${n}-produto" class="chip">--</span></div>
    <div class="row"><span>Modelo:</span><span id="p${n}-modelo" class="chip muted">--</span></div>
    <div class="row"><span>Estado:</span><span id="p${n}-estado" class="chip">IDLE</span></div>

    <div class="operator-row">
      <span>Operador:</span>
      <div class="operator">
        <div class="operator-avatar" id="p${n}-op-avatar">?</div>
        <span class="operator-name" id="p${n}-op-nome">Não alocado</span>
      </div>
    </div>

    `;
  return el;
}

// Monta o grid
const grid = document.getElementById('grid-postos');
for(let n=0; n<window.NUM_POSTOS; n++){
  grid.appendChild(buildCard(n));
}

// Socket.IO
const socket = io();

// Entra nas salas de cada posto e pede snapshot
function joinAll(){
  for(let n=0; n<window.NUM_POSTOS; n++){
    socket.emit('join_posto', { posto: `posto_${n}` });
  }
}

// SINCRONIZAÇÃO GLOBAL E DOS POSTOS
socket.on('connect', () => {
    joinAll(); 
    console.log("Conectado. Solicitando sincronização global...");
    socket.emit('global/request_sync'); 
});

// Evento disparado pelo supervisor.py quando há check-in/out
socket.on('global/operador_update', (data) => {
    console.log("Atualização de operador:", data);
    atualizarInterfaceOperador(data.posto, data.operador);
});

socket.on('global/sync_data', (data) => {
    console.log("Dados globais recebidos:", data);

    // A. Sincronizar Meta e Produção Atual
    if(data.meta !== undefined) meta_prod = data.meta;
    
    if(data.producao_atual !== undefined) {
        setKpiProducao(data.producao_atual, meta_prod);
    }
    
    // B. Sincronizar Projeção (Valor já calculado pelo Backend)
    if(data.projecao !== undefined) {
        setKpiProjecao(data.projecao);
    }

    // C. Sincronizar Order ID (Opcional)
    if(data.order_id) {
        document.getElementById("kpi-order").textContent = data.order_id;
    }

    // D. Sincronizar Cronômetro
    if (data.timer_ms !== undefined) {
        timer.set(data.timer_ms); 
    }
    
    if (data.timer_running === true) {
        timer.start(); 
    } else {
        timer.stop();
    }

    if (data.operadores) {
        Object.keys(data.operadores).forEach(postoId => {
            atualizarInterfaceOperador(postoId, data.operadores[postoId]);
        });
    }
});

// Atualização de UI a partir de um snapshot/evento
function updateFromSnapshot(s){
  if(!s || !s.id) return;
  const n = s.id.split('_')[1];
  const n_number = Number(n);
  const numPostos = Number(window.NUM_POSTOS) || 0;

  // NOTA: A atualização de produção global não é mais feita aqui
  // ela é feita pelo evento 'producao/update' que o backend emite.
  // if (n_number === numPostos - 1){ setKpiProducao(s.n_produtos, meta_prod); }

  // Título dinâmico (Montagem/Preparo/Espera) a partir do ESTADO
  const titulo = titleFor(s.state);
  const head = document.getElementById(`p${n}-head`);
  const tag  = document.getElementById(`p${n}-tag`);
  if(head) head.textContent = titulo;
  if(tag){
    tag.classList.remove('arrival','montagem','preparo','espera');
    tag.classList.add(titleClass(titulo));
  }

  // Campos básicos
  const setText = (id, txt) => { const el = document.getElementById(id); if(el) el.textContent = txt; };

  setText(`p${n}-produto`, s.produto ?? '--');
  setText(`p${n}-modelo`,  s.modelo  ?? '—'); // opcional, caso envie do backend
  setText(`p${n}-estado`,  stateName(s.state));

  // Operador (nome + foto)
  const nomeOp =
    s.funcionario_nome ||
    s.operador_nome ||
    (s.funcionario && s.funcionario.nome) ||
    null;

  const imgOp =
    s.funcionario_imagem ||
    s.operador_imagem ||
    (s.funcionario && s.funcionario.imagem) ||
    null;

  const nomeEl   = document.getElementById(`p${n}-op-nome`);
  const avatarEl = document.getElementById(`p${n}-op-avatar`);

  if (nomeEl && avatarEl){
    if (nomeOp){
      nomeEl.textContent = nomeOp;
    } else {
      nomeEl.textContent = 'Não alocado';
    }

    if (imgOp){
      // usa imagem como fundo, remove texto
      avatarEl.style.backgroundImage = `url(${imgOp})`;
      avatarEl.textContent = '';
    } else {
      avatarEl.style.backgroundImage = '';
      const inicial = (nomeOp && nomeOp.trim()) ? nomeOp.trim()[0].toUpperCase() : '?';
      avatarEl.textContent = inicial;
    }
  }
}

// Eventos do backend
socket.on('posto/state_snapshot', updateFromSnapshot);
socket.on('posto/state_changed', updateFromSnapshot);
socket.on('producao/control', data => {
  meta_prod = data.meta_producao;
  setKpiProducao(currentProd, meta_prod);
});

// NOVO EVENTO: Recebe atualização da produção e projeção já calculada do backend
socket.on('producao/update', (data) => {
    meta_prod = data.meta;
    setKpiProducao(data.atual, data.meta);
    setKpiProjecao(data.projecao); 
});


// Comandos → backend → Supervisor → Posto → MQTT
function cmd(n, command, args={}){
  socket.emit('posto/command', { posto:`posto_${n}`, cmd:command, args });
}
window.cmd = cmd; // para testar no console


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
    setTimeout(checarPing, 1000); // tenta de novo em 1s
  }
}

// quando desconectar, ativa monitoramento
socket.on("disconnect", () => {
  console.warn("Socket.IO desconectado, iniciando checagem...");
  pauseTimer();
  checarPing();
});

/* ================== CONTADOR CONTROLÁVEL ================== */

let timerInterval = null;
let elapsedMs = 0;
let running = false;
let lastTick = null;

function fmtTime(ms) {
  const hh = String(Math.floor(ms / 3600000)).padStart(2, '0');
  const mm = String(Math.floor(ms / 60000) % 60).padStart(2, '0');
  const ss = String(Math.floor(ms / 1000) % 60).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

function updateDisplay() {
  document.getElementById("kpi-time").textContent = fmtTime(elapsedMs);
}

function startTimer() {
  if (running) return;
  running = true;
  lastTick = Date.now();

  timerInterval = setInterval(() => {
    const now = Date.now();
    const delta = now - lastTick; // tempo real desde o último tick
    lastTick = now;               // atualiza referência
    elapsedMs += delta;
    updateDisplay();
  }, 1000);
}

function pauseTimer() {
  if (!running) return;
  running = false;
  clearInterval(timerInterval);
  timerInterval = null;
}

function resetTimer() {
  pauseTimer();
  elapsedMs = 0;
  updateDisplay();
}

/* Disponibiliza para o console/manual e para o backend */
window.timer = {
  start: startTimer,
  stop: pauseTimer,
  reset: resetTimer,
  set: (ms) => { elapsedMs = ms; updateDisplay(); },
  get: () => elapsedMs
};

socket.on("timer/control", (msg) => {
  if (msg.action === "start") timer.start();
  if (msg.action === "stop")  timer.stop();
  if (msg.action === "reset") timer.reset();
  if (msg.action === "set")   timer.set(msg.ms || 0);
});

/* ========= KPI Produção + Projeção (Backend-Driven) ========= */

// NOVO MÉTODO: Apenas exibe o texto da projeção que veio do Python
function setKpiProjecao(texto) {
  const projEl = document.getElementById("kpi-proj");
  if (projEl) projEl.textContent = texto || "--";
}

// MÉTODO ATUALIZADO: Não chama mais a lógica de cálculo local
function setKpiProducao(atual, meta) {
  currentProd = atual;
  document.getElementById("kpi-prod").textContent = `${atual}/${meta}`;
  // A projeção será atualizada via 'global/sync_data' ou 'producao/update'
}

// Lógica de cálculo 'function atualizarProjecao(atual, meta)' REMOVIDA
// para centralizar no backend.

function mostrarPopup(mensagem, cor = '#333', duracao_ms = 3000) {
            const popup = document.getElementById('popup-aviso');
            popup.textContent = mensagem;
            popup.style.backgroundColor = cor;
            popup.style.display = 'block';

            setTimeout(() => {
                popup.style.display = 'none';
            }, duracao_ms);
        }

socket.on('alerta_geral', data => {
    mostrarPopup(data.mensagem, data.cor, data.tempo);
});

// Função para atualizar visualmente o operador no card
function atualizarInterfaceOperador(postoId, operador) {
    const n = postoId.split('_')[1];
    const nomeEl = document.getElementById(`p${n}-op-nome`);
    const avatarEl = document.getElementById(`p${n}-op-avatar`);

    if (!nomeEl || !avatarEl) return;

    if (operador) {
        nomeEl.textContent = operador.nome;
        if (operador.foto) {
            avatarEl.style.backgroundImage = `url(/${operador.foto})`;
            avatarEl.textContent = '';
        } else {
            avatarEl.style.backgroundImage = '';
            avatarEl.textContent = operador.nome[0].toUpperCase();
        }
    } else {
        nomeEl.textContent = 'Não alocado';
        avatarEl.style.backgroundImage = '';
        avatarEl.textContent = '?';
    }
}