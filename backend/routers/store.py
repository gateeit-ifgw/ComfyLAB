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
import json
import time
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from comfylab.engine.config import (
    get_config,
    get_store_dir,
    get_store_installed_file,
    get_store_subscriptions_file,
    get_store_catalog_cache_file,
    DEFAULT_STORE_URL,
)
from comfylab.engine.security import sign_python_file, evaluate_trust, verify_python_file
from comfylab.blocks.loader import reload_registry

logger = logging.getLogger("backend.routers.store")

router = APIRouter(prefix="/store")

CATALOG_CACHE_TTL = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SubscribePayload(BaseModel):
    type: str  # "category", "vendor", or "package"
    target: str  # e.g. "instruments", "agilent", or "instruments/agilent/hp34401a"
    name: Optional[str] = None
    subscribed: bool = True


class InstallPayload(BaseModel):
    package_ids: List[str]


class UninstallPayload(BaseModel):
    package_id: str


class UpdatePayload(BaseModel):
    package_ids: Optional[List[str]] = None  # None = update all available


class StoreSettingsPayload(BaseModel):
    auto_sync_on_startup: Optional[bool] = None
    auto_install_new_in_subscriptions: Optional[bool] = None
    store_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Storage Helpers
# ---------------------------------------------------------------------------

def load_installed() -> Dict[str, Any]:
    f = get_store_installed_file()
    if f.exists():
        try:
            with open(f, "r", encoding="utf-8") as fp:
                return json.load(fp)
        except Exception as e:
            logger.error(f"Failed to read store installed.json: {e}")
    return {}


def save_installed(data: Dict[str, Any]) -> None:
    f = get_store_installed_file()
    tmp = f.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)
    os.replace(tmp, f)


def load_subscriptions() -> Dict[str, Any]:
    f = get_store_subscriptions_file()
    default_sub = {
        "auto_sync_on_startup": True,
        "auto_install_new_in_subscriptions": True,
        "subscriptions": []
    }
    if f.exists():
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                default_sub.update(data)
                return default_sub
        except Exception as e:
            logger.error(f"Failed to read store subscriptions.json: {e}")
    return default_sub


def save_subscriptions(data: Dict[str, Any]) -> None:
    f = get_store_subscriptions_file()
    tmp = f.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)
    os.replace(tmp, f)


def parse_version_tuple(v_str: str):
    parts = []
    clean = v_str.strip().lstrip("vV")
    for p in clean.split("."):
        num_part = ""
        for ch in p:
            if ch.isdigit():
                num_part += ch
            else:
                break
        parts.append(int(num_part) if num_part else 0)
    return tuple(parts)


def is_newer_version(latest_str: str, current_str: str) -> bool:
    try:
        return parse_version_tuple(latest_str) > parse_version_tuple(current_str)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Catalog Fetching & Caching
# ---------------------------------------------------------------------------

async def fetch_store_catalog(force: bool = False) -> Dict[str, Any]:
    cache_file = get_store_catalog_cache_file()
    now = time.time()

    if not force and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as fp:
                cached = json.load(fp)
            if now - cached.get("_cached_at", 0) < CATALOG_CACHE_TTL:
                return cached.get("data", {})
        except Exception as e:
            logger.debug(f"Catalog cache read failed: {e}")

    config = get_config()
    store_url = config.get("store_url") or DEFAULT_STORE_URL
    catalog_url = f"{store_url.rstrip('/')}/catalog.json"

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(catalog_url)
            if resp.status_code == 200:
                data = resp.json()
                # Save to cache
                try:
                    cache_payload = {"_cached_at": now, "data": data}
                    with open(cache_file, "w", encoding="utf-8") as fp:
                        json.dump(cache_payload, fp, indent=2)
                except Exception as e:
                    logger.debug(f"Failed to save catalog cache: {e}")
                return data
            else:
                logger.warning(f"Store catalog returned HTTP {resp.status_code} from {catalog_url}")
    except Exception as e:
        logger.warning(f"Failed to fetch store catalog from {catalog_url}: {e}")

    # Fallback to expired cache if network is down/offline
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as fp:
                cached = json.load(fp)
            return cached.get("data", {})
        except Exception:
            pass

    return {
        "schema_version": "1.0",
        "categories": ["instruments", "blocks", "clusters", "blueprints"],
        "packages": []
    }


def matches_subscription(pkg: Dict[str, Any], sub: Dict[str, Any]) -> bool:
    sub_type = sub.get("type", "").lower()
    sub_target = sub.get("target", "").lower()

    if sub_type == "all" or sub_target == "*":
        return True

    if sub_type == "category":
        pkg_type = pkg.get("type", "").lower()
        return pkg_type == sub_target or pkg.get("path", "").lower().startswith(sub_target)

    if sub_type == "vendor":
        pkg_vendor = pkg.get("vendor", "").lower()
        return pkg_vendor == sub_target

    if sub_type == "package":
        return pkg.get("id", "").lower() == sub_target

    return False


# ---------------------------------------------------------------------------
# Package Installation & File Writing
# ---------------------------------------------------------------------------

async def download_and_install_package(pkg: Dict[str, Any]) -> Dict[str, Any]:
    config = get_config()
    store_url = config.get("store_url") or DEFAULT_STORE_URL
    store_dir = get_store_dir()

    pkg_id = pkg.get("id")
    rel_path = pkg.get("path") or pkg_id
    files = pkg.get("files") or ["manifest.json"]
    hashes = pkg.get("hashes") or {}

    pkg_dir = store_dir / rel_path
    pkg_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files = []

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for filename in files:
            file_url = f"{store_url.rstrip('/')}/{rel_path}/{filename}"
            resp = await client.get(file_url)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to download {filename} from {file_url} (HTTP {resp.status_code})")

            content = resp.content

            # Verify hash if present
            expected_hash = hashes.get(filename)
            if expected_hash:
                actual_hash = hashlib.sha256(content).hexdigest()
                if actual_hash.lower() != expected_hash.lower():
                    raise RuntimeError(f"Hash mismatch for {filename}: expected {expected_hash}, got {actual_hash}")

            target_file = pkg_dir / filename
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(content)

            # Authorize and sign any downloaded python file with the local host key
            if filename.endswith(".py"):
                sign_python_file(target_file)

            downloaded_files.append(filename)

    # Update installed.json
    installed = load_installed()
    installed[pkg_id] = {
        "id": pkg_id,
        "name": pkg.get("name", pkg_id),
        "version": pkg.get("version", "1.0.0"),
        "vendor": pkg.get("vendor"),
        "category": pkg.get("category"),
        "type": pkg.get("type", "instrument"),
        "path": rel_path,
        "files": downloaded_files,
        "installed_at": time.time()
    }
    save_installed(installed)

    return installed[pkg_id]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/catalog")
async def get_catalog(force: bool = Query(False)):
    """Fetches the Store catalog (cached by default, or forced refresh)."""
    catalog = await fetch_store_catalog(force=force)
    return {
        "catalog": catalog,
        "store_url": get_config().get("store_url") or DEFAULT_STORE_URL
    }


@router.get("/status")
async def get_status(force_catalog: bool = Query(False)):
    """Returns installed packages, active subscriptions, and pending update counts."""
    catalog_data = await fetch_store_catalog(force=force_catalog)
    packages = catalog_data.get("packages", [])
    pkg_by_id = {p["id"]: p for p in packages if "id" in p}

    installed = load_installed()
    subscriptions_obj = load_subscriptions()
    active_subs = subscriptions_obj.get("subscriptions", [])

    available_updates = []
    for pkg_id, inst in installed.items():
        if pkg_id in pkg_by_id:
            cat_ver = pkg_by_id[pkg_id].get("version", "1.0.0")
            inst_ver = inst.get("version", "1.0.0")
            if is_newer_version(cat_ver, inst_ver):
                available_updates.append({
                    "id": pkg_id,
                    "name": inst.get("name", pkg_id),
                    "current_version": inst_ver,
                    "latest_version": cat_ver,
                    "vendor": inst.get("vendor"),
                })

    new_in_subscriptions = []
    for pkg in packages:
        pkg_id = pkg.get("id")
        if not pkg_id or pkg_id in installed:
            continue
        for sub in active_subs:
            if matches_subscription(pkg, sub):
                new_in_subscriptions.append({
                    "id": pkg_id,
                    "name": pkg.get("name", pkg_id),
                    "version": pkg.get("version", "1.0.0"),
                    "vendor": pkg.get("vendor"),
                    "type": pkg.get("type", "instrument"),
                    "matched_subscription": sub.get("name") or sub.get("target")
                })
                break

    return {
        "installed": installed,
        "subscriptions": subscriptions_obj,
        "updates_count": len(available_updates),
        "available_updates": available_updates,
        "new_in_subscriptions_count": len(new_in_subscriptions),
        "new_in_subscriptions": new_in_subscriptions,
    }


@router.get("/badge")
async def get_badge():
    """Fast, lightweight endpoint for TopBar badge updates."""
    status = await get_status(force_catalog=False)
    total_count = status["updates_count"] + status["new_in_subscriptions_count"]
    return {
        "total_badge_count": total_count,
        "updates_count": status["updates_count"],
        "new_in_subscriptions_count": status["new_in_subscriptions_count"],
        "has_badge": total_count > 0
    }


@router.post("/subscribe")
async def toggle_subscription(payload: SubscribePayload):
    """Subscribes or unsubscribes from a category, vendor, or specific package."""
    subs_obj = load_subscriptions()
    subs = subs_obj.get("subscriptions", [])

    existing_idx = None
    for idx, s in enumerate(subs):
        if s.get("type") == payload.type and s.get("target") == payload.target:
            existing_idx = idx
            break

    if payload.subscribed:
        if existing_idx is None:
            subs.append({
                "type": payload.type,
                "target": payload.target,
                "name": payload.name or payload.target,
                "created_at": time.time()
            })
    else:
        if existing_idx is not None:
            subs.pop(existing_idx)

    subs_obj["subscriptions"] = subs
    save_subscriptions(subs_obj)

    return {"status": "success", "subscriptions": subs_obj}


@router.post("/settings")
async def update_settings(payload: StoreSettingsPayload):
    """Updates Store configuration and subscription preferences."""
    subs_obj = load_subscriptions()
    if payload.auto_sync_on_startup is not None:
        subs_obj["auto_sync_on_startup"] = payload.auto_sync_on_startup
    if payload.auto_install_new_in_subscriptions is not None:
        subs_obj["auto_install_new_in_subscriptions"] = payload.auto_install_new_in_subscriptions
    save_subscriptions(subs_obj)

    if payload.store_url is not None:
        from comfylab.engine.config import update_config
        update_config({"store_url": payload.store_url})

    return {"status": "success", "settings": subs_obj}


@router.post("/install")
async def install_packages(payload: InstallPayload):
    """Downloads and installs specified package IDs from the Store."""
    catalog_data = await fetch_store_catalog(force=False)
    packages = catalog_data.get("packages", [])
    pkg_by_id = {p["id"]: p for p in packages if "id" in p}

    installed_results = []
    errors = []

    for pkg_id in payload.package_ids:
        if pkg_id not in pkg_by_id:
            errors.append(f"Package '{pkg_id}' not found in Store catalog.")
            continue
        try:
            res = await download_and_install_package(pkg_by_id[pkg_id])
            installed_results.append(res)
        except Exception as e:
            logger.error(f"Error installing package {pkg_id}: {e}")
            errors.append(f"Failed to install {pkg_id}: {str(e)}")

    if installed_results:
        await run_in_threadpool(reload_registry)

    return {
        "status": "partial_success" if errors and installed_results else ("error" if errors else "success"),
        "installed": installed_results,
        "errors": errors
    }


@router.post("/uninstall")
async def uninstall_package(payload: UninstallPayload):
    """Uninstalls a package and deletes its local folder."""
    pkg_id = payload.package_id
    installed = load_installed()

    if pkg_id not in installed:
        raise HTTPException(status_code=404, detail=f"Package '{pkg_id}' is not installed.")

    pkg_info = installed[pkg_id]
    rel_path = pkg_info.get("path") or pkg_id

    store_dir = get_store_dir()
    pkg_dir = (store_dir / rel_path).resolve()

    # Safety check: must be inside store directory
    if not pkg_dir.is_relative_to(store_dir):
        raise HTTPException(status_code=400, detail="Path traversal attempt detected.")

    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)

    del installed[pkg_id]
    save_installed(installed)

    await run_in_threadpool(reload_registry)

    return {"status": "success", "uninstalled": pkg_id}


@router.post("/update")
async def update_packages(payload: UpdatePayload):
    """Updates installed packages to their latest catalog versions."""
    status = await get_status(force_catalog=True)
    available_updates = status.get("available_updates", [])
    target_ids = set(payload.package_ids) if payload.package_ids else {u["id"] for u in available_updates}

    install_payload = InstallPayload(package_ids=list(target_ids))
    return await install_packages(install_payload)


@router.post("/sync")
async def sync_subscriptions():
    """
    Syncs subscriptions:
    - Checks catalog
    - Updates any outdated subscribed packages
    - If auto_install_new_in_subscriptions is on, installs newly added subscribed packages
    """
    status = await get_status(force_catalog=True)
    subs_obj = status.get("subscriptions", {})
    auto_install_new = subs_obj.get("auto_install_new_in_subscriptions", True)

    to_install = [u["id"] for u in status.get("available_updates", [])]

    if auto_install_new:
        to_install.extend([n["id"] for n in status.get("new_in_subscriptions", [])])

    to_install = list(dict.fromkeys(to_install))  # deduplicate

    if not to_install:
        return {"status": "up_to_date", "synced_count": 0, "errors": []}

    install_payload = InstallPayload(package_ids=to_install)
    res = await install_packages(install_payload)
    return {
        "status": res["status"],
        "synced_count": len(res["installed"]),
        "installed": res["installed"],
        "errors": res["errors"]
    }
