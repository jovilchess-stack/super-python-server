#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUPER PYTHON BROS ONLINE - SERVIDOR DEDICADO GLOBAL
Maneja salas de juego, sincro de físicas a 60Hz y matchmaking.
Requisitos: Python 3.8+ (Sin librerías externas)
Ejecutar: python server.py
"""
import asyncio
import json
import logging
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

PORT = 9999
HOST = '0.0.0.0'

rooms = {}

class GameRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self.seed = random.randint(10000, 999999)
        self.clients = {}  # writer -> player_id
        self.players_state = {}

    def add_player(self, writer, p_id, name):
        self.clients[writer] = p_id
        colors = [(40, 120, 230), (230, 70, 160), (40, 200, 100), (240, 180, 40)]
        color = colors[p_id % len(colors)]
        
        self.players_state[p_id] = {
            'id': p_id,
            'name': name,
            'x': 70 + (p_id * 40),
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

    def remove_player(self, writer):
        if writer in self.clients:
            p_id = self.clients[writer]
            del self.clients[writer]
            if p_id in self.players_state:
                del self.players_state[p_id]
            return p_id
        return None

    async def broadcast(self, message, exclude=None):
        data = (json.dumps(message) + "\n").encode('utf-8')
        for writer in list(self.clients.keys()):
            if writer != exclude:
                try:
                    writer.write(data)
                    await writer.drain()
                except Exception:
                    self.remove_player(writer)

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    logging.info(f"Nueva conexión desde {addr}")
    current_room = None
    player_id = None

    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            
            try:
                msg = json.loads(line.decode('utf-8').strip())
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
                current_room.add_player(writer, player_id, name)

                init_msg = {
                    'type': 'init',
                    'id': player_id,
                    'seed': current_room.seed,
                    'players': current_room.players_state
                }
                writer.write((json.dumps(init_msg) + "\n").encode('utf-8'))
                await writer.drain()

                await current_room.broadcast({
                    'type': 'player_joined',
                    'player': current_room.players_state[player_id]
                }, exclude=writer)

            elif mtype == 'update' and current_room and player_id is not None:
                p_data = msg.get('state', {})
                if player_id in current_room.players_state:
                    current_room.players_state[player_id].update(p_data)
                
                await current_room.broadcast({
                    'type': 'world_state',
                    'players': current_room.players_state
                }, exclude=writer)

            elif mtype == 'ping':
                writer.write((json.dumps({'type': 'pong', 't': msg.get('t', 0)}) + "\n").encode('utf-8'))
                await writer.drain()

    except Exception as e:
        logging.error(f"Error con cliente {addr}: {e}")
    finally:
        if current_room:
            pid = current_room.remove_player(writer)
            if pid is not None:
                await current_room.broadcast({'type': 'player_left', 'id': pid})
                logging.info(f"Jugador {pid} desconectado de sala {current_room.room_id}")
            if not current_room.clients:
                del rooms[current_room.room_id]
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    logging.info(f"Servidor Online Global activo en el puerto {PORT}...")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
