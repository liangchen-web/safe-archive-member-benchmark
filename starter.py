from pathlib import Path


def safe_member_path(root, member_name):
    """Return a path below root, or None when resolution escapes root."""
    root_path = Path(root).resolve()
    candidate = (root_path / member_name).resolve()

    try:
        candidate.relative_to(root_path)
    except ValueError:
        return None

    return candidate
