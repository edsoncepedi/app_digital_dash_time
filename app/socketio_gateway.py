# app/socketio_gateway.py
from flask_socketio import join_room
from flask import request

def register_socketio_handlers(socketio, supervisor):
    @socketio.on("join_posto")
    def join_posto(data):
        pid = data["posto"]                # ex: "posto_0"
        join_room(f"posto:{pid}")          # cliente entra na sala do posto
        snap = supervisor.get_snapshot(pid)
        if snap:
            socketio.emit("posto/state_snapshot", snap, room=request.sid)

    @socketio.on("posto/command")
    def posto_command(data):
        supervisor.command(data["posto"], data["cmd"], **(data.get("args") or {}))

    @socketio.on("global/request_sync")
    def handle_global_sync():
        # Pede ao supervisor o estado atual de tudo
        dados = supervisor.get_global_status()
        # Devolve apenas para quem pediu (request.sid)
        socketio.emit("global/sync_data", dados, room=request.sid)
