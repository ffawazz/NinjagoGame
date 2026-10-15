"""
powers.py - each ninja's elemental power (press E / F / left mouse).

    KAI    fire       fireball that explodes, damages and sets enemies on fire
    JAY    lightning  chain bolt that zaps the 3 nearest enemies
    COLE   earth      ground shockwave: smashes enemies, rocks and walls
    ZANE   ice        freezes every enemy ahead; touch a frozen one to shatter it
    LLOYD  spin       Spinjitzu tornado: invincible, smashes everything, pulls studs

Powers cost energy (see config).  Energy refills with studs, time and kills.
`Powers` also owns the particle system (`FX`) used for all effects.
"""
import random

from ursina import Entity, Vec3, camera, color, destroy, sin, cos, curve

import config as C
from ps1 import box

FIRE_ORANGE = color.rgb32(255, 120, 20)
FIRE_YELLOW = color.rgb32(255, 220, 60)
BOLT = color.rgb32(170, 220, 255)
ICE = color.rgb32(150, 220, 255)
ROCK = color.rgb32(110, 90, 70)


# ===========================================================================
#  Particles
# ===========================================================================
class FX:
    """Tiny particle manager: coloured cubes that fly, fall and shrink away."""

    def __init__(self):
        self.parts = []      # [entity, velocity, life, max_life, gravity]
        self.timed = []      # [entity, life]  (things that just vanish later)

    def burst(self, pos, col, n=14, speed=6.0, size=0.2, life=0.7, up=4.0, gravity=14.0):
        for _ in range(n):
            e = box(position=pos, scale=size * random.uniform(0.6, 1.4), color=col,
                    rotation=(random.uniform(0, 360), random.uniform(0, 360), 0))
            v = Vec3(random.uniform(-1, 1), random.uniform(0, 1), random.uniform(-1, 1)) * speed
            v.y += up
            self.parts.append([e, v, life * random.uniform(0.6, 1.2), life, gravity])

    def vanish_after(self, entity, life):
        self.timed.append([entity, life])

    def update(self, dt):
        for p in self.parts[:]:
            e, v, life, mx, g = p
            p[2] -= dt
            if p[2] <= 0:
                destroy(e)
                self.parts.remove(p)
                continue
            v.y -= g * dt
            e.position += v * dt
            e.rotation_x += 300 * dt
            s = max(0.05, p[2] / mx)
            e.scale = e.scale_x * (0.97 if s < 0.5 else 1.0)
        for t in self.timed[:]:
            t[1] -= dt
            if t[1] <= 0:
                destroy(t[0])
                self.timed.remove(t)

    def clear(self):
        for p in self.parts:
            destroy(p[0])
        for t in self.timed:
            destroy(t[0])
        self.parts, self.timed = [], []


# ===========================================================================
#  Powers
# ===========================================================================
class Powers:
    def __init__(self, game):
        self.g = game
        self.fx = FX()
        self.fireballs = []      # [entity, start_z]
        self.waves = []          # earthquake shockwaves  [entity, start_z, hit_set]
        self.tornado = None

    # -- helpers ----------------------------------------------------------
    @property
    def p(self):
        return self.g.player

    def enemies_ahead(self, max_dist):
        return sorted([e for e in self.g.world.enemies if 0 < e.z - self.p.z < max_dist],
                      key=lambda e: e.z)

    def damage(self, enemy, amount):
        """Hurt an enemy; kill it if it dies.  Returns True if killed."""
        if enemy.hurt(amount):
            self.kill(enemy)
            return True
        self.fx.burst(enemy.position + Vec3(0, 1.4, 0), color.white, 5, 3, 0.15, 0.4)
        return False

    def kill(self, enemy, reward=True, col=None):
        """Remove an enemy with a bone-scattering poof."""
        if enemy in self.g.world.enemies:
            self.g.world.enemies.remove(enemy)
        pal = self.g.lv['enemy']
        self.fx.burst(enemy.position + Vec3(0, 1.2, 0), col or pal[0], 16, 6, 0.3, 0.9)
        self.fx.burst(enemy.position + Vec3(0, 1.8, 0), pal[2], 6, 4, 0.22, 0.6)
        destroy(enemy)
        if reward:
            self.g.on_enemy_killed()
        self.g.sounds.sfx('kill', 0.8)

    def smash_obstacle(self, o):
        """Destroy a rock/wall (earth shockwave, tornado)."""
        if o in self.g.world.obstacles:
            self.g.world.obstacles.remove(o)
        self.fx.burst(o.position + Vec3(0, 1.0, 0), self.g.lv['obstacle'][0], 14, 6, 0.4, 0.9)
        self.fx.burst(o.position + Vec3(0, 1.0, 0), ROCK, 8, 5, 0.3, 0.8)
        destroy(o)
        self.g.on_smash()

    def shatter(self, enemy):
        """Player ran into a frozen enemy: it explodes into ice."""
        self.kill(enemy, reward=True, col=ICE)
        self.fx.burst(enemy.position + Vec3(0, 1.2, 0), ICE, 14, 7, 0.3, 0.9)

    # -- casting ----------------------------------------------------------
    def cast(self):
        kind = self.g.spec['power']
        getattr(self, f'_cast_{kind}')()
        self.g.sounds.sfx({'fire': 'fire', 'lightning': 'zap', 'earth': 'quake',
                           'ice': 'freeze', 'spin': 'spin'}[kind])

    def _cast_fire(self):
        p = self.p
        root = Entity(position=(p.x, 1.1, p.z + 1.6))
        box(root, model='sphere', scale=0.9, color=FIRE_ORANGE)
        box(root, model='sphere', scale=0.55, color=FIRE_YELLOW)
        self.fireballs.append([root, p.z])
        self.fx.burst(root.position, FIRE_ORANGE, 8, 3, 0.2, 0.4)

    def _cast_lightning(self):
        p = self.p
        targets = self.enemies_ahead(60)[:3]
        start = Vec3(p.x, 1.6, p.z + 0.8)
        if not targets:                                    # no enemies: strike down your own lane
            self._bolt(start, Vec3(p.x, 1.2, p.z + 30))
        for e in targets:
            target = Vec3(e.x, 1.4, e.z)                   # read position BEFORE the enemy can die
            self._bolt(start, target)
            self.fx.burst(target, BOLT, 12, 5, 0.2, 0.5)
            self.damage(e, 1)
            start = target                                 # chain from one target to the next
        self.g.flash_screen(color.rgba(150, 200, 255, 110))

    def _bolt(self, a, b, segments=9):
        pts = [a + (b - a) * (i / segments) + (Vec3(random.uniform(-0.5, 0.5), random.uniform(-0.4, 0.4), 0)
                                                if 0 < i < segments else Vec3(0, 0, 0))
               for i in range(segments + 1)]
        for i in range(segments):
            mid = (pts[i] + pts[i + 1]) / 2
            length = (pts[i + 1] - pts[i]).length()
            seg = box(position=mid, scale=(0.16, 0.16, length + 0.1), color=BOLT if i % 2 else color.white)
            seg.look_at(pts[i + 1])
            self.fx.vanish_after(seg, 0.22)

    def _cast_earth(self):
        p = self.p
        wave = box(position=(0, 0.45, p.z + 2), scale=(7.8, 0.9, 1.4), color=ROCK)
        box(wave, position=(0, 0.6, 0), scale=(0.9, 0.5, 0.9), color=C.GOLD)
        self.waves.append([wave, p.z, set()])
        self.g.shake = max(self.g.shake, 0.6)

    def _cast_ice(self):
        p = self.p
        for e in self.enemies_ahead(45):
            e.freeze(5.0)
            self.fx.burst(e.position + Vec3(0, 1.2, 0), ICE, 12, 4, 0.25, 0.6)
        for i in range(16):                                # expanding ring of ice shards
            a = i / 16 * 6.283
            self.fx.burst(Vec3(p.x + cos(a) * 1.5, 0.6, p.z + 2 + sin(a) * 1.5), ICE, 1, 12, 0.2, 0.7, 2, 3)
        self.g.flash_screen(color.rgba(150, 230, 255, 110))

    def _cast_spin(self):
        self.g.tornado_t = 3.2
        if self.tornado:
            destroy(self.tornado)
        self.tornado = Entity(parent=self.p)
        for i in range(16):                                 # spiral of spinning blocks around the ninja
            ang = i * 50
            r = 1.0 + i * 0.07
            holder = Entity(parent=self.tornado, rotation_y=ang, y=0.1 + i * 0.15)
            box(holder, position=(r, 0, 0), scale=(0.45, 0.14, 0.45),
                color=C.LLOYD_GREEN if i % 2 == 0 else C.GOLD)
        self.g.invuln = 0

    # -- per-frame ----------------------------------------------------------
    def update(self, dt):
        g, p = self.g, self.p
        # Fireballs
        for fb in self.fireballs[:]:
            e, z0 = fb
            e.z += 78 * dt
            e.rotation_y += 400 * dt
            if random.random() < 0.8:
                self.fx.burst(e.position, random.choice((FIRE_ORANGE, FIRE_YELLOW, C.KAI_RED)), 1, 1.2, 0.3, 0.35, 1, -3)
            hit = next((en for en in g.world.enemies
                        if abs(en.z - e.z) < en.hd + 1.0 and abs(en.x - e.x) < en.hw + 1.0), None)
            if hit or e.z - z0 > 70:
                if hit:                                     # explosion: area damage + burning
                    self.fx.burst(e.position, FIRE_ORANGE, 26, 9, 0.4, 0.8)
                    self.fx.burst(e.position, FIRE_YELLOW, 12, 6, 0.3, 0.6)
                    g.shake = max(g.shake, 0.25)
                    for en in list(g.world.enemies):
                        if (Vec3(en.x, 0, en.z) - Vec3(e.x, 0, e.z)).length() < 3.2:
                            if not self.damage(en, 1):
                                en.ignite(2.0)
                destroy(e)
                self.fireballs.remove(fb)
        # Earthquake shockwaves
        for w in self.waves[:]:
            e, z0, done = w
            e.z += 60 * dt
            self.fx.burst(Vec3(random.uniform(-3.6, 3.6), 0.6, e.z), ROCK, 2, 3, 0.3, 0.5, 5)
            for en in list(g.world.enemies):
                if id(en) not in done and abs(en.z - e.z) < en.hd + 1.2:
                    done.add(id(en))
                    self.damage(en, 2)
            for o in list(g.world.obstacles):
                if o.kind in ('low', 'wall') and abs(o.z - e.z) < o.hd + 1.2:
                    self.smash_obstacle(o)
            if e.z - z0 > 32:
                destroy(e)
                self.waves.remove(w)
        # Spinjitzu tornado
        if self.tornado:
            if g.tornado_t > 0:
                self.tornado.rotation_y += 700 * dt
            else:
                destroy(self.tornado)
                self.tornado = None
        self.fx.update(dt)

    def clear(self):
        for fb in self.fireballs:
            destroy(fb[0])
        for w in self.waves:
            destroy(w[0])
        if self.tornado:
            destroy(self.tornado)
        self.fireballs, self.waves, self.tornado = [], [], None
        self.fx.clear()
