"""
cutscene.py - the funny clip that plays at the end of every level.

Strategy
--------
1. Look for  assets/videos/<level['video']>   (default level1.mp4 ... level3.mp4)
   and play it full screen with Panda3D's MovieTexture (video + audio).
2. If the file is missing - or your machine's Panda3D build cannot decode it -
   fall back to a built-in ANIMATED SEQUENCE: bouncing ninja avatars, a
   cake-stealing gag and typewriter captions (see LEVELS[...]['gags']).

Either way the player can press ENTER / SPACE / ESC to skip, and
`on_done` is called when the cutscene ends (the game then loads the next
level or the victory screen).

Tip: if an .mp4 does not play, re-encode it to H.264 + AAC:
     ffmpeg -i in.mp4 -c:v libx264 -profile:v baseline -c:a aac out.mp4
"""
import time
from pathlib import Path

from ursina import Entity, Text, camera, color, destroy, window, sin, application

import config as C

VIDEO_DIR = Path(__file__).parent / 'assets' / 'videos'


class Cutscene(Entity):
    BEAT = 3.4          # seconds per gag caption in the animated fallback

    def __init__(self):
        super().__init__(parent=camera.ui, enabled=False)
        self.playing = False
        self.on_done = None
        self.video_tex = None
        self.sound = None

    # ------------------------------------------------------------------
    def start(self, level_index, on_done, music=None):
        """Begin the cutscene for `level_index` (0-2)."""
        self.stop_media()
        self.on_done = on_done
        self.level = C.LEVELS[level_index]
        self.level_index = level_index
        self.t = 0.0
        self.enabled = True
        self.playing = True
        if music:
            music.stop()                                   # silence the soundtrack for the clip
        path = VIDEO_DIR / self.level['video']
        self.mode = 'video' if (path.exists() and self._start_video(path)) else None
        if self.mode is None:
            self._start_animation()
            self.mode = 'anim'

    # ------------------------------------------------------------------
    # 1) real video
    # ------------------------------------------------------------------
    def _start_video(self, path):
        try:
            from panda3d.core import MovieTexture, Filename, TextureStage
            tex = MovieTexture('cutscene')
            fn = Filename.from_os_specific(str(path))
            if not tex.read(fn) or tex.get_video_length() <= 0:
                print(f'[cutscene] could not decode {path.name}, using built-in gag instead')
                return False
            w, h = tex.get_video_width(), tex.get_video_height()
            s = min(1.0, window.aspect_ratio / (w / h))     # letter-box into the screen
            self.bg = Entity(parent=self, model='quad', color=color.black, scale=(4, 2), z=1)
            self.screen = Entity(parent=self, model='quad', z=0.5,
                                 scale=((w / h) * s, s))
            self.screen.set_shader_off()                    # fixed pipeline handles the tex transform
            self.screen.model.set_texture(tex, 1)
            self.screen.model.set_tex_scale(TextureStage.get_default(), tex.get_tex_scale())
            self.hint = Text('ENTER = skip', parent=self, position=(0.62, -0.46), scale=0.9, color=color.white66)
            self.video_len = tex.get_video_length()
            self.video_tex = tex
            self.sound = application.base.loader.load_sfx(fn)
            if self.sound and self.sound.length() > 0:
                tex.synchronize_to(self.sound)
                self.sound.play()
            else:
                tex.play()
            return True
        except Exception as e:                              # missing codec etc.
            print('[cutscene] video playback failed:', e)
            self._clear_children()
            return False

    # ------------------------------------------------------------------
    # 2) built-in animated gag
    # ------------------------------------------------------------------
    def _start_animation(self):
        lv = self.level
        self.bg = Entity(parent=self, model='quad', color=lv['sky'], scale=(4, 2), z=1)
        # confetti-ish stripes in the level colours
        self.stripes = []
        for i in range(8):
            s = Entity(parent=self, model='quad', color=lv['obstacle'][i % 2], z=0.9,
                       scale=(0.5, 3), x=-1.1 + i * 0.32, rotation_z=20, alpha=0.35)
            self.stripes.append(s)
        self.banner = Text(f'{lv["name"]} COMPLETE!', parent=self, origin=(0, 0), y=0.36,
                           scale=3, color=C.GOLD)
        self.caption = Text('', parent=self, origin=(0, 0), y=-0.3, scale=1.4, color=color.white)
        self.hint = Text('ENTER = skip', parent=self, position=(0.62, -0.46), scale=0.9, color=color.white66)
        # five bouncing ninja avatars (one per ninja) + a stolen cake
        self.avatars = []
        for i, n in enumerate(C.NINJAS):
            a = Entity(parent=self, x=-0.6 + i * 0.3, y=-0.02, z=0.3)
            Entity(parent=a, model='quad', color=n['suit'], scale=(0.14, 0.17), y=-0.03)        # body
            Entity(parent=a, model='quad', color=n['accent'], scale=(0.15, 0.03), y=-0.06)      # belt
            Entity(parent=a, model='quad', color=n['suit'], scale=(0.13, 0.12), y=0.1)          # hood
            Entity(parent=a, model='quad', color=C.LEGO_YELLOW, scale=(0.08, 0.04), y=0.1, z=-0.01)
            a.base_x, a.phase = a.x, i * 0.9
            self.avatars.append(a)
        self.cake = Entity(parent=self, z=0.2, position=(0.95, -0.02))
        Entity(parent=self.cake, model='quad', color=color.rgb32(240, 140, 190), scale=(0.12, 0.07))
        Entity(parent=self.cake, model='quad', color=color.white, scale=(0.12, 0.02), y=0.04)
        Entity(parent=self.cake, model='quad', color=C.KAI_RED, scale=(0.012, 0.04), y=0.08)
        self.video_len = len(lv['gags']) * self.BEAT

    # ------------------------------------------------------------------
    def update(self):
        if not self.playing:
            return
        self.t += time.dt
        if self.mode == 'video':
            if self.t >= self.video_len + 0.25:
                self.finish()
            return
        # ---- animated fallback ----
        t = self.t
        beat = min(int(t // self.BEAT), len(self.level['gags']) - 1)
        text = self.level['gags'][beat]
        shown = int((t - beat * self.BEAT) * 28)             # typewriter effect
        self.caption.text = text[:shown]
        self.banner.scale = 3 + sin(t * 6) * 0.15
        for s in self.stripes:
            s.x = (s.x + 0.002) if s.x < 1.2 else -1.2
        for a in self.avatars:
            if beat == 0:                                    # victory dance
                a.y = -0.02 + abs(sin(t * 7 + a.phase)) * 0.08
                a.rotation_z = sin(t * 7 + a.phase) * 12
            elif beat == 1:                                  # everybody faceplants in turn
                fall = max(0, sin(t * 3 + a.phase))
                a.rotation_z = fall * 90
                a.y = -0.02 - fall * 0.05
            else:                                            # chase the stolen cake
                a.x = a.base_x + (t - 2 * self.BEAT) * 0.25 * (1 + a.phase * 0.2)
                a.y = -0.02 + abs(sin(t * 12 + a.phase)) * 0.05
                a.rotation_z = 0
        self.cake.x = 0.95 - max(0, t - 2 * self.BEAT) * 0.35
        if t >= self.video_len:
            self.finish()

    def input(self, key):
        if self.playing and key in C.KEYS_SKIP:
            self.finish()

    # ------------------------------------------------------------------
    def finish(self):
        if not self.playing:
            return
        self.playing = False
        self.stop_media()
        self.enabled = False
        cb, self.on_done = self.on_done, None
        if cb:
            cb()

    def stop_media(self):
        if self.sound:
            self.sound.stop()
            self.sound = None
        if self.video_tex:
            try:
                self.video_tex.stop()
            except Exception:
                pass
            self.video_tex = None
        self._clear_children()

    def _clear_children(self):
        for c in list(self.children):
            destroy(c)
