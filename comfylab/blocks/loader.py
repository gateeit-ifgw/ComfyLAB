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

import types
import os
import importlib
import importlib.util
import sys
from pathlib import Path
import logging

logger = logging.getLogger("comfylab.blocks.loader")

def load_module_from_filepath(filepath: str, module_name: str = None):
    """Dynamically imports a Python module from an absolute filesystem path."""
    path_obj = Path(filepath).resolve()
    pkg_dir = path_obj.parent
    pkg_dir_str = str(pkg_dir)

    if pkg_dir_str not in sys.path:
        sys.path.insert(0, pkg_dir_str)

    if not module_name:
        # Generate a unique package and module name based on directory and file stem
        # to allow relative imports (e.g. from .driver import ...) to resolve correctly
        pkg_name = f"comfylab_pkg_{pkg_dir.name}_{abs(hash(pkg_dir_str)) & 0xffffffff}"
        if pkg_name not in sys.modules:
            parent_mod = types.ModuleType(pkg_name)
            parent_mod.__path__ = [pkg_dir_str]
            parent_mod.__file__ = str(pkg_dir / "__init__.py")
            parent_mod.__package__ = pkg_name
            sys.modules[pkg_name] = parent_mod
        else:
            parent_mod = sys.modules[pkg_name]

        module_name = f"{pkg_name}.{path_obj.stem}"
        pkg_parent = pkg_name
    else:
        pkg_parent = module_name.rsplit(".", 1)[0] if "." in module_name else ""
        parent_mod = sys.modules.get(pkg_parent)

    # If module is already loaded in current lifecycle, reuse it
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, str(path_obj))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for module {module_name} at {filepath}")

    module = importlib.util.module_from_spec(spec)
    if pkg_parent:
        module.__package__ = pkg_parent
    sys.modules[module_name] = module
    if parent_mod is not None:
        setattr(parent_mod, path_obj.stem, module)

    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise e

def load_blocks_from_directory(directory_path: str):
    """Recursively scans a directory for .py files and loads them dynamically."""
    dir_path = Path(directory_path).resolve()
    if not dir_path.exists() or not dir_path.is_dir():
        return

    for root, dirs, files in os.walk(dir_path):
        if ".temp" in dirs:
            dirs.remove(".temp")
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                full_path = Path(root) / file
                try:
                    load_module_from_filepath(str(full_path))
                    logger.info(f"Dynamically loaded user block module: {full_path}")
                except Exception as e:
                    # Fault-tolerance: log error, but do not raise, so other blocks continue loading!
                    logger.error(f"Failed to dynamically load user block module at {full_path}: {e}")

def load_all_blocks():
    """
    Recursively scans and imports block files from multiple discovery paths:
    1. Core blocks (comfylab/blocks/)
    2. Global user blocks (~/.comfylab/user_blocks/)
    3. Custom directories from config settings
    4. Current workspace blocks (<workspace>/blocks/)
    """
    # 1. Load Core Blocks
    from comfylab.engine.config import get_config
    config = get_config()
    if getattr(sys, 'frozen', False):
        import comfylab.blocks
        package_path = os.path.join(os.path.dirname(sys.executable), "comfylab", "blocks")
        if hasattr(comfylab.blocks, '__path__'):
            comfylab.blocks.__path__ = list(comfylab.blocks.__path__)
            if package_path not in comfylab.blocks.__path__:
                comfylab.blocks.__path__.insert(0, package_path)
    else:
        package_path = os.path.dirname(os.path.abspath(__file__))
    for root, dirs, files in os.walk(package_path):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                # Determine absolute import path relative to the package root
                rel_path = os.path.relpath(os.path.join(root, file), package_path)
                # Normalize separators (e.g. backslashes on Windows) to forward slash
                normalized_rel_path = rel_path.replace(os.sep, "/")
                module_parts = normalized_rel_path[:-3].split("/")
                
                # Exclude base.py, loader.py, and cluster.py in the root directory
                if len(module_parts) == 1:
                    module_name_root = module_parts[0]
                    if module_name_root in ["base", "loader", "cluster"]:
                        continue
                    if module_name_root.startswith("script_"):
                        lang = module_name_root[7:]
                        config_key = f"enable_{lang}_scripting"
                        if config_key in config and not config.get(config_key, False):
                            continue
                
                module_name = "comfylab.blocks." + ".".join(module_parts)
                try:
                    if module_name in sys.modules:
                        importlib.reload(sys.modules[module_name])
                    else:
                        importlib.import_module(module_name)
                    logger.info(f"Auto-discovered and loaded block module: {module_name}")
                except Exception as e:
                    logger.error(f"Failed to import auto-discovered module {module_name}: {e}")
                    # Keep it raise for core blocks because they shouldn't fail
                    raise e

    # 2. Load Global User Blocks (~/.comfylab/user_blocks)
    try:
        from comfylab.engine.config import get_global_user_blocks_dir
        global_user_dir = get_global_user_blocks_dir()
        load_blocks_from_directory(str(global_user_dir))
    except Exception as e:
        logger.error(f"Error loading global user blocks: {e}")

    # 2.5. Load ComfyLAB Store installed packages (~/.comfylab/store/)
    try:
        from comfylab.engine.config import get_store_dir
        store_dir = get_store_dir()
        if store_dir.exists():
            store_instruments = store_dir / "instruments"
            if store_instruments.exists():
                if str(store_instruments) not in sys.path:
                    sys.path.insert(0, str(store_instruments))
                load_blocks_from_directory(str(store_instruments))
            store_blocks = store_dir / "blocks"
            if store_blocks.exists():
                if str(store_blocks) not in sys.path:
                    sys.path.insert(0, str(store_blocks))
                load_blocks_from_directory(str(store_blocks))
    except Exception as e:
        logger.error(f"Error loading store blocks: {e}")

    # 3. Load Custom Directories from Config
    try:
        from comfylab.engine.config import get_config
        config = get_config()
        custom_dirs = config.get("custom_block_dirs", [])
        for custom_dir in custom_dirs:
            load_blocks_from_directory(custom_dir)
    except Exception as e:
        logger.error(f"Error loading custom directory blocks: {e}")

    # 4. Load Active Workspace Blocks (<workspace>/blocks)
    try:
        from backend.workspace import get_workspace_path
        workspace_path = get_workspace_path()
        if workspace_path:
            workspace_blocks_dir = Path(workspace_path) / "blocks"
            load_blocks_from_directory(str(workspace_blocks_dir))
    except Exception as e:
        logger.error(f"Error loading workspace blocks: {e}")

    # (cluster loading is called separately after load_all_blocks returns)


def load_all_clusters():
    # 1. Load Built-in Core clusters (comfylab/clusters/)
    try:
        from comfylab.blocks.cluster import load_clusters_from_directory
        if getattr(sys, 'frozen', False):
            core_clusters_dir = Path(os.path.dirname(sys.executable)) / "comfylab" / "clusters"
        else:
            core_clusters_dir = Path(__file__).resolve().parent.parent / "clusters"
        if core_clusters_dir.exists():
            count = load_clusters_from_directory(str(core_clusters_dir))
            if count > 0:
                logger.info(f"Loaded {count} built-in clusters from {core_clusters_dir}.")
    except Exception as e:
        logger.error(f"Error loading built-in core clusters: {e}")

    # 2. Load Global User clusters (~/.comfylab/user_clusters)
    try:
        from comfylab.engine.config import get_global_user_clusters_dir
        from comfylab.blocks.cluster import load_clusters_from_directory
        global_cluster_dir = get_global_user_clusters_dir()
        count = load_clusters_from_directory(str(global_cluster_dir))
        if count > 0:
            logger.info(f"Loaded {count} clusters from global user clusters directory.")
    except Exception as e:
        logger.error(f"Error loading global user clusters: {e}")

    # 2.5. Load Store clusters (~/.comfylab/store/clusters)
    try:
        from comfylab.engine.config import get_store_dir
        from comfylab.blocks.cluster import load_clusters_from_directory
        store_clusters_dir = get_store_dir() / "clusters"
        if store_clusters_dir.exists():
            count = load_clusters_from_directory(str(store_clusters_dir))
            if count > 0:
                logger.info(f"Loaded {count} clusters from store clusters directory.")
    except Exception as e:
        logger.error(f"Error loading store clusters: {e}")

    # 3. Load Workspace clusters (<workspace>/clusters)
    try:
        from comfylab.blocks.cluster import load_clusters_from_directory
        from backend.workspace import get_workspace_path
        workspace_path = get_workspace_path()
        if workspace_path:
            workspace_clusters_dir = Path(workspace_path) / "clusters"
            workspace_clusters_dir.mkdir(parents=True, exist_ok=True)
            count = load_clusters_from_directory(str(workspace_clusters_dir))
            if count > 0:
                logger.info(f"Loaded {count} clusters from workspace clusters directory.")
    except Exception as e:
        logger.error(f"Error loading workspace clusters: {e}")


def reload_registry():
    """Clears and fully reloads all blocks and clusters in the global registry."""
    from comfylab.engine.registry import BLOCK_REGISTRY, load_all_clusters_deferred, invalidate_schema_cache
    from comfylab.engine.security import clear_signature_cache
    BLOCK_REGISTRY.clear()
    invalidate_schema_cache()
    clear_signature_cache()

    # Clear dynamically loaded modules so they reload and re-register cleanly
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("comfylab_pkg_") or mod_name.startswith("comfylab_dynamic_"):
            del sys.modules[mod_name]

    load_all_blocks()
    load_all_clusters_deferred(force=True)

