"""
NINJAGO RUNNER - a PS1 "Pepsiman"-style behind-the-back endless... well,
three-level runner starring the Ninjago ninjas.  Run:   python main.py

Files
-----
main.py      this file: window, menu, HUD, game states, player physics
config.py    ninjas, difficulties, levels, jokes, key bindings (edit freely)
entities.py  3D models: the ninja, obstacles, endless floor, scenery
ps1.py       PS1 look: vertex-snapping + flat-shading + fog shader
cutscene.py  end-of-level .mp4 player with animated fallback
assets/      YOUR files: models/, music/, sfx/, videos/  (see README.md)

Game states (Game.state)
------------------------
menu -> intro -> play -> finish -> cutscene -> intro (next level) ... -> victory
                  |  \\-> paused                                  |
                  \\-> gameover (retry the level / back to menu)  \\-> menu
"""
import os
import sys
import time
from pathlib import Path

from ursina import (Ursina, Entity, Text, Button, camera, color, window, application,
                    clamp, lerp, sin, Vec3, destroy, mouse)

import config as C
from config import shade
import ps1
from ps1 import box
from entities import NinjaModel, World
from cutscene import Cutscene

ASSETS = Path(__file__).parent / 'assets'
AUDIO_EXT = ('.ogg', '.mp3', '.wav', '.flac')


# ===========================================================================
#  AUDIO  -  looping soundtrack + optional sound effects
# ===========================================================================
class Sounds:
    """
    Drop files into assets/music and assets/sfx - no code changes needed.

      assets/music/ninjago_theme.(ogg|mp3|wav)   main soundtrack (loops)
      assets/music/menu.*  level1.*  level2.*  level3.*   optional per-screen tracks
      assets/sfx/jump.* slide.* stud.* hit.* win.* lose.*  optional effects

    Missing files are simply skipped, so the game also runs silently.
    """

    def __init__(self):
        self.loader = application.base.loader
        self.music = None
        self.music_name = None
        self.cache = {}
        self.volume = 0.6

    @staticmethod
    def find(folder, name):
        for ext in AUDIO_EXT:
            p = ASSETS / folder / (name + ext)
            if p.exists():
                return p
        return None

    def play_music(self, *names):
        """Play the first track that exists (e.g. 'level2', then 'ninjago_theme')."""
        from panda3d.core import Filename
        for name in names:
            p = self.find('music', name)
            if p is None:
                continue
            if self.music_name == p.name and self.music and self.music.status() == self.music.PLAYING:
                return                                   # already playing this track
            self.stop()
            try:
                self.music = self.loader.load_music(Filename.from_os_specific(str(p)))
                self.music.set_loop(True)                # <<< the looping soundtrack hook
                self.music.set_volume(self.volume)
                self.music.play()
                self.music_name = p.name
            except Exception as e:
                print('[audio] could not play', p, e)
            return

    def stop(self):
        if self.music:
            self.music.stop()
        self.music, self.music_name = None, None

    def sfx(self, name, volume=0.9):
        from panda3d.core import Filename
        if name not in self.cache:
            p = self.find('sfx', name)
            self.cache[name] = self.loader.load_sfx(Filename.from_os_specific(str(p))) if p else None
        s = self.cache[name]
        if s:
            s.set_volume(volume)
            s.play()


# ===========================================================================
#  GAME
# ===========================================================================
class Game(Entity):
    def __init__(self):
        super().__init__()
        self.sounds = Sounds()
        self.cutscene = Cutscene()
        self.state = None
        self.lock = 0.0                      # blocks confirm keys briefly after screen changes

        # menu choices
        self.ninja_i = 0
        self.diff_name = 'NORMAL'
        # run state
        self.level_i = 0
        self.world = None
        self.player = None
        self.score_base = 0                  # banked score from finished levels

        self._build_menu()
        self._build_hud()
        self._build_overlay()
        self.menu_ninja = None
        self.go_menu()

    # ------------------------------------------------------------------
    #  UI construction
    # ------------------------------------------------------------------
    def _build_menu(self):
        self.menu = Entity(parent=camera.ui, enabled=False)
        m = self.menu
        Entity(parent=m, model='quad', color=color.rgba(0, 0, 0, 120), scale=(1.0, 1.2), x=-0.48, z=2)
        Text('NINJAGO', parent=m, position=(-0.85, 0.46), scale=4, color=C.GOLD)
        Text('SPINJITZU RUNNER', parent=m, position=(-0.85, 0.37), scale=1.9, color=C.KAI_RED)
        Text('CHOOSE YOUR NINJA', parent=m, position=(-0.85, 0.29), scale=1.1, color=color.white)

        self.sel_frame = Entity(parent=m, model='quad', color=C.GOLD, z=0.2)
        self.ninja_buttons = []
        for i, n in enumerate(C.NINJAS):
            b = Button(parent=m, text=f'{n["name"]}  -  {n["title"]}', scale=(0.56, 0.068),
                       position=(-0.55, 0.22 - i * 0.085), color=n['suit'], text_color=color.white,
                       highlight_color=shade(n['suit'], 1.25), pressed_color=n['suit'])
            b.on_click = (lambda i=i: self.pick_ninja(i))
            self.ninja_buttons.append(b)
        self.perk_text = Text('', parent=m, position=(-0.85, -0.22), scale=1.2, color=C.GOLD)

        Text('DIFFICULTY', parent=m, position=(-0.85, -0.29), scale=1.1, color=color.white)
        self.diff_buttons = {}
        diff_cols = {'EASY': C.LLOYD_GREEN, 'NORMAL': C.JAY_BLUE, 'HARD': C.KAI_RED}
        for i, d in enumerate(C.DIFFICULTY_ORDER):
            b = Button(parent=m, text=d, scale=(0.18, 0.06), position=(-0.74 + i * 0.19, -0.36),
                       color=diff_cols[d], text_color=color.white)
            b.on_click = (lambda d=d: self.pick_diff(d))
            self.diff_buttons[d] = b
        self.start_btn = Button(parent=m, text='START RUN!', scale=(0.56, 0.08), position=(-0.55, -0.46),
                                color=C.GOLD, text_color=C.COLE_BLACK, highlight_color=shade(C.GOLD, 1.15))
        self.start_btn.on_click = self.begin_game
        Text('UP/DOWN ninja   LEFT/RIGHT difficulty   ENTER start   ESC quit',
             parent=m, position=(-0.85, -0.53), scale=0.8, color=color.white66)
        Text('IN GAME:  A/D or arrows = lane   W/SPACE = jump   S/DOWN = slide   ESC = pause',
             parent=m, position=(0.88, 0.47), origin=(0.5, 0), scale=0.8, color=color.white66)

    def _build_hud(self):
        self.hud = Entity(parent=camera.ui, enabled=False)
        h = self.hud
        self.score_text = Text('', parent=h, position=(-0.87, 0.48), scale=1.8, color=C.GOLD)
        self.stud_text = Text('', parent=h, position=(-0.87, 0.42), scale=1.2, color=color.white)
        self.level_text = Text('', parent=h, position=(0.87, 0.48), origin=(0.5, 0), scale=1.3, color=color.white)
        self.speed_text = Text('', parent=h, position=(0.87, 0.43), origin=(0.5, 0), scale=1.0, color=C.JAY_BLUE)
        self.lives_icons = []
        for i in range(6):
            e = Entity(parent=h, model='quad', color=C.LEGO_YELLOW, scale=(0.035, 0.035), position=(-0.85 + i * 0.045, 0.37))
            Entity(parent=e, model='quad', color=color.black, scale=(0.5, 0.12), y=0.05, z=-0.01)
            self.lives_icons.append(e)
        # level progress bar
        Entity(parent=h, model='quad', color=color.rgba(0, 0, 0, 160), scale=(0.62, 0.025), y=0.47, z=1)
        self.bar = Entity(parent=h, model='quad', color=C.GOLD, scale=(0.0, 0.017), y=0.47, x=-0.3, origin=(-0.5, 0))
        self.flash = Entity(parent=camera.ui, model='quad', color=color.rgba(255, 0, 0, 0), scale=(3, 2), z=-5)

    def _build_overlay(self):
        self.overlay = Entity(parent=camera.ui, enabled=False, z=-3)
        self.dim = Entity(parent=self.overlay, model='quad', color=color.rgba(0, 0, 0, 150), scale=(3, 2), z=1)
        self.big = Text('', parent=self.overlay, origin=(0, 0), y=0.12, scale=4, color=C.GOLD)
        self.small = Text('', parent=self.overlay, origin=(0, 0), y=-0.02, scale=1.6, color=color.white)
        self.tiny = Text('', parent=self.overlay, origin=(0, 0), y=-0.14, scale=1.1, color=color.white66)

    def show_overlay(self, big, small='', tiny='', dim=True, col=None):
        self.overlay.enabled = True
        self.dim.visible = dim
        self.big.text, self.small.text, self.tiny.text = big, small, tiny
        self.big.y, self.small.y, self.tiny.y = 0.2, 0.1, 0.03
        self.big.color = col or C.GOLD

    # ------------------------------------------------------------------
    #  Menu logic
    # ------------------------------------------------------------------
    def pick_ninja(self, i):
        self.ninja_i = i % len(C.NINJAS)
        self.refresh_menu()

    def pick_diff(self, d):
        self.diff_name = d
        self.refresh_menu()

    def refresh_menu(self):
        for i, b in enumerate(self.ninja_buttons):
            n = C.NINJAS[i]
            sel = i == self.ninja_i
            b.color = n['suit'] if sel else shade(n['suit'], 0.45)
            b.text_color = color.white if n['id'] not in ('zane',) or not sel else C.COLE_BLACK
            b.scale = (0.6, 0.074) if sel else (0.56, 0.068)
            if sel:
                self.sel_frame.position = (b.x, b.y, 0.2)
                self.sel_frame.scale = (0.63, 0.092)
        n = C.NINJAS[self.ninja_i]
        self.perk_text.text = f'{n["name"]}:  {n["perk"]}   ({n["lives"]} lives)'
        for d, b in self.diff_buttons.items():
            sel = d == self.diff_name
            b.scale = (0.2, 0.07) if sel else (0.18, 0.06)
            b.alpha = 1.0 if sel else 0.45
        self._spawn_menu_ninja()

    def _spawn_menu_ninja(self):
        if self.menu_ninja:
            destroy(self.menu_ninja)
        self.menu_ninja = NinjaModel(C.NINJAS[self.ninja_i], position=(1.9, 0, 0), scale=1.0, rotation_y=160)

    def go_menu(self):
        self._teardown_run()
        self.state = 'menu'
        self.lock = 0.3
        self.hud.enabled = False
        self.overlay.enabled = False
        self.menu.enabled = True
        window.color = color.rgb32(25, 10, 12)
        ps1.set_fog(color.rgb32(25, 10, 12), 60, 120)
        camera.position, camera.rotation, camera.fov = (0, 1.5, -9), (0, 0, 0), 40
        self.refresh_menu()
        self.sounds.play_music('menu', 'ninjago_theme')

    def begin_game(self):
        if self.menu_ninja:
            destroy(self.menu_ninja)
            self.menu_ninja = None
        self.menu.enabled = False
        self.level_i = 0
        self.score_base = 0
        self.start_level(0)

    # ------------------------------------------------------------------
    #  Level setup / teardown
    # ------------------------------------------------------------------
    def _teardown_run(self):
        if self.world:
            self.world.clear()
            self.world = None
        if self.player:
            destroy(self.player)
            self.player = None

    def start_level(self, i):
        """Build level i from scratch (also used for 'retry')."""
        self._teardown_run()
        self.level_i = i
        lv = C.LEVELS[i]
        dif = C.DIFFICULTIES[self.diff_name]
        spec = C.NINJAS[self.ninja_i]
        self.spec, self.lv, self.dif = spec, lv, dif

        window.color = lv['sky']
        ps1.set_fog(lv['fog'], *lv['fog_range'])
        camera.fov = 85
        self.base_speed = dif['speed'] * lv['speed_mult']
        self.world = World(lv, dif, self.base_speed)

        # --- player: a root entity (logic) holding the visual model -----
        self.player = Entity(position=(0, 0, 0))
        self.model = NinjaModel(spec, parent=self.player, scale=0.9)
        self.lane = 1
        self.vy = 0.0
        self.slide_t = 0.0
        self.want_slide = False
        self.invuln = 0.0
        self.slow = 0.0
        self.shake = 0.0
        self.lives = spec['lives']
        self.studs = 0
        self.level_time = 0.0
        self.run_clock = 0.0
        self.speed = 0.0

        self.intro_t = 0.0
        self.state = 'intro'
        self.hud.enabled = True
        self.level_text.text = f'{lv["name"]}  {lv["subtitle"]}'
        self._snap_camera()
        self.sounds.play_music(lv['music'], 'ninjago_theme')
        self.show_overlay(lv['name'], lv['subtitle'], f'{spec["name"]} - {self.diff_name}', dim=False, col=C.GOLD)

    def _snap_camera(self):
        camera.position = (self.player.x * 0.55, 3.5, self.player.z - 7.5)
        camera.rotation = (12, 0, 0)

    # ------------------------------------------------------------------
    #  Input
    # ------------------------------------------------------------------
    def input(self, key):
        if self.state == 'menu':
            if key == 'down arrow':
                self.pick_ninja(self.ninja_i + 1)
            elif key == 'up arrow':
                self.pick_ninja(self.ninja_i - 1)
            elif key == 'right arrow':
                self.pick_diff(C.DIFFICULTY_ORDER[min(C.DIFFICULTY_ORDER.index(self.diff_name) + 1, 2)])
            elif key == 'left arrow':
                self.pick_diff(C.DIFFICULTY_ORDER[max(C.DIFFICULTY_ORDER.index(self.diff_name) - 1, 0)])
            elif key in ('enter', 'space') and self.lock <= 0:
                self.begin_game()
            elif key == 'escape':
                application.quit()
            return

        if self.state == 'play':
            if key in C.KEYS_LEFT:
                self.lane = max(0, self.lane - 1)
            elif key in C.KEYS_RIGHT:
                self.lane = min(2, self.lane + 1)
            elif key in C.KEYS_JUMP:
                self.try_jump()
            elif key in C.KEYS_SLIDE:
                self.try_slide()
            elif key in C.KEYS_PAUSE:
                self.state = 'paused'
                self.show_overlay('PAUSED', 'ESC / P = resume', 'M = main menu')
            return

        if self.state == 'paused':
            if key in C.KEYS_PAUSE:
                self.overlay.enabled = False
                self.state = 'play'
            elif key == 'm':
                self.go_menu()
            return

        if self.lock > 0:
            return
        if self.state == 'gameover':
            if key in ('enter', 'space', 'r'):
                self.start_level(self.level_i)
            elif key in ('m', 'escape'):
                self.go_menu()
        elif self.state == 'victory':
            if key in ('enter', 'space', 'escape'):
                self.go_menu()

    def try_jump(self):
        if self.player.y <= 0.01:
            self.vy = self.spec['jump']
            self.slide_t = 0
            self.want_slide = False
            self.sounds.sfx('jump')

    def try_slide(self):
        if self.player.y > 0.01:
            self.vy = min(self.vy, -22)             # fast-fall, then slide on landing
            self.want_slide = True
        elif self.slide_t <= 0:
            self.slide_t = C.SLIDE_TIME
            self.sounds.sfx('slide')

    # ------------------------------------------------------------------
    #  Per-frame update
    # ------------------------------------------------------------------
    def update(self):
        dt = min(time.dt, 0.05)
        self.lock = max(0, self.lock - dt)

        if self.state == 'menu':
            if self.menu_ninja:
                self.menu_ninja.rotation_y += 40 * dt
                self.menu_ninja.animate_run(time.time() * 1.2, 10, 'run')
                self.menu_ninja.y = 0
            return
        if self.state == 'intro':
            self._update_intro(dt)
        elif self.state == 'play':
            self._update_play(dt)
        elif self.state == 'finish':
            self._update_finish(dt)
        elif self.state in ('gameover', 'victory'):
            self.model.rotation_y += 90 * dt
        if self.state in ('intro', 'play', 'finish', 'paused', 'gameover', 'victory'):
            self._update_camera(dt)

    # --- intro: title card + 3-2-1 --------------------------------------
    def _update_intro(self, dt):
        self.intro_t += dt
        self.world.update(self.player.z)
        self.model.animate_run(self.intro_t * 2, 4, 'run')
        t = self.intro_t
        if t > 1.6:
            n = 3 - int(t - 1.6)
            self.show_overlay('GO!' if n <= 0 else str(n), '', '', dim=False, col=C.KAI_RED)
        if t > 4.6:
            self.overlay.enabled = False
            self.state = 'play'
        self._refresh_hud()

    # --- the actual run --------------------------------------------------
    def _update_play(self, dt):
        p = self.player
        self.level_time += dt
        ramp = 1 + self.dif['ramp'] * min(self.level_time, 25)          # gets faster as you survive
        self.slow = max(0.0, self.slow - dt * 0.7)                      # stumble recovery
        self.speed = self.base_speed * ramp * (1 - 0.5 * self.slow)
        p.z += self.speed * dt
        self.run_clock += dt

        # lane change (smooth)
        target = C.LANES[self.lane]
        dx = target - p.x
        p.x += dx * min(1.0, self.spec['lane_speed'] * dt)
        self.model.rotation_y = clamp(dx * 14, -28, 28)

        # jump / gravity
        if p.y > 0 or self.vy > 0:
            self.vy -= C.GRAVITY * dt
            p.y += self.vy * dt
            if p.y <= 0:
                p.y, self.vy = 0, 0
                if self.want_slide:
                    self.slide_t, self.want_slide = C.SLIDE_TIME, False
        # slide timer
        if self.slide_t > 0:
            self.slide_t -= dt
        sliding = self.slide_t > 0 and p.y <= 0.01
        state = 'slide' if sliding else ('jump' if p.y > 0.05 else 'run')
        self.model.animate_run(self.run_clock, self.speed, state)
        if state != 'run':
            self.model.y = 0 if state == 'slide' else self.model.y

        # invulnerability blink
        if self.invuln > 0:
            self.invuln -= dt
            self.model.visible = int(self.invuln * 14) % 2 == 0
        else:
            self.model.visible = True

        self.world.update(p.z)
        self._collisions(sliding)
        self._studs(dt)

        if p.z >= self.lv['length']:
            self._level_complete()
        self._refresh_hud()

    def _collisions(self, sliding):
        p = self.player
        height = C.SLIDE_HEIGHT if sliding else C.STAND_HEIGHT
        if self.invuln > 0:
            return
        for o in self.world.obstacles:
            if abs(o.z - p.z) > o.hd + 0.35 or abs(o.x - p.x) > o.hw + 0.3:
                continue
            if p.y + height > o.y0 + 0.05 and p.y < o.y1 - 0.05:
                self._hit()
                return

    def _hit(self):
        self.lives -= 1
        self.invuln = self.spec['invuln']
        self.slow = 1.0
        self.shake = 0.5
        self.flash.color = color.rgba(255, 30, 30, 140)
        self.flash.animate_color(color.rgba(255, 30, 30, 0), duration=0.5)
        self.sounds.sfx('hit')
        if self.lives <= 0:
            self.state = 'gameover'
            self.lock = 0.8
            self.model.visible = True
            self.sounds.sfx('lose')
            self.show_overlay('GAME OVER', f'SCORE  {self.total_score()}',
                              'ENTER = retry level     M = main menu', col=C.KAI_RED)

    def _studs(self, dt):
        p = self.player
        mag = self.spec['magnet']
        for s in self.world.studs[:]:
            s.rotation_y += 240 * dt
            if mag and 0 < s.z - p.z < mag * 1.5 and abs(s.x - p.x) < mag:
                s.position += (p.position + Vec3(0, 1, 0.5) - s.position) * min(1, dt * 9)
            if abs(s.z - p.z) < 1.1 and abs(s.x - p.x) < 1.3 and -0.5 < s.y - p.y < 2.6:
                self.studs += 1
                self.world.studs.remove(s)
                destroy(s)
                self.sounds.sfx('stud', 0.6)

    def total_score(self):
        return int(self.score_base + self.player.z * C.DISTANCE_SCORE + self.studs * C.STUD_SCORE)

    def _refresh_hud(self):
        self.score_text.text = f'SCORE {self.total_score()}'
        self.stud_text.text = f'STUDS {self.studs}'
        self.speed_text.text = f'{int(self.speed * 3.6)} KM/H' if self.speed else ''
        for i, e in enumerate(self.lives_icons):
            e.visible = i < self.lives
        frac = clamp(self.player.z / self.lv['length'], 0, 1)
        self.bar.scale_x = 0.62 * frac

    # --- level end --------------------------------------------------------
    def _level_complete(self):
        self.state = 'finish'
        self.finish_t = 0.0
        self.score_base = self.total_score() + 500          # level clear bonus
        self.studs_banked = self.studs
        self.sounds.sfx('win')
        self.show_overlay('LEVEL CLEAR!', f'SCORE  {self.score_base}', '', dim=False, col=C.GOLD)
        self.model.visible = True

    def _update_finish(self, dt):
        self.finish_t += dt
        p = self.player
        self.speed = max(0, self.speed - 30 * dt)
        p.z += self.speed * dt
        p.x += (0 - p.x) * min(1, 4 * dt)
        self.model.animate_run(self.finish_t * 1.5, self.speed, 'run' if self.speed > 6 else 'jump')
        if self.speed <= 6:                                   # victory hop
            p.y = abs(sin(self.finish_t * 6)) * 1.0
        if self.finish_t > 2.4:
            p.y = 0
            self.overlay.enabled = False
            self.hud.enabled = False
            self.state = 'cutscene'
            self.cutscene.start(self.level_i, self._after_cutscene, music=self.sounds)

    def _after_cutscene(self):
        """Called by the Cutscene when the clip ends (or is skipped)."""
        if self.level_i < len(C.LEVELS) - 1:
            self.start_level(self.level_i + 1)
        else:
            self._victory()

    def _victory(self):
        self._teardown_run()
        # re-create a small stage for the final spin
        window.color = C.GOLD
        ps1.set_fog(C.GOLD, 50, 100)
        self.player = Entity(position=(0, 0, 0))
        self.model = NinjaModel(self.spec, parent=self.player, scale=1.0)
        self.model.animate_run(1, 0, 'jump')
        self.state = 'victory'
        self.lock = 0.8
        camera.position, camera.rotation, camera.fov = (0, 2.0, -8), (0, 0, 0), 50
        self.sounds.play_music('ninjago_theme')
        self.show_overlay('YOU ARE THE MASTER!', f'FINAL SCORE  {self.score_base}',
                          'All 3 levels cleared - ENTER = main menu', dim=False, col=C.KAI_RED)
        self.big.y, self.small.y, self.tiny.y = 0.4, -0.3, -0.38

    # --- camera ----------------------------------------------------------
    def _update_camera(self, dt):
        if self.state in ('gameover', 'victory'):
            return
        p = self.player
        tx = p.x * 0.55
        camera.x += (tx - camera.x) * min(1, 8 * dt)
        camera.y = 3.5 + p.y * 0.35
        camera.z = p.z - 7.5
        camera.rotation_x = 12
        # speed feel: widen the FOV a little as we go faster
        camera.fov += ((84 + (self.speed / max(self.base_speed, 1) - 1) * 18) - camera.fov) * min(1, 3 * dt)
        if self.shake > 0:
            self.shake = max(0, self.shake - dt)
            camera.x += sin(time.time() * 80) * self.shake * 0.4
            camera.y += sin(time.time() * 97) * self.shake * 0.3


# ===========================================================================
#  ENTRY POINT
# ===========================================================================
def build_game(fullscreen=True, **window_kwargs):
    """Create the engine window + Game.  Split out so tests can call it."""
    app = Ursina(title='NINJAGO RUNNER', fullscreen=fullscreen, borderless=fullscreen,
                 vsync=True, development_mode=False, **window_kwargs)
    window.exit_button.visible = False          # hide Ursina's red 'X' button
    window.fps_counter.enabled = False
    if hasattr(window, 'cog_button'):
        window.cog_button.enabled = False
    Text.default_resolution = 1080 * Text.size  # crisper text in fullscreen
    return app, Game()


if __name__ == '__main__':
    windowed = '--windowed' in sys.argv or os.environ.get('NINJAGO_WINDOWED')
    app, game = build_game(fullscreen=not windowed)
    app.run()
