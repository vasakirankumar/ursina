import importlib.util
import sys
import types

fake = types.ModuleType('ursina')
class DummyEntity:
    def __init__(self, *args, **kwargs):
        self.position = kwargs.get('position', (0,0,0))
        self.rotation_y = 0
        self.y = 0
        self.visible = True
        self.enabled = True
        self.model = kwargs.get('model')
        self.parent = kwargs.get('parent')
        self.color = kwargs.get('color')
        self.scale = kwargs.get('scale', (1,1,1))
        self.text = ''
        self.world_y = 0
        self.rotation = (0,0,0)
        self.ui = None
        self.cursor = types.SimpleNamespace(visible=True, enabled=True)
        self.speed = 0
        self.gravity = 0
        self.jump_height = 0
        self.height = 0
        self.mouse_sensitivity = (0,0)
    def disable(self):
        self.enabled = False
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

class DummyApp:
    def run(self):
        self.ran = True

class DummyWindow:
    def __init__(self):
        self.title = ''
        self.borderless = False
        self.exit_button = types.SimpleNamespace(visible=True)
        self.fps_counter = types.SimpleNamespace(enabled=False)
        self.color = None

class DummyColor:
    def __init__(self, *a, **k):
        pass
    @staticmethod
    def rgb(*args):
        return tuple(args)
    @staticmethod
    def rgba(*args):
        return tuple(args)
    @staticmethod
    def white():
        return (255,255,255)

class DummyText(DummyEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text = kwargs.get('text', '')

class DummySky:
    def __init__(self, *args, **kwargs):
        pass

class DummyVec3(tuple):
    def __new__(cls, *args):
        return super().__new__(cls, tuple(args))
    @property
    def x(self): return self[0]
    @property
    def y(self): return self[1]
    @property
    def z(self): return self[2]

class DummyFirstPersonController(DummyEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.position = DummyVec3(*kwargs.get('position', (0,0,0)))
        self.rotation_y = 0
        self.cursor = types.SimpleNamespace(visible=True, enabled=True)

class DummyButton(DummyEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text = kwargs.get('text', '')

class DummyInputField(DummyEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text = kwargs.get('text', '')
        self.default = kwargs.get('default', '')
        self.visible = kwargs.get('visible', True)
        self.enabled = kwargs.get('enabled', True)
        self.focused = False
        def focus(): self.focused = True
        self.focus = focus

fake.Ursina = lambda: DummyApp()
fake.window = DummyWindow()
fake.scene = types.SimpleNamespace()
fake.camera = types.SimpleNamespace(ui=types.SimpleNamespace(), world_position=(0,0,0), forward=(0,0,-1))
fake.color = DummyColor()
fake.Entity = DummyEntity
fake.Text = DummyText
fake.Sky = DummySky
fake.FirstPersonController = DummyFirstPersonController
fake.Button = DummyButton
fake.InputField = DummyInputField
fake.Vec3 = DummyVec3
fake.raycast = lambda *args, **kwargs: types.SimpleNamespace(hit=False)
fake.distance = lambda a,b: 0
fake.hold_keys = {}
fake.mouse = types.SimpleNamespace(left=False,right=False)
fake.time = types.SimpleNamespace(dt=0.016)
fake.application = types.SimpleNamespace(quit=lambda: None)
fake.held_keys = {}

sys.modules['ursina'] = fake

spec = importlib.util.spec_from_file_location('main_under_test', 'main.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('imported', hasattr(mod, 'Game'))
print('game_attr', hasattr(mod, 'game'))
print('run_called', getattr(mod, 'app', None) is not None and getattr(mod.app, 'ran', False))