"""Backward-compatible entry point for World Workbench v0.1."""
from main import Workbench

if __name__ == "__main__":
    import runpy
    runpy.run_module("main", run_name="__main__")
