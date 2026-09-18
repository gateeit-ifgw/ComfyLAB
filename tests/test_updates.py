# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import sys
import zipfile
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers.updates import (
    is_newer_version,
    parse_version_tuple,
    detect_install_type,
    extract_pypi_wheel_url,
    _IN_MEMORY_CACHE,
)


def test_version_comparisons():
    assert is_newer_version("0.5.0", "0.4.1") is True
    assert is_newer_version("v0.5.0", "0.4.1") is True
    assert is_newer_version("0.4.2", "0.4.1") is True
    assert is_newer_version("1.0.0", "0.9.9") is True
    assert is_newer_version("0.4.1", "0.4.1") is False
    assert is_newer_version("0.4.0", "0.4.1") is False
    assert is_newer_version("0.3.9", "0.4.1") is False


def test_detect_install_type_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert detect_install_type() == "standalone"


def test_detect_install_type_git(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    (fake_repo / ".git").mkdir()
    monkeypatch.setattr("backend.routers.updates.get_app_root_dir", lambda: fake_repo)
    assert detect_install_type() == "git"


def test_detect_install_type_pip(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    fake_root = tmp_path / "app"
    fake_root.mkdir()
    monkeypatch.setattr("backend.routers.updates.get_app_root_dir", lambda: fake_root)

    fake_comfylab = MagicMock()
    fake_comfylab.__file__ = str(tmp_path / "site-packages" / "comfylab" / "__init__.py")
    monkeypatch.setattr("backend.routers.updates.comfylab", fake_comfylab)

    assert detect_install_type() == "pip"


def test_detect_install_type_portable_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    fake_root = tmp_path / "portable_app"
    fake_root.mkdir()
    (fake_root / "frontend" / "dist").mkdir(parents=True)
    (fake_root / "start.sh").write_text("#!/bin/sh\n")
    (fake_root / "VERSION").write_text("0.4.1")

    monkeypatch.setattr("backend.routers.updates.get_app_root_dir", lambda: fake_root)
    fake_comfylab = MagicMock()
    fake_comfylab.__file__ = str(fake_root / "comfylab" / "__init__.py")
    monkeypatch.setattr("backend.routers.updates.comfylab", fake_comfylab)

    assert detect_install_type() == "portable_zip"


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch, tmp_path):
    _IN_MEMORY_CACHE["timestamp"] = 0
    _IN_MEMORY_CACHE["data"] = None
    fake_cache = tmp_path / "update_cache.json"
    monkeypatch.setattr("backend.routers.updates.get_cache_file_path", lambda: fake_cache)


def test_check_updates_endpoint_newer_available(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.routers.updates.get_current_version", lambda: "0.4.1")
    monkeypatch.setattr("backend.routers.updates.detect_install_type", lambda: "pip")

    mock_release = {
        "tag_name": "v0.5.0",
        "name": "ComfyLAB v0.5.0 Release",
        "body": "- New awesome features\n- Bug fixes",
        "html_url": "https://github.com/gateeit-ifgw/ComfyLAB/releases/tag/v0.5.0",
        "published_at": "2026-08-27T12:00:00Z",
        "assets": [
            {
                "name": "comfylab-release-v0.5.0.zip",
                "browser_download_url": "https://github.com/gateeit-ifgw/ComfyLAB/releases/download/v0.5.0/comfylab-release-v0.5.0.zip",
                "size": 1234567,
            }
        ],
    }

    with patch("backend.routers.updates.fetch_github_release_info", new=AsyncMock(return_value=mock_release)), \
         patch("backend.routers.updates.fetch_pypi_release_info", new=AsyncMock(return_value=None)):
        resp = client.get("/updates/check?force=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["update_available"] is True
        assert data["current_version"] == "0.4.1"
        assert data["latest_version"] == "0.5.0"
        assert data["install_type"] == "pip"
        assert data["asset_url"] is not None

        # Verify caching works on second call without force
        cached_resp = client.get("/updates/check")
        assert cached_resp.status_code == 200
        assert cached_resp.json()["from_cache"] is True


def test_check_updates_endpoint_up_to_date(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.routers.updates.get_current_version", lambda: "0.5.0")
    monkeypatch.setattr("backend.routers.updates.detect_install_type", lambda: "pip")

    mock_release = {
        "tag_name": "v0.5.0",
        "name": "ComfyLAB v0.5.0 Release",
        "body": "No updates needed",
        "html_url": "https://github.com/gateeit-ifgw/ComfyLAB/releases/tag/v0.5.0",
        "assets": [],
    }

    with patch("backend.routers.updates.fetch_github_release_info", new=AsyncMock(return_value=mock_release)), \
         patch("backend.routers.updates.fetch_pypi_release_info", new=AsyncMock(return_value=None)):
        resp = client.get("/updates/check?force=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["update_available"] is False
        assert data["current_version"] == "0.5.0"
        assert data["latest_version"] == "0.5.0"


def test_apply_update_git_and_standalone_rejected(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr("backend.routers.updates.detect_install_type", lambda: "git")
    resp = client.post("/updates/apply")
    assert resp.status_code == 400
    assert "git pull" in resp.json()["detail"]

    monkeypatch.setattr("backend.routers.updates.detect_install_type", lambda: "standalone")
    resp = client.post("/updates/apply")
    assert resp.status_code == 400
    assert "download" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_apply_update_pip(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.routers.updates.detect_install_type", lambda: "pip")

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"Successfully installed comfylab-0.5.0", b""))

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        resp = client.post("/updates/apply")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["install_type"] == "pip"
        assert "restart" in data["message"].lower()


def test_apply_update_portable_zip(tmp_path, monkeypatch):
    client = TestClient(app)
    fake_root = tmp_path / "comfylab_install"
    fake_root.mkdir()
    (fake_root / "VERSION").write_text("0.4.1")
    (fake_root / "backend").mkdir()
    (fake_root / "backend" / "main.py").write_text("# old code")

    monkeypatch.setattr("backend.routers.updates.get_app_root_dir", lambda: fake_root)
    monkeypatch.setattr("backend.routers.updates.detect_install_type", lambda: "portable_zip")

    # Create a dummy update zip
    zip_path = tmp_path / "test_release.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("comfylab/VERSION", "0.5.0")
        zf.writestr("comfylab/backend/main.py", "# new code")

    # Mock load_cached_update_info to return asset_url
    monkeypatch.setattr(
        "backend.routers.updates.load_cached_update_info",
        lambda: {"asset_url": "https://fake.url/comfylab-release-v0.5.0.zip"},
    )

    # Mock httpx streaming download
    class MockStreamContext:
        async def __aenter__(self):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            async def aiter_bytes(chunk_size=65536):
                with open(zip_path, "rb") as f:
                    while chunk := f.read(chunk_size):
                        yield chunk
            mock_resp.aiter_bytes = aiter_bytes
            return mock_resp

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockHttpxClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def stream(self, method, url):
            return MockStreamContext()

    monkeypatch.setattr("httpx.AsyncClient", MockHttpxClient)

    resp = client.post("/updates/apply")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["install_type"] == "portable_zip"
    assert (fake_root / "VERSION").read_text().strip() == "0.5.0"
    assert (fake_root / "backend" / "main.py").read_text().strip() == "# new code"


def test_check_updates_prefers_pypi_when_newer(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.routers.updates.get_current_version", lambda: "0.4.2")
    monkeypatch.setattr("backend.routers.updates.detect_install_type", lambda: "pip")

    mock_github = {
        "tag_name": "v0.4.2",
        "name": "ComfyLAB v0.4.2 Release",
        "body": "Older release",
        "html_url": "https://github.com/gateeit-ifgw/ComfyLAB/releases/tag/v0.4.2",
        "assets": [],
    }
    mock_pypi = {
        "info": {
            "version": "0.4.3",
            "summary": "Brand new 0.4.3 on PyPI",
        }
    }

    with patch("backend.routers.updates.fetch_github_release_info", new=AsyncMock(return_value=mock_github)):
        with patch("backend.routers.updates.fetch_pypi_release_info", new=AsyncMock(return_value=mock_pypi)):
            resp = client.get("/updates/check?force=true")
            assert resp.status_code == 200
            data = resp.json()
            assert data["update_available"] is True
            assert data["current_version"] == "0.4.2"
            assert data["latest_version"] == "0.4.3"


def test_extract_pypi_wheel_url():
    # Empty or None
    assert extract_pypi_wheel_url(None) is None
    assert extract_pypi_wheel_url({}) is None

    # Prefer wheel over sdist
    pypi_data = {
        "urls": [
            {"filename": "comfylab-0.6.2.tar.gz", "packagetype": "sdist", "url": "https://files.pythonhosted.org/sdist.tar.gz"},
            {"filename": "comfylab-0.6.2-py3-none-any.whl", "packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/wheel.whl"},
        ]
    }
    assert extract_pypi_wheel_url(pypi_data) == "https://files.pythonhosted.org/wheel.whl"

    # Fallback to sdist if no wheel
    sdist_only = {
        "urls": [
            {"filename": "comfylab-0.6.2.tar.gz", "packagetype": "sdist", "url": "https://files.pythonhosted.org/sdist.tar.gz"},
        ]
    }
    assert extract_pypi_wheel_url(sdist_only) == "https://files.pythonhosted.org/sdist.tar.gz"

    # Specific version from releases dict
    releases_data = {
        "urls": [],
        "releases": {
            "0.6.2": [
                {"filename": "comfylab-0.6.2-py3-none-any.whl", "packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/0.6.2.whl"},
            ]
        }
    }
    assert extract_pypi_wheel_url(releases_data, target_version="0.6.2") == "https://files.pythonhosted.org/0.6.2.whl"


@pytest.mark.asyncio
async def test_apply_update_pip_uses_wheel_url_first(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.routers.updates.detect_install_type", lambda: "pip")

    executed_cmds = []

    def mock_subprocess(*args, **kwargs):
        executed_cmds.append(list(args))
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"Successfully installed", b""))
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
        wheel_url = "https://files.pythonhosted.org/packages/comfylab-0.6.2.whl"
        resp = client.post("/updates/apply", json={
            "install_type": "pip",
            "target_version": "0.6.2",
            "wheel_url": wheel_url,
        })
        assert resp.status_code == 200
        assert len(executed_cmds) == 1
        assert wheel_url in executed_cmds[0]


@pytest.mark.asyncio
async def test_apply_update_pip_falls_back_when_wheel_url_fails(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.routers.updates.detect_install_type", lambda: "pip")

    executed_cmds = []

    def mock_subprocess(*args, **kwargs):
        executed_cmds.append(list(args))
        mock_proc = MagicMock()
        # First command (wheel url) fails, second command (fallback pkg_spec) succeeds
        if len(executed_cmds) == 1:
            mock_proc.returncode = 1
            mock_proc.communicate = AsyncMock(return_value=(b"", b"Failed to fetch wheel"))
        else:
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"Successfully installed comfylab-0.6.2", b""))
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
        wheel_url = "https://files.pythonhosted.org/packages/comfylab-0.6.2.whl"
        resp = client.post("/updates/apply", json={
            "install_type": "pip",
            "target_version": "0.6.2",
            "wheel_url": wheel_url,
        })
        assert resp.status_code == 200
        assert len(executed_cmds) == 2
        assert wheel_url in executed_cmds[0]
        assert "comfylab>=0.6.2" in executed_cmds[1]
