"""
tools/make_audio.py - synthesises the placeholder soundtrack + sound effects.

Run once (needs numpy):   python tools/make_audio.py
It writes ORIGINAL chiptune-style tracks (not the real Ninjago theme, which
is copyrighted) into assets/music and assets/sfx as 22 kHz mono .wav files.

To use your own music just drop  assets/music/ninjago_theme.mp3  (or .ogg):
the game looks for .ogg, .mp3, then .wav, so your file wins over these.
"""
import wave
from pathlib import Path

import numpy as np

SR = 22050
ROOT = Path(__file__).resolve().parent.parent / 'assets'


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def osc(kind, freq, t):
    ph = (freq * t) % 1.0
    if kind == 'square':
        return np.where(ph < 0.5, 1.0, -1.0)
    if kind == 'pulse':
        return np.where(ph < 0.25, 1.0, -1.0)
    if kind == 'saw':
        return 2 * ph - 1
    if kind == 'tri':
        return 4 * np.abs(ph - 0.5) - 1
    return np.sin(2 * np.pi * ph)


def add(buf, start, dur, freq, kind, vol, rel=0.08, slide=0.0):
    """Mix one note into buf (wraps around the end so the loop is seamless)."""
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    f = freq * (1 + slide * t)
    env = np.minimum(1, t / 0.005) * np.where(t < dur, 1.0, np.exp(-(t - dur) / (rel / 3)))
    env *= np.exp(-t * 1.5)                                    # gentle pluck decay
    sig = osc(kind, f, t) * env * vol
    idx = (start + np.arange(n)) % len(buf)
    np.add.at(buf, idx, sig)


def drum(buf, start, kind, vol=1.0):
    rng = np.random.default_rng(start % 9973)
    if kind == 'kick':
        n = int(0.18 * SR); t = np.arange(n) / SR
        sig = np.sin(2 * np.pi * (140 * np.exp(-t * 28) + 42) * t) * np.exp(-t * 16)
    elif kind == 'snare':
        n = int(0.16 * SR); t = np.arange(n) / SR
        sig = (rng.uniform(-1, 1, n) * 0.8 + np.sin(2 * np.pi * 190 * t) * 0.4) * np.exp(-t * 24)
    elif kind == 'taiko':
        n = int(0.45 * SR); t = np.arange(n) / SR
        sig = np.sin(2 * np.pi * (90 * np.exp(-t * 6) + 55) * t) * np.exp(-t * 7)
    else:  # hat
        n = int(0.04 * SR); t = np.arange(n) / SR
        sig = rng.uniform(-1, 1, n) * np.exp(-t * 90) * 0.5
    idx = (start + np.arange(n)) % len(buf)
    np.add.at(buf, idx, sig * vol)


def track(bpm, root, scale, prog, bars, lead_kind, seed, drive=1.0, arp=True, sparse=False):
    """Build a looping track.  prog = chord roots (semitones) per bar."""
    rng = np.random.default_rng(seed)
    step = 60.0 / bpm / 2                                   # one eighth note
    total = int(bars * 8 * step * SR)
    buf = np.zeros(total)
    motif = [rng.choice(len(scale), 8) for _ in range(4)]    # 4 different bar-long phrases
    for bar in range(bars):
        chord = prog[(bar // 2) % len(prog)]
        phrase = motif[(bar // 2) % 4] if bar % 8 < 6 else motif[0]
        for s in range(8):
            t0 = int((bar * 8 + s) * step * SR)
            # drums
            if s % 2 == 0 and not (sparse and bar % 4 == 0):
                drum(buf, t0, 'kick', 1.0 * drive)
            if s in (2, 6):
                drum(buf, t0, 'snare', 0.8 * drive)
            drum(buf, t0, 'hat', 0.35 if s % 2 else 0.5)
            if s == 0 and bar % 4 == 3:
                drum(buf, t0, 'taiko', 1.1)
            # bass (octave pumping on the chord root)
            bnote = root + chord - 12 + (12 if s % 4 == 3 else 0)
            add(buf, t0, step * 0.9, midi(bnote), 'saw' if drive > 1 else 'tri', 0.30)
            # arpeggio
            if arp:
                an = root + chord + 12 + [0, 7, 12, 7][s % 4] + (3 if scale[0] == 0 and s % 8 == 7 else 0)
                add(buf, t0, step * 0.5, midi(an), 'pulse', 0.10, rel=0.05)
            # lead melody (every bar after the first 2 of each 8)
            if bar % 8 >= 2 and (s % 2 == 0 or rng.random() < 0.4):
                deg = scale[phrase[s] % len(scale)]
                add(buf, t0, step * 1.4, midi(root + chord + 24 + deg), lead_kind, 0.16, rel=0.1)
    buf = np.tanh(buf * 1.4)                                # soft clip = a bit of grit
    return buf / np.max(np.abs(buf)) * 0.85


def save(buf, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(buf, -1, 1) * 32767).astype('<i2').tobytes())
    print(f'wrote {path.relative_to(ROOT.parent)}  {len(buf) / SR:.1f}s')


# ---------------------------------------------------------------- sfx
def sfx():
    def tone(freqs, dur, kind='square', vol=0.5, slide=0.0):
        buf = np.zeros(int(dur * SR) + 2000)
        for i, f in enumerate(freqs):
            add(buf, int(i * dur / len(freqs) * SR), dur / len(freqs), f, kind, vol, rel=0.05, slide=slide)
        return buf / max(1e-6, np.max(np.abs(buf))) * 0.8

    d = ROOT / 'sfx'
    save(tone([330, 440, 587, 740], 0.22, 'square', slide=0.0), d / 'jump.wav')
    rng = np.random.default_rng(1)
    n = int(0.35 * SR); t = np.arange(n) / SR
    save(rng.uniform(-1, 1, n) * np.exp(-t * 6) * np.sin(2 * np.pi * 900 * t * np.exp(-t * 3)) * 0.8, d / 'slide.wav')
    save(tone([988, 1319], 0.16, 'square', 0.5), d / 'stud.wav')
    n = int(0.45 * SR); t = np.arange(n) / SR
    hit = rng.uniform(-1, 1, n) * np.exp(-t * 14) + np.sin(2 * np.pi * (120 * np.exp(-t * 7) + 40) * t) * 1.5 * np.exp(-t * 8)
    save(hit / np.max(np.abs(hit)) * 0.9, d / 'hit.wav')
    save(tone([523, 659, 784, 1047, 784, 1047, 1319], 0.8, 'pulse', 0.5), d / 'win.wav')
    save(tone([392, 330, 262, 196], 0.9, 'saw', 0.4), d / 'lose.wav')
    # --- power sounds
    n = int(0.6 * SR); t = np.arange(n) / SR
    whoosh = rng.uniform(-1, 1, n) * np.sin(np.pi * t / 0.6) ** 2 * (0.6 + 0.4 * np.sin(2 * np.pi * 30 * t))
    whoosh = np.convolve(whoosh, np.ones(6) / 6, mode='same') + np.sin(2 * np.pi * (200 + 500 * t) * t) * 0.3
    save(whoosh / np.max(np.abs(whoosh)) * 0.85, d / 'fire.wav')
    n = int(0.4 * SR); t = np.arange(n) / SR
    zap = np.sign(np.sin(2 * np.pi * (1800 * np.exp(-t * 5)) * t + 8 * np.sin(2 * np.pi * 90 * t))) * np.exp(-t * 6) \
        + rng.uniform(-1, 1, n) * np.exp(-t * 18)
    save(zap / np.max(np.abs(zap)) * 0.85, d / 'zap.wav')
    n = int(0.8 * SR); t = np.arange(n) / SR
    quake = np.sin(2 * np.pi * (60 * np.exp(-t * 3) + 28) * t) * np.exp(-t * 3.5) \
        + rng.uniform(-1, 1, n) * np.exp(-t * 7) * 0.5
    save(quake / np.max(np.abs(quake)) * 0.95, d / 'quake.wav')
    freeze = tone([2093, 1760, 1568, 1319, 1175, 988], 0.7, 'tri', 0.5)
    save(freeze, d / 'freeze.wav')
    n = int(0.9 * SR); t = np.arange(n) / SR
    spin = np.sin(2 * np.pi * (300 + 400 * np.sin(np.pi * t / 0.9)) * t) * np.sin(np.pi * t / 0.9) \
        + rng.uniform(-1, 1, n) * 0.3 * np.sin(np.pi * t / 0.9)
    save(spin / np.max(np.abs(spin)) * 0.85, d / 'spin.wav')
    n = int(0.25 * SR); t = np.arange(n) / SR
    kill = (rng.uniform(-1, 1, n) * np.exp(-t * 25) + np.sin(2 * np.pi * (500 * np.exp(-t * 12) + 150) * t)) * np.exp(-t * 5)
    save(kill / np.max(np.abs(kill)) * 0.85, d / 'kill.wav')


if __name__ == '__main__':
    m = ROOT / 'music'
    minor = [0, 3, 5, 7, 10]                      # minor pentatonic
    #            bpm root(E) scale  chord roots     bars lead
    save(track(100, 40, minor, [0, -4, -2, -5], 12, 'tri', 1, 0.8, True, True), m / 'menu.wav')
    save(track(140, 40, minor, [0, -4, -2, -5], 16, 'square', 2), m / 'level1.wav')
    save(track(150, 38, [0, 3, 5, 6, 7, 10], [0, -2, -4, -5], 16, 'saw', 3, 1.3), m / 'level2.wav')
    save(track(162, 45, [0, 2, 4, 7, 9], [0, -3, -5, -7], 16, 'pulse', 4, 1.0), m / 'level3.wav')
    # main fallback theme = level 1 track
    save(track(140, 40, minor, [0, -4, -2, -5], 16, 'square', 2), m / 'ninjago_theme.wav')
    sfx()
