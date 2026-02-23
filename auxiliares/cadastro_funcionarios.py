
from flask import app, current_app, render_template, request, jsonify, url_for, flash, redirect
from auxiliares.banco_post import Conectar_DB
from auxiliares.associacao import inicializa_funcionario
from sqlalchemy.orm import sessionmaker
from auxiliares.classes import verifica_estado_producao
from datetime import datetime
from threading import Event

evento_resposta = Event()
debug_mode=True
Funcionario, Posto, SessaoTrabalho = inicializa_funcionario()
db = Conectar_DB('funcionarios')  # deve retornar o engine
SessionLocal = sessionmaker(bind=db)

def rehidratar_operadores(supervisor):
    session = SessionLocal()
    try:
        # todas as sessões ativas (um por posto, idealmente)
        sessoes_ativas = (
            session.query(SessaoTrabalho)
            .filter(SessaoTrabalho.horario_saida.is_(None))
            .all()
        )

        # limpa tudo no supervisor primeiro (opcional, depende do seu design)
        # supervisor.reset_operadores()  # se existir

        for s in sessoes_ativas:
            func = session.query(Funcionario).get(s.funcionario_id)
            if not func:
                continue

            supervisor.atualizar_operador_posto(s.posto_nome, {
                "id": func.id,
                "nome": func.nome,
                "foto": func.imagem_path
            })

        print(f"✅ Rehidratação concluída: {len(sessoes_ativas)} sessões ativas.")
    except Exception as e:
        print("❌ Falha ao rehidratar operadores:", repr(e))
    finally:
        session.close()

def rotas_funcionarios(app, mqttc, socketio, supervisor):
    
    rehidratar_operadores(supervisor)

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
        data = request.get_json(silent=True) or {}
        tag = data.get('tag')
        posto_nome = data.get('posto')
        acao = data.get('acao') # "entrada" ou "saida"

        session = SessionLocal()
        agora = datetime.now()

        try:
            # 1. Busca as configurações do Posto
            posto_db = session.query(Posto).filter_by(nome=posto_nome).first()
            if not posto_db:
                print("Posto não cadastrado:", posto_nome)
                return jsonify({
                    "status": "error", 
                    "message": "Posto não cadastrado", 
                    "autorizado": False
                }), 200

            # --- LÓGICA DE ENTRADA (Check-in) ---
            if acao == "entrada":
                if not tag:
                    print("Tag ausente na entrada")
                    supervisor.emit_alerta_posto(posto_nome, f"Acesso Negado: Tag ausente", cor="#ff0000", tempo=2500)
                    return jsonify({"status": "error", "message": "Tag ausente", "autorizado": False}), 200

                func = session.query(Funcionario).filter_by(rfid_tag=tag).first()
                if not func:
                    print("Funcionário não cadastrado para a tag:", tag)
                    supervisor.emit_alerta_posto(posto_nome, f"Acesso Negado: Tag {tag} não cadastrada", cor="#ff0000", tempo=2500)
                    return jsonify({"status": "unknown_tag", "message": "Funcionário não cadastrado", "autorizado": False}), 200

                if posto_db.funcionario_id != func.id:
                    print(f"Acesso Negado: {func.nome} não autorizado para o posto {posto_nome}")
                    supervisor.emit_alerta_posto(posto_nome, f"Acesso Negado: {func.nome} não autorizado para o posto {posto_nome}", cor="#ff0000", tempo=2500)
                    return jsonify({
                        "status": "forbidden", 
                        "message": f"Acesso Negado: {func.nome} não autorizado", 
                        "autorizado": False
                    }), 200

                sessao_existente = session.query(SessaoTrabalho).filter_by(
                    posto_nome=posto_nome,
                    horario_saida=None
                ).first()

                if sessao_existente:
                    # Se quem está tentando entrar é o mesmo que já está logado
                    if sessao_existente.funcionario_id == func.id:
                        print(f"⚠️ {func.nome} já está logado no posto {posto_nome}. Permitindo acesso sem criar nova sessão.")
                        supervisor.emit_alerta_posto(posto_nome, f"⚠️ {func.nome} já está logado no posto {posto_nome}. Permitindo acesso sem criar nova sessão.", cor="#ff0000", tempo=2500)
                        return jsonify({
                            "status": "ok",
                            "message": f"Você já está logado, {func.nome}",
                            "autorizado": True
                        }), 200

                    # Caso seja outro funcionário
                    print(f"Posto {posto_nome} já ocupado por outro funcionário.")
                    return jsonify({
                        "status": "error",
                        "message": "Posto já ocupado",
                        "autorizado": False
                    }), 200

                # Cria a sessão
                nova_sessao = SessaoTrabalho(funcionario_id=func.id, posto_nome=posto_nome, horario_entrada=agora)
                session.add(nova_sessao)
                
                # --- COMMIT AQUI ---
                session.commit()

                try:
                    supervisor.atualizar_operador_posto(posto_nome, {
                        "id": func.id,
                        "nome": func.nome,
                        "foto": func.imagem_path
                    })
                except Exception as e:
                    print("⚠️ Falha ao atualizar supervisor:", repr(e))

                print(f"Entrada registrada: {func.nome} no posto {posto_nome}")
                supervisor.emit_alerta_posto(posto_nome, f"Entrada registrada: {func.nome}", cor="#00ff00", tempo=2500)
                return jsonify({
                    "status": "ok", 
                    "message": f"Bem-vindo, {func.nome}", 
                    "autorizado": True
                }), 200

            # --- LÓGICA DE SAÍDA (Check-out) ---
            elif acao == "saida":
                sessao_ativa = session.query(SessaoTrabalho).filter_by(posto_nome=posto_nome, horario_saida=None).first()

                if not sessao_ativa:
                    print("Nenhum operador logado no posto:", posto_nome)
                    supervisor.emit_alerta_posto(posto_nome, f"Nenhum operador logado", cor="#ff0000", tempo=2500)
                    return jsonify({"status": "error", "message": "Nenhum operador logado", "autorizado": False}), 200

                # Fecha a sessão
                sessao_ativa.horario_saida = agora
                delta = agora - sessao_ativa.horario_entrada
                sessao_ativa.duracao_segundos = int(delta.total_seconds())
                
                # --- COMMIT AQUI ---
                session.commit()
                
                supervisor.atualizar_operador_posto(posto_nome, None)
                print(f"Saída registrada do posto {posto_nome}")
                supervisor.emit_alerta_posto(posto_nome, f"Saída registrada do posto {posto_nome}", cor="#00ff00", tempo=2500)
                return jsonify({"status": "ok", "message": "Saída registrada", "autorizado": True}), 200

        except Exception as e:
            session.rollback()
            return jsonify({"status": "error", "message": str(e), "autorizado": False}), 500
        finally:
            session.close()