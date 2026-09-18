# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

import os
from pathlib import Path
from typing import Optional

DEFAULT_WORKSPACE_NAME = ".comfylab/workspace"

_workspace_path: Optional[Path] = None


def get_default_workspace_path() -> Path:
    return (Path.home() / DEFAULT_WORKSPACE_NAME).resolve()


def get_workspace_path() -> Path:
    global _workspace_path
    if _workspace_path is None:
        _workspace_path = get_default_workspace_path()
    _ensure_directory_exists(_workspace_path)
    os.environ["COMFYLAB_WORKSPACE"] = str(_workspace_path)
    os.environ["WORKSPACE"] = str(_workspace_path)
    return _workspace_path


def get_temp_dir() -> Path:
    tmp = get_workspace_path() / ".tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


def set_workspace_path(path: str | Path) -> Path:
    global _workspace_path
    resolved = Path(path).resolve()
    _ensure_directory_exists(resolved)
    _workspace_path = resolved
    os.environ["COMFYLAB_WORKSPACE"] = str(resolved)
    os.environ["WORKSPACE"] = str(resolved)
    return _workspace_path


def _ensure_directory_exists(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def resolve_within(base_dir: Path, filename: str) -> Path:
    """
    Safely resolves a user-supplied filename inside base_dir.
    Raises ValueError if the result would escape base_dir (path traversal).
    """
    resolved = (base_dir / filename).resolve()
    if not resolved.is_relative_to(base_dir.resolve()):
        raise ValueError(f"Path '{filename}' escapes the allowed directory.")
    return resolved
