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

import copy
import json
import os
from pathlib import Path
import logging

logger = logging.getLogger("comfylab.engine.config")

# Remote access token for the current server process.
# Assigned by backend.main at startup (kept here so any module can read it
# without import-order tricks or monkey-patching).
SESSION_TOKEN: str = None

OFFICIAL_STORE_PUBKEY = "3a61083b4c2ebce87fa7c250b3e64712a457315920952ce920dd8bd88509a022"
DEFAULT_STORE_URL = "https://raw.githubusercontent.com/gateeit-ifgw/comfylab-store/main"

DEFAULT_CONFIG = {
    "custom_block_dirs": [],
    "last_workspace": "",
    "script_timeout": 30.0,
    "visa_backend": "",
    "enable_lua_scripting": False,
    "enable_julia_scripting": False,
    "enable_js_scripting": False,
    "enable_rust_scripting": False,
    "enable_r_scripting": False,
    "enable_octave_scripting": False,
    "enable_wolfram_scripting": False,
    "enable_sage_scripting": False,
    "enable_maxima_scripting": False,
    "enable_powershell_scripting": False,
    "enable_csharp_scripting": False,
    "external_python_path": "",
    "creator_identity": "",
    "trusted_origins": [OFFICIAL_STORE_PUBKEY],
    "store_url": DEFAULT_STORE_URL,
    "plot_downsample_threshold": 10000,
    "plot_downsample_target": 2000,
    "custom_users": {}
}

def get_comfylab_base_dir() -> Path:
    """Returns the base ~/.comfylab path and ensures it exists."""
    base_dir = (Path.home() / ".comfylab").resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

def get_global_user_blocks_dir() -> Path:
    """Returns the base user_blocks directory (~/.comfylab/user_blocks) and ensures it exists."""
    blocks_dir = get_comfylab_base_dir() / "user_blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)
    return blocks_dir


def get_global_user_clusters_dir() -> Path:
    """Returns the base user_clusters directory (~/.comfylab/user_clusters) and ensures it exists."""
    clusters_dir = get_comfylab_base_dir() / "user_clusters"
    clusters_dir.mkdir(parents=True, exist_ok=True)
    return clusters_dir


def get_store_dir() -> Path:
    """Returns the ComfyLAB Store local root directory (~/.comfylab/store) and ensures it exists."""
    store_dir = get_comfylab_base_dir() / "store"
    store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir


def get_store_installed_file() -> Path:
    """Returns path to ~/.comfylab/store/installed.json."""
    return get_store_dir() / "installed.json"


def get_store_subscriptions_file() -> Path:
    """Returns path to ~/.comfylab/store/subscriptions.json."""
    return get_store_dir() / "subscriptions.json"


def get_store_catalog_cache_file() -> Path:
    """Returns path to ~/.comfylab/store/catalog_cache.json."""
    return get_store_dir() / "catalog_cache.json"

def get_config_file_path() -> Path:
    """Returns the path to ~/.comfylab/config.json."""
    return get_comfylab_base_dir() / "config.json"

# In-memory cache of the parsed config, keyed by (path, mtime_ns, size).
# A stat() call is ~100x cheaper than open+read+json.loads, and the key means
# external edits to config.json are still picked up on the very next call.
_config_cache: dict = None
_config_cache_key: tuple = None


def get_config() -> dict:
    """Loads and returns the configuration dictionary, merging defaults for any missing keys."""
    global _config_cache, _config_cache_key
    path = get_config_file_path()
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        key = (str(path), None, None)

    if _config_cache is not None and key == _config_cache_key:
        # Return a deep copy so callers can never mutate the cached dict
        return copy.deepcopy(_config_cache)

    # Deep copy so callers can never mutate the shared DEFAULT_CONFIG nested values
    config = copy.deepcopy(DEFAULT_CONFIG)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    # Merge loaded keys on top of default ones
                    config.update(loaded)
        except Exception as e:
            logger.error(f"Error loading config file {path}: {e}. Using defaults.")
    else:
        # Save defaults if no file exists
        save_config(config)

    _config_cache = config
    _config_cache_key = key
    return copy.deepcopy(config)

def save_config(config: dict):
    """Saves the configuration dictionary to ~/.comfylab/config.json (atomically)."""
    global _config_cache, _config_cache_key
    path = get_config_file_path()
    tmp_path = path.with_suffix(".json.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        os.replace(tmp_path, path)
        _config_cache = copy.deepcopy(config)
        try:
            st = path.stat()
            _config_cache_key = (str(path), st.st_mtime_ns, st.st_size)
        except OSError:
            _config_cache_key = None
    except Exception as e:
        logger.error(f"Error saving config file {path}: {e}")
        _config_cache = None
        _config_cache_key = None
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass

def update_config(updates: dict) -> dict:
    """Updates specific keys in the configuration file and returns the updated config."""
    config = get_config()
    config.update(updates)
    save_config(config)
    return config
