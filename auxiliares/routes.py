import pandas as pd
from flask import render_template, request, jsonify, url_for, flash, redirect
from auxiliares.utils import imprime_qrcode, gera_codigo_produto, verifica_cod_produto, memoriza_produto, reiniciar_produtos, reiniciar_sistema
from auxiliares.banco_post import verifica_conexao_banco, Conectar_DB, inserir_dados, consulta_paletes
from auxiliares.associacao import inicializa_funcionario
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from time import sleep
import auxiliares.classes as classes
from threading import Event
from auxiliares.socketio_handlers import tem_cliente_associacao
from auxiliares.configuracoes import cartao_palete
evento_resposta = Event()
import numpy as np

debug_mode=True

Funcionario, Posto = inicializa_funcionario()

db = Conectar_DB('funcionarios')  # deve retornar o engine
SessionLocal = sessionmaker(bind=db)

def configurar_rotas(app, mqttc, socketio):
    @app.route("/ping")
    def ping():
        return jsonify({"status": "ok"}), 200

    #Rota para interface de associção
    @app.route("/associacao")
    def associacao():
        sleep(1)
        if not tem_cliente_associacao():
            return render_template("index.html")
        else:
            return "Já existe um Cliente de Associação Conectado!!!"

    @socketio.on('resposta_estado_aguardando')
    def receber_resposta_estado(data):
        global resposta_recebida
        resposta_recebida = data['aguardando']
        evento_resposta.set()

    #Rota para enviar comandos do Raspberry
    @app.route("/comando", methods=['POST'])
    def comando():
        if classes.verifica_estado_producao():
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
            #imprime_qrcode(produto)
            socketio.emit('add_produto_impresso', {'codigo': produto})
            mqttc.publish(f"rastreio_nfc/esp32/posto_0/dispositivo", "BS")
            print(f'IMPRIMINDO CÓDIGO DE PRODUTO {produto}')
        else:
            socketio.emit('aviso_ao_operador_assoc', {'mensagem': "Antes de gerar um produto. Insira o palete no posto", 'cor': "#ffc107", 'tempo': 2000})
        #evento_resposta.set()

    #Rota para o acesso da interface de controle
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
                socketio.emit('aviso_lista_func', {'mensagem': "Alocação de operadores atualizada com sucesso!", 'cor': "#00a80e", 'tempo': 1000})
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
        session.close()

        return render_template(
            "controle.html",
            funcionarios=funcionarios,
            postos=postos
        )

    # Função controlada pela interface de controle.
    @app.route('/enviar', methods=['POST'])
    def enviar_dados():
        # Dados coletados do JS
        dados = request.get_json()

        #Se for o comando Start
        if dados and dados['tipo'] == 'start':
            # Inicialização do sistema de Postos
            classes.inicializar_postos(mqttc)
            classes.inicia_producao()
            mqttc.publish(f"ControleProducao_DD", f"Start")

            #Retorna para a página o sucesso da inicialização do sistema
            return jsonify(status='sucesso', mensagem='O Sistema foi inciado: Produção ON'), 200
        #Se for um comando para o sistema (Reiniciar sistema ou produtos)
        elif dados and dados['tipo'] == 'comando':
            comando = dados['mensagem']

            # Lógica para tratar comandos diferentes
            if comando == 'Start':
                #Enviando Tópicos para os dispositivos temporizadores
                mqttc.publish(f"ControleProducao_DD", f"Start")
                #Retorna para a página o sucesso da inicialização do sistema
                return jsonify(status='sucesso', mensagem='O Sistema foi inciado: Produção ON'), 200
            
            elif comando == 'Restart':
                # Lógica para reiniciar o sistema
                reiniciar_produtos()
                reiniciar_sistema(debug=debug_mode)
                return jsonify(status='sucesso', mensagem='Sistema reiniciado.'), 200
            
            elif comando == 'Restart_Produtos':
                # Lógica para reiniciar produtos
                reiniciar_produtos()
                return jsonify(status='sucesso', mensagem='Produtos reiniciados.'), 200
            
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
        if not classes.verifica_estado_producao():
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
