from ursina import *
from random import randint
from math import sin

app = Ursina()
window.title = 'VoxelCraft Demo'
window.borderless = False
window.exit_button.visible = False
window.fps_counter.enabled = True

GRASS = color.rgb(110, 180, 90)
DIRT = color.rgb(120, 85, 55)
STONE = color.rgb(120, 120, 130)
SAND = color.rgb(220, 205, 120)
WOOD = color.rgb(160, 110, 60)
LEAF = color.rgb(80, 170, 100)


class DemoWorld:
    def __init__(self, radius=10):
        self.radius = radius
        self.blocks = {}
        self.generate()

    def terrain_height(self, x, z):
        wave = sin(x * 0.7) + sin(z * 0.6)
        return max(2, min(6, int((wave + 3) * 1.2)))

    def add_block(self, x, y, z, color):
        key = (round(x), round(y), round(z))
        if key in self.blocks:
            return
        block = Entity(
            parent=scene,
            model='cube',
            color=color,
            texture='white_cube',
            position=(x, y, z),
            collider='box'
        )
        self.blocks[key] = block

    def remove_block(self, x, y, z):
        key = (round(x), round(y), round(z))
        block = self.blocks.pop(key, None)
        if block is not None:
            destroy(block)

    def add_tree(self, x, y, z):
        trunk = randint(3, 4)
        for h in range(trunk):
            self.add_block(x, y + h, z, WOOD)

        for dx in range(-2, 3):
            for dz in range(-2, 3):
                for dy in range(2, 5):
                    if abs(dx) + abs(dz) + abs(dy) <= 5:
                        self.add_block(x + dx, y + trunk + dy - 2, z + dz, LEAF)

    def generate(self):
        for x in range(-self.radius, self.radius + 1):
            for z in range(-self.radius, self.radius + 1):
                h = self.terrain_height(x, z)
                for y in range(-2, h + 1):
                    if y == h:
                        color = SAND if h <= 2 else GRASS
                    elif y >= h - 2:
                        color = DIRT
                    else:
                        color = STONE
                    self.add_block(x, y, z, color)

                if h > 2 and randint(0, 8) == 0:
                    self.add_tree(x, h + 1, z)


class DemoGame:
    def __init__(self):
        Sky(color=color.rgb(130, 190, 255))
        self.world = DemoWorld(radius=8)
        self.player = FirstPersonController(
            position=(0, 8, 0),
            speed=6,
            gravity=1.2,
            jump_height=2.5,
            height=2,
            mouse_sensitivity=(120, 120),
        )
        self.player.cursor.visible = False
        self.player.cursor.enabled = False

        self.materials = [GRASS, STONE, SAND]
        self.selected_index = 0

        self.hud = Text(
            text='WASD move | Space jump | Left click remove | Right click place | 1/2/3 switch block',
            position=(-0.78, 0.45),
            scale=1.1,
            origin=(0, 0),
            color=color.white,
            background=True,
        )

        self.preview = Entity(
            parent=camera.ui,
            model='cube',
            color=self.materials[0],
            scale=(0.08, 0.08, 0.08),
            position=(0.78, -0.38),
            rotation=(20, 30, 0),
            texture='white_cube'
        )

    def update(self):
        if held_keys['1']:
            self.selected_index = 0
        elif held_keys['2']:
            self.selected_index = 1
        elif held_keys['3']:
            self.selected_index = 2
        self.preview.color = self.materials[self.selected_index]

        if mouse.left:
            hit = raycast(camera.world_position, camera.forward, distance=8, ignore=[self.player])
            if hit.hit and hit.entity in self.world.blocks.values():
                pos = hit.entity.position
                self.world.remove_block(pos.x, pos.y, pos.z)

        if mouse.right:
            hit = raycast(camera.world_position, camera.forward, distance=8, ignore=[self.player])
            if hit.hit:
                target = hit.entity.position + hit.normal
                x, y, z = round(target.x), round(target.y), round(target.z)
                self.world.add_block(x, y, z, self.materials[self.selected_index])

    def input(self, key):
        if key == 'escape':
            application.quit()


if __name__ == '__main__':
    game = DemoGame()
    app.run()
