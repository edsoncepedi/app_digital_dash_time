
from flask import current_app, render_template, request, jsonify, url_for, flash, redirect
from auxiliares.banco_post import Conectar_DB
from auxiliares.associacao import inicializa_funcionario
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from threading import Event

evento_resposta = Event()
debug_mode=True
Funcionario, Posto = inicializa_funcionario()
db = Conectar_DB('funcionarios')  # deve retornar o engine
SessionLocal = sessionmaker(bind=db)

def rotas_funcionarios(app, mqttc, socketio):
    @app.route('/cadastro_funcionario', methods=['GET', 'POST'])
    def cadastro_funcionario():
        if request.method == 'POST':
            nome = request.form['nome']
            data_nascimento = datetime.strptime(
                request.form['data_nascimento'], '%Y-%m-%d'
            ).date()
            horas_trabalho = float(request.form['horas_trabalho'])

            # RFID OBRIGATÓRIA
            rfid_tag = request.form.get('rfid_tag', '').strip()
            if not rfid_tag:
                flash('A tag RFID é obrigatória.', 'error')
                return redirect(url_for('cadastro_funcionario'))

            imagem = request.files.get('imagem')
            imagem_path = None
            if imagem and imagem.filename:
                from werkzeug.utils import secure_filename
                import os
                filename = secure_filename(imagem.filename)
                pasta = os.path.join('static', 'funcionarios')
                os.makedirs(pasta, exist_ok=True)
                caminho = os.path.join(pasta, filename)
                imagem.save(caminho)
                imagem_path = caminho

            session = SessionLocal()
            # Verifica duplicidade antes de inserir
            existe = session.query(Funcionario).filter_by(rfid_tag=rfid_tag).first()
            if existe:
                session.close()
                flash(f"A tag RFID {rfid_tag} já está cadastrada para {existe.nome}.", "error")
                return redirect(url_for('cadastro_funcionario'))

            try:
                funcionario = Funcionario(
                    nome=nome,
                    data_nascimento=data_nascimento,
                    horas_trabalho=horas_trabalho,
                    imagem_path=imagem_path,
                    rfid_tag=rfid_tag   # <-- agora sempre vem preenchida
                )
                session.add(funcionario)
                session.commit()
                flash('Funcionário cadastrado com sucesso!', 'success')
            except Exception as e:
                session.rollback()
                flash(f'Erro ao cadastrar funcionário (RFID pode estar duplicada): {e}', 'error')
            finally:
                session.close()

            return redirect(url_for('cadastro_funcionario'))

        # GET → listar funcionários
        session = SessionLocal()
        funcionarios = session.query(Funcionario).order_by(Funcionario.id).all()
        session.close()

        return render_template('funcionarios.html', funcionarios=funcionarios)


    @app.route("/deletar_funcionario/<int:func_id>", methods=["POST"])
    def deletar_funcionario(func_id):
        senha = request.form.get("senha_confirmacao", "")

        if senha != current_app.config["ADMIN_DELETE_PASSWORD"]:
            flash("Senha de exclusão inválida.", "error")
            return redirect(url_for("cadastro_funcionario"))

        # 🔴 se chegou aqui, senha está correta → pode excluir
        session = SessionLocal()
        try:
            func = session.query(Funcionario).get(func_id)
            if not func:
                flash("Funcionário não encontrado.", "error")
                return redirect(url_for("cadastro_funcionario"))

            session.delete(func)
            session.commit()
            flash("Funcionário excluído com sucesso.", "success")
        except Exception as e:
            session.rollback()
            flash("Erro ao excluir funcionário.", "error")
        finally:
            session.close()

        return redirect(url_for("cadastro_funcionario"))

    @app.route('/rfid__checkin_posto', methods=['POST'])
    def rfid_event():
        # 1) Pegar JSON da requisição
        data = request.get_json(silent=True) or {}
        tag = data.get('tag')
        posto_nome = data.get('posto')   # ex.: "posto_0"

        if not tag or not posto_nome:
            return jsonify({
                "status": "error",
                "message": "Campos 'tag' e 'posto' são obrigatórios."
            }), 400

        session = SessionLocal()

        try:
            # 2) Buscar funcionário pela tag
            func = session.query(Funcionario).filter_by(rfid_tag=tag).first()

            if func is None:
                # 🔴 Tag não encontrada
                resposta = {
                    "status": "unknown_tag",
                    "posto": posto_nome,
                    "message": f"Tag {tag} não cadastrada.",
                    "autorizado": False
                }
                return jsonify(resposta), 200

            # 3) Buscar posto pelo NOME recebido (posto_0, posto_1, ...)
            posto_db = session.query(Posto).filter_by(nome=posto_nome).first()

            if posto_db is None:
                # posto não existe na tabela
                resposta = {
                    "status": "invalid_posto",
                    "posto": posto_nome,
                    "message": f"Posto '{posto_nome}' não cadastrado.",
                    "autorizado": False,
                    "funcionario": {
                        "id": func.id,
                        "nome": func.nome,
                        "rfid_tag": func.rfid_tag,
                    }
                }
                return jsonify(resposta), 200

            # 4) Verificar se o funcionário é o responsável por ESTE posto
            # (coluna funcionario_id da tabela posto)
            if posto_db.funcionario_id != func.id:
                resposta = {
                    "status": "forbidden_posto",
                    "posto": posto_nome,
                    "message": (
                    f"Funcionário '{func.nome}' não está autorizado "
                    f"a operar no posto '{posto_nome}'."
                    ),
                    "autorizado": False,
                    "funcionario": {
                        "id": func.id,
                        "nome": func.nome,
                        "rfid_tag": func.rfid_tag,
                    }
                }
                return jsonify(resposta), 200

            # 🟢 Se chegou aqui: tag encontrada e funcionário bate com o posto
            resposta = {
                "status": "ok",
                "message": "Acesso autorizado.",
                "posto": posto_nome,
                "autorizado": True,
                "funcionario": {
                    "id": func.id,
                    "nome": func.nome,
                    "rfid_tag": func.rfid_tag,
                    "horas_trabalho": float(func.horas_trabalho)
                    }
                }
            return jsonify(resposta), 200

        finally:
            session.close()