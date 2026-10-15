"""
entities.py - everything you can SEE in the 3D world:

    NinjaModel  : the low-poly minifig-style ninja (or your own model)
    World       : endless floor chunks, scenery, obstacles, studs, finish gate

The player runs along +Z.  X is left/right, Y is up.
Collision uses simple boxes: every obstacle stores
    kind  : 'wall' | 'low' | 'beam'
    hw    : half width (X)       hd : half depth (Z)
    y0,y1 : vertical span the obstacle occupies
and the player is a box of width ~0.7 and height STAND/SLIDE_HEIGHT.
"""
import random
from pathlib import Path

from ursina import Entity, Vec3, destroy, color, sin, lerp
from ursina.models.procedural.cone import Cone

import config as C
from config import shade
from ps1 import box
from enemies import Enemy

ASSET_DIR = Path(__file__).parent / 'assets'
SKULL_WHITE = color.rgb32(235, 232, 215)

CONE5 = None


def cone5():
    """5-sided cone mesh, created lazily and reused."""
    global CONE5
    if CONE5 is None:
        CONE5 = Cone(resolution=5, radius=0.5, height=1)
        # procedural meshes have no vertex colours; the PS1 shader multiplies
        # by them, so give every vertex white or the cone renders black.
        CONE5.colors = [color.white] * len(CONE5.vertices)
        CONE5.generate()
    return CONE5


# ===========================================================================
#  NINJA
# ===========================================================================
class NinjaModel(Entity):
    """
    A blocky minifig ninja built from cubes (≈ 40 triangles per limb, very PS1).

    Want a real model?  Drop  assets/models/<ninja id>.glb|.obj|.bam  (e.g.
    kai.glb) and it is used instead of the cube ninja (no limb animation).
    The model should face +Z, stand on y=0 and be roughly 2 units tall.
    """

    def __init__(self, spec, **kwargs):
        super().__init__(**kwargs)
        self.spec = spec
        self.custom = self._find_custom_model(spec['id'])
        if self.custom:
            box(self, model=spec['id'], scale=1)
            return

        suit, trim = spec['suit'], spec['accent']
        dark = shade(suit, 0.7)
        # Black ninjas need a lighter highlight so they don't vanish in the fog.
        hood = suit
        face = C.LEGO_YELLOW

        # --- legs: pivot at the hip so rotating swings the whole leg -------
        self.leg_l = Entity(parent=self, position=(-0.22, 0.85, 0))
        self.leg_r = Entity(parent=self, position=(0.22, 0.85, 0))
        for leg in (self.leg_l, self.leg_r):
            box(leg, position=(0, -0.42, 0), scale=(0.4, 0.85, 0.42), color=dark)
            box(leg, position=(0, -0.8, 0.06), scale=(0.42, 0.18, 0.55), color=color.rgb32(25, 25, 25))

        # --- torso + belt + gold trim --------------------------------------
        box(self, position=(0, 1.3, 0), scale=(0.95, 0.8, 0.55), color=suit)
        box(self, position=(0, 0.92, 0), scale=(0.98, 0.17, 0.58), color=trim)
        box(self, position=(0, 1.35, 0.29), scale=(0.28, 0.6, 0.02), color=trim)       # chest stripe

        # --- arms (pivot at the shoulder) ----------------------------------
        self.arm_l = Entity(parent=self, position=(-0.64, 1.58, 0))
        self.arm_r = Entity(parent=self, position=(0.64, 1.58, 0))
        for arm in (self.arm_l, self.arm_r):
            box(arm, position=(0, -0.36, 0), scale=(0.3, 0.72, 0.32), color=suit)
            box(arm, position=(0, -0.76, 0), scale=(0.28, 0.2, 0.3), color=face)        # LEGO hand

        # --- head: hood, face slot, top stud -------------------------------
        self.head = Entity(parent=self, position=(0, 1.95, 0))
        box(self.head, scale=(0.78, 0.7, 0.7), color=hood)
        box(self.head, position=(0, -0.02, 0.36), scale=(0.52, 0.26, 0.04), color=face)   # face
        box(self.head, position=(-0.1, 0.0, 0.385), scale=(0.07, 0.07, 0.02), color=color.black)
        box(self.head, position=(0.1, 0.0, 0.385), scale=(0.07, 0.07, 0.02), color=color.black)
        box(self.head, position=(0, 0.42, 0), scale=(0.28, 0.14, 0.28), color=trim)        # stud

        # --- katana on the back (this is what you stare at all game!) ------
        self.sword = Entity(parent=self, position=(0, 1.35, -0.35), rotation_z=40)
        box(self.sword, position=(0, 0.15, 0), scale=(0.09, 1.3, 0.06), color=color.rgb32(190, 195, 205))
        box(self.sword, position=(0, -0.55, 0), scale=(0.14, 0.25, 0.1), color=trim)
        box(self.sword, position=(0, -0.38, 0), scale=(0.3, 0.07, 0.1), color=trim)

        # --- flowing scarf --------------------------------------------------
        self.scarf = Entity(parent=self, position=(0, 1.72, -0.34))
        box(self.scarf, position=(0, 0, -0.3), scale=(0.34, 0.08, 0.6), color=trim)

    @staticmethod
    def _find_custom_model(name):
        folder = ASSET_DIR / 'models'
        if folder.exists():
            for ext in ('.glb', '.gltf', '.obj', '.bam', '.ursinamesh'):
                if (folder / f'{name}{ext}').exists():
                    return True
        return False

    def animate_run(self, t, speed, state):
        """
        Procedural animation.  t = running clock, speed = world speed,
        state = 'run' | 'jump' | 'slide'.
        """
        if self.custom:
            return
        rate = 9 + speed * 0.25
        swing = sin(t * rate) * 55
        if state == 'run':
            self.leg_l.rotation_x = swing
            self.leg_r.rotation_x = -swing
            self.arm_l.rotation_x = -swing * 0.8
            self.arm_r.rotation_x = swing * 0.8
            self.rotation_x = 8                    # lean forward
            self.y = abs(sin(t * rate)) * 0.12     # bounce
        elif state == 'jump':
            self.leg_l.rotation_x = -50
            self.leg_r.rotation_x = 25
            self.arm_l.rotation_x = -160
            self.arm_r.rotation_x = -160
            self.rotation_x = 0
        elif state == 'slide':
            self.leg_l.rotation_x = -80
            self.leg_r.rotation_x = -80
            self.arm_l.rotation_x = -120
            self.arm_r.rotation_x = -120
            self.rotation_x = -55                  # lean way back
        self.scarf.rotation_x = -15 + sin(t * rate * 1.3) * 20
        self.sword.rotation_z = 40 + sin(t * rate) * 3


# ===========================================================================
#  OBSTACLE BUILDERS
# ===========================================================================
def _tag(e, kind, hw, hd, y0, y1):
    """Attach collision data to an obstacle entity."""
    e.kind, e.hw, e.hd, e.y0, e.y1 = kind, hw, hd, y0, y1
    return e


HAZARD_Y = color.rgb32(255, 214, 0)
HAZARD_K = color.rgb32(20, 20, 20)


def hazard_band(root, x, y, width, z, h=0.22):
    """Black/yellow warning stripes facing the player - reads clearly against any floor."""
    n = max(2, int(width / 0.4))
    w = width / n
    for i in range(n):
        box(root, position=(x - width / 2 + w * (i + 0.5), y, z), scale=(w, h, 0.03),
            color=HAZARD_Y if i % 2 == 0 else HAZARD_K)


def make_low(x, z, lanes, pal):
    """Low LEGO brick wall - JUMP over it.  lanes = 1 or 3."""
    main, trim = pal
    root = Entity(position=(x, 0, z))
    width = 2.0 * lanes + (lanes - 1) * 0.4
    for i in range(lanes):
        bx = (i - (lanes - 1) / 2) * 2.4
        box(root, position=(bx, 0.45, 0), scale=(2.0, 0.9, 1.1), color=main)
        for sx in (-0.5, 0.5):                                 # LEGO studs on top
            box(root, position=(bx + sx, 1.0, 0), scale=(0.5, 0.2, 0.5), color=trim)
        hazard_band(root, bx, 0.45, 2.0, -0.57)
    return _tag(root, 'low', width / 2, 0.55, 0.0, 0.9)


def make_beam(x, z, lanes, pal):
    """Overhead beam on posts - SLIDE under it.  lanes = 1 or 3."""
    main, trim = pal
    root = Entity(position=(x, 0, z))
    width = 2.0 * lanes + (lanes - 1) * 0.4
    for sx in (-width / 2 + 0.2, width / 2 - 0.2):
        box(root, position=(sx, 1.3, 0), scale=(0.4, 2.6, 0.4), color=trim)
    box(root, position=(0, 1.9, 0), scale=(width, 1.0, 0.7), color=main)
    box(root, position=(0, 1.9, -0.36), scale=(width, 0.25, 0.02), color=trim)
    # hazard stripes
    for i in range(int(width // 1.2)):
        box(root, position=(-width / 2 + 0.7 + i * 1.2, 1.9, -0.37), scale=(0.35, 1.0, 0.02), color=trim)
    return _tag(root, 'beam', width / 2, 0.4, 1.35, 2.4)


def make_wall(x, z, pal):
    """Tall Skulkin-skull block - change LANE to dodge."""
    main, trim = pal
    root = Entity(position=(x, 0, z))
    box(root, position=(0, 1.6, 0), scale=(2.1, 3.2, 1.3), color=main)
    box(root, position=(0, 3.25, 0), scale=(2.3, 0.3, 1.5), color=trim)
    # skull face on the side the player sees
    box(root, position=(0, 1.9, -0.67), scale=(1.4, 1.2, 0.04), color=SKULL_WHITE)
    box(root, position=(-0.35, 2.0, -0.7), scale=(0.35, 0.4, 0.04), color=color.black)
    box(root, position=(0.35, 2.0, -0.7), scale=(0.35, 0.4, 0.04), color=color.black)
    box(root, position=(0, 1.5, -0.7), scale=(0.7, 0.18, 0.04), color=color.black)
    hazard_band(root, 0, 0.35, 2.0, -0.68, 0.4)
    return _tag(root, 'wall', 1.05, 0.65, 0.0, 3.2)


def make_stud(x, y, z):
    """Collectable gold LEGO stud."""
    e = box(position=(x, y, z), model='sphere', scale=(0.7, 0.7, 0.25), color=C.GOLD)
    e.is_stud = True
    return e


def make_finish_gate(z):
    """Chequered Ninjago arch marking the end of the level."""
    root = Entity(position=(0, 0, z))
    for sx in (-4.4, 4.4):
        box(root, position=(sx, 3.5, 0), scale=(1.0, 7, 1.0), color=C.GOLD)
    for i in range(10):                                    # chequered banner
        for j in range(2):
            col = color.white if (i + j) % 2 == 0 else color.black
            box(root, position=(-4.05 + i * 0.9, 7.4 - j * 0.9 + 0.0, -0.1), scale=(0.9, 0.9, 0.3), color=col)
    box(root, position=(0, 8.6, 0), scale=(10, 0.6, 1.0), color=C.KAI_RED)
    return root


# ===========================================================================
#  SCENERY (per level theme)
# ===========================================================================
def build_deco(parent, theme, rng):
    """Populate one floor chunk with side scenery for the given theme."""
    for side in (-1, 1):
        for _ in range(3):
            x = side * rng.uniform(6.0, 22.0)
            z = rng.uniform(0, C.CHUNK_LENGTH)
            if theme == 'bamboo':
                h = rng.uniform(5, 13)
                col = random.choice([C.LLOYD_GREEN, shade(C.LLOYD_GREEN, 0.7), color.rgb32(110, 200, 80)])
                box(parent, position=(x, h / 2, z), scale=(0.5, h, 0.5), color=col)
                box(parent, position=(x, h * 0.6, z), scale=(0.7, 0.15, 0.7), color=shade(col, 0.6))
                if rng.random() < 0.25:                    # little gold-roofed dojo
                    box(parent, position=(x, 1.5, z), scale=(5, 3, 5), color=color.rgb32(150, 100, 60))
                    box(parent, position=(x, 3.6, z), model=cone5(), scale=(8, 2.2, 8), color=C.GOLD)
            elif theme == 'lava':
                h = rng.uniform(6, 16)
                box(parent, position=(x, h / 2 - 1, z), model=cone5(), scale=(rng.uniform(3, 6), h, rng.uniform(3, 6)),
                    color=rng.choice([C.COLE_BLACK, shade(C.COLE_BLACK, 1.8)]))
                if rng.random() < 0.5:                     # glowing ember
                    box(parent, position=(x + 0.4, 1.0, z - 2), model='sphere', scale=0.9, color=color.rgb32(255, 140, 20))
            else:                                          # ice
                h = rng.uniform(5, 14)
                box(parent, position=(x, h / 2, z), model=cone5(), scale=(rng.uniform(2.5, 5), h, rng.uniform(2.5, 5)),
                    color=rng.choice([C.ZANE_WHITE, C.JAY_BLUE, color.rgb32(170, 215, 255)]))
                if rng.random() < 0.3:                     # floating crystal
                    box(parent, position=(x, rng.uniform(8, 14), z), model='diamond', scale=(1.5, 3, 1.5), color=C.JAY_BLUE)


class Chunk(Entity):
    """One recycled 30-unit slice of track: floor tiles + side ground + scenery."""

    def __init__(self, level, rng, **kw):
        super().__init__(**kw)
        self.level, self.rng = level, rng
        self.deco = Entity(parent=self)
        self._build_floor()
        self.rebuild_deco()

    def _build_floor(self):
        lv = self.level
        n = 10
        step = C.CHUNK_LENGTH / n
        for i in range(n):
            col = lv['floor_a'] if i % 2 == 0 else lv['floor_b']
            box(self, position=(0, -0.2, i * step + step / 2), scale=(8.0, 0.4, step), color=col)
        # lane dividers (gold dashes)
        for lane_x in (-1.2, 1.2):
            for i in range(0, n, 2):
                box(self, position=(lane_x, 0.02, i * step + step / 2), scale=(0.1, 0.02, step * 0.5), color=C.GOLD)
        # ground outside the track; lava level sits lower so it looks like a chasm
        y = -2.5 if lv['deco'] == 'lava' else -0.6
        for side in (-1, 1):
            box(self, position=(side * (4 + 25), y, C.CHUNK_LENGTH / 2),
                scale=(50, 1, C.CHUNK_LENGTH), color=lv['side'])
        # edge rails
        for side in (-1, 1):
            box(self, position=(side * 4.1, 0.35, C.CHUNK_LENGTH / 2), scale=(0.3, 0.7, C.CHUNK_LENGTH),
                color=self.level['obstacle'][1])

    def rebuild_deco(self):
        for c in list(self.deco.children):
            destroy(c)
        build_deco(self.deco, self.level['deco'], self.rng)


# ===========================================================================
#  WORLD
# ===========================================================================
class World:
    """Owns the floor chunks, obstacles, studs and finish gate of one level."""

    def __init__(self, level, diff, speed_for_spawn):
        self.level = level
        self.diff = diff
        self.spawn_speed = speed_for_spawn        # base speed used to size gaps
        self.rng = random.Random()
        self.obstacles, self.studs, self.enemies = [], [], []
        self.level_index = C.LEVELS.index(level)
        self.chunks = [Chunk(level, self.rng, z=(i - 1) * C.CHUNK_LENGTH)   # one chunk behind the start
                       for i in range(C.VIEW_CHUNKS)]
        self.next_chunk = C.VIEW_CHUNKS - 1
        self.spawn_z = 60.0                       # first obstacle row (runway before it)
        self.last_was_action = False
        self.gate = make_finish_gate(level['length'])

        # distant mountains / backdrop that follows the player (draw-distance trick)
        self.backdrop = Entity()
        for i in range(9):
            x = (i - 4) * 38 + self.rng.uniform(-8, 8)
            h = self.rng.uniform(30, 55)
            box(self.backdrop, position=(x, h / 2 - 5, 100), model=cone5(), scale=(45, h, 30),
                color=shade(level['fog'], self.rng.uniform(0.75, 1.0)))

    # -- chunk recycling ----------------------------------------------------
    def update(self, player_z):
        self.backdrop.z = player_z
        first = self.chunks[0]
        if first.z + C.CHUNK_LENGTH < player_z - 25:
            self.chunks.pop(0)
            first.z = self.next_chunk * C.CHUNK_LENGTH
            first.rebuild_deco()
            self.chunks.append(first)
            self.next_chunk += 1
        self._spawn_until(player_z + C.SPAWN_AHEAD)
        # cull things we have passed
        for lst in (self.obstacles, self.studs, self.enemies):
            for e in lst[:]:
                if e.z < player_z - 20:
                    lst.remove(e)
                    destroy(e)

    # -- obstacle generation -----------------------------------------------
    def _spawn_until(self, z_limit):
        stop = self.level['length'] - 50
        while self.spawn_z < z_limit and self.spawn_z < stop:
            self._spawn_row(self.spawn_z)

    def _spawn_row(self, z):
        d, rng, pal = self.diff, self.rng, self.level['obstacle']
        lanes = list(range(3))
        rng.shuffle(lanes)

        def single(kind, lane):
            x = C.LANES[lane]
            if kind == 'wall':
                return make_wall(x, z, pal)
            if kind == 'low':
                return make_low(x, z, 1, pal)
            return make_beam(x, z, 1, pal)

        full_width = False
        r = rng.random()
        enemy_p = self.level['enemy_chance'] * d['enemy']
        if not self.last_was_action and rng.random() < enemy_p:
            # --- Skulkin ambush: 1-2 enemies, always leaving one lane free
            n = 2 if rng.random() < d['extra'] * 0.8 else 1
            for i in range(n):
                brute = self.level_index >= 1 and rng.random() < 0.3
                self.enemies.append(Enemy('brute' if brute else 'warrior', C.LANES[lanes[i]],
                                          z + rng.uniform(0, 6), self.level['enemy']))
            self.last_was_action = False
            gap = max(d['gap'] * rng.uniform(0.9, 1.3), self.spawn_speed * 0.7)
            for i in range(max(int((gap - 8) // 2.6), 0)):
                self.studs.append(make_stud(C.LANES[lanes[2]], 1.0, z + 5 + i * 2.6))
            self.spawn_z += gap
            return
        if r < 0.55:                                   # one single-lane obstacle (+ maybe another)
            kinds = ['wall', 'low', 'beam']
            first = rng.choice(kinds)
            self.obstacles.append(single(first, lanes[0]))
            if rng.random() < d['extra']:
                self.obstacles.append(single(rng.choice(kinds), lanes[1]))
        elif r < 0.80:                                 # full-width low wall -> must jump
            self.obstacles.append(make_low(0, z, 3, pal))
            full_width = True
        else:                                          # full-width beam -> must slide
            self.obstacles.append(make_beam(0, z, 3, pal))
            full_width = True

        # Distance to the next row.  Denser on harder modes, but never shorter
        # than the time needed to react after a jump/slide-only row.
        gap = d['gap'] * rng.uniform(0.8, 1.25)
        reaction = self.spawn_speed * (0.95 if (full_width or self.last_was_action) else 0.5)
        gap = max(gap, reaction)
        self.last_was_action = full_width

        # gold studs trail through the gap in the lane that was left free
        free_lane = lanes[2] if len(self.obstacles) and not full_width else rng.randrange(3)
        n = int((gap - 8) // 2.6)
        for i in range(max(n, 0)):
            self.studs.append(make_stud(C.LANES[free_lane], 1.0, z + 5 + i * 2.6))
        self.spawn_z += gap

    def update_enemies(self, dt, player_z):
        """Run enemy AI.  Returns the list of enemies that burned to death this frame."""
        return [en for en in self.enemies[:] if en.update_ai(dt, player_z)]

    def clear(self):
        for e in self.obstacles + self.studs + self.enemies + self.chunks + [self.gate, self.backdrop]:
            destroy(e)
        self.obstacles, self.studs, self.enemies, self.chunks = [], [], [], []
