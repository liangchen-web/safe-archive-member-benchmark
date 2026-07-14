import re
from pathlib import Path


_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_INVALID_CHARS = set('<>:"|?*')
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_member_path(root, member_name):
    """Return a safe absolute extraction path without touching the filesystem."""
    if not isinstance(member_name, str) or not member_name:
        return None

    normalized = member_name.replace("\\", "/")
    if normalized.startswith("/") or _DRIVE_PREFIX.match(normalized):
        return None

    parts = []
    for part in normalized.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            return None
        if part.endswith((" ", ".")):
            return None
        if any(
            char in _INVALID_CHARS or ord(char) < 32 or 127 <= ord(char) <= 159
            for char in part
        ):
            return None
        if part.split(".", 1)[0].rstrip(" ").upper() in _RESERVED:
            return None
        parts.append(part)

    if not parts:
        return None

    root_path = Path(root).resolve()
    candidate = root_path.joinpath(*parts)
    try:
        candidate.resolve(strict=False).relative_to(root_path)
    except (OSError, ValueError):
        return None
    return candidate
