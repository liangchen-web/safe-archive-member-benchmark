import argparse
import importlib.util
import os
import random
import secrets
import string
import sys
import tempfile
from pathlib import Path


STATIC_CASES = {
    "docs/report.txt": ("docs", "report.txt"),
    "资料/报告.txt": ("资料", "报告.txt"),
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
    "folder/CON .txt": None,
    "folder/trailing. ": None,
    "folder/trailing.": None,
    "folder/trailing ": None,
    "folder/null\x00byte": None,
    "folder/delete\x7fchar": None,
    "folder/c1\x85char": None,
    "folder/bad<name.txt": None,
    "folder/bad>name.txt": None,
    'folder/bad"name.txt': None,
    "folder/bad|name.txt": None,
    "folder/bad?name.txt": None,
    "folder/bad*name.txt": None,
    None: None,
    123: None,
    b"docs/report.txt": None,
    Path("docs/report.txt"): None,
}

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_MUTATING_EVENTS = {
    "os.chmod",
    "os.link",
    "os.mkdir",
    "os.remove",
    "os.rename",
    "os.rmdir",
    "os.symlink",
    "os.truncate",
    "os.utime",
    "shutil.copyfile",
    "shutil.copymode",
    "shutil.copystat",
    "shutil.move",
    "subprocess.Popen",
    "os.system",
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


def dynamic_cases(seed):
    rng = random.Random(seed)
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


def install_side_effect_recorder():
    attempts = []

    def audit(event, args):
        is_write = False
        if event == "open":
            mode = args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 else 0
            is_write = (
                isinstance(mode, str) and any(char in mode for char in "wax+")
            ) or (isinstance(flags, int) and bool(flags & _WRITE_FLAGS))
        elif event in _MUTATING_EVENTS:
            is_write = True

        if is_write and len(attempts) < 20:
            target = args[0] if args else "unknown"
            attempts.append(f"{event}: {target!r}")

    sys.addaudithook(audit)
    return attempts


def verify(candidate_path, seed):
    failures = []

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir, "root")
        root.mkdir()
        outside = Path(temp_dir, "outside")
        outside.mkdir()
        link = root / "outside-link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            link = None

        before = tuple(root.rglob("*"))
        sys.dont_write_bytecode = True
        side_effects = install_side_effect_recorder()
        function = load_candidate(candidate_path)

        def check_case(member_name, expected_parts):
            try:
                result = function(root, member_name)
            except BaseException as exc:  # Invalid input must return None, not abort.
                failures.append(f"{member_name!r}: raised {type(exc).__name__}: {exc}")
                return

            if expected_parts is None:
                if result is not None:
                    failures.append(f"{member_name!r}: expected None, got {result!r}")
                return

            expected = root.resolve().joinpath(*expected_parts)
            if not isinstance(result, Path):
                failures.append(f"{member_name!r}: expected Path, got {type(result).__name__}")
            elif result != expected:
                failures.append(f"{member_name!r}: expected {expected!r}, got {result!r}")
            elif not result.is_absolute():
                failures.append(f"{member_name!r}: result is not absolute")

        for member_name, expected_parts in {
            **STATIC_CASES,
            **dynamic_cases(seed),
        }.items():
            check_case(member_name, expected_parts)

        if link is not None:
            check_case("outside-link/escape.txt", None)

        after = tuple(root.rglob("*"))
        if after != before:
            failures.append("candidate modified the filesystem")
        if side_effects:
            failures.append(
                "candidate attempted a filesystem/process side effect: "
                + "; ".join(side_effects[:3])
            )

    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    seed = args.seed if args.seed is not None else secrets.randbits(64)
    print(f"SEED: {seed}")

    try:
        failures = verify(args.candidate.resolve(), seed)
    except BaseException as exc:
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
