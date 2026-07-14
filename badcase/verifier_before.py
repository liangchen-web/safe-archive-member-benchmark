import argparse
import importlib.util
import random
import string
import sys
import tempfile
from pathlib import Path


STATIC_CASES = {
    "docs/report.txt": ("docs", "report.txt"),
    "./docs//report.txt": ("docs", "report.txt"),
    r"images\2026\photo.png": ("images", "2026", "photo.png"),
    ".hidden/config": (".hidden", "config"),
    "folder/...x/file": ("folder", "...x", "file"),
    "": None,
    ".": None,
    "./": None,
    "../secret.txt": None,
    "safe/../secret.txt": None,
    r"safe\..\secret.txt": None,
    "/etc/passwd": None,
    r"\server\share\file.txt": None,
    "//server/share/file.txt": None,
    r"C:\Windows\win.ini": None,
    "C:relative.txt": None,
    "file.txt:stream": None,
    "folder/NUL.txt": None,
    "folder/con": None,
    "folder/COM1.json": None,
    "folder/LPT9": None,
    "folder/trailing. ": None,
    "folder/trailing.": None,
    "folder/trailing ": None,
    "folder/null\x00byte": None,
}


def load_candidate(path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, "safe_member_path", None)
    if not callable(function):
        raise RuntimeError("safe_member_path is missing or not callable")
    return function


def dynamic_cases():
    rng = random.Random(20260714)
    alphabet = string.ascii_letters + string.digits + "_-"
    cases = {}

    for _ in range(24):
        parts = [
            "".join(rng.choice(alphabet) for _ in range(rng.randint(3, 12)))
            for _ in range(rng.randint(1, 4))
        ]
        safe_name = "/".join(parts) + ".txt"
        cases[safe_name] = (*parts[:-1], parts[-1] + ".txt")

        index = rng.randrange(len(parts) + 1)
        unsafe_parts = parts.copy()
        unsafe_parts.insert(index, "..")
        separator = rng.choice(("/", "\\"))
        cases[separator.join(unsafe_parts) + separator + "escape.txt"] = None

    return cases


def verify(candidate_path):
    function = load_candidate(candidate_path)
    failures = []

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir, "root")
        root.mkdir()
        before = tuple(root.rglob("*"))

        for member_name, expected_parts in {**STATIC_CASES, **dynamic_cases()}.items():
            try:
                result = function(root, member_name)
            except Exception as exc:  # The contract requires None for invalid input.
                failures.append(f"{member_name!r}: raised {type(exc).__name__}: {exc}")
                continue

            if expected_parts is None:
                if result is not None:
                    failures.append(f"{member_name!r}: expected None, got {result!r}")
                continue

            expected = root.resolve().joinpath(*expected_parts)
            if not isinstance(result, Path):
                failures.append(f"{member_name!r}: expected Path, got {type(result).__name__}")
            elif result != expected:
                failures.append(f"{member_name!r}: expected {expected!r}, got {result!r}")
            elif not result.is_absolute():
                failures.append(f"{member_name!r}: result is not absolute")

        after = tuple(root.rglob("*"))
        if after != before:
            failures.append("candidate modified the filesystem")

    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()

    try:
        failures = verify(args.candidate.resolve())
    except Exception as exc:
        print(f"VERIFIER ERROR: {exc}")
        return 2

    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for failure in failures[:20]:
            print(f"- {failure}")
        if len(failures) > 20:
            print(f"- ... {len(failures) - 20} more")
        return 1

    print("PASS: all static, dynamic, and side-effect checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
