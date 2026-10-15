"""
enemies.py - the Skulkin skeleton army that ambushes you.

Two kinds
---------
warrior : 1 hit point, charges at you once you get close.
brute   : 1.5x bigger, 3 hit points, slower - needs several hits or a big power.

How the ninjas' powers interact with them lives in powers.py; this file only
knows how an enemy looks, moves, takes damage, freezes and burns.

An enemy has the same collision fields as an obstacle (hw, hd, y0, y1), so
main.Game._collisions treats both the same way.
"""
import random

from ursina import Entity, color, sin

import config as C
from ps1 import box

ICE = color.rgb32(150, 220, 255)
FIRE = color.rgb32(255, 120, 20)


def mix(a, b, t):
    """Blend colour a towards colour b by t (0-1)."""
    return color.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t,
                      a.b + (b.b - a.b) * t, a.a)


class Enemy(Entity):
    def __init__(self, kind, x, z, pal):
        super().__init__(position=(x, 0, z))
        self.kind = 'enemy'                    # collision kind (obstacles use wall/low/beam)
        self.type = kind                       # 'warrior' | 'brute'
        bone, armor, glow = pal
        s = 1.0 if kind == 'warrior' else 1.55
        self.hp = 1.0 if kind == 'warrior' else 3.0
        self.hw, self.hd, self.y0, self.y1 = 0.75 * s, 0.5 * s, 0.0, 2.3 * s
        self.charge_speed = 9.0 if kind == 'warrior' else 6.0
        self.trigger = 52.0                    # starts charging when this close
        self.state = 'idle'
        self.freeze_t = 0.0
        self.burn_t = 0.0
        self.burn_tick = 0.0
        self.flash = 0.0
        self.clock = random.uniform(0, 6)
        self.on_burn_kill = None               # set by World: called if burning kills it

        self.parts = []                        # (entity, base colour) for tinting

        def part(parent, **kw):
            e = box(parent, **kw)
            self.parts.append((e, kw['color']))
            return e

        # body faces -Z (towards the player), so rotate the +Z-facing model 180°
        self.body = Entity(parent=self, scale=s, rotation_y=180)
        b = self.body
        # legs (bone) pivoting at the hip
        self.leg_l = Entity(parent=b, position=(-0.2, 0.8, 0))
        self.leg_r = Entity(parent=b, position=(0.2, 0.8, 0))
        for leg in (self.leg_l, self.leg_r):
            part(leg, position=(0, -0.4, 0), scale=(0.16, 0.8, 0.16), color=bone)
            part(leg, position=(0, -0.78, 0.07), scale=(0.24, 0.12, 0.38), color=armor)
        # ribcage + spine + pelvis
        part(b, position=(0, 0.88, 0), scale=(0.5, 0.16, 0.3), color=bone)
        part(b, position=(0, 1.3, 0), scale=(0.2, 0.7, 0.18), color=bone)
        for i in range(3):
            part(b, position=(0, 1.1 + i * 0.22, 0.02), scale=(0.74, 0.1, 0.34), color=bone)
        part(b, position=(0, 1.3, 0.2), scale=(0.62, 0.55, 0.06), color=armor)       # chest plate
        part(b, position=(0, 1.3, 0.24), scale=(0.2, 0.2, 0.04), color=glow)         # glowing emblem
        # shoulder pads
        for sx in (-0.5, 0.5):
            part(b, position=(sx, 1.62, 0), scale=(0.38, 0.2, 0.42), color=armor)
        # arms
        self.arm_l = Entity(parent=b, position=(-0.5, 1.55, 0))
        self.arm_r = Entity(parent=b, position=(0.5, 1.55, 0))
        for arm in (self.arm_l, self.arm_r):
            part(arm, position=(0, -0.33, 0), scale=(0.13, 0.66, 0.13), color=bone)
        # bone sword in the right hand
        part(self.arm_r, position=(0, -0.75, 0.3), scale=(0.1, 0.1, 0.9), color=color.rgb32(200, 205, 215))
        part(self.arm_r, position=(0, -0.7, 0.0), scale=(0.3, 0.1, 0.1), color=armor)
        # skull head
        self.head = Entity(parent=b, position=(0, 1.98, 0))
        part(self.head, scale=(0.55, 0.5, 0.5), color=bone)
        part(self.head, position=(0, -0.3, 0.05), scale=(0.4, 0.14, 0.4), color=bone)     # jaw
        for ex in (-0.14, 0.14):
            part(self.head, position=(ex, 0.03, 0.26), scale=(0.15, 0.17, 0.04), color=glow)   # glowing eyes
        part(self.head, position=(0, 0.3, 0), scale=(0.6, 0.14, 0.56), color=armor)       # helmet band
        if kind == 'brute':
            for hx in (-0.34, 0.34):                           # horns
                part(self.head, position=(hx, 0.5, 0), scale=(0.12, 0.45, 0.12), color=bone)

    # ------------------------------------------------------------------
    @property
    def frozen(self):
        return self.freeze_t > 0

    def _tint(self):
        if self.flash > 0:
            tint, amt = color.white, 0.85
        elif self.frozen:
            tint, amt = ICE, 0.75
        elif self.burn_t > 0:
            tint, amt = FIRE, 0.5 + 0.25 * sin(self.clock * 30)
        else:
            tint, amt = None, 0
        for e, base in self.parts:
            e.color = base if tint is None else mix(base, tint, amt)

    def hurt(self, amount):
        """Apply damage.  Returns True if the enemy is now dead."""
        self.hp -= amount
        self.flash = 0.12
        self._tint()
        return self.hp <= 0

    def freeze(self, seconds):
        self.freeze_t = seconds
        self.burn_t = 0
        self._tint()

    def ignite(self, seconds=2.0):
        self.burn_t = seconds
        self.burn_tick = 0.5

    # ------------------------------------------------------------------
    def update_ai(self, dt, player_z):
        """Move/animate.  Returns True if this enemy burned to death."""
        self.clock += dt
        died = False
        if self.flash > 0:
            self.flash -= dt
            if self.flash <= 0:
                self._tint()
        if self.frozen:
            self.freeze_t -= dt
            if self.freeze_t <= 0:
                self._tint()
            return False
        if self.burn_t > 0:                                    # damage over time
            self.burn_t -= dt
            self.burn_tick -= dt
            if self.burn_tick <= 0:
                self.burn_tick = 0.5
                died = self.hurt(0.5)
            self._tint()
        dist = self.z - player_z
        if self.state == 'idle' and 0 < dist < self.trigger:
            self.state = 'charge'
        t = self.clock
        if self.state == 'charge':
            self.z -= self.charge_speed * dt
            sw = sin(t * 12) * 50
            self.leg_l.rotation_x, self.leg_r.rotation_x = sw, -sw
            self.arm_l.rotation_x, self.arm_r.rotation_x = -sw * 0.6, -120 + sin(t * 12) * 15   # sword raised
            self.body.y = abs(sin(t * 12)) * 0.12
        else:                                                  # taunting: rattle + wave sword
            self.arm_r.rotation_x = -100 + sin(t * 5) * 25
            self.arm_l.rotation_x = 0
            self.head.rotation_z = sin(t * 3) * 8
        return died
