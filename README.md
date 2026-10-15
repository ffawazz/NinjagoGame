# NINJAGO RUNNER - PS1 "Pepsiman"-style 3D runner (Python + Ursina)

Behind-the-back auto-runner: dodge, jump and slide through **3 levels** as
Kai, Jay, Cole, Zane or Lloyd. Launches **full screen** on Windows.
Runs with **zero assets** (everything is built from low-poly cubes, with an
animated fallback cutscene) - add your own models, music and videos any time.

## 1. Install (Windows, Python 3.9 - 3.12 recommended)

```bat
python -m venv venv
venv\Scripts\activate
pip install ursina
python main.py
```
`ursina` pulls in `panda3d` (renderer, audio, video) automatically.
Use `python main.py --windowed` to debug in a window.
(Optional, to build an .exe: `pip install pyinstaller` then
`pyinstaller --onefile --noconsole --add-data "assets;assets" main.py`.)

## 2. Folder structure

```
NinjagoGame/
├── main.py          game loop, menu, HUD, states, player physics
├── config.py        ninjas, difficulties, levels, jokes, key bindings
├── entities.py      ninja model, obstacles, endless floor, scenery
├── ps1.py           PS1 shader (vertex snap, flat shading, 15-bit colour, fog)
├── cutscene.py      end-of-level video player + animated fallback
├── requirements.txt
└── assets/                     <- YOUR FILES GO HERE
    ├── music/
    │   ├── ninjago_theme.ogg   main looping soundtrack (.ogg/.mp3/.wav)
    │   ├── menu.ogg            (optional) menu track
    │   └── level1.ogg level2.ogg level3.ogg   (optional per-level tracks)
    ├── sfx/                    (all optional) jump, slide, stud, hit, win, lose (.wav/.ogg)
    ├── videos/
    │   └── level1.mp4  level2.mp4  level3.mp4   funny clips (played after each level)
    └── models/                 (optional) kai.glb  jay.glb  cole.glb  zane.glb  lloyd.glb
                                (.glb/.gltf/.obj/.bam; face +Z, feet at y=0, ~2 units tall)
```
Every asset is optional. Missing music = silence, missing video = built-in
animated gag with captions, missing model = built-in blocky minifig ninja.
If an `.mp4` will not play, re-encode it:
`ffmpeg -i in.mp4 -c:v libx264 -profile:v baseline -c:a aac out.mp4`
(the game then falls back to the animated gag instead of crashing).

## 3. Controls

| Action | Keys |
|---|---|
| Menu | Up/Down = ninja, Left/Right = difficulty, Enter = start, Esc = quit (mouse works too) |
| Lane left / right | A / D or arrow keys |
| Jump (over low brick walls) | W / Up / Space |
| Slide (under beams) | S / Down / Ctrl / Shift (press in mid-air to fast-fall into a slide) |
| Dodge by changing lane | skull blocks |
| Pause | Esc or P |
| Skip cutscene | Enter / Space / Esc |

## 4. How the requirements are met

* **Full screen / Windows**: `Ursina(fullscreen=True, borderless=True)` in `main.build_game`.
* **Pepsiman gameplay**: auto-run along +Z, 3 lanes, jump, slide, hit = stumble + lose a life.
* **Ninjago palette**: `config.py` (Kai red, Jay blue, Cole black, Zane white, Lloyd green, gold) drives UI, obstacles and levels.
* **Character select**: 5 ninjas on the main menu, each with a small perk.
* **Difficulty**: `config.DIFFICULTIES` - Easy/Normal/Hard scale both *running speed* and *obstacle density* (row gap + chance of double obstacles); speed also ramps up during a run and per level.
* **3 levels**: Dojo Training Grounds (green), Caverns of Fire & Stone (red/black), Ice Peaks of the Sky Temple (blue/white) - each with its own scenery, palette, fog, length and speed multiplier.
* **Audio**: `Sounds.play_music()` in `main.py` loads and **loops** the soundtrack (`set_loop(True)`).
* **Cutscenes**: `cutscene.py` plays `assets/videos/levelN.mp4` after each level (or an animated sequence), then loads the next level or the victory screen.

Tweak anything (speeds, lengths, colours, jokes) in `config.py`.
