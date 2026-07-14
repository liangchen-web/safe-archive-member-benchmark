import sys
from pathlib import Path


sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reference_solution import safe_member_path  # noqa: E402


Path(__file__).with_name("side-effect.txt").write_text("unexpected", encoding="utf-8")
