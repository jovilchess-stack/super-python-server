#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUPER PYTHON BROS ONLINE - SERVIDOR DEDICADO GLOBAL
Maneja salas de juego, sincro de físicas a 60Hz y matchmaking.
Requisitos: pip install websockets
Ejecutar: python server.py
"""
import asyncio
import json
import logging
import os
import random
import websockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Render asigna dinámicamente el puerto en la variable PORT
PORT = int(os.environ.get("PORT", 10000))

rooms = {}

class GameRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self.seed = random.randint(10000, 999999)
        self.clients = {}  # ws -> player_id
        self.players_state = {}

    def add_player(self, ws, p_id, name):
        self.clients[ws] = p_id
        colors = [(40, 120, 230), (230, 70, 160), (40, 200, 100), (240, 180, 40)]
        color = colors[p_id % len(colors)]
        
        self.players_state[p_id] = {
            'id': p_id,
            'name': name,
            'x': 80 + (p_id * 60),
            'y': 400,
            'vx': 0.0,
            'vy': 0.0,
            'power': 0,
            'facing': 1,
            'state': 'play',
            'score': 0,
            'lives': 3,
            'color': color,
            'anim': 0.0
        }

    def remove_player(self, ws):
        if ws in self.clients:
            p_id = self.clients[ws]
            del self.clients[ws]
            if p_id in self.players_state:
                del self.players_state[p_id]
            return p_id
        return None

    async def broadcast(self, message, exclude=None):
        data = json.dumps(message)
        for ws in list(self.clients.keys()):
            if ws != exclude:
                try:
                    await ws.send(data)
                except Exception:
                    self.remove_player(ws)

async def handle_client(websocket):
    logging.info(f"Nueva conexión WebSocket recibida")
    current_room = None
    player_id = None

    try:
        async for message in websocket:
            try:
                msg = json.loads(message)
            except Exception:
                continue

            mtype = msg.get('type')

            if mtype == 'join':
                room_id = msg.get('room', 'global_1')
                name = msg.get('name', 'Jugador')
                
                if room_id not in rooms:
                    rooms[room_id] = GameRoom(room_id)
                
                current_room = rooms[room_id]
                player_id = len(current_room.clients)
                current_room.add_player(websocket, player_id, name)

                init_msg = {
                    'type': 'init',
                    'id': player_id,
                    'seed': current_room.seed,
                    'players': current_room.players_state
                }
                await websocket.send(json.dumps(init_msg))

                await current_room.broadcast({
                    'type': 'player_joined',
                    'player': current_room.players_state[player_id]
                }, exclude=websocket)

            elif mtype == 'update' and current_room and player_id is not None:
                p_data = msg.get('state', {})
                if player_id in current_room.players_state:
                    current_room.players_state[player_id].update(p_data)
                
                await current_room.broadcast({
                    'type': 'world_state',
                    'players': current_room.players_state
                }, exclude=websocket)

            elif mtype == 'ping':
                await websocket.send(json.dumps({'type': 'pong', 't': msg.get('t', 0)}))

    except Exception as e:
        logging.error(f"Error con cliente: {e}")
    finally:
        if current_room:
            pid = current_room.remove_player(websocket)
            if pid is not None:
                await current_room.broadcast({'type': 'player_left', 'id': pid})
                logging.info(f"Jugador {pid} desconectado")
            if not current_room.clients:
                del rooms[current_room.room_id]

async def main():
    async with websockets.serve(handle_client, "0.0.0.0", PORT):
        logging.info(f"Servidor WebSocket iniciado en el puerto {PORT}...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
