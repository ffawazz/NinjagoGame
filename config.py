"""
config.py - all tweakable game data lives here.

Nothing in this file touches the engine except `ursina.color`, so you can
rebalance the game (speeds, densities, colours, jokes...) without reading
the gameplay code.
"""
from ursina import color

# ---------------------------------------------------------------------------
# Core Ninjago palette (LEGO-ish saturated colours)
# ---------------------------------------------------------------------------
KAI_RED     = color.rgb32(215, 25, 32)
JAY_BLUE    = color.rgb32(0, 110, 220)
COLE_BLACK  = color.rgb32(30, 30, 36)
ZANE_WHITE  = color.rgb32(238, 242, 248)
LLOYD_GREEN = color.rgb32(30, 170, 60)
GOLD        = color.rgb32(255, 200, 20)
LEGO_YELLOW = color.rgb32(250, 215, 40)   # minifig skin


def shade(c, amount):
    """Return colour `c` multiplied by `amount` (<1 darker, >1 lighter)."""
    return color.rgba(min(c.r * amount, 1), min(c.g * amount, 1),
                      min(c.b * amount, 1), c.a)


# ---------------------------------------------------------------------------
# Playable ninjas.  Each has a small gameplay perk so the choice matters.
#   suit / accent   : body and trim colour of the model
#   lane_speed      : how fast the ninja changes lanes (higher = snappier)
#   jump            : jump launch velocity
#   lives           : starting hit points
#   invuln          : seconds of invincibility after a hit
#   magnet          : radius (world units) in which gold studs fly to you
#   model           : optional file name (no extension) in assets/models/
# ---------------------------------------------------------------------------
NINJAS = [
    dict(id='kai',   name='KAI',   title='Ninja of Fire',      suit=KAI_RED,     accent=GOLD,
         lane_speed=15, jump=11.0, lives=3, invuln=1.5, magnet=0.0,
         perk='Fastest lane changes'),
    dict(id='jay',   name='JAY',   title='Ninja of Lightning', suit=JAY_BLUE,    accent=GOLD,
         lane_speed=11, jump=13.0, lives=3, invuln=1.5, magnet=0.0,
         perk='Highest jump'),
    dict(id='cole',  name='COLE',  title='Ninja of Earth',     suit=COLE_BLACK,  accent=GOLD,
         lane_speed=11, jump=11.0, lives=3, invuln=2.6, magnet=0.0,
         perk='Long invincibility after a hit'),
    dict(id='zane',  name='ZANE',  title='Ninja of Ice',       suit=ZANE_WHITE,  accent=JAY_BLUE,
         lane_speed=11, jump=11.0, lives=4, invuln=1.5, magnet=0.0,
         perk='Nindroid: +1 life'),
    dict(id='lloyd', name='LLOYD', title='The Green Ninja',    suit=LLOYD_GREEN, accent=GOLD,
         lane_speed=11, jump=11.0, lives=3, invuln=1.5, magnet=5.0,
         perk='Golden power: stud magnet'),
]

# ---------------------------------------------------------------------------
# Difficulty.  These two numbers are what the brief asks us to scale:
#   speed : forward running speed in units / second  (+ per-level multiplier)
#   gap   : average distance between obstacle rows   (smaller = denser)
#   extra : chance (0-1) that a row contains a second obstacle
# ---------------------------------------------------------------------------
DIFFICULTIES = {
    'EASY':   dict(speed=14.0, gap=26.0, extra=0.15, ramp=0.010),
    'NORMAL': dict(speed=19.0, gap=19.0, extra=0.35, ramp=0.015),
    'HARD':   dict(speed=25.0, gap=14.0, extra=0.60, ramp=0.020),
}
DIFFICULTY_ORDER = ['EASY', 'NORMAL', 'HARD']

# ---------------------------------------------------------------------------
# The three levels.
#   length      : distance (world units) to the finish gate
#   speed_mult  : multiplies the difficulty's base speed
#   sky / fog   : background + distance-fog colour (the PS1 'draw distance')
#   floor_a/b   : alternating floor tile colours
#   side        : colour of the ground outside the track
#   deco        : which scenery generator entities.py should use
#   obstacle    : (main, trim) colours for obstacles
#   music       : optional file in assets/music/ (falls back to the main theme)
#   video       : optional file in assets/videos/ (falls back to an animated gag)
#   gags        : captions for the built-in animated cutscene
# ---------------------------------------------------------------------------
LEVELS = [
    dict(name='LEVEL 1', subtitle='Dojo Training Grounds',
         length=900, speed_mult=1.00,
         sky=color.rgb32(120, 200, 150), fog=color.rgb32(120, 200, 150), fog_range=(30, 150),
         floor_a=color.rgb32(40, 150, 60), floor_b=color.rgb32(30, 120, 50),
         side=color.rgb32(25, 90, 40), deco='bamboo',
         obstacle=(LLOYD_GREEN, GOLD),
         music='level1', video='level1.mp4',
         gags=["SENSEI WU: Today's lesson - never run into a wall!",
               "LLOYD: ...I ran into three walls.",
               "SENSEI WU: Tomorrow's lesson - tea. Lots of tea."]),
    dict(name='LEVEL 2', subtitle='Caverns of Fire & Stone',
         length=1100, speed_mult=1.12,
         sky=color.rgb32(40, 8, 8), fog=color.rgb32(60, 10, 10), fog_range=(25, 130),
         floor_a=color.rgb32(40, 40, 46), floor_b=color.rgb32(26, 26, 32),
         side=color.rgb32(200, 50, 10), deco='lava',
         obstacle=(KAI_RED, COLE_BLACK),
         music='level2', video='level2.mp4',
         gags=["KAI: That lava was totally not hot.",
               "COLE: Your shoes are on fire, Kai.",
               "KAI: ...Cole, do you have any cake to put it out?"]),
    dict(name='LEVEL 3', subtitle='Ice Peaks of the Sky Temple',
         length=1300, speed_mult=1.25,
         sky=color.rgb32(150, 200, 255), fog=color.rgb32(190, 220, 255), fog_range=(25, 130),
         floor_a=color.rgb32(235, 245, 255), floor_b=color.rgb32(120, 170, 235),
         side=color.rgb32(0, 90, 190), deco='ice',
         obstacle=(JAY_BLUE, ZANE_WHITE),
         music='level3', video='level3.mp4',
         gags=["ZANE: I have calculated a 99.9% chance of victory.",
               "JAY: And the 0.1%?! Talk to me, Zane!",
               "ZANE: It involves Jay talking for four more minutes."]),
]

# ---------------------------------------------------------------------------
# Gameplay constants
# ---------------------------------------------------------------------------
LANES = (-2.4, 0.0, 2.4)     # x position of the 3 lanes
GRAVITY = 32.0
SLIDE_TIME = 0.75            # seconds a slide lasts
STAND_HEIGHT = 1.9           # collision height standing
SLIDE_HEIGHT = 0.8           # collision height sliding
CHUNK_LENGTH = 30            # length of one recycled floor chunk
VIEW_CHUNKS = 7              # how many chunks exist at once
SPAWN_AHEAD = 150            # obstacles are generated this far ahead
STUD_SCORE = 10
DISTANCE_SCORE = 0.5         # points per world unit run

# ---------------------------------------------------------------------------
# Key bindings (Ursina key names)
# ---------------------------------------------------------------------------
KEYS_LEFT  = ('a', 'left arrow')
KEYS_RIGHT = ('d', 'right arrow')
KEYS_JUMP  = ('w', 'up arrow', 'space')
KEYS_SLIDE = ('s', 'down arrow', 'left control', 'left shift')
KEYS_PAUSE = ('escape', 'p')
KEYS_CONFIRM = ('enter', 'space')
KEYS_SKIP = ('enter', 'space', 'escape')
