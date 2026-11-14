# The Fractured Aether — World Workbench v0.1 (modular)

This is an independent Python/Pygame application for generating, inspecting and saving worlds. It does not change the original game. **The existing generation algorithms are preserved** in this refactor, including the known rectangular town footprints and straight roads.

## Start

From this folder:

```bash
python -m pip install -r requirements.txt
python main.py
```

If Pygame and OpenSimplex are already installed, you can skip installation. The older command `python world_workbench.py` also works.

## Project structure

```text
world_workbench/
├── main.py                  # Entry point, optional --load argument
├── world_workbench.py       # Backward-compatible launcher
├── config.py                # Parameters, terrain IDs and blueprints
├── requirements.txt
├── README.md
├── generation/
│   ├── __init__.py
│   └── algorithms.py        # Flood fill and A* pathfinding
├── models/
│   ├── __init__.py
│   └── world_model.py       # World generation, data, save/load
├── ui/
│   ├── __init__.py
│   ├── slider.py            # Slider input and drawing
│   └── workbench.py         # Pygame event loop and preview
├── tests/
│   ├── __init__.py
│   └── test_world.py        # Regression tests
└── saved_worlds/            # Created as needed; your saved maps
```

## What the files do

1. **`config.py`:** `Parameters` is a dataclass, a collection of named values; `asdict()` turns it into JSON-compatible save data. Terrain IDs are integers, so keep them consistent if building runtime support.
2. **`generation/algorithms.py`:** `water_components()` uses breadth-first search (flood fill) to find connected bodies of water. `find_route()` uses A* search and a priority queue to find cheaper paths that avoid certain terrain.
3. **`models/world_model.py`:** `WorldModel` owns the world snapshot and currently coordinates noise, water classification, site placement, road routing and save/load. Once we improve the algorithms, we can split those stages further without touching the UI.
4. **`ui/slider.py`:** converts mouse positions into numeric parameters; does not generate terrain itself.
5. **`ui/workbench.py`:** receives input, calls the model and renders a preview. It doesn't implement noise or pathfinding.
6. **`main.py`:** the simple launcher. The dependency direction is UI → model → algorithms, making algorithm testing and an eventual C# port easier.

### Tile coordinate math

The terrain is one flat array. Tile `(x, y)` is stored at index `y * n + x`, where `n` is the world width. To reverse: `x = index % n` and `y = index // n`. This is why much of the generator uses expressions like `yy*n+xx`.

### Why save full worlds instead of seeds alone?

Changing the generator could cause an old seed to produce different geography. Our `.world.json.gz` files preserve the **actual generated terrain and settlement/road data** along with the seed and parameters. That supports future curated starting-world presets.

## Controls

| Control | Effect |
|---|---|
| Drag sliders + Generate | Update current seed with new settings |
| New seed | Randomize seed and generate |
| Save map / S | Save full world snapshot |
| Load latest / L | Load latest saved world |
| `python main.py --load path/to/map.world.json.gz` | Load chosen save |
| 1–4 | Switch terrain/elevation/moisture/settlement layers |
| Mouse wheel | Zoom preview |
| Right-drag | Pan preview |
| F | Fit entire map |
| Esc | Quit |

## Tests

From inside the project folder:

```bash
python -m unittest discover -s tests -v
```

## Known v0.1 shortcomings

- Settlements still replace rectangular patches with grass.
- Roads can be straight/right-angled and do not build bridges.
- Real rivers, drainage basins, cliffs, docks and boat routes are not modeled yet.
- Settlements are markers/reserved areas, not individual building layouts.
- Story-hub placement exists, but story progression accessibility is not validated.
- Generation is synchronous, so large maps may freeze the UI briefly.

Commit this as a **refactor-only milestone** before changing generation algorithms. The included `.gitignore` omits experimental saves; deliberately track any curated map you choose for the game.

