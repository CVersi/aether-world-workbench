# The Fractured Aether — World Workbench v0.4

This is an independent Python/Pygame application for generating, inspecting and saving worlds. It does not change the original game. **v0.2 makes forests more prevalent, preserves terrain when placing settlements, improves roads and adds lightweight resource objects.**

**v0.3 adds experimental river routing and an ancient infrastructure route class.** Forests now carry only a small road-construction penalty, reflecting the setting's engineering capabilities.

**v0.4 improves river appearance and introduces isolated ruins with incomplete forest trails.**

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
│   ├── algorithms.py        # Flood fill and A* pathfinding
│   ├── hydrology.py         # Water routing and river centerlines
│   └── ruins.py             # Ruin placement and forgotten trails
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
3. **`models/world_model.py`:** `WorldModel` owns the world snapshot and currently coordinates noise, water classification, site placement, road routing, decorative objects and save/load. Once we improve the algorithms, we can split those stages further without touching the UI.
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

- Settlement regions are still rectangular *metadata*, but no longer clear the surrounding terrain. Individual building footprints are the next step.
- Roads use slope and deterministic coherent variation; they can still look angular and do not build bridges.
- Real rivers, drainage basins, cliffs, docks and boat routes are not modeled yet.
- Settlements are markers/reserved areas, not individual building layouts.
- Story-hub placement exists, but story progression accessibility is not validated.
- Generation is synchronous, so large maps may freeze the UI briefly.

## What's new in v0.2?

- **Forest threshold:** Lowering the threshold produces more forest. Default is now `-0.18`, which gives roughly 49% forest on seed 12345 (256×256).
- **Settlement placement:** The generator scores plausible land and stores settlement footprints without painting broad grass rectangles. A required story hub falls back to a real walkable tile.
- **Roads:** A* now prefers gentler slopes and follows broad deterministic road-preference bands. Road geometry is still tile-based and will need more work.
- **Decorative objects:** Deterministically positioned trees and boulders make the preview easier to read. They are recorded in `WorldModel.objects` and serialized in saved worlds.
- **Backward compatibility:** Old v0.1 world saves without an `objects` field still load (with an empty object list). Existing saved landscapes stay unchanged.

## What's new in v0.3?

- **`generation/hydrology.py`** adds `carve_rivers()`. A multi-source Dijkstra search begins from lakes and map boundaries, then traces sources back to outlets. The streams are deliberately shallow and may cross on foot; deeper, wider river rules will come later.
- **River sources slider** sets the requested maximum number of upland streams. Some maps may produce fewer qualifying sources.
- **Ancient roads** use a separate route type and purple color. The example generator attempts to connect the hub to a castle using costly crossings over water or mountains. These represent surviving infrastructure, not newly constructed roads.
- **Modern road cost:** Forests are almost as easy to traverse as grassland. Mountains and deep water remain significant barriers unless an ancient route exists.
- **World saves** now also contain `rivers` and typed routes. Older v0.1/v0.2 saves remain loadable.

### Hydrology limitations

The current routing is a useful prototype, **not physically correct watershed modeling**. River courses can still appear unnaturally straight, flow accumulation/tributaries are not simulated, and depression resolution may create a slightly uphill outlet. We'll need a more complete hydrology pass, including sediment/erosion rules, before calling the geography realistic.

## What's new in v0.4?

- **Rivers prefer lakes** instead of the world boundary whenever deep water exists. If no deep lake exists, map boundaries become fallback outlets.
- **Meandering centerlines:** a post-processing function displaces river waypoints sideways with broad bends while keeping their ends connected. It rejects unsafe bends through lakes and mountains. This makes the preview more organic; it is not a substitute for erosion simulation.
- **Ruins terrain:** the new `RUINS` tile (ID 9, tan) marks small irregular remnants. The workbench also marks ruin centers with amber Xs so designers can find them; this overlay need not exist on a player's map.
- **Overgrown trails:** `TRAIL` (ID 10, muted brown) leads generally toward a ruin but ends 7–14 tiles early. Players must search the surrounding wilderness.
- **Separation rules:** ruin centers must be at least 28 tiles from current settlement centers and 25 tiles from other ruins. The algorithm may generate fewer ruins than requested if suitable positions aren't available.
- **Ruin count:** configure `ruins_count` in `config.py` (default 4). A UI slider can be added when we reorganize the control panel.
- **Save compatibility:** new saves contain a `ruins` array and trail route records; v0.1–v0.3 saves still load.

### Important limitations for our eventual game

Ruin sites are currently small tile markers, not enterable structures, quest locations, dungeons, or loot containers. Their paths are generated independently and don't yet model ownership, construction history or decay. A future story-aware generator should distinguish mandatory ruins from optional points of interest and validate that each required one can eventually be reached.

### Important design distinction

The dark-green **forest terrain** indicates biome and general vegetation suitability; a **tree object** is a particular harvestable or collidable thing we can eventually put in the game. This separation lets us clear a tree for a road without changing the underlying forest biome.

Commit this as a **refactor-only milestone** before changing generation algorithms. The included `.gitignore` omits experimental saves; deliberately track any curated map you choose for the game.

