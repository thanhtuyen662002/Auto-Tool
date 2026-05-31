from __future__ import annotations

from pathlib import Path

from app.utils.app_paths import backend_dir, executable_dir, project_root, unique_paths


def default_base_dirs(primary_base: str | Path | None = None) -> list[Path]:
    bases: list[Path] = []
    if primary_base is not None:
        bases.append(Path(primary_base))
    bases.extend(
        [
            Path.cwd(),
            project_root(),
            project_root() / "examples",
            backend_dir(),
            executable_dir(),
        ]
    )
    return unique_paths(bases)


def resolve_path(path: str, base_dir: str | Path, must_exist: bool = False) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    candidates = [(base / candidate).resolve() for base in default_base_dirs(base_dir)]
    if must_exist:
        for item in candidates:
            if item.exists():
                return item
        return candidates[0]

    for item in candidates:
        if item.exists() or item.parent.exists():
            return item
    return candidates[0]
