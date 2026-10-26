import importlib.util
import sys
import types


def _stub_ursina_module():
    module = types.ModuleType('ursina')

    class DummyApp:
        def __init__(self):
            self.ran = False

        def run(self):
            self.ran = True

    class DummyWindow:
        def __init__(self):
            self.title = ''
            self.borderless = False
            self.exit_button = types.SimpleNamespace(visible=True)
            self.fps_counter = types.SimpleNamespace(enabled=False)
            self.color = None

    class DummyEntity:
        def __init__(self, *args, **kwargs):
            self.position = kwargs.get('position', (0, 0, 0))
            self.rotation_y = 0
            self.visible = kwargs.get('visible', True)
            self.enabled = kwargs.get('enabled', True)
            self.text = ''
            self.parent = kwargs.get('parent')
            self.model = kwargs.get('model')
            self.color = kwargs.get('color')
            self.scale = kwargs.get('scale', (1, 1, 1))
            self.rotation = kwargs.get('rotation', (0, 0, 0))
            self.y = 0
            self.cursor = types.SimpleNamespace(visible=True, enabled=True)
            self.speed = 0
            self.gravity = 0
            self.jump_height = 0
            self.height = 0
            self.mouse_sensitivity = (0, 0)

        def disable(self):
            self.enabled = False

    class DummyText(DummyEntity):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.text = kwargs.get('text', '')
            self.background = kwargs.get('background', False)
            self.origin = kwargs.get('origin', (0, 0))
            self.world_y = kwargs.get('world_y', 0)

    class DummyButton(DummyText):
        pass

    class DummyInputField(DummyText):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.visible = kwargs.get('visible', True)
            self.enabled = kwargs.get('enabled', True)
            self.default = kwargs.get('default', '')
            self.focused = False

        def focus(self):
            self.focused = True

    class DummySky:
        def __init__(self, *args, **kwargs):
            pass

    class DummyVec3(tuple):
        def __new__(cls, *args):
            if len(args) == 1 and isinstance(args[0], (list, tuple)):
                args = tuple(args[0])
            return super().__new__(cls, tuple(float(value) for value in args))

        @property
        def x(self):
            return self[0]

        @property
        def y(self):
            return self[1]

        @property
        def z(self):
            return self[2]

    class DummyFirstPersonController(DummyEntity):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.position = DummyVec3(kwargs.get('position', (0, 0, 0)))
            self.rotation_y = 0
            self.cursor = types.SimpleNamespace(visible=True, enabled=True)

    module.Ursina = lambda: DummyApp()
    module.window = DummyWindow()
    module.scene = types.SimpleNamespace()
    module.camera = types.SimpleNamespace(ui=types.SimpleNamespace(), world_position=(0, 0, 0), forward=(0, 0, -1))
    module.color = types.SimpleNamespace(
        rgb=lambda *args: args,
        rgba=lambda *args: args,
        white=(255, 255, 255),
        yellow=(255, 255, 0),
        azure=(0, 127, 255),
        red=(255, 0, 0),
        rbg=lambda *args: args,
    )
    module.Entity = DummyEntity
    module.Text = DummyText
    module.Sky = DummySky
    module.FirstPersonController = DummyFirstPersonController
    module.Button = DummyButton
    module.InputField = DummyInputField
    module.Vec3 = DummyVec3
    module.raycast = lambda *args, **kwargs: types.SimpleNamespace(hit=False, entity=None, normal=(0, 1, 0))
    module.distance = lambda a, b: 0
    module.time = types.SimpleNamespace(dt=0.016)
    module.application = types.SimpleNamespace(quit=lambda: None)
    module.held_keys = {}
    module.mouse = types.SimpleNamespace(left=False, right=False)
    return module


def test_main_does_not_run_on_import():
    original = sys.modules.get('ursina')
    fake_ursina = _stub_ursina_module()
    sys.modules['ursina'] = fake_ursina

    try:
        spec = importlib.util.spec_from_file_location('main_under_test', 'main.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert not getattr(module.app, 'ran', False), 'main.py should not auto-start during import'
    finally:
        if original is not None:
            sys.modules['ursina'] = original
        else:
            sys.modules.pop('ursina', None)
