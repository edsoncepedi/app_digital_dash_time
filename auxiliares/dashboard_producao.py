from flask import render_template, jsonify
from auxiliares.db import get_sessionmaker
from auxiliares.models_log_producao import LogProducao
from auxiliares.associacao import inicializa_funcionario
from sqlalchemy import text
from sqlalchemy.orm import joinedload

Funcionario, Posto, SessaoTrabalho = inicializa_funcionario()

SessionLocal = get_sessionmaker('funcionarios')


def _dt(v):
    return v.isoformat() if v else None


def rotas_dashboard(app):

    @app.route("/dashboard_producao")
    def dashboard():
        return render_template("dashboard_producao.html")


    @app.route("/api/log_producao")
    def api_log_producao():

        session = SessionLocal()

        try:
            logs = (
                session.query(LogProducao)
                .options(joinedload(LogProducao.ordem))
                .order_by(LogProducao.id.desc())
                .limit(100)
                .all()
            )

            return jsonify([
                {
                    "id": l.id,
                    "ordem_codigo": l.ordem.codigo_op if l.ordem else None,
                    "meta": l.meta,
                    "status": l.status,
                    "armada_em": _dt(l.armada_em),
                    "inicio_em": _dt(l.inicio_em),
                    "fim_em": _dt(l.fim_em),
                    "motivo_fim": l.motivo_fim
                }
                for l in logs
            ])

        finally:
            session.close()


    @app.route("/api/sessoes_trabalho")
    def api_sessoes():

        session = SessionLocal()

        try:

            resultados = (
                session.query(
                    SessaoTrabalho,
                    Funcionario.nome
                )
                .outerjoin(Funcionario, Funcionario.id == SessaoTrabalho.funcionario_id)
                .order_by(SessaoTrabalho.horario_entrada.desc())
                .limit(200)
                .all()
            )

            data = []

            for sessao, nome in resultados:

                data.append({
                    "funcionario": nome,
                    "posto_nome": sessao.posto_nome,
                    "horario_entrada": _dt(sessao.horario_entrada),
                    "horario_saida": _dt(sessao.horario_saida),
                    "duracao_segundos": sessao.duracao_segundos
                })

            return jsonify(data)

        finally:
            session.close()

    @app.route("/api/experiencia_operador_produto")
    def api_experiencia():

        session = SessionLocal()

        query = text("""
        SELECT
            f.nome AS funcionario,
            op.produto AS produto,
            SUM(st.duracao_segundos)/3600.0 AS horas

        FROM sessoes_trabalho st

        JOIN funcionario f
            ON f.id = st.funcionario_id

        JOIN log_producao lp
            ON st.horario_entrada <= lp.fim_em
            AND st.horario_saida >= lp.inicio_em

        JOIN ordens_producao op
            ON lp.ordem_id = op.id

        GROUP BY f.nome, op.produto
        ORDER BY f.nome
        """)

        result = session.execute(query)

        dados = []

        for row in result:
            dados.append({
                "funcionario": row.funcionario,
                "produto": row.produto,
                "horas": float(row.horas)
            })

        session.close()

        return jsonify(dados)

    @app.route("/api/operadores_ativos")
    def api_operadores_ativos():

        session = SessionLocal()

        try:

            total = session.execute(text("""
                SELECT COUNT(DISTINCT funcionario_id)
                FROM sessoes_trabalho
                WHERE horario_saida IS NULL
            """)).scalar()

            return jsonify({"operadores": total})

        finally:
            session.close()