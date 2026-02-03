const socket = io();

function stateIndex(s){
    return (s && typeof s==='object' && 'value' in s) ? s.value : s;
}

const DEFAULT_STATE_TITLES = {
    0:"Arrival",
    1:"Preparo",
    2:"Montagem",
    3:"Espera"
};

function titleFor(s){
    return DEFAULT_STATE_TITLES[stateIndex(s)] || "Arrival";
}

function stateName(s){
    return ["IDLE","BS","BT1","BT2","BD"][stateIndex(s)] || "IDLE";
}

// Entrar apenas na sala do posto
socket.on("connect", () => {
    socket.emit("join_posto", { posto: `posto_${POSTO_ID}` });
    socket.emit("posto/request_snapshot", { posto:`posto_${POSTO_ID}` });
});

// atualizar UI do posto
function updateUI(s){
    if(!s) return;

    document.getElementById("titulo-etapa").textContent = titleFor(s.state);
    document.getElementById("produto").textContent = s.produto ?? "--";
    document.getElementById("modelo").textContent  = s.modelo ?? "--";
    document.getElementById("estado").textContent  = stateName(s.state);

    // operador
    let nome =
        s.funcionario_nome ||
        s.operador_nome ||
        (s.funcionario && s.funcionario.nome) ||
        "Não alocado";

    let img =
        s.funcionario_imagem ||
        s.operador_imagem ||
        (s.funcionario && s.funcionario.imagem);

    document.getElementById("op-nome").textContent = nome;

    const foto = document.getElementById("op-foto");
    if(img){
        let url = img;

        // Se vier "static/..." → força "/static/..."
        if (!url.startsWith("/")) {
            url = "/" + url;
        }

        foto.style.backgroundImage = `url("${url}")`;
        foto.textContent = "";
    }else{
        foto.textContent = nome[0] ?? "?";
        foto.style.backgroundImage = "";
    }

    // Progresso (se você enviar pelo backend)
    if(s.mats_percent !== undefined){
        document.getElementById("mats-texto").textContent = s.mats_percent + "%";
    }
}


function normalizarFotoUrl(foto) {
  if (!foto) return null;

  // Se já for URL absoluta, mantém
  if (/^https?:\/\//i.test(foto)) return foto;

  // Garante barra inicial (ex: "static/..." -> "/static/...")
  return foto.startsWith("/") ? foto : "/" + foto;
}

function aplicarOperadorUI({ nomeElId, avatarElId, operador }) {
  const nomeEl = document.getElementById(nomeElId);
  const avatarEl = document.getElementById(avatarElId);
  if (!nomeEl || !avatarEl) return;

  if (operador && operador.nome) {
    const nome = operador.nome.trim();
    nomeEl.textContent = nome;

    const fotoUrl = normalizarFotoUrl(operador.foto || operador.imagem);
    if (fotoUrl) {
      avatarEl.style.backgroundImage = `url("${fotoUrl}")`;
      avatarEl.textContent = "";
    } else {
      avatarEl.style.backgroundImage = "";
      avatarEl.textContent = nome ? nome[0].toUpperCase() : "?";
    }
  } else {
    nomeEl.textContent = "Não alocado";
    avatarEl.style.backgroundImage = "";
    avatarEl.textContent = "?";
  }
}

socket.on("global/operador_update", (data) => {
  // data.posto esperado: "posto_0", "posto_1", ...
  if (!data || data.posto !== `posto_${POSTO_ID}`) return;

  aplicarOperadorUI({
    nomeElId: "op-nome",
    avatarElId: "op-foto",
    operador: data.operador
  });
});

socket.on("global/sync_data", (data) => {
  // data.operadores esperado: { "posto_0": {...}, "posto_1": null, ... }
  if (!data || !data.operadores) return;

  const op = data.operadores[`posto_${POSTO_ID}`];
  aplicarOperadorUI({
    nomeElId: "op-nome",
    avatarElId: "op-foto",
    operador: op
  });
});


// eventos
socket.on("posto/state_snapshot", (s)=>{
    if(s.id === `posto_${POSTO_ID}`) updateUI(s);
});

socket.on("posto/state_changed", (s)=>{
    if(s.id === `posto_${POSTO_ID}`) updateUI(s);
});

// Logs
socket.on("posto/log", (data)=>{
    if(data.id !== `posto_${POSTO_ID}`) return;

    const box = document.getElementById("log-box");
    const p = document.createElement("div");
    p.textContent = data.texto;
    box.appendChild(p);
});
