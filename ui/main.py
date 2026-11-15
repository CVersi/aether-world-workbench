"""Launch the standalone World Workbench from the project root.

Usage:
    python main.py
    python main.py --load saved_worlds/my_map.world.json.gz
"""
import argparse
from pathlib import Path
from ui.workbench import Workbench

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--load", type=Path, help="Load an existing .world.json.gz save")
    args = parser.parse_args()
    Workbench(args.load).run()


