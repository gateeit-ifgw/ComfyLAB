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
import sys
import time
import json
import shutil
import zipfile
import tempfile
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import comfylab

logger = logging.getLogger("backend.routers.updates")

router = APIRouter(prefix="/updates")

GITHUB_REPO = "gateeit-ifgw/ComfyLAB"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CACHE_TTL_SECONDS = 6 * 3600  # 6 hours

_IN_MEMORY_CACHE: Dict[str, Any] = {
    "timestamp": 0,
    "data": None,
}


def get_cache_file_path() -> Path:
    cache_dir = Path.home() / ".comfylab"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "update_cache.json"


def get_current_version() -> str:
    """Returns current ComfyLAB version string."""
    try:
        if hasattr(comfylab, "__version__") and comfylab.__version__:
            return comfylab.__version__
    except Exception:
        pass
    root = get_app_root_dir()
    for p in [root / "VERSION", Path(__file__).resolve().parent.parent.parent / "VERSION"]:
        if p.exists():
            return p.read_text().strip()
    return "0.0.0"


def parse_version_tuple(v_str: str):
    """Parses a version string into a comparable tuple or packaging.version object."""
    clean = v_str.strip().lstrip("vV")
    try:
        from packaging import version
        return version.parse(clean)
    except Exception:
        parts = []
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
    """Returns True if latest_str is strictly newer than current_str."""
    try:
        return parse_version_tuple(latest_str) > parse_version_tuple(current_str)
    except Exception as e:
        logger.warning(f"Failed to compare versions '{latest_str}' and '{current_str}': {e}")
        return False


def get_app_root_dir() -> Path:
    """Resolves the application root directory containing backend, comfylab, and frontend."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
        Path(sys.executable).parent,
    ]
    for candidate in candidates:
        if (candidate / "backend").exists() and (candidate / "comfylab").exists():
            return candidate
    return candidates[0]


def detect_install_type() -> str:
    """
    Detects how ComfyLAB was installed/launched:
    - 'standalone': Frozen executable compiled with PyInstaller
    - 'pip': Installed as a package in site-packages or dist-packages
    - 'git': Working within a Git clone of the repository
    - 'portable_zip': Extracted release archive with pre-compiled frontend and start scripts
    - 'unknown': Other/unrecognized setup
    """
    # 1. Standalone frozen binary
    if getattr(sys, "frozen", False):
        return "standalone"

    # 2. Pip installation check (if comfylab is imported from site-packages / dist-packages)
    try:
        comfylab_file = Path(comfylab.__file__).resolve()
        parts = [p.lower() for p in comfylab_file.parts]
        if "site-packages" in parts or "dist-packages" in parts:
            return "pip"
    except Exception:
        pass

    # 3. Git clone check relative to app root
    app_root = get_app_root_dir()
    candidate_git_dirs = [
        app_root / ".git",
        app_root.parent / ".git",
    ]
    for git_dir in candidate_git_dirs:
        if git_dir.is_dir() or git_dir.is_file():
            return "git"

    # 4. Portable release package check
    # Typically has frontend/dist, start.sh or start.bat, and VERSION file
    if (app_root / "frontend" / "dist").exists() and (
        (app_root / "start.sh").exists() or (app_root / "start.bat").exists() or (app_root / "start.py").exists()
    ):
        return "portable_zip"

    return "unknown"


def load_cached_update_info() -> Optional[Dict[str, Any]]:
    now = time.time()
    if _IN_MEMORY_CACHE["data"] and (now - _IN_MEMORY_CACHE["timestamp"] < CACHE_TTL_SECONDS):
        return _IN_MEMORY_CACHE["data"]

    cache_file = get_cache_file_path()
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_time = data.get("_cached_at", 0)
            if now - cached_time < CACHE_TTL_SECONDS:
                _IN_MEMORY_CACHE["timestamp"] = cached_time
                _IN_MEMORY_CACHE["data"] = data
                return data
        except Exception as e:
            logger.debug(f"Failed to read update cache file: {e}")

    return None


def save_cached_update_info(data: Dict[str, Any]):
    now = time.time()
    data["_cached_at"] = now
    _IN_MEMORY_CACHE["timestamp"] = now
    _IN_MEMORY_CACHE["data"] = data

    cache_file = get_cache_file_path()
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logger.debug(f"Failed to write update cache file: {e}")


def clear_cached_update_info():
    _IN_MEMORY_CACHE["timestamp"] = 0.0
    _IN_MEMORY_CACHE["data"] = None
    cache_file = get_cache_file_path()
    if cache_file.exists():
        try:
            cache_file.unlink()
        except Exception:
            pass


PYPI_API_URL = "https://pypi.org/pypi/comfylab/json"


async def fetch_github_release_info(timeout: float = 5.0) -> Dict[str, Any]:
    """Fetches latest release info from GitHub API."""
    headers = {
        "User-Agent": "ComfyLAB-UpdateChecker",
        "Accept": "application/vnd.github.v3+json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(GITHUB_API_URL, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 403:
            # Rate limited
            logger.warning("GitHub API rate limit exceeded while checking for updates.")
            raise HTTPException(status_code=429, detail="GitHub API rate limit exceeded. Please try again later.")
        elif resp.status_code == 404:
            raise HTTPException(status_code=404, detail="No releases found on GitHub repository.")
        else:
            raise HTTPException(status_code=resp.status_code, detail=f"GitHub API returned HTTP {resp.status_code}")


async def fetch_pypi_release_info(version: Optional[str] = None, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """Fetches latest (or specific version) release info from PyPI JSON API."""
    url = f"https://pypi.org/pypi/comfylab/{version}/json" if version else PYPI_API_URL
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers={"User-Agent": "ComfyLAB-UpdateChecker"})
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.debug(f"Failed to fetch PyPI release info from {url}: {e}")
    return None


def extract_pypi_wheel_url(pypi_data: Optional[Dict[str, Any]], target_version: Optional[str] = None) -> Optional[str]:
    """
    Extracts the direct download URL for a wheel or sdist from PyPI JSON response.
    Prefers wheel (.whl) over sdist (.tar.gz / .zip).
    """
    if not pypi_data:
        return None

    urls = []
    # If target_version specified and exists under releases, check releases[target_version]
    if target_version and "releases" in pypi_data and target_version in pypi_data["releases"]:
        urls = pypi_data["releases"][target_version]
    elif "urls" in pypi_data and pypi_data["urls"]:
        urls = pypi_data["urls"]

    wheel_url = None
    sdist_url = None
    for item in urls:
        filename = item.get("filename", "")
        pkg_type = item.get("packagetype", "")
        url = item.get("url")
        if not url:
            continue
        if pkg_type == "bdist_wheel" or filename.endswith(".whl"):
            wheel_url = url
            break
        elif pkg_type == "sdist" or filename.endswith(".tar.gz") or filename.endswith(".zip"):
            if not sdist_url:
                sdist_url = url

    return wheel_url or sdist_url


@router.get("/check")
async def check_updates(force: bool = Query(False)) -> Dict[str, Any]:
    """
    Checks if a newer version of ComfyLAB is available on GitHub or PyPI.
    Uses local cache with 6-hour TTL unless force=True.
    """
    current_version = get_current_version()
    install_type = detect_install_type()

    if not force:
        cached = load_cached_update_info()
        if cached:
            # Ensure install_type and current_version reflect live runtime
            result = dict(cached)
            result["current_version"] = current_version
            result["install_type"] = install_type
            result["update_available"] = is_newer_version(result.get("latest_version", current_version), current_version)
            result["from_cache"] = True
            return result

    raw_release = None
    try:
        raw_release = await fetch_github_release_info()
    except Exception as e:
        logger.debug(f"GitHub release check encountered an issue: {e}")

    pypi_release = None
    try:
        pypi_release = await fetch_pypi_release_info()
    except Exception as e:
        logger.debug(f"PyPI release check encountered an issue: {e}")

    if not raw_release and not pypi_release:
        cached = load_cached_update_info()
        if cached:
            result = dict(cached)
            result["current_version"] = current_version
            result["install_type"] = install_type
            result["update_available"] = is_newer_version(result.get("latest_version", current_version), current_version)
            result["from_cache"] = True
            result["network_warning"] = "Could not reach update servers; showing cached update information."
            return result
        raise HTTPException(status_code=502, detail="Failed to check for updates from GitHub or PyPI.")

    latest_version = "0.0.0"
    raw_tag = ""
    release_name = ""
    release_notes = ""
    release_url = f"https://github.com/{GITHUB_REPO}/releases/latest"
    published_at = ""
    asset_url = None
    asset_size = 0

    if raw_release:
        raw_tag = raw_release.get("tag_name", "")
        latest_version = raw_tag.lstrip("vV")
        release_name = raw_release.get("name") or f"ComfyLAB v{latest_version}"
        release_notes = raw_release.get("body") or ""
        release_url = raw_release.get("html_url") or release_url
        published_at = raw_release.get("published_at") or ""
        for asset in raw_release.get("assets", []):
            asset_name = asset.get("name", "")
            if asset_name.endswith(".zip") and "release" in asset_name.lower():
                asset_url = asset.get("browser_download_url")
                asset_size = asset.get("size", 0)
                break

    pypi_wheel_url = None
    # If PyPI reports a newer version, use PyPI version info
    if pypi_release:
        pypi_version = pypi_release.get("info", {}).get("version", "")
        pypi_wheel_url = extract_pypi_wheel_url(pypi_release, pypi_version)
        if is_newer_version(pypi_version, latest_version):
            latest_version = pypi_version
            raw_tag = f"v{pypi_version}"
            release_name = f"ComfyLAB v{pypi_version} (PyPI)"
            release_url = f"https://pypi.org/project/comfylab/{pypi_version}/"
            if not release_notes or not raw_release:
                release_notes = pypi_release.get("info", {}).get("summary", "") or f"Release v{pypi_version} available on PyPI."

    if not pypi_wheel_url and pypi_release:
        pypi_wheel_url = extract_pypi_wheel_url(pypi_release, latest_version)

    update_available = is_newer_version(latest_version, current_version)

    info = {
        "status": "success",
        "update_available": update_available,
        "current_version": current_version,
        "latest_version": latest_version,
        "release_tag": raw_tag,
        "release_name": release_name,
        "release_notes": release_notes,
        "release_url": release_url,
        "published_at": published_at,
        "asset_url": asset_url,
        "asset_size": asset_size,
        "pypi_wheel_url": pypi_wheel_url,
        "install_type": install_type,
        "from_cache": False,
    }

    save_cached_update_info(info)
    return info


class ApplyUpdatePayload(BaseModel):
    install_type: Optional[str] = None
    target_version: Optional[str] = None
    wheel_url: Optional[str] = None


@router.post("/apply")
async def apply_update(payload: Optional[ApplyUpdatePayload] = None) -> Dict[str, Any]:
    """
    Applies an available update depending on the detected install type:
    - pip: executes 'pip install --upgrade --no-cache-dir <wheel_url|comfylab>=target_version>'
    - portable_zip: downloads and extracts the release archive over the application root
    - standalone / git: returns error explaining that manual update is required
    """
    detected_type = detect_install_type()
    req_type = payload.install_type if payload and payload.install_type else detected_type

    if req_type == "pip":
        target_version = payload.target_version if payload and payload.target_version else None
        cached = load_cached_update_info()
        if not target_version and cached and cached.get("latest_version"):
            target_version = cached.get("latest_version")

        # Determine wheel URL to bypass PyPI Simple Index CDN cache lag
        wheel_url = payload.wheel_url if payload and payload.wheel_url else None
        if not wheel_url and cached:
            cached_wheel = cached.get("pypi_wheel_url")
            if cached_wheel and (not target_version or target_version in cached_wheel):
                wheel_url = cached_wheel

        # If wheel_url not known yet, try fetching it directly from PyPI JSON API
        if not wheel_url:
            pypi_info = await fetch_pypi_release_info(version=target_version)
            if pypi_info:
                wheel_url = extract_pypi_wheel_url(pypi_info, target_version)

        # Primary attempt: install directly from PyPI wheel URL if available.
        # This completely bypasses Fastly CDN edge caching delays on the Simple Index (PEP 503/691).
        candidates = []
        if wheel_url:
            candidates.append(wheel_url)

        # Fallback candidate: package name specifier
        pkg_spec = f"comfylab>={target_version}" if target_version else "comfylab"
        candidates.append(pkg_spec)

        last_error = None
        for target in candidates:
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", target]
            logger.info(f"Applying update via pip (target: '{target}'): {' '.join(cmd)}")
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300.0)
                stdout_text = stdout.decode().strip()
                stderr_text = stderr.decode().strip()
                if process.returncode == 0:
                    logger.info(f"ComfyLAB upgraded successfully via pip with target '{target}': {stdout_text}")
                    clear_cached_update_info()
                    return {
                        "status": "success",
                        "install_type": "pip",
                        "message": "ComfyLAB was upgraded successfully via pip! Please restart the application to apply changes.",
                        "output": stdout_text
                    }
                else:
                    last_error = stderr_text or stdout_text
                    logger.warning(f"pip install failed for target '{target}' (code {process.returncode}): {last_error}")
            except asyncio.TimeoutError:
                raise HTTPException(status_code=504, detail="pip upgrade timed out after 5 minutes.")
            except Exception as e:
                logger.error(f"Failed to execute pip update with target '{target}': {e}")
                last_error = str(e)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to update via pip: {last_error}"
        )

    elif req_type == "portable_zip":
        logger.info("Applying update via portable release ZIP...")
        # Check cached or live release info for the asset URL
        cached = load_cached_update_info()
        asset_url = cached.get("asset_url") if cached else None

        if not asset_url:
            raw_release = await fetch_github_release_info()
            if raw_release:
                for asset in raw_release.get("assets", []):
                    asset_name = asset.get("name", "")
                    if asset_name.endswith(".zip") and "release" in asset_name.lower():
                        asset_url = asset.get("browser_download_url")
                        break

        if not asset_url:
            raise HTTPException(
                status_code=404,
                detail="Could not locate a release ZIP asset on GitHub to perform the portable update."
            )

        app_root = get_app_root_dir()

        # Check write permissions on app_root
        test_file = app_root / f".write_test_{os.getpid()}"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            raise HTTPException(
                status_code=403,
                detail=f"Installation directory '{app_root}' is not writable ({e}). Please update manually."
            )

        temp_dir = Path(tempfile.mkdtemp(prefix="comfylab_update_"))
        zip_dest = temp_dir / "release.zip"
        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"Downloading release archive from {asset_url}...")
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                async with client.stream("GET", asset_url) as response:
                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Failed to download release archive (HTTP {response.status_code})"
                        )
                    with open(zip_dest, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            f.write(chunk)

            logger.info("Extracting release archive safely...")
            with zipfile.ZipFile(zip_dest, "r") as zip_ref:
                for member in zip_ref.infolist():
                    target_path = Path(extract_dir / member.filename).resolve()
                    if not target_path.is_relative_to(extract_dir.resolve()):
                        raise HTTPException(status_code=400, detail=f"Path traversal detected in archive: {member.filename}")
                    if member.is_dir():
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with zip_ref.open(member) as src_f, open(target_path, "wb") as dst_f:
                            shutil.copyfileobj(src_f, dst_f)

            # Check if archive has a top-level 'comfylab' directory
            content_root = extract_dir
            subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
            if len(subdirs) == 1 and subdirs[0].name == "comfylab":
                content_root = subdirs[0]

            logger.info(f"Applying extracted files into {app_root}...")
            # Copy contents into app_root
            for item in content_root.iterdir():
                dest_item = app_root / item.name
                if item.is_dir():
                    shutil.copytree(item, dest_item, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest_item)

            # Ensure start.sh has executable permissions on POSIX
            if os.name != "nt":
                start_sh = app_root / "start.sh"
                if start_sh.exists():
                    try:
                        os.chmod(start_sh, 0o755)
                    except Exception:
                        pass

            # Invalidate update cache after successful update
            _IN_MEMORY_CACHE["timestamp"] = 0
            _IN_MEMORY_CACHE["data"] = None
            cache_file = get_cache_file_path()
            if cache_file.exists():
                try:
                    cache_file.unlink()
                except Exception:
                    pass

            return {
                "status": "success",
                "install_type": "portable_zip",
                "message": "ComfyLAB was updated successfully! Please restart the application to apply changes."
            }

        finally:
            # Clean up temporary files
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.debug(f"Failed to clean temporary update directory: {e}")

    elif req_type == "standalone":
        raise HTTPException(
            status_code=400,
            detail="Standalone compiled binary cannot be updated automatically in-place. Please download the new executable from GitHub."
        )

    elif req_type == "git":
        raise HTTPException(
            status_code=400,
            detail="Git development installation detected. Please run 'git pull' in your repository to update."
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Automated update is not supported for install type: '{req_type}'."
        )
