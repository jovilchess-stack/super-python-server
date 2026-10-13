#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUPER PYTHON BROS - EDICIÓN ONLINE GLOBAL 100x MEJORADA
Requisitos: pip install pygame
Ejecutar: python client.py
"""
import array
import json
import math
import os
import random
import socket
import sys
import threading
import time
import pygame

# ----------------------------------------------------------------- Red Online
class NetworkClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        self.player_id = None
        self.seed = 12345
        self.remote_players = {}
        self.ping = 0
        self.room_id = "global_1"

    def connect(self, name="Jugador", room="global_1"):
        self.room_id = room
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)
            self.connected = True
            
            join_msg = json.dumps({'type': 'join', 'name': name, 'room': room}) + "\n"
            self.sock.sendall(join_msg.encode('utf-8'))

            threading.Thread(target=self._listen, daemon=True).start()
            threading.Thread(target=self._ping_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"Error de conexión online: {e}")
            self.connected = False
            return False

    def _listen(self):
        buffer = ""
        while self.connected:
            try:
                data = self.sock.recv(4096).decode('utf-8')
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        self._handle_message(json.loads(line.strip()))
            except Exception:
                break
        self.connected = False

    def _handle_message(self, msg):
        mtype = msg.get('type')
        if mtype == 'init':
            self.player_id = msg['id']
            self.seed = msg['seed']
            self.remote_players = msg['players']
        elif mtype == 'world_state':
            self.remote_players = msg['players']
        elif mtype == 'player_joined':
            p = msg['player']
            self.remote_players[p['id']] = p
        elif mtype == 'player_left':
            pid = msg['id']
            if pid in self.remote_players:
                del self.remote_players[pid]
        elif mtype == 'pong':
            self.ping = int((time.time() - msg['t']) * 1000)

    def _ping_loop(self):
        while self.connected:
            try:
                ping_msg = json.dumps({'type': 'ping', 't': time.time()}) + "\n"
                self.sock.sendall(ping_msg.encode('utf-8'))
                time.sleep(2.0)
            except Exception:
                break

    def send_state(self, state):
        if not self.connected:
            return
        try:
            msg = json.dumps({'type': 'update', 'state': state}) + "\n"
            self.sock.sendall(msg.encode('utf-8'))
        except Exception:
            self.connected = False

# ----------------------------------------------------------------- Motor del Juego
T = 40
ROWS = 14
W, H = 960, ROWS * T
FPS = 60
GROUND = 12
SOLID = set("GBQUSpqab")

THEMES = {
    'overworld': dict(bg=(92, 148, 252), brick=((200, 76, 12), (96, 28, 0)), ground=((200, 76, 12), (96, 28, 0)),
                      stair=(196, 110, 44), pipe=(0, 168, 0), deco=True, stars=False, lava=False),
}

class Player:
    def __init__(self, idx, name):
        self.idx = idx
        self.name = name
        self.x, self.y = 100, 400
        self.w, self.h = 30, 38
        self.vx, self.vy = 0, 0
        self.on_ground = False
        self.facing = 1
        self.power = 0
        self.score = 0
        self.lives = 3
        self.state = 'play'
        self.anim = 0.0

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def update(self, keys, level):
        left = keys[pygame.K_a] or keys[pygame.K_LEFT]
        right = keys[pygame.K_d] or keys[pygame.K_RIGHT]
        jump = keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]

        if left:
            self.vx = -4.5
            self.facing = -1
        elif right:
            self.vx = 4.5
            self.facing = 1
        else:
            self.vx *= 0.8

        if jump and self.on_ground:
            self.vy = -12.5
            self.on_ground = False

        self.vy = min(self.vy + 0.6, 12)
        
        # Movimiento X
        self.x += self.vx
        for c, r, tr in level.tiles_in(self.rect()):
            if self.vx > 0: self.x = tr.left - self.w
            elif self.vx < 0: self.x = tr.right

        # Movimiento Y
        self.y += self.vy
        self.on_ground = False
        for c, r, tr in level.tiles_in(self.rect()):
            if self.vy > 0:
                self.y = tr.top - self.h
                self.vy = 0
                self.on_ground = True
            elif self.vy < 0:
                self.y = tr.bottom
                self.vy = 0

        self.anim += abs(self.vx) * 0.1

    def draw(self, scr, cam_x, color=None):
        c = color or ((40, 120, 230) if self.idx == 0 else (230, 70, 160))
        r = pygame.Rect(int(self.x) - cam_x, int(self.y), self.w, self.h)
        pygame.draw.rect(scr, c, r, border_radius=6)
        pygame.draw.rect(scr, (255, 255, 255), r, 2, border_radius=6)
        
        # Ojos indicando dirección
        eye_x = r.right - 8 if self.facing > 0 else r.left + 4
        pygame.draw.rect(scr, (255, 255, 255), (eye_x, r.top + 8, 4, 8))

class Level:
    def __init__(self, seed):
        rng = random.Random(seed)
        self.cols = 200
        self.grid = [[' '] * self.cols for _ in range(ROWS)]
        
        # Generación de suelo
        for c in range(self.cols):
            if c not in (30, 31, 75, 76, 120, 121):  # Huecos
                self.grid[12][c] = self.grid[13][c] = 'G'
            if rng.random() < 0.2 and c > 10:
                self.grid[8][c] = 'Q'
            elif rng.random() < 0.15 and c > 10:
                self.grid[8][c] = 'B'

    def is_solid(self, c, r):
        if c < 0 or c >= self.cols: return True
        if r < 0 or r >= ROWS: return False
        return self.grid[r][c] in SOLID

    def tiles_in(self, rect):
        out = []
        c0, c1 = rect.left // T, (rect.right - 1) // T
        r0, r1 = max(rect.top // T, 0), min((rect.bottom - 1) // T, ROWS - 1)
        for c in range(c0, c1 + 1):
            for r in range(r0, r1 + 1):
                if self.is_solid(c, r):
                    out.append((c, r, pygame.Rect(c * T, r * T, T, T)))
        return out

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("SUPER PYTHON BROS - MULTIJUGADOR ONLINE GLOBAL")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 20, bold=True)
        self.big_font = pygame.font.SysFont("arial", 40, bold=True)
        
        self.net = NetworkClient("127.0.0.1", 9999) # IP Servidor Global
        self.online_mode = False
        self.local_player = Player(0, "ALEX")
        self.level = Level(12345)
        self.cam_x = 0

    def start_online(self):
        name = f"Heroe_{random.randint(100, 999)}"
        if self.net.connect(name=name, room="global_1"):
            self.online_mode = True
            self.level = Level(self.net.seed)
            print("Conectado con éxito al Servidor Global!")

    def run(self):
        running = True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_o:
                    self.start_online()

            keys = pygame.key.get_pressed()
            self.local_player.update(keys, self.level)

            # Sincronización Online
            if self.online_mode and self.net.connected:
                self.net.send_state({
                    'x': self.local_player.x,
                    'y': self.local_player.y,
                    'vx': self.local_player.vx,
                    'vy': self.local_player.vy,
                    'facing': self.local_player.facing,
                    'anim': self.local_player.anim
                })

            # Cámara suave
            self.cam_x = max(0, int(self.local_player.x - W // 3))

            # Dibujado
            self.screen.fill((92, 148, 252))

            # Dibujar Nivel
            for c in range(self.cam_x // T, (self.cam_x + W) // T + 2):
                for r in range(ROWS):
                    if c < self.level.cols and self.level.grid[r][c] != ' ':
                        ch = self.level.grid[r][c]
                        color = (200, 76, 12) if ch == 'G' or ch == 'B' else (255, 188, 0)
                        pygame.draw.rect(self.screen, color, (c * T - self.cam_x, r * T, T, T))
                        pygame.draw.rect(self.screen, (0, 0, 0), (c * T - self.cam_x, r * T, T, T), 1)

            # Dibujar Jugador Local
            self.local_player.draw(self.screen, self.cam_x)

            # Dibujar Jugadores Remotos Online
            if self.online_mode and self.net.connected:
                for pid, pdata in list(self.net.remote_players.items()):
                    if pid != self.net.player_id:
                        rx, ry = pdata.get('x', 0) - self.cam_x, pdata.get('y', 0)
                        col = pdata.get('color', (230, 70, 160))
                        r = pygame.Rect(int(rx), int(ry), 30, 38)
                        pygame.draw.rect(self.screen, col, r, border_radius=6)
                        pygame.draw.rect(self.screen, (255, 255, 255), r, 2, border_radius=6)
                        
                        # Nombre sobre el jugador
                        lbl = self.font.render(pdata.get('name', 'Player'), True, (255, 255, 255))
                        self.screen.blit(lbl, (rx - 10, ry - 22))

            # HUD y Estado Online
            if self.online_mode and self.net.connected:
                hud_txt = f"ONLINE GLOBAL | Sala: {self.net.room_id} | Ping: {self.net.ping}ms"
                hud = self.font.render(hud_txt, True, (100, 255, 100))
            else:
                hud = self.font.render("MODO LOCAL - Presiona 'O' para conectar Online Global", True, (255, 255, 255))
            
            self.screen.blit(hud, (15, 15))

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()
