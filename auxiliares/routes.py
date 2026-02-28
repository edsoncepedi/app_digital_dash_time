import pandas as pd
from flask import render_template, request, jsonify, url_for, flash, redirect
from auxiliares.utils import imprime_qrcode, gera_codigo_produto, verifica_cod_produto, memoriza_produto, reiniciar_produtos, reiniciar_sistema, posto_nome_para_id
from auxiliares.banco_post import verifica_conexao_banco, Conectar_DB, inserir_dados, consulta_paletes
from auxiliares.associacao import inicializa_funcionario
from auxiliares.models_ordens import OrdemProducao
from auxiliares.log_producao_repo import LogProducaoRepo
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from time import sleep
import auxiliares.classes as classes
from threading import Event
from auxiliares.socketio_handlers import tem_cliente_associacao
from auxiliares.configuracoes import cartao_palete
from auxiliares.configuracoes import ultimo_posto_bios
evento_resposta = Event()
import numpy as np
from dotenv import load_dotenv
import os

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

debug_mode=bool(int(os.getenv('DEBUG')))
print(f"Debug mode: {debug_mode}")

Funcionario, Posto, SessaoTrabalho = inicializa_funcionario()

db = Conectar_DB('funcionarios')  # deve retornar o engine
SessionLocal = sessionmaker(bind=db)
log_repo = LogProducaoRepo(db)

def configurar_rotas(app, mqttc, socketio, supervisor):
    @app.route("/ping")
    def ping():
        return jsonify({"status": "ok"}), 200

    @socketio.on('resposta_estado_aguardando')
    def receber_resposta_estado(data):
        global resposta_recebida
        resposta_recebida = data['aguardando']
        evento_resposta.set()

    #Rota para enviar comandos do Raspberry
    @app.route("/comando", methods=['POST'])
    def comando():
        if supervisor.state.producao_ligada():
            dados = request.get_json(silent=True)
            comando = dados.get('comando')
            # Se o comando for de impressão de produto chama-se a função de gerar produto e depois ele é impresso
            if comando == 'imprime_produto':
                socketio.emit('palete_recebido')
            return f"Comando Executado: {comando}"
        else:
            socketio.emit('aviso_ao_operador_assoc', {'mensagem': "Produção não inciada. Não foi processado nenhum comando.", 'cor': "#dc3545", 'tempo': 3000})
            return f"Produção não inciada. Não foi processado nenhum comando."

    @socketio.on('campo_palete')
    def campo_palete(data):
        cod_palete = data['palete']
        if cod_palete:
            produto = gera_codigo_produto()
            if not debug_mode:
                print(f'IMPRIMINDO CÓDIGO DE PRODUTO {produto}')
                imprime_qrcode(produto)
            socketio.emit('add_produto_impresso', {'codigo': produto})
        else:
            socketio.emit('aviso_ao_operador_assoc', {'mensagem': "Antes de gerar um produto. Insira o palete no posto", 'cor': "#ffc107", 'tempo': 2000})
        #evento_resposta.set()

    #Rota para o acesso da interface de controle
    @app.route("/api/q_postos", methods=["GET"])
    def quantidade_postos():
        return jsonify({"q_postos": ultimo_posto_bios})

    @app.route("/controle", methods=["GET", "POST"])
    def painel_controle():
        session = SessionLocal()

        if request.method == "POST":
            postos = session.query(Posto).order_by(Posto.id).all()

            # 1) Monta um mapa posto_id -> funcionario_id (do formulário)
            selecoes = {}
            selecionados = []

            for posto in postos:
                campo_name = f"posto_{posto.id}"
                func_id_str = request.form.get(campo_name)

                if func_id_str:
                    func_id = int(func_id_str)
                    selecoes[posto.id] = func_id
                    selecionados.append(func_id)

            # 2) Verifica se algum funcionário foi selecionado em mais de um posto
            if len(selecionados) != len(set(selecionados)):
                session.close()
                #flash("Não é permitido selecionar o mesmo funcionário para mais de um posto.", "error")
                socketio.emit('aviso_lista_func', {'mensagem': "Não é permitido selecionar o mesmo funcionário para mais de um posto.", 'cor': "#dc3545", 'tempo': 1000})
                sleep(1)
                return redirect(url_for("painel_controle"))

            try:
                # 3) Primeiro: limpa todos os funcionarios dos postos
                for posto in postos:
                    posto.funcionario_id = None

                session.flush()  # aplica os UPDATEs no banco sem dar commit ainda

                # 4) Agora: aplica a nova alocação com segurança
                for posto in postos:
                    if posto.id in selecoes:
                        posto.funcionario_id = selecoes[posto.id]

                # 5) Confirma tudo
                session.commit()
                socketio.emit('aviso_lista_func', {'mensagem': "Alocação de operadores atualizada com sucesso!", 'cor': "#74FF95", 'tempo': 1000})
                sleep(1)

            except Exception as e:
                session.rollback()
                flash(f"Erro ao atualizar alocação: {e}", "error")
            finally:
                session.close()

            return redirect(url_for("painel_controle"))

        # GET → carrega dados normalmente
        funcionarios = session.query(Funcionario).order_by(Funcionario.nome).all()
        postos = session.query(Posto).order_by(Posto.id).all()
        ops_abertas = session.query(OrdemProducao)\
            .filter_by(status="ABERTA")\
            .order_by(OrdemProducao.id.desc())\
            .all()
        session.close()

        return render_template(
            "controle.html",
            funcionarios=funcionarios,
            postos=postos,
            ops=ops_abertas,
            ordem_atual=supervisor.state.get_ordem_atual()
        )

    @app.route('/supervisorio')
    def supervisorio():
        from auxiliares.configuracoes import ultimo_posto_bios
        return render_template('supervisorio.html', num_postos=ultimo_posto_bios+1)
    
    # Função controlada pela interface de controle.
    @app.route('/enviar', methods=['POST'])
    def enviar_dados():
        # Dados coletados do JS
        dados = request.get_json()

        if dados and dados['tipo'] == 'comando':
            comando = dados['mensagem']

            # Lógica para tratar comandos diferentes
            if comando == 'Start':
                # 🔥 Start agora exige Ordem de Produção
                ordem_codigo = (dados.get("ordem") or "").strip()
                if not ordem_codigo:
                    return jsonify(status="erro", mensagem="Selecione uma Ordem de Produção."), 400

                # Consulta OP no banco
                session = SessionLocal()
                try:
                    ordem_db = session.query(OrdemProducao).filter_by(codigo_op=ordem_codigo).first()
                    if not ordem_db:
                        return jsonify(status="erro", mensagem="Ordem não encontrada no banco."), 404

                    if ordem_db.status != "ABERTA":
                        return jsonify(status="erro", mensagem=f"Ordem {ordem_codigo} não está ABERTA."), 400

                    meta_producao = int(ordem_db.meta or 0)
                    if meta_producao <= 0:
                        return jsonify(status="erro", mensagem="Meta inválida na ordem (<= 0)."), 400
                    
                    log_id = log_repo.criar(ordem_codigo, meta_producao)
                    
                    # 🔥 Marca ordem como em execução (evita reuso acidental)
                    ordem_db.status = "EM_EXECUCAO"
                    ordem_db.atualizada_em = datetime.utcnow()
                    session.commit()

                finally:
                    session.close()

                for posto_nome in supervisor.postos.keys():
                    operador = supervisor.operadores_ativos.get(posto_nome)
                    posto_id = posto_nome_para_id(posto_nome)
                    supervisor.state.set_posto_pronto(posto_id, operador is not None)

                supervisor.state.armar_producao(
                    meta=meta_producao,
                    ordem_codigo=ordem_codigo,
                    log_id=log_id,
                    por="painel",
                    motivo="aguardando check-ins"
                )

               #Retorna para a página o sucesso da inicialização do sistema
                return jsonify(
                    status='sucesso',
                    mensagem=f"Produção armada na ordem {ordem_codigo} (meta: {meta_producao}). Aguardando check-ins."
                ), 200
            
            elif comando == 'Restart':
                supervisor.resetar_timer()
                reiniciar_produtos()
                reiniciar_sistema(debug=debug_mode)
                return jsonify(status='sucesso', mensagem='Sistema reiniciado.'), 200
            
            elif comando == 'Stop':
                # Lógica para reiniciar produtos
                supervisor.parar_timer()
                log_id = supervisor.state.get_log_producao_id()
                if log_id:
                    log_repo.finalizar(log_id, "stop manual")

                # Finaliza ordem no banco (se existir)
                ordem_codigo = supervisor.state.get_ordem_atual()
                if ordem_codigo:
                    session = SessionLocal()
                    try:
                        ordem_db = session.query(OrdemProducao).filter_by(codigo_op=ordem_codigo).first()
                        if ordem_db:
                            ordem_db.status = "FINALIZADA"
                            ordem_db.atualizada_em = datetime.utcnow()
                            session.commit()
                    except Exception:
                        session.rollback()
                    finally:
                        session.close()

                supervisor.state.desligar_producao(por="painel_controle", motivo="stop manual")
                mqttc.publish("ControleProducao_DD", "Stop")

                return jsonify(status='sucesso', mensagem='Produção encerrada'), 200
            
            else:
                return jsonify(status='erro', mensagem='Comando desconhecido.'), 400

        else:
            return jsonify(status='erro', mensagem='Tipo de dados inválido.'), 400



    # Rota para associação de palete. Ela é chamada quando o produto e palete já foram encaminhados pelo javascript.
    @app.route('/associacao/submit', methods=['POST'])
    def submit():
        # Data processa a requisição e recolhe os dados enviados pelo javascript via json.
        data = request.get_json(silent=True)

        # Armazenando os dados recebidos em variaveis do python.
        produto = data.get('produto')
        palete = data.get('palete')

        # Se a produção não foi iniciada Retorna para a interface a mensagem
        if not supervisor.state.producao_ligada():
            return f"A produção ainda não foi iniciada. Não é possível associar."

        # Se o código de produto for inválido
        if not verifica_cod_produto(produto):
            return f"ERRO: CÓDIGO LIDO NÃO É PRODUTO"

        # Faz a consulta na tabela para verificar quais paletes estão cadastrados.
        lista_paletes = classes.associacoes.paletes_assoc()
        # Se a palete recebido não estiver presente na lista de paletes vinculados o código segue.
        # Se estiver presente é retornada uma mensagem de erro para o javascript.
        if palete not in lista_paletes:
            try:
                # Guarda numa lista interna quais foram os produtos gerados.
                memoriza_produto(produto)

                classes.associacoes.associa(palete, produto)
                supervisor.postos['posto_0'].insert_produto(produto)
                mqttc.publish(f"rastreio_nfc/esp32/posto_0/dispositivo", "BT1")
                #classes.adicionarProduto(produto)

                #Inicia a contagem do tempo de tranporte no posto 0
                #classes.tratamento_palete(palete, "posto_0", mqttc)

                #mqttc.publish(f"rastreio_nfc/esp32/posto_0/dispositivo", "BD")
                # Coleta a data e hora, do instante quando os dados foram recebidos, para armazenar nas tabelas
                horario = str(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
                # Modelo para enviar os dados para a tabela de Associações.
                associacao_dado = pd.DataFrame([{
                    'palete': palete,
                    'produto': produto,
                    'horario': horario
                }])

                inserir_dados(associacao_dado, 'paletes', 'associacoes')

                print(f"Recebido: {palete} - Associados a {produto}")
                # Retorna para o javascript uma mensagem de sucesso da associação.
                return f"Associação Realizada com Sucesso: {produto}-{palete}"
            except Exception as e:
                # Para evitar problemas, os comandos estão em um try e se ocorrer um erro é retornada uma mensagem de erro.
                return f"ERRO: Associação não realizada : {e}"
        else:
            return f"ERRO: PALETE JÁ VINCULADO"

    @app.route("/posto/<int:posto_id>")
    def posto_operador(posto_id):
        if posto_id >= ultimo_posto_bios + 1:
            return "Posto inválido.", 404
        elif posto_id == 0:
            sleep(1)
            if not tem_cliente_associacao():
                return render_template("posto0.html", posto_id=posto_id)
            else:
                return "Já existe um Cliente de Associação Conectado!!!"
        return render_template("posto.html", posto_id=posto_id)