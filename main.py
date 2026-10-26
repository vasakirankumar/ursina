from ursina import *
from random import randint
from math import sin
import json
import os
import socket
import sys
import threading
import time as _time

app = Ursina()
window.title = 'VoxelCraft'
window.borderless = False
window.exit_button.visible = False
window.fps_counter.enabled = True
window.color = color.rgb(145, 185, 255)

GRASS = color.rgb(110, 180, 90)
DIRT = color.rgb(120, 85, 55)
STONE = color.rgb(120, 120, 130)
SAND = color.rgb(220, 205, 120)
WOOD = color.rgb(160, 110, 60)
LEAF = color.rgb(80, 170, 100)
BEDROCK = color.rgb(70, 70, 80)
BRICK = color.rgb(180, 90, 70)
SEMICONDUCTOR = color.rgb(80, 120, 180)
PHONE = color.rgb(35, 35, 40)
PORTAL = color.rgb(185, 70, 245)
WATER = color.rgba(55, 145, 220, 155)
CRYSTAL = color.rgb(105, 220, 235)
WORLD_SEED = 25981


class VoxelWorld:
    def __init__(self, radius=10):
        self.radius = radius
        self.seed = WORLD_SEED
        self.blocks = {}
        self.generate()

    def decoration_value(self, x, y, z=0):
        return abs((x * 374761393 + y * 668265263 + z * 2147483647 + self.seed) % 1000)

    def terrain_height(self, x, z):
        wave = sin(x * 0.75) + sin(z * 0.9) + sin((x + z) * 0.5)
        height = int((wave + 3.0) * 1.1)
        return max(2, min(7, height))

    def add_block(self, x, y, z, color, collider='box'):
        key = (round(x), round(y), round(z))
        if key in self.blocks:
            return
        if abs(x) > self.radius + 5 or abs(z) > self.radius + 5:
            return
        block = Entity(
            parent=scene,
            model='cube',
            color=color,
            texture='white_cube',
            position=(x, y, z),
            collider=collider
        )
        self.blocks[key] = block

    def remove_block(self, x, y, z):
        key = (round(x), round(y), round(z))
        block = self.blocks.pop(key, None)
        if block is not None:
            destroy(block)

    def add_tree(self, x, y, z):
        trunk_height = 3 + self.decoration_value(x, 17, z) % 3
        for h in range(trunk_height):
            self.add_block(x, y + h, z, WOOD)

        for dx in range(-2, 3):
            for dz in range(-2, 3):
                for dy in range(2, 5):
                    if abs(dx) + abs(dz) + abs(dy) <= 5:
                        if self.decoration_value(x + dx, y + dy, z + dz) % 3 != 0:
                            self.add_block(x + dx, y + trunk_height + dy - 2, z + dz, LEAF)

    def add_ruin(self, x, y, z):
        for dx in range(-2, 3):
            self.add_block(x + dx, y, z - 2, STONE)
            self.add_block(x + dx, y, z + 2, STONE)
        for dz in range(-1, 2):
            self.add_block(x - 2, y, z + dz, STONE)
            self.add_block(x + 2, y, z + dz, STONE)
        for height in range(1, 4):
            self.add_block(x - 2, y + height, z - 2, STONE)
            self.add_block(x + 2, y + height, z - 2, STONE)
            self.add_block(x - 2, y + height, z + 2, STONE)
            self.add_block(x + 2, y + height, z + 2, STONE)
        for dx in range(-1, 2):
            self.add_block(x + dx, y + 4, z - 2, STONE)

    def add_crystal_cluster(self, x, y, z):
        self.add_block(x, y, z, CRYSTAL)
        self.add_block(x, y + 1, z, CRYSTAL)
        if (x + z) % 2 == 0:
            self.add_block(x + 1, y, z, CRYSTAL)
        else:
            self.add_block(x, y, z + 1, CRYSTAL)

    def generate(self):
        for x in range(-self.radius, self.radius + 1):
            for z in range(-self.radius, self.radius + 1):
                height = self.terrain_height(x, z)

                for y in range(-4, height + 1):
                    if y == height:
                        top_color = SAND if height <= 3 else GRASS
                    elif y >= height - 2:
                        top_color = DIRT
                    else:
                        top_color = STONE
                    self.add_block(x, y, z, top_color)

                if height <= 3:
                    self.add_block(x, 3, z, WATER, collider=None)
                elif (x * 17 + z * 31) % 47 == 0:
                    self.add_crystal_cluster(x, height + 1, z)
                elif height > 2 and self.decoration_value(x, height, z) % 10 == 0:
                    self.add_tree(x, height + 1, z)

        ruin_x, ruin_z = self.radius - 5, self.radius - 5
        self.add_ruin(ruin_x, self.terrain_height(ruin_x, ruin_z) + 1, ruin_z)

        for x in range(-self.radius, self.radius + 1):
            for z in range(-self.radius, self.radius + 1):
                self.add_block(x, -5, z, BEDROCK)

    def expand_if_needed(self, position):
        if max(abs(position.x), abs(position.z)) < self.radius - 6:
            return
        self.radius += 12
        self.generate()


class MultiplayerManager:
    def __init__(self, host_mode=False, host='127.0.0.1', port=5005, player_name='Player', room_code='WORLD1'):
        self.host_mode = host_mode
        self.host = host
        self.port = port
        self.player_name = player_name
        self.room_code = room_code
        self.running = True
        self.peers = {}
        self.remote_players = {}
        self.remote_block_events = []
        self.chat_messages = []
        self.phone_messages = []
        self.server_block_state = {}
        self.host_state = {'name': self.player_name, 'growth_score': 0}
        self.votes = {}
        self.governor_name = ''

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', 0))
        self.socket.setblocking(False)

        if self.host_mode:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.setblocking(False)
            self.server_thread = threading.Thread(target=self._host_loop, daemon=True)
            self.server_thread.start()
        else:
            self.server_address = (self.host, self.port)
            self.client_thread = threading.Thread(target=self._client_loop, daemon=True)
            self.client_thread.start()

    def _host_loop(self):
        while self.running:
            try:
                data, addr = self.server_socket.recvfrom(65535)
            except socket.error:
                _time.sleep(0.05)
                continue

            try:
                payload = json.loads(data.decode('utf-8'))
            except Exception:
                continue

            if payload.get('room') != self.room_code:
                continue

            if payload.get('type') == 'player_state':
                self.peers[addr] = payload['data']
                snapshot = {
                    'type': 'snapshot',
                    'room': self.room_code,
                    'server_name': self.player_name,
                    'players': {
                        self.host_state.get('name', self.player_name): self.host_state,
                        **{player.get('name', str(peer[0])): player for peer, player in self.peers.items()},
                    },
                    'votes': self.votes,
                    'governor': self.governor_name,
                }
                for peer in list(self.peers.keys()):
                    try:
                        self.server_socket.sendto(json.dumps(snapshot).encode('utf-8'), peer)
                    except OSError:
                        pass
            elif payload.get('type') == 'block_action':
                self._apply_authoritative_block_event(payload)
                self.remote_block_events.append(payload)
                for peer in list(self.peers.keys()):
                    try:
                        self.server_socket.sendto(json.dumps(payload).encode('utf-8'), peer)
                    except OSError:
                        pass
            elif payload.get('type') == 'chat_message':
                self.chat_messages.append(payload)
                for peer in list(self.peers.keys()):
                    try:
                        self.server_socket.sendto(json.dumps(payload).encode('utf-8'), peer)
                    except OSError:
                        pass
            elif payload.get('type') == 'vote':
                self._register_vote(payload, addr)
            elif payload.get('type') in ('direct_message', 'location_share'):
                self._route_phone_payload(payload, addr)

    def _client_loop(self):
        while self.running:
            try:
                data, _ = self.socket.recvfrom(65535)
            except socket.error:
                _time.sleep(0.05)
                continue

            try:
                payload = json.loads(data.decode('utf-8'))
            except Exception:
                continue

            if payload.get('room') != self.room_code:
                continue

            if payload.get('type') == 'snapshot':
                self.remote_players = payload.get('players', {})
                self.server_player_name = payload.get('server_name', '')
                self.votes = payload.get('votes', {})
                self.governor_name = payload.get('governor', '')
            elif payload.get('type') == 'block_action':
                self.remote_block_events.append(payload)
            elif payload.get('type') == 'chat_message':
                self.chat_messages.append(payload)
            elif payload.get('type') in ('direct_message', 'location_share'):
                self.phone_messages.append(payload)
            elif payload.get('type') == 'governance':
                self.votes = payload.get('votes', {})
                self.governor_name = payload.get('governor', '')

    def _apply_authoritative_block_event(self, payload):
        action = payload.get('action')
        x = int(payload.get('x', 0))
        y = int(payload.get('y', 0))
        z = int(payload.get('z', 0))
        key = (x, y, z)

        if action == 'remove':
            self.server_block_state.pop(key, None)
        elif action == 'add':
            color_name = payload.get('color', 'grass')
            self.server_block_state[key] = color_name

    def _register_vote(self, payload, voter_address=None):
        voter_state = self.peers.get(voter_address, {})
        voter_name = voter_state.get('name', self.player_name if voter_address is None else '')
        candidate = payload.get('candidate', '').strip()
        candidates = {self.player_name} | {
            state.get('name') for state in self.peers.values() if state.get('name')
        }
        if not voter_name or candidate not in candidates:
            return

        self.votes[voter_name] = candidate
        counts = {name: 0 for name in candidates}
        for voted_name in self.votes.values():
            if voted_name in counts:
                counts[voted_name] += 1
        top_count = max(counts.values(), default=0)
        leaders = [name for name, count in counts.items() if count == top_count and count > 0]
        self.governor_name = leaders[0] if len(leaders) == 1 else ''
        governance_payload = {
            'type': 'governance',
            'room': self.room_code,
            'votes': self.votes,
            'governor': self.governor_name,
        }
        self._broadcast_payload(governance_payload)

    def _broadcast_payload(self, payload):
        for peer in list(self.peers.keys()):
            try:
                self.server_socket.sendto(json.dumps(payload).encode('utf-8'), peer)
            except OSError:
                pass

    def _route_phone_payload(self, payload, sender_address):
        sender_state = self.peers.get(sender_address, {})
        sender_name = sender_state.get('name', self.player_name if sender_address is None else payload.get('sender', 'Player'))
        recipient = payload.get('recipient', '').strip()
        if not recipient:
            return

        routed_payload = dict(payload)
        routed_payload['room'] = self.room_code
        routed_payload['sender'] = sender_name
        for peer, state in list(self.peers.items()):
            if state.get('name') == recipient:
                try:
                    self.server_socket.sendto(json.dumps(routed_payload).encode('utf-8'), peer)
                except OSError:
                    pass
                return

        if self.host_mode and recipient == self.player_name:
            self.phone_messages.append(routed_payload)

    def send_state(self, position, rotation_y=0.0, growth_score=0):
        payload = {
            'type': 'player_state',
            'room': self.room_code,
            'data': {
                'name': self.player_name,
                'x': float(position.x),
                'y': float(position.y),
                'z': float(position.z),
                'yaw': float(rotation_y),
                'growth_score': int(growth_score),
            }
        }

        if self.host_mode:
            self.host_state = payload['data']
            for peer in list(self.peers.keys()):
                try:
                    self.server_socket.sendto(json.dumps(payload).encode('utf-8'), peer)
                except OSError:
                    pass
        else:
            try:
                self.socket.sendto(json.dumps(payload).encode('utf-8'), self.server_address)
            except OSError:
                pass

    def send_block_action(self, action, x, y, z, color_name='grass'):
        payload = {'type': 'block_action', 'room': self.room_code, 'action': action, 'x': round(x), 'y': round(y), 'z': round(z), 'color': color_name}
        if self.host_mode:
            self._apply_authoritative_block_event(payload)
            for peer in list(self.peers.keys()):
                try:
                    self.server_socket.sendto(json.dumps(payload).encode('utf-8'), peer)
                except OSError:
                    pass
        else:
            try:
                self.socket.sendto(json.dumps(payload).encode('utf-8'), self.server_address)
            except OSError:
                pass

    def send_chat(self, text):
        payload = {'type': 'chat_message', 'room': self.room_code, 'sender': self.player_name, 'text': text}
        if self.host_mode:
            self.chat_messages.append(payload)
            for peer in list(self.peers.keys()):
                try:
                    self.server_socket.sendto(json.dumps(payload).encode('utf-8'), peer)
                except OSError:
                    pass
        else:
            try:
                self.socket.sendto(json.dumps(payload).encode('utf-8'), self.server_address)
            except OSError:
                pass

    def send_vote(self, candidate):
        payload = {'type': 'vote', 'room': self.room_code, 'candidate': candidate}
        if self.host_mode:
            self._register_vote(payload)
        else:
            try:
                self.socket.sendto(json.dumps(payload).encode('utf-8'), self.server_address)
            except OSError:
                pass

    def send_direct_message(self, recipient, text):
        payload = {
            'type': 'direct_message',
            'room': self.room_code,
            'sender': self.player_name,
            'recipient': recipient,
            'text': text,
        }
        if self.host_mode:
            self._route_phone_payload(payload, None)
        else:
            try:
                self.socket.sendto(json.dumps(payload).encode('utf-8'), self.server_address)
            except OSError:
                pass

    def send_location(self, recipient, position):
        payload = {
            'type': 'location_share',
            'room': self.room_code,
            'sender': self.player_name,
            'recipient': recipient,
            'x': round(float(position.x), 2),
            'y': round(float(position.y), 2),
            'z': round(float(position.z), 2),
        }
        if self.host_mode:
            self._route_phone_payload(payload, None)
        else:
            try:
                self.socket.sendto(json.dumps(payload).encode('utf-8'), self.server_address)
            except OSError:
                pass

    def is_room_member(self):
        return self.room_code is not None and bool(self.room_code.strip())


class Game:
    def __init__(self):
        self.sky = Sky(color=color.rgb(120, 170, 255))
        self.sun = Entity(parent=scene, model='sphere', color=color.yellow, scale=6, position=(25, 30, 25))

        self.game_started = False
        self.mobile_mode = '--mobile' in sys.argv
        self.player_profile_path = os.path.join(os.getcwd(), 'player_profiles.json')
        self.avatar_choice = 'Builder'
        self.player_name = 'Player'
        self.saved_profiles = []
        self.current_profile_index = 0
        self.room_code = 'WORLD1'
        self.avatar_palette = {
            'Builder': color.rgb(110, 180, 90),
            'Scout': color.rgb(90, 140, 220),
            'Engineer': color.rgb(200, 120, 80),
        }
        self.load_profile()

        self.player = FirstPersonController(
            position=(0, 12, 0),
            speed=6,
            gravity=1.2,
            height=2,
            mouse_sensitivity=(120, 120),
            jump_height=2.5,
        )
        self.player.cursor.visible = False
        self.player.cursor.enabled = False
        self.player.enabled = False

        self.player_avatar = Entity(
            parent=scene,
            model='cube',
            color=self.avatar_palette[self.avatar_choice],
            scale=(0.7, 1.7, 0.7),
            visible=False,
        )
        self.player_name_tag = Text(
            parent=self.player_avatar,
            text=self.player_name,
            position=(0, 1.4, 0),
            scale=0.9,
            origin=(0, 0),
            color=color.white,
            world_y=0,
        )
        self.player_speech_bubble = Text(
            parent=self.player_avatar,
            text='',
            position=(0, 1.9, 0),
            scale=0.75,
            origin=(0, 0),
            color=color.rgb(255, 245, 190),
            background=True,
        )
        self.player_speech_timer = 0.0

        self._build_avatar_selection()

        self.world = VoxelWorld(radius=12)
        self.locals = []
        self.local_dialogue_index = {}
        self.local_ambient_timer = 8.0
        self._build_locals()

        self.multiplayer = None
        self.remote_players = {}
        self.remote_player_entities = {}
        self._setup_multiplayer()

        self.materials = [GRASS, STONE, SAND, WOOD, BRICK, SEMICONDUCTOR, PHONE, PORTAL]
        self.inventory = [6, 6, 6, 4, 0, 0, 0, 0]
        self.selected_index = 0
        self.recipe_index = 0
        self.technology_tier = 0
        self.challenge_index = 0
        self.challenge_progress = 0
        self.challenges_enabled = True
        self.challenge_notice = ''
        self.challenge_notice_timer = 0.0
        self.growth_score = 0
        self.governance_started = False
        self.governor_name = ''
        self.settlement_name = 'Frontier Haven'
        self.governance_notice = ''
        self.phone_open = False
        self.phone_screen_mode = 0
        self.private_chat_mode = False
        self.private_recipient = ''
        self.portal_locations = []
        self.portal_cooldown = 0.0
        self.phone_apps = [
            ("Map", "Basecamp: x=0, z=0\nBiome: Meadow\nSignal: strong\nNearby: trees, stone"),
            ("Craft", "Crafting menu:\n- Stone Brick\n- Semiconductor\n- Mobile Phone\nUse C and R"),
            ("Messages", "From: System\n\nWelcome back!\nYour phone is online."),
            ("Tools", "Tools:\n- Pickaxe\n- Axe\n- Flashlight\n- Map"),
        ]
        self.crafting_recipes = [
            {"name": "Stone Brick", "requires": {"stone": 2, "sand": 1}, "result_index": 4, "tier": 0},
            {"name": "Wood Planks", "requires": {"wood": 2}, "result_index": 0, "tier": 0},
            {"name": "Semiconductor", "requires": {"stone": 2, "sand": 1}, "result_index": 5, "tier": 1},
            {"name": "Mobile Phone", "requires": {"semiconductor": 2, "wood": 1, "brick": 1}, "result_index": 6, "tier": 2},
            {"name": "Transportation Portal", "requires": {"semiconductor": 4, "brick": 4, "phone": 1}, "result_index": 7, "tier": 3},
        ]
        self.challenges = [
            {'name': 'Gatherer', 'kind': 'mined', 'goal': 10, 'reward_index': 4, 'reward_amount': 2},
            {'name': 'Builder', 'kind': 'built', 'goal': 5, 'reward_index': 3, 'reward_amount': 3},
            {'name': 'Craftsman', 'kind': 'crafted', 'goal': 3, 'reward_index': 5, 'reward_amount': 1},
            {'name': 'Wayfinder', 'kind': 'distance', 'goal': 100, 'reward_index': 2, 'reward_amount': 4},
            {'name': 'Storykeeper', 'kind': 'listened', 'goal': 3, 'reward_index': 1, 'reward_amount': 4},
        ]

        self.slot_widgets = []
        self.hotbar_background = Entity(parent=camera.ui, model='quad', color=color.rgba(20, 20, 20, 180), scale=(0.58, 0.11), position=(0, -0.44))

        for index, color_value in enumerate(self.materials):
            slot = Entity(
                parent=camera.ui,
                model='quad',
                color=color.rgba(80, 80, 80, 160),
                scale=(0.12, 0.10),
                position=(-0.27 + index * 0.077, -0.44),
            )
            Entity(
                parent=slot,
                model='cube',
                color=color_value,
                scale=(0.45, 0.45, 0.45),
                position=(0, 0, -0.02),
                texture='white_cube',
            )
            count_text = Text(
                text=str(self.inventory[index]),
                position=(0.04, -0.03),
                scale=0.8,
                parent=slot,
                origin=(0, 0),
                color=color.white,
            )
            self.slot_widgets.append((slot, count_text))

        self.selection_border = Entity(
            parent=camera.ui,
            model='quad',
            color=color.rgba(255, 255, 255, 180),
            scale=(0.13, 0.11),
            position=(-0.27, -0.44),
            z=0.05,
        )

        self.block_preview = Entity(
            parent=camera.ui,
            model='cube',
            texture='white_cube',
            color=self.materials[0],
            scale=(0.08, 0.08, 0.08),
            position=(0.78, -0.38),
            rotation=(20, 30, 0),
            double_sided=True,
        )
        self.phone_ui = Entity(
            parent=camera.ui,
            model='quad',
            color=color.rgba(15, 20, 30, 220),
            scale=(0.38, 0.62),
            position=(0, 0.08),
            visible=False,
        )
        self.phone_screen = Text(
            parent=self.phone_ui,
            text='',
            position=(-0.12, 0.18),
            scale=1.25,
            origin=(0, 0),
            color=color.white,
        )
        self.phone_status = Text(
            parent=self.phone_ui,
            text='Battery: 83%\nSignal: strong',
            position=(-0.12, -0.15),
            scale=1.0,
            origin=(0, 0),
            color=color.rgb(120, 220, 150),
        )
        self.private_chat_button = Button(
            parent=self.phone_ui,
            text='P',
            position=(0.13, 0.25),
            scale=(0.08, 0.08),
            color=color.rgb(70, 150, 110),
            on_click=self.toggle_private_chat,
        )
        self.private_target_button = Button(
            parent=self.phone_ui,
            text='>',
            position=(0.13, 0.15),
            scale=(0.08, 0.08),
            color=color.rgb(70, 90, 120),
            on_click=self.cycle_private_recipient,
        )
        self.private_mode_label = Text(
            parent=self.phone_ui,
            text='Public chat',
            position=(-0.12, -0.22),
            scale=0.75,
            origin=(0, 0),
            color=color.rgb(220, 220, 220),
        )
        self.crosshair = Entity(
            parent=camera.ui,
            model='quad',
            color=color.white,
            scale=(0.008, 0.03),
            position=(0, 0),
        )

        self.health = 100.0
        self.hunger = 100.0
        self.stamina = 100.0
        self.food = 3
        self.day_time = 0.0
        self.day_length = 180.0
        self.last_y = self.player.y
        self.last_position = Vec3(self.player.position)
        self.restore_progression()

        self.health_bg = Entity(parent=camera.ui, model='quad', color=color.rgba(30, 30, 30, 180), scale=(0.38, 0.03), position=(-0.38, 0.47))
        self.health_bar = Entity(parent=camera.ui, model='quad', color=color.red, scale=(0.36, 0.02), position=(-0.38, 0.47))
        self.hunger_bg = Entity(parent=camera.ui, model='quad', color=color.rgba(30, 30, 30, 180), scale=(0.38, 0.03), position=(-0.38, 0.41))
        self.hunger_bar = Entity(parent=camera.ui, model='quad', color=color.rgb(235, 180, 60), scale=(0.36, 0.02), position=(-0.38, 0.41))
        self.stamina_bg = Entity(parent=camera.ui, model='quad', color=color.rgba(30, 30, 30, 180), scale=(0.38, 0.03), position=(-0.38, 0.35))
        self.stamina_bar = Entity(parent=camera.ui, model='quad', color=color.rgb(80, 180, 255), scale=(0.36, 0.02), position=(-0.38, 0.35))

        self.hud = Text(
            text='WASD move | Space jump | Left click remove | Right click place | 1-8 hotbar | E listen | F eat | C craft | R recipe | P phone',
            position=(-0.8, 0.46),
            scale=1.0,
            origin=(0, 0),
            color=color.white,
            background=True,
        )
        self.craft_text = Text(
            text='',
            position=(-0.8, 0.12),
            scale=1.0,
            origin=(0, 0),
            color=color.yellow,
        )
        self.quest_text = Text(
            text='',
            position=(-0.8, 0.06),
            scale=0.9,
            origin=(0, 0),
            color=color.rgb(150, 220, 255),
        )
        self.network_label = Text(
            text='',
            position=(0.52, 0.46),
            scale=0.9,
            origin=(0, 0),
            color=color.rgb(120, 250, 180),
            background=True,
        )
        self.status = Text(
            text='',
            position=(-0.8, 0.26),
            scale=1.0,
            origin=(0, 0),
            color=color.white,
        )
        self.local_dialogue = Text(
            text='',
            position=(-0.8, -0.18),
            scale=1.05,
            origin=(0, 0),
            color=color.rgb(255, 235, 170),
            background=True,
        )
        self._build_mobile_controls()

    def _build_mobile_controls(self):
        self.mobile_controls = Entity(parent=camera.ui, visible=self.mobile_mode)
        control_color = color.rgba(30, 40, 50, 190)
        controls = [
            ('UP', (0.0, -0.26), lambda: self._mobile_step(0, 1)),
            ('DOWN', (0.0, -0.44), lambda: self._mobile_step(0, -1)),
            ('LEFT', (-0.1, -0.35), lambda: self._mobile_step(-1, 0)),
            ('RIGHT', (0.1, -0.35), lambda: self._mobile_step(1, 0)),
            ('JUMP', (0.68, -0.22), self._mobile_jump),
            ('BREAK', (0.68, -0.34), self._mobile_break_block),
            ('PLACE', (0.68, -0.46), self._mobile_place_block),
            ('LISTEN', (-0.68, -0.28), self._listen_to_local),
            ('PHONE', (-0.68, -0.40), self._mobile_phone),
            ('CRAFT', (-0.68, -0.52), self.craft_selected),
            ('QUESTS', (0.68, -0.52), self._toggle_challenges),
        ]
        for label, position, action in controls:
            Button(
                parent=self.mobile_controls,
                text=label,
                position=position,
                scale=(0.15, 0.09),
                color=control_color,
                on_click=action,
            )

    def _mobile_step(self, x, z):
        self.player.position += Vec3(x * 1.3, 0, z * 1.3)

    def _mobile_jump(self):
        self.player.jump()

    def _mobile_phone(self):
        if self.inventory[6] > 0:
            self.phone_open = True

    def _mobile_break_block(self):
        hit = raycast(camera.world_position, camera.forward, distance=8, ignore=[self.player])
        if not hit.hit or hit.entity not in self.world.blocks.values():
            return
        position = hit.entity.position
        block_color = hit.entity.color
        if self.multiplayer is not None:
            if self.multiplayer.host_mode:
                self.world.remove_block(position.x, position.y, position.z)
            self.multiplayer.send_block_action('remove', position.x, position.y, position.z, 'grass')
        else:
            self.world.remove_block(position.x, position.y, position.z)
        color_indexes = {GRASS: 0, STONE: 1, SAND: 2, WOOD: 3, BRICK: 4, SEMICONDUCTOR: 5, PHONE: 6, PORTAL: 7}
        if block_color in color_indexes:
            self.inventory[color_indexes[block_color]] += 1
        self._record_activity('mined')

    def _mobile_place_block(self):
        if self.inventory[self.selected_index] <= 0:
            return
        hit = raycast(camera.world_position, camera.forward, distance=8, ignore=[self.player])
        if not hit.hit:
            return
        target = hit.entity.position + hit.normal
        x, y, z = round(target.x), round(target.y), round(target.z)
        if abs(x) > self.world.radius + 3 or abs(z) > self.world.radius + 3:
            return
        color_names = ['grass', 'stone', 'sand', 'wood', 'brick', 'semiconductor', 'phone', 'portal']
        color_name = color_names[self.selected_index]
        self.world.add_block(x, y, z, self.materials[self.selected_index])
        self.inventory[self.selected_index] -= 1
        if color_name == 'portal' and (x, y, z) not in self.portal_locations:
            self.portal_locations.append((x, y, z))
        self._record_activity('built')
        if self.multiplayer is not None:
            self.multiplayer.send_block_action('add', x, y, z, color_name)

    def _build_locals(self):
        local_data = [
            ('Mara the Mason', -5, -2, color.rgb(210, 135, 90), [
                'The old stones remember every builder who came before us.',
                'Brick is humble, but every great machine starts with a solid frame.',
                'There is a ruin near the eastern ridge. Listen for the wind through it.',
            ]),
            ('Tovin the Scout', 4, -4, color.rgb(95, 170, 220), [
                'The land keeps unfolding. Walk far enough and it will make room for you.',
                'Crystals glow where the deep earth is close to the surface.',
                'Keep your coordinates handy. The frontier is wider than it looks.',
            ]),
            ('Iria the Tinkerer', -3, 5, color.rgb(170, 105, 210), [
                'Semiconductors are the first whisper of an electronic age.',
                'Phones can carry messages farther than any campfire can carry a voice.',
                'Two portal frames can turn a long journey into a single step.',
            ]),
        ]

        for name, x, z, npc_color, lines in local_data:
            ground_y = self.world.terrain_height(x, z) + 1
            entity = Entity(
                parent=scene,
                model='cube',
                color=npc_color,
                scale=(0.7, 1.6, 0.7),
                position=(x, ground_y + 0.8, z),
            )
            Text(
                parent=entity,
                text=name,
                position=(0, 1.2, 0),
                scale=0.7,
                origin=(0, 0),
                color=color.white,
                world_y=0,
            )
            self.locals.append({
                'name': name,
                'entity': entity,
                'base_y': ground_y + 0.8,
                'lines': lines,
            })
            self.local_dialogue_index[name] = 0

    def _nearest_local(self, max_distance=10):
        nearby = [
            local for local in self.locals
            if distance(self.player.position, local['entity'].position) <= max_distance
        ]
        return min(
            nearby,
            key=lambda local: distance(self.player.position, local['entity'].position),
            default=None,
        )

    def _listen_to_local(self):
        local = self._nearest_local()
        if local is None:
            self.local_dialogue.text = 'No local is close enough to hear you.'
            return

        name = local['name']
        line_index = self.local_dialogue_index[name]
        self.local_dialogue.text = f'{name}: {local["lines"][line_index]}'
        self.local_dialogue_index[name] = (line_index + 1) % len(local['lines'])
        self._record_activity('listened')

    def _toggle_challenges(self):
        self.challenges_enabled = not self.challenges_enabled
        self.challenge_notice = 'Challenges enabled' if self.challenges_enabled else 'Challenges paused'
        self.challenge_notice_timer = 3.0

    def _record_activity(self, kind, amount=1):
        growth_weights = {'mined': 1, 'built': 3, 'crafted': 4, 'listened': 1, 'distance': 0.1}
        if kind in growth_weights:
            self.growth_score += max(1, int(amount * growth_weights[kind]))
        if not self.challenges_enabled:
            return
        challenge = self.challenges[self.challenge_index]
        if challenge['kind'] != kind:
            return
        self.challenge_progress = min(challenge['goal'], self.challenge_progress + amount)
        if self.challenge_progress >= challenge['goal']:
            self.inventory[challenge['reward_index']] += challenge['reward_amount']
            self.challenge_notice = f'Challenge complete: {challenge["name"]} (+{challenge["reward_amount"]} reward)'
            self.challenge_notice_timer = 4.0
            self.challenge_index = (self.challenge_index + 1) % len(self.challenges)
            self.challenge_progress = 0

    def _update_governance(self):
        candidates = {self.player_name: self.growth_score}
        candidates.update({
            name: int(state.get('growth_score', 0))
            for name, state in self.remote_players.items()
            if isinstance(state, dict)
        })
        highest_growth = max(candidates.values(), default=0)
        if highest_growth < 20:
            self.governance_started = False
            self.governor_name = ''
            return

        if not self.governance_started:
            self.governance_started = True
            self.governor_name = ''
            self.governance_notice = f'{self.settlement_name} is voting. Use /vote PlayerName.'

        manager_governor = getattr(self.multiplayer, 'governor_name', '') if self.multiplayer is not None else ''
        if manager_governor in candidates:
            self.governor_name = manager_governor

    def _speak(self, message):
        message = message.strip()
        if not message:
            return

        self.player_speech_bubble.text = message[:80]
        self.player_speech_timer = 5.0
        local = self._nearest_local(max_distance=12)
        if local is not None:
            self.local_dialogue.text = f'{local["name"]} heard you: Keep moving, {self.player_name}.'
        if self.multiplayer is not None:
            self.multiplayer.send_chat(message)

    def _update_locals(self):
        local = self._nearest_local()
        if local is not None and not self.local_dialogue.text:
            self.local_dialogue.text = f'{local["name"]} is nearby. Press E to listen.'
        elif local is None and self.local_dialogue.text.endswith('Press E to listen.'):
            self.local_dialogue.text = ''

        self.local_ambient_timer -= time.dt
        self.player_speech_timer = max(0.0, self.player_speech_timer - time.dt)
        if self.player_speech_timer <= 0:
            self.player_speech_bubble.text = ''
        if self.local_ambient_timer <= 0:
            self.local_ambient_timer = 12.0
            if local is not None:
                line_index = self.local_dialogue_index[local['name']]
                self.local_dialogue.text = f'{local["name"]}: {local["lines"][line_index]}'
                self.local_dialogue_index[local['name']] = (line_index + 1) % len(local['lines'])

        for index, resident in enumerate(self.locals):
            resident['entity'].y = resident['base_y'] + sin(self.day_time * 1.7 + index) * 0.04

    def load_profile(self):
        if os.path.exists(self.player_profile_path):
            try:
                with open(self.player_profile_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                if isinstance(data, list):
                    self.saved_profiles = data
                elif isinstance(data, dict):
                    self.saved_profiles = [data]
            except Exception:
                self.saved_profiles = []

        if not self.saved_profiles:
            self.saved_profiles = [{'name': 'Player', 'avatar': 'Builder'}]

        self.current_profile_index = 0
        self.player_name = self.saved_profiles[0].get('name', 'Player')
        self.avatar_choice = self.saved_profiles[0].get('avatar', 'Builder')
        if self.avatar_choice not in self.avatar_palette:
            self.avatar_choice = 'Builder'
        if not self.player_name.strip():
            self.player_name = 'Player'

    def restore_progression(self):
        profile = self.saved_profiles[self.current_profile_index]
        progression = profile.get('progression', {})
        saved_inventory = progression.get('inventory')

        if isinstance(saved_inventory, list):
            migrated_inventory = saved_inventory[:len(self.inventory)]
            migrated_inventory.extend([0] * (len(self.inventory) - len(migrated_inventory)))
            self.inventory = [max(0, int(value)) for value in migrated_inventory]

        self.health = min(100.0, max(0.0, float(progression.get('health', self.health))))
        self.hunger = min(100.0, max(0.0, float(progression.get('hunger', self.hunger))))
        self.stamina = min(100.0, max(0.0, float(progression.get('stamina', self.stamina))))
        self.food = max(0, int(progression.get('food', self.food)))
        self.selected_index = min(len(self.inventory) - 1, max(0, int(progression.get('selected_index', self.selected_index))))
        self.recipe_index = min(len(self.crafting_recipes) - 1, max(0, int(progression.get('recipe_index', self.recipe_index))))
        self.technology_tier = min(3, max(0, int(progression.get('technology_tier', self.technology_tier))))
        self.challenge_index = min(len(self.challenges) - 1, max(0, int(progression.get('challenge_index', self.challenge_index))))
        self.challenge_progress = max(0, int(progression.get('challenge_progress', self.challenge_progress)))
        self.challenges_enabled = bool(progression.get('challenges_enabled', self.challenges_enabled))
        self.growth_score = max(0, int(progression.get('growth_score', self.growth_score)))
        self.governance_started = bool(progression.get('governance_started', self.governance_started))
        self.governor_name = progression.get('governor_name', self.governor_name)
        self.day_time = max(0.0, float(progression.get('day_time', self.day_time)))

        position = progression.get('position')
        if isinstance(position, list) and len(position) == 3:
            self.player.position = tuple(float(value) for value in position)
        self.last_y = self.player.y
        self.last_position = Vec3(self.player.position)

    def save_profile(self):
        profile = {
            'name': self.player_name,
            'avatar': self.avatar_choice,
            'progression': {
                'inventory': list(self.inventory),
                'health': round(self.health, 2),
                'hunger': round(self.hunger, 2),
                'stamina': round(self.stamina, 2),
                'food': self.food,
                'selected_index': self.selected_index,
                'recipe_index': self.recipe_index,
                'technology_tier': self.technology_tier,
                'challenge_index': self.challenge_index,
                'challenge_progress': self.challenge_progress,
                'challenges_enabled': self.challenges_enabled,
                'growth_score': self.growth_score,
                'governance_started': self.governance_started,
                'governor_name': self.governor_name,
                'day_time': round(self.day_time, 2),
                'position': [round(self.player.x, 2), round(self.player.y, 2), round(self.player.z, 2)],
            },
        }
        if self.current_profile_index < len(self.saved_profiles):
            self.saved_profiles[self.current_profile_index] = profile
        else:
            self.saved_profiles.append(profile)
            self.current_profile_index = len(self.saved_profiles) - 1

        try:
            with open(self.player_profile_path, 'w', encoding='utf-8') as file:
                json.dump(self.saved_profiles, file)
        except Exception:
            pass

    def select_profile(self, index):
        if 0 <= index < len(self.saved_profiles):
            self.current_profile_index = index
            profile = self.saved_profiles[index]
            self.player_name = profile.get('name', 'Player')
            self.avatar_choice = profile.get('avatar', 'Builder')
            if self.avatar_choice not in self.avatar_palette:
                self.avatar_choice = 'Builder'
            self.avatar_name_input.text = self.player_name
            self.avatar_preview.color = self.avatar_palette[self.avatar_choice]
            self.player_avatar.color = self.avatar_palette[self.avatar_choice]
            if hasattr(self, 'inventory'):
                self.restore_progression()

    def _build_avatar_selection(self):
        self.selection_panel = Entity(parent=camera.ui, y=0.1)
        Text('Choose your avatar', parent=self.selection_panel, y=0.18, scale=1.6, origin=(0, 0), color=color.white)

        self.profile_buttons = []
        for index, profile in enumerate(self.saved_profiles[:3]):
            btn = Button(
                parent=self.selection_panel,
                text=f"{profile.get('name', 'Player')} ({profile.get('avatar', 'Builder')})",
                color=self.avatar_palette.get(profile.get('avatar', 'Builder'), color.white),
                scale=(0.28, 0.08),
                position=(-0.32 + index * 0.32, 0.25),
                on_click=lambda idx=index: self.select_profile(idx),
            )
            self.profile_buttons.append(btn)

        self.avatar_name_input = InputField(
            parent=self.selection_panel,
            default=self.player_name,
            text=self.player_name,
            position=(0, 0.08),
            scale=(0.5, 0.06),
            max_lines=1,
        )

        self.avatar_preview = Entity(
            parent=self.selection_panel,
            model='cube',
            color=self.avatar_palette[self.avatar_choice],
            scale=(0.9, 1.8, 0.45),
            position=(0.35, -0.07),
        )

        self.avatar_buttons = []
        for index, name in enumerate(self.avatar_palette.keys()):
            button = Button(
                parent=self.selection_panel,
                text=name,
                color=self.avatar_palette[name],
                scale=(0.22, 0.08),
                position=(-0.3 + index * 0.3, -0.2),
                on_click=lambda choice=name: self.select_avatar(choice),
            )
            self.avatar_buttons.append(button)

        self.new_profile_button = Button(
            parent=self.selection_panel,
            text='New profile',
            color=color.rgba(70, 70, 70, 180),
            scale=(0.2, 0.07),
            position=(0.25, 0.25),
            on_click=self.create_new_profile,
        )

    def create_new_profile(self):
        new_name = f'Player {len(self.saved_profiles) + 1}'
        new_profile = {'name': new_name, 'avatar': 'Builder'}
        self.saved_profiles.append(new_profile)
        self.current_profile_index = len(self.saved_profiles) - 1
        self.player_name = new_name
        self.avatar_choice = 'Builder'
        self.avatar_name_input.text = self.player_name
        self.avatar_preview.color = self.avatar_palette[self.avatar_choice]
        self.player_avatar.color = self.avatar_palette[self.avatar_choice]
        self.inventory = [6, 6, 6, 4, 0, 0, 0, 0]
        self.health = 100.0
        self.hunger = 100.0
        self.stamina = 100.0
        self.food = 3
        self.selected_index = 0
        self.recipe_index = 0
        self.technology_tier = 0
        self.challenge_index = 0
        self.challenge_progress = 0
        self.challenges_enabled = True
        self.growth_score = 0
        self.governance_started = False
        self.governor_name = ''
        self.day_time = 0.0
        self.player.position = (0, 12, 0)
        self.save_profile()

    def select_avatar(self, choice):
        self.avatar_choice = choice
        self.avatar_preview.color = self.avatar_palette[choice]
        self.player_avatar.color = self.avatar_palette[choice]
        self.player_name = self.avatar_name_input.text.strip() or 'Player'
        self.player_name_tag.text = self.player_name
        self.save_profile()
        self.game_started = True
        self.player.enabled = True
        self.selection_panel.disable()
        destroy(self.selection_panel)

    def _setup_multiplayer(self):
        self.room_code = 'WORLD1'
        if '--host' in sys.argv:
            for arg in sys.argv:
                if arg.startswith('--host='):
                    self.room_code = arg.split('=', 1)[1].upper()
                    break
            self.multiplayer = MultiplayerManager(host_mode=True, host='127.0.0.1', port=5005, player_name=self.player_name or 'Host', room_code=self.room_code)
            self.network_label.text = f'Multiplayer: Host [{self.room_code}]'
        elif '--join' in sys.argv:
            target = '127.0.0.1'
            room_arg = self.room_code
            for arg in sys.argv:
                if arg.startswith('--join='):
                    value = arg.split('=', 1)[1]
                    if '@' in value:
                        room_arg, target = value.split('@', 1)
                    else:
                        room_arg = value
                    break
            self.room_code = room_arg.upper()
            self.multiplayer = MultiplayerManager(host_mode=False, host=target, port=5005, player_name=self.player_name or 'Client', room_code=self.room_code)
            self.network_label.text = f'Multiplayer: Client -> {target} [{self.room_code}]'
        else:
            self.network_label.text = 'Multiplayer: Offline'

        self.chat_messages = []
        self.chat_input = InputField(
            parent=camera.ui,
            position=(0, -0.36),
            scale=(0.42, 0.06),
            text='',
            default='',
            visible=False,
            enabled=False,
        )
        self.chat_label = Text(
            parent=camera.ui,
            text='',
            position=(-0.78, -0.26),
            scale=0.9,
            origin=(0, 0),
            color=color.white,
        )

    def _sync_remote_players(self):
        if self.multiplayer is None:
            return

        self.remote_players = getattr(self.multiplayer, 'remote_players', {})
        current_names = set(self.remote_players.keys())

        for name, state in self.remote_players.items():
            if name == self.multiplayer.player_name:
                continue
            if name not in self.remote_player_entities:
                self.remote_player_entities[name] = Entity(
                    parent=scene,
                    model='cube',
                    color=color.azure,
                    position=(state['x'], state['y'], state['z']),
                    scale=(0.8, 1.8, 0.8),
                )
            entity = self.remote_player_entities[name]
            entity.position = (state['x'], state['y'], state['z'])
            entity.rotation_y = state.get('yaw', 0.0)

        for name in list(self.remote_player_entities.keys()):
            if name not in current_names:
                destroy(self.remote_player_entities.pop(name))

    def _phone_contacts(self):
        if self.multiplayer is None:
            return []
        contacts = set(self.remote_players.keys())
        server_name = getattr(self.multiplayer, 'server_player_name', '')
        if server_name and server_name != self.player_name:
            contacts.add(server_name)
        return sorted(contact for contact in contacts if contact and contact != self.player_name)

    def toggle_private_chat(self):
        self.private_chat_mode = not self.private_chat_mode
        if self.private_chat_mode and not self.private_recipient:
            contacts = self._phone_contacts()
            self.private_recipient = contacts[0] if contacts else ''

    def cycle_private_recipient(self):
        contacts = self._phone_contacts()
        if not contacts:
            self.private_recipient = ''
            return
        if self.private_recipient not in contacts:
            self.private_recipient = contacts[0]
            return
        current_index = contacts.index(self.private_recipient)
        self.private_recipient = contacts[(current_index + 1) % len(contacts)]

    def _send_phone_command(self, command):
        if self.multiplayer is None:
            return

        lowered = command.lower()
        contacts = sorted(self._phone_contacts(), key=len, reverse=True)
        if lowered.startswith('/vote '):
            candidate = command[6:].strip()
            candidates = contacts + ([self.player_name] if self.player_name not in contacts else [])
            for name in sorted(candidates, key=len, reverse=True):
                if candidate.lower() == name.lower():
                    if self.multiplayer is not None:
                        self.multiplayer.send_vote(name)
                    else:
                        self.votes = {self.player_name: name}
                        self.governor_name = name
                    return
            return
        if lowered.startswith('/msg '):
            message_body = command[5:].strip()
            for contact in contacts:
                prefix = f'{contact} '
                if message_body.lower().startswith(prefix.lower()):
                    text = message_body[len(prefix):].strip()
                    if text:
                        self.multiplayer.send_direct_message(contact, text)
                    return
        if lowered.startswith('/loc '):
            recipient = command[5:].strip()
            for contact in contacts:
                if recipient.lower() == contact.lower():
                    self.multiplayer.send_location(contact, self.player.position)
                    return
        self.multiplayer.send_chat(command)

    def _apply_block_event(self, action, x, y, z, color_name='grass'):
        if not self.multiplayer:
            return

        if action == 'remove':
            self.world.remove_block(x, y, z)
            location = (round(x), round(y), round(z))
            if location in self.portal_locations:
                self.portal_locations.remove(location)
            return

        color_map = {
            'grass': GRASS,
            'stone': STONE,
            'sand': SAND,
            'wood': WOOD,
            'brick': BRICK,
            'semiconductor': SEMICONDUCTOR,
            'phone': PHONE,
            'portal': PORTAL,
            'dirt': DIRT,
            'leaf': LEAF,
            'bedrock': BEDROCK,
        }
        if not self.world.blocks.get((round(x), round(y), round(z))):
            self.world.add_block(x, y, z, color_map.get(color_name, GRASS))
            if color_name == 'portal' and (round(x), round(y), round(z)) not in self.portal_locations:
                self.portal_locations.append((round(x), round(y), round(z)))

    def _process_remote_block_events(self):
        if self.multiplayer is None:
            return

        events = getattr(self.multiplayer, 'remote_block_events', [])
        if not events:
            return

        for event in events:
            action = event.get('action')
            x = int(event.get('x', 0))
            y = int(event.get('y', 0))
            z = int(event.get('z', 0))
            color_name = event.get('color', 'grass')
            self._apply_block_event(action, x, y, z, color_name)

        self.multiplayer.remote_block_events = []

    def _activate_portal(self):
        if self.portal_cooldown > 0 or len(self.portal_locations) < 2:
            return

        current = Vec3(self.player.x, self.player.y, self.player.z)
        nearby = next(
            (location for location in self.portal_locations if distance(current, Vec3(*location)) < 1.8),
            None,
        )
        if nearby is None:
            return

        destination = next((location for location in self.portal_locations if location != nearby), None)
        if destination is not None:
            self.player.position = (destination[0], destination[1] + 2, destination[2])
            self.portal_cooldown = 2.0

    def take_damage(self, amount):
        self.health = max(0.0, self.health - amount)
        if self.health <= 0:
            self.player.position = (0, 12, 0)
            self.health = 100.0
            self.hunger = 70.0
            self.stamina = 100.0

    def eat_food(self):
        if self.food > 0 and self.hunger < 100:
            self.food -= 1
            self.hunger = min(100.0, self.hunger + 35.0)
            self.health = min(100.0, self.health + 8.0)

    def time_of_day(self):
        minutes = int((self.day_time % self.day_length) / self.day_length * 24 * 60)
        hours = (minutes // 60) % 24
        minute = minutes % 60
        return f'{hours:02d}:{minute:02d}'

    def update_ui(self):
        self.health_bar.scale_x = 0.36 * (self.health / 100.0)
        self.hunger_bar.scale_x = 0.36 * (self.hunger / 100.0)
        self.stamina_bar.scale_x = 0.36 * (self.stamina / 100.0)

        if self.health < 30:
            self.health_bar.color = color.rgb(220, 50, 50)
        else:
            self.health_bar.color = color.rgb(220, 70, 70)

        for index, (slot, count_text) in enumerate(self.slot_widgets):
            count_text.text = str(self.inventory[index])
            if index == self.selected_index:
                slot.color = color.rgba(120, 120, 120, 200)
            else:
                slot.color = color.rgba(80, 80, 80, 160)
            slot.scale = Vec2(0.12, 0.10)

        self.selection_border.position = (-0.27 + self.selected_index * 0.077, -0.44)
        self.selection_border.scale = (0.13, 0.11)

        phone_selected = self.selected_index == 6 and self.inventory[6] > 0
        self.phone_ui.visible = phone_selected and self.phone_open
        self.block_preview.visible = not (phone_selected and self.phone_open)
        contacts = self._phone_contacts()
        if self.private_recipient not in contacts:
            self.private_recipient = contacts[0] if contacts else ''
        self.private_chat_button.text = 'P' if self.private_chat_mode else 'C'
        self.private_chat_button.color = color.rgb(180, 85, 85) if self.private_chat_mode else color.rgb(70, 150, 110)
        self.private_target_button.text = '>'
        self.private_mode_label.text = (
            f'Private: {self.private_recipient}' if self.private_chat_mode and self.private_recipient
            else 'Private: no friend' if self.private_chat_mode
            else 'Public chat'
        )

        app_name, app_text = self.phone_apps[self.phone_screen_mode]
        if self.phone_screen_mode == 2 and self.multiplayer is not None:
            contacts = ', '.join(self._phone_contacts()) or 'No friends online'
            messages = []
            for message in self.multiplayer.phone_messages[-3:]:
                if message.get('type') == 'location_share':
                    messages.append(
                        f'{message.get("sender", "Friend")} shared ({message.get("x")}, {message.get("y")}, {message.get("z")})'
                    )
                else:
                    messages.append(f'{message.get("sender", "Friend")}: {message.get("text", "")}')
            app_text = (
                f'Friends: {contacts}\n'
                + ('\n'.join(messages) if messages else 'No private messages')
                + '\n\n/msg Friend hello\n/loc Friend'
            )
        self.phone_screen.text = f'PixelCraft\n\n{app_name}\n\n{app_text}'

        current_recipe = self.crafting_recipes[self.recipe_index]
        tier_names = ['Primitive', 'Industrial', 'Electronic', 'Advanced']
        recipe_tier = current_recipe.get('tier', 0)
        recipe_state = 'Unlocked' if recipe_tier <= self.technology_tier + 1 else 'Locked'
        self.craft_text.text = (
            f'Tech: {tier_names[self.technology_tier]} | Recipe: {current_recipe["name"]} ({current_recipe["requires"]}) | {recipe_state} | Press C to craft'
        )
        challenge = self.challenges[self.challenge_index]
        governance_text = (
            f'Vote for governor with /vote Name' if self.governance_started and not self.governor_name
            else f'Governor: {self.governor_name}' if self.governor_name
            else ''
        )
        self.quest_text.text = (
            self.challenge_notice if self.challenge_notice_timer > 0 else
            f'Challenge: {challenge["name"]} {self.challenge_progress}/{challenge["goal"]} | Q: toggle'
            if self.challenges_enabled else
            'Challenges paused | Press Q or tap QUESTS to enable'
        )
        if governance_text:
            self.local_dialogue.text = governance_text

        if self.multiplayer is not None:
            self.chat_label.text = ' | '.join(
                f'{msg["sender"]}: {msg["text"]}' for msg in self.multiplayer.chat_messages[-3:]
            )
        else:
            self.chat_label.text = ''

        self.status.text = (
            f'Health: {int(self.health)} | Hunger: {int(self.hunger)} | Stamina: {int(self.stamina)} | Food: {self.food} | Time: {self.time_of_day()} | Pos: ({self.player.x:.1f}, {self.player.y:.1f}, {self.player.z:.1f}) | Gov: {self.governor_name or "none"} | Room: {self.room_code}'
        )

    def craft_selected(self):
        recipe = self.crafting_recipes[self.recipe_index]
        material_index = {'grass': 0, 'stone': 1, 'sand': 2, 'wood': 3, 'brick': 4, 'semiconductor': 5, 'phone': 6, 'portal': 7}

        if recipe.get('tier', 0) > self.technology_tier + 1:
            self.craft_text.text = f'Locked: reach {recipe["tier"]} technology first'
            return False

        if all(self.inventory[material_index[name]] >= amount for name, amount in recipe['requires'].items()):
            for name, amount in recipe['requires'].items():
                self.inventory[material_index[name]] -= amount
            self.inventory[recipe['result_index']] += 1
            self._record_activity('crafted')
            self.technology_tier = max(self.technology_tier, recipe.get('tier', 0))
            self.craft_text.text = f'Crafted: {recipe["name"]}!'
            return True

        self.craft_text.text = f'Need: {recipe["requires"]} for {recipe["name"]}'
        return False

    def update(self):
        if not self.game_started:
            self.player_avatar.position = self.player.position + Vec3(0, 0.8, 0)
            self.player_avatar.rotation_y = self.player.rotation_y
            return

        dt = time.dt
        self.day_time += dt
        self.portal_cooldown = max(0.0, self.portal_cooldown - dt)
        self.challenge_notice_timer = max(0.0, self.challenge_notice_timer - dt)
        distance_traveled = distance(self.player.position, self.last_position)
        if distance_traveled > 0:
            self._record_activity('distance', int(distance_traveled))
            self.last_position = Vec3(self.player.position)
        self.world.expand_if_needed(self.player.position)
        self._update_locals()

        if self.multiplayer is not None:
            self.multiplayer.send_state(self.player.position, self.player.rotation_y, self.growth_score)
            self._sync_remote_players()
            self._process_remote_block_events()
            self.chat_messages = self.multiplayer.chat_messages
        self._update_governance()

        self.player_avatar.visible = True
        self.player_avatar.position = self.player.position + Vec3(0, 0.8, 0)
        self.player_avatar.rotation_y = self.player.rotation_y
        self.player_name_tag.text = self.player_name
        self.player_name_tag.rotation = (0, -self.player.rotation_y, 0)
        if self.game_started:
            self.save_profile()

        if held_keys['1']:
            self.selected_index = 0
        elif held_keys['2']:
            self.selected_index = 1
        elif held_keys['3']:
            self.selected_index = 2
        elif held_keys['4']:
            self.selected_index = 3
        elif held_keys['5']:
            self.selected_index = 4
        elif held_keys['6']:
            self.selected_index = 5
        elif held_keys['7']:
            self.selected_index = 6
        elif held_keys['8']:
            self.selected_index = 7

        self.block_preview.color = self.materials[self.selected_index]

        sprinting = (held_keys['left_shift'] or held_keys['right_shift']) and (held_keys['w'] or held_keys['a'] or held_keys['s'] or held_keys['d'])
        if sprinting and self.stamina > 0:
            self.player.speed = 11
            self.stamina = max(0.0, self.stamina - dt * 22)
        else:
            self.player.speed = 6
            self.stamina = min(100.0, self.stamina + dt * 12)

        self.hunger = max(0.0, self.hunger - dt * 0.7)
        if self.hunger <= 0:
            self.take_damage(dt * 5)
        else:
            if self.hunger < 25:
                self.take_damage(dt * 1.25)

        cycle = (self.day_time % self.day_length) / self.day_length
        angle = cycle * 2 * 3.14159
        self.sun.position = (sin(angle) * 45, cos(angle) * 26 + 10, cos(angle) * 18)

        night_factor = 1.0 - abs(cycle - 0.5) * 2.0
        light = max(0.25, night_factor)
        self.sky.color = color.rgb(int(70 + light * 120), int(120 + light * 70), int(200 + light * 40))

        if cycle < 0.2 or cycle > 0.8:
            self.take_damage(dt * 2.5)

        if self.player.y < -10:
            self.take_damage(25)

        if self.player.y < self.last_y - 8:
            self.take_damage(12)
        self.last_y = self.player.y
        self._activate_portal()

        self.update_ui()

        if mouse.left:
            hit = raycast(camera.world_position, camera.forward, distance=8, ignore=[self.player])
            if hit.hit and hit.entity in self.world.blocks.values():
                pos = hit.entity.position
                block_color = hit.entity.color
                if self.multiplayer is not None:
                    if self.multiplayer.host_mode:
                        self.world.remove_block(pos.x, pos.y, pos.z)
                    self.multiplayer.send_block_action('remove', pos.x, pos.y, pos.z, 'grass')
                else:
                    self.world.remove_block(pos.x, pos.y, pos.z)

                if block_color == GRASS:
                    self.inventory[0] += 1
                elif block_color == STONE:
                    self.inventory[1] += 1
                elif block_color == SAND:
                    self.inventory[2] += 1
                elif block_color == WOOD:
                    self.inventory[3] += 1
                elif block_color == BRICK:
                    self.inventory[4] += 1
                elif block_color == SEMICONDUCTOR:
                    self.inventory[5] += 1
                elif block_color == PHONE:
                    self.inventory[6] += 1
                elif block_color == PORTAL:
                    self.inventory[7] += 1
                    location = (round(pos.x), round(pos.y), round(pos.z))
                    if location in self.portal_locations:
                        self.portal_locations.remove(location)
                self._record_activity('mined')

        if mouse.right:
            hit = raycast(camera.world_position, camera.forward, distance=8, ignore=[self.player])
            if hit.hit and self.inventory[self.selected_index] > 0:
                target = hit.entity.position + hit.normal
                x, y, z = round(target.x), round(target.y), round(target.z)
                if abs(x) <= self.world.radius + 3 and abs(z) <= self.world.radius + 3:
                    color_name = ['grass', 'stone', 'sand', 'wood', 'brick', 'semiconductor', 'phone', 'portal'][self.selected_index]
                    if self.multiplayer is not None:
                        if self.multiplayer.host_mode:
                            self.world.add_block(x, y, z, self.materials[self.selected_index])
                            self.inventory[self.selected_index] -= 1text = 'Private message sent'
                self.player_speech_timer = 3.0
            elif self.multiplayer is not None and msg.startswith('/'):
                self._send_phone_command(msg)
            els           self.chat_input.visible = False


if __name__ == '__main__':
    game = Game()
    app.run()
