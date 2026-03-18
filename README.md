# DigitalDash Time (app_digital_dash_time)

Sistema supervisório de linha de produção com IoT, Web e análise de ciclo.

## 🚀 Visão Geral

DigitalDash Time integra ESP32, leitores NFC/RFID, impressoras Zebra e interface web para:
- Rastreamento de pallets/produtos
- Controle de operadores (alocação, check-in/out)
- Gestão de ordens de produção
- Monitoramento em tempo real via Socket.IO
- Cálculo de tempos de ciclo, preparação, montagem, espera e transferência
- Histórico em CSV/SQLite

## 🧩 Arquitetura

- `main.py` - ponto de entrada, cria Flask, MQTT, SocketIO e supervisor.
- `app/supervisor.py` - controle do ciclo de produção e projeções.
- `auxiliares/` - lógica de negócios, rotas, MQTT, classes e utilidades:
  - `classes.py` - `Posto`, `Tabela_Assoc`, máquina de estados (BS, BT1, BT2, BD).
  - `routes.py` - rotas web e API de controle.
  - `mqtt_handlers.py` - mapeia payload MQTT para postos/ações.
  - `socketio_handlers.py` - eventos de UI em tempo real.
  - `associacao.py` - persistência de `palete <-> produto`.
  - `cadastro_funcionarios.py` - CRUD de colaboradores.
  - `dashboard_producao.py` - visão do fluxo e métricas.
  - `cadastro_ordens.py` - ordem de produção (Meta, Produto, Status).

## 🛠️ Recursos Principais

1. Máquina de estados por posto:
   - IDLE (0)
   - BS (1) - início do pallet
   - BT1 (2) - início montagem
   - BT2 (3) - fim montagem
   - BD (4) - saída do posto

2. Dados em tempo real via SocketIO para frontend.
3. Integrado a MQTT => tópico padrão `rastreio_nfc/esp32/posto_<i>/dispositivo`.
4. Impressão de QR code / ZPL (não em modo debug).
5. Persistência em 
   - CSV: `POSTO_0.csv`, `associacoes.csv`, etc.
   - SQLite: funcionários, ordens, produção.
6. Controle de produção:
   - Start (com ordem aberta)
   - Restart/reiniciar sistema
   - Stop (fecha ordem e desliga produção)

## 📁 Estrutura de Pastas

- `app/` - gateway SocketIO + supervisor
- `auxiliares/` - backend lógico, DB, associações
- `static/` - JS/CSS/fotos funcionários, front web
- `templates/` - Jinja2 HTML: `controle.html`, `supervisorio.html`, `posto.html`, `posto0.html`
- `dados_producao/` - produção histórica por ano
- `.env` - configurações de ambiente

## ⚙️ Configuração

1. Crie ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Variáveis em `.env`:

```ini
IP_EXT=0.0.0.0
PORT_EXT=7000
MQTT_BROKER_URL=127.0.0.1
MQTT_BROKER_PORT=1883
MQTT_USERNAME=seu_usuario
MQTT_PASSWORD=sua_senha
MQTT_CLIENT_ID=Supervisor_PC
NUMERO_POSTOS=2
ADMIN_DELETE_PASSWORD=senha_mestra
DEBUG=1
```

3. Defina `auxiliares/configuracoes.py` com:
- `cartao_palete` (mapeamento NFC -> palete)
- `ultimo_posto_bios` (inteiro último posto)

## ▶️ Executar

```bash
python main.py
```

Acesse:
- `http://localhost:7000/controle` (painel de controle)
- `http://localhost:7000/supervisorio` (supervisório)
- `http://localhost:7000/posto/0` + `.../posto/1` etc.

## 📡 MQTT

- tópico: `rastreio_nfc/esp32/posto_<n>/dispositivo`
- payloads suportados:
  - `BS`, `BT1`, `BT2`, `BD`
  - NFC: UID da tag para palete
- emit para comandos internos: `ControleProducao_DD` e tópicos de planta.

## 🧪 API de Controle

- `GET /ping`
- `POST /comando` com payload JSON:
  - `imprime_produto`
- `POST /enviar` com objeto `{tipo:'comando', mensagem:'Start'|'Restart'|'Stop', ordem:'...'}`

## 🧾 Lógica de Produção

1. `Start` exige ordem de produção aberta e meta > 0.
2. Atualiza estado de postos prontos e arma produção no `State`.
3. `Stop` finaliza ordem no DB, salva log, reinicia sistema.
4. Posto 0 faz associação de palete -> produto quando recebe NFC.
5. Postos usam `Posto.tratamento_dispositivo` para transições de estados.

## 📌 Contribuições

- use branches `feature/...`
- adicione testes para `auxiliares/testes` (se existente)
- garanta compatibilidade com `eventlet` e `flask-socketio`

## 🔧 Dicas Rápidas

- Execute Mosquitto local ou remota antes de rodar o app.
- Para debug rápido: `DEBUG=1` para evitar impressora ZPL.
- Reimponha`NUMERO_POSTOS` e atualize `ultimo_posto_bios` ao alterar postos.
- Backup dos CSVs em `dados_producao/YYYY`

---

> Desenvolvido por Edson Alves. Atualizado automaticamente via ferramenta de manutenção.
