"""Snowsight's default entrypoint; execute the dashboard on every rerun."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("app.py")), run_name="__main__")
