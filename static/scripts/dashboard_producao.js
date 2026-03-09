let dadosExperiencia = []
let chartPostos
let chartExperiencia

async function carregarDados(){

    const logs = await fetch("/api/log_producao").then(r=>r.json())
    const sessoes = await fetch("/api/sessoes_trabalho").then(r=>r.json())
    dadosExperiencia = await fetch("/api/experiencia_operador_produto").then(r=>r.json())

    atualizarCards(logs)

    tabelaLogs(logs)

    tabelaSessoes(sessoes)

    graficoPostos(sessoes)

    popularFiltros()

    atualizarTabelaExperiencia()

    atualizarGraficoExperiencia()

}

async function carregarOperadoresAtivos(){

    const resp = await fetch("/api/operadores_ativos")
    const data = await resp.json()

    document.getElementById("operadoresAtivos").innerText = data.operadores
}

function atualizarCards(logs){

    document.getElementById("totalOrdens").innerText = logs.length

    const finalizadas = logs.filter(l=>l.status=="FINALIZADA").length

    const armadas = logs.filter(l=>l.status=="ARMED").length
    
    const iniciadas = logs.filter(l=>l.status=="INICIADA").length

    document.getElementById("finalizadas").innerText = finalizadas

    document.getElementById("armadas").innerText = armadas

    document.getElementById("iniciadas").innerText = iniciadas

}

function tabelaLogs(logs){

    const tbody = document.querySelector("#tabelaLog tbody")

    tbody.innerHTML=""

    logs.forEach(l=>{

        const tr = document.createElement("tr")

        const statusClasses = {
            "ARMED": "status-armed",
            "ON": "status-on",
            "FINALIZADA": "status-finalizada"
        }

        const statusClass = statusClasses[l.status] || "status-default"

        tr.innerHTML=`
        <td>${l.id}</td>
        <td>${l.ordem_codigo}</td>
        <td class="${statusClass}">
        ${l.status}
        </td>
        <td>${formatarData(l.armada_em)}</td>
        <td>${formatarData(l.inicio_em)}</td>
        <td>${formatarData(l.fim_em)}</td>
        `

        tbody.appendChild(tr)

    })

}

function tabelaSessoes(sessoes){

    const tbody = document.querySelector("#tabelaSessoes tbody")

    tbody.innerHTML=""

    sessoes.slice(0,50).forEach(s=>{

        const tr = document.createElement("tr")

        tr.innerHTML=`
        <td>${s.funcionario}</td>
        <td>${formatarPosto(s.posto_nome)}</td>
        <td>${formatarData(s.horario_entrada)}</td>
        <td>${formatarData(s.horario_saida)}</td>
        <td>${formatarDuracao(s.duracao_segundos) ?? ""}</td>
        `

        tbody.appendChild(tr)

    })

}

function graficoPostos(sessoes){

    const contagem = {}

    sessoes.forEach(s=>{

        if(!contagem[s.posto_nome])
            contagem[s.posto_nome]=0

        contagem[s.posto_nome]++

    })

    // ordena pelos números do posto
    const postosOrdenados = Object.keys(contagem)
        .sort((a,b)=>{
            const na = parseInt(a.match(/\d+/))
            const nb = parseInt(b.match(/\d+/))
            return na - nb
        })

    const labels = postosOrdenados.map(p => formatarPosto(p))
    const valores = postosOrdenados.map(p => contagem[p])

    const ctx = document.getElementById("graficoPostos")

    if(chartPostos) chartPostos.destroy()
    chartPostos = new Chart(ctx,{

        type:"bar",

        data:{
            labels: labels,
            datasets:[{
                label:"Sessões por posto",
                data: valores
            }]
        },

        options:{
            plugins:{
                legend:{
                    display:false
                }
            },
            scales:{
                x:{
                    ticks:{
                        color:"#e5e7eb"
                    }
                },
                y:{
                    ticks:{
                        color:"#e5e7eb"
                    }
                }
            }
        }

    })

}

function popularFiltros(){

    const operadores = [...new Set(dadosExperiencia.map(d=>d.funcionario))]
    const produtos = [...new Set(dadosExperiencia.map(d=>d.produto))]

    operadores.forEach(o=>{

        const opt=document.createElement("option")
        opt.value=o
        opt.text=o
        document.getElementById("filtroOperador").appendChild(opt)

    })

    produtos.forEach(p=>{

        const opt=document.createElement("option")
        opt.value=p
        opt.text=p
        document.getElementById("filtroProduto").appendChild(opt)

    })

}

function filtrarExperiencia(){

    const operador=document.getElementById("filtroOperador").value
    const produto=document.getElementById("filtroProduto").value

    return dadosExperiencia.filter(d=>{

        if(operador && d.funcionario!==operador) return false
        if(produto && d.produto!==produto) return false

        return true

    })

}

function atualizarTabelaExperiencia(){

    const dados=filtrarExperiencia()

    const tbody=document.querySelector("#tabelaExperiencia tbody")

    tbody.innerHTML=""

    dados.forEach(d=>{

        const tr=document.createElement("tr")

        tr.innerHTML=`
        <td>${d.funcionario}</td>
        <td>${d.produto}</td>
        <td>${d.horas.toFixed(2)}</td>
        `

        tbody.appendChild(tr)

    })

}

function atualizarGraficoExperiencia(){

    const dados=filtrarExperiencia()

    const labels=dados.map(d=>d.produto)
    const valores=dados.map(d=>d.horas)

    const ctx=document.getElementById("graficoExperiencia")

    if(chartExperiencia) chartExperiencia.destroy()

    chartExperiencia = new Chart(ctx,{

        type:"bar",

        data:{
            labels:labels,
            datasets:[{
                label:"Horas de experiência",
                data:valores
            }]
        }

    })

}

function formatarData(dt){

    if(!dt) return ""

    const d = new Date(dt)

    return d.toLocaleString("pt-BR",{
        day:"2-digit",
        month:"2-digit",
        hour:"2-digit",
        minute:"2-digit",
        second:"2-digit"
    })

}

function formatarPosto(posto){

    if(!posto) return ""

    const match = posto.match(/posto_(\d+)/i)

    if(match){
        return `Posto ${match[1]}`
    }

    return posto
}

function formatarDuracao(segundos){

    if(segundos === null || segundos === undefined) return "";

    segundos = Math.floor(segundos);

    const h = Math.floor(segundos / 3600);
    const m = Math.floor((segundos % 3600) / 60);
    const s = segundos % 60;

    const hh = String(h).padStart(2,'0');
    const mm = String(m).padStart(2,'0');
    const ss = String(s).padStart(2,'0');

    return `${hh}:${mm}:${ss}`;
}

document.getElementById("filtroOperador").addEventListener("change",()=>{

    atualizarTabelaExperiencia()
    atualizarGraficoExperiencia()

})

document.getElementById("filtroProduto").addEventListener("change",()=>{

    atualizarTabelaExperiencia()
    atualizarGraficoExperiencia()

})

carregarDados()
carregarOperadoresAtivos()