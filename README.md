# VoxelCraft

A compact Minecraft-inspired voxel sandbox built with Python and Ursina.

## Features
- Procedural terrain generation
- First-person movement and jumping
- Block removal and placement
- Basic trees and world depth
- Simple block selection HUD

## Setup

```bash
python -m pip install -r requirements.txt
python main.py
```

For touch controls, launch mobile mode:

```bash
python main.py --mobile
```

Mobile mode adds on-screen movement, jump, break, place, listen, phone, and craft buttons. Native Android packaging requires a Panda3D/Ursina Android build toolchain; the current project provides the touch-ready runtime mode.

## Controls
- WASD: move
- Space: jump
- Left click: break block
- Right click: place block
- 1 / 2 / 3: switch material
- Escape: quit

## Notes
This project is a lightweight sandbox prototype inspired by Minecraft and is designed as a starting point for a larger game project.
