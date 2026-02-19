# auxiliares/cadastro_ordens.py
from __future__ import annotations

from datetime import datetime

from flask import (
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from sqlalchemy.orm import sessionmaker

from auxiliares.banco_post import Conectar_DB
from auxiliares.models_ordens import OrdemProducao, inicializa_ordens


def rotas_ordens(app, mqttc, socketio, supervisor):
    # ✅ Por enquanto: usa o MESMO Postgres do sistema (mock)
    # (mais tarde você pode trocar para outro banco/schema sem mudar o front)
    engine = Conectar_DB("funcionarios")
    inicializa_ordens(engine)
    SessionLocal = sessionmaker(bind=engine)

    @app.route("/ordens", methods=["GET", "POST"])
    def ordens():
        if request.method == "POST":
            codigo_op = (request.form.get("codigo_op") or "").strip()
            produto = (request.form.get("produto") or "").strip()
            descricao = (request.form.get("descricao") or "").strip()
            status = (request.form.get("status") or "ABERTA").strip().upper()

            meta_str = (request.form.get("meta") or "").strip()
            try:
                meta = int(meta_str)
            except Exception:
                meta = -1

            # validações simples
            if not codigo_op:
                flash("Código da OP é obrigatório.", "error")
                return redirect(url_for("ordens"))
            if not produto:
                flash("Produto é obrigatório.", "error")
                return redirect(url_for("ordens"))
            if meta < 0:
                flash("Meta inválida (use um número inteiro >= 0).", "error")
                return redirect(url_for("ordens"))
            if status not in {"ABERTA", "EM_EXECUCAO", "FINALIZADA"}:
                flash("Status inválido.", "error")
                return redirect(url_for("ordens"))

            session = SessionLocal()
            try:
                existe = session.query(OrdemProducao).filter_by(codigo_op=codigo_op).first()
                if existe:
                    flash(f"A OP {codigo_op} já existe.", "error")
                    return redirect(url_for("ordens"))

                now = datetime.utcnow()
                op = OrdemProducao(
                    codigo_op=codigo_op,
                    produto=produto,
                    descricao=descricao or None,
                    meta=meta,
                    status=status,
                    criada_em=now,
                    atualizada_em=now,
                )
                session.add(op)
                session.commit()
                flash("Ordem de Produção cadastrada com sucesso!", "success")
            except Exception as e:
                session.rollback()
                flash(f"Erro ao cadastrar OP: {e}", "error")
            finally:
                session.close()

            return redirect(url_for("ordens"))

        # GET -> listar
        session = SessionLocal()
        try:
            ops = (
                session.query(OrdemProducao)
                .order_by(OrdemProducao.id.desc())
                .all()
            )
        finally:
            session.close()

        return render_template("ordens.html", ops=ops)

    @app.route("/ordens/deletar/<int:op_id>", methods=["POST"])
    def deletar_op(op_id: int):
        # Mesma lógica do cadastro de funcionários: senha admin opcional
        senha = (request.form.get("senha_confirmacao") or "").strip()
        if senha and senha != current_app.config.get("ADMIN_DELETE_PASSWORD", "1234"):
            flash("Senha de exclusão inválida.", "error")
            return redirect(url_for("ordens"))

        session = SessionLocal()
        try:
            op = session.query(OrdemProducao).get(op_id)
            if not op:
                flash("OP não encontrada.", "error")
                return redirect(url_for("ordens"))

            session.delete(op)
            session.commit()
            flash("OP excluída com sucesso.", "success")
        except Exception as e:
            session.rollback()
            flash(f"Erro ao excluir OP: {e}", "error")
        finally:
            session.close()

        return redirect(url_for("ordens"))
