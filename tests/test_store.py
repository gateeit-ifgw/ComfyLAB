# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import json
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers.store import (
    matches_subscription,
    is_newer_version,
    parse_version_tuple,
)


def test_matches_subscription():
    pkg = {
        "id": "instruments/agilent/hp34401a",
        "name": "HP 34401A",
        "vendor": "Agilent",
        "type": "instrument",
        "path": "instruments/agilent/hp34401a"
    }

    # All subscription
    assert matches_subscription(pkg, {"type": "all", "target": "*"}) is True

    # Category subscription
    assert matches_subscription(pkg, {"type": "category", "target": "instruments"}) is True
    assert matches_subscription(pkg, {"type": "category", "target": "blocks"}) is False

    # Vendor subscription
    assert matches_subscription(pkg, {"type": "vendor", "target": "agilent"}) is True
    assert matches_subscription(pkg, {"type": "vendor", "target": "keysight"}) is False

    # Package subscription
    assert matches_subscription(pkg, {"type": "package", "target": "instruments/agilent/hp34401a"}) is True
    assert matches_subscription(pkg, {"type": "package", "target": "instruments/keysight/dsox1204a"}) is False


def test_store_status_and_badge_flow(tmp_path, monkeypatch):
    store_dir = tmp_path / "store"
    store_dir.mkdir(parents=True)
    installed_file = store_dir / "installed.json"
    subs_file = store_dir / "subscriptions.json"
    cache_file = store_dir / "catalog_cache.json"

    monkeypatch.setattr("backend.routers.store.get_store_dir", lambda: store_dir)
    monkeypatch.setattr("backend.routers.store.get_store_installed_file", lambda: installed_file)
    monkeypatch.setattr("backend.routers.store.get_store_subscriptions_file", lambda: subs_file)
    monkeypatch.setattr("backend.routers.store.get_store_catalog_cache_file", lambda: cache_file)

    mock_catalog = {
        "schema_version": "1.0",
        "packages": [
            {
                "id": "instruments/agilent/hp34401a",
                "name": "HP 34401A",
                "vendor": "Agilent",
                "type": "instrument",
                "version": "1.2.0",
                "path": "instruments/agilent/hp34401a",
                "files": ["manifest.json", "driver.py", "blocks.py"]
            },
            {
                "id": "instruments/keysight/dsox1204a",
                "name": "Keysight DSOX1204A",
                "vendor": "Keysight",
                "type": "instrument",
                "version": "1.0.0",
                "path": "instruments/keysight/dsox1204a",
                "files": ["manifest.json", "driver.py", "blocks.py"]
            }
        ]
    }

    # Pre-populate installed: hp34401a is at 1.0.0 (older than catalog 1.2.0)
    installed_file.write_text(json.dumps({
        "instruments/agilent/hp34401a": {
            "id": "instruments/agilent/hp34401a",
            "name": "HP 34401A",
            "version": "1.0.0",
            "vendor": "Agilent",
            "path": "instruments/agilent/hp34401a",
            "files": ["manifest.json", "driver.py", "blocks.py"]
        }
    }), encoding="utf-8")

    # Pre-populate subscriptions: subscribed to Keysight vendor
    subs_file.write_text(json.dumps({
        "auto_sync_on_startup": True,
        "auto_install_new_in_subscriptions": True,
        "subscriptions": [
            {"type": "vendor", "target": "keysight", "name": "Keysight Technologies"}
        ]
    }), encoding="utf-8")

    # Mock catalog fetch
    monkeypatch.setattr(
        "backend.routers.store.fetch_store_catalog",
        AsyncMock(return_value=mock_catalog)
    )

    client = TestClient(app)

    # 1. Check status
    res = client.get("/store/status")
    assert res.status_code == 200
    data = res.json()
    assert data["updates_count"] == 1
    assert data["available_updates"][0]["id"] == "instruments/agilent/hp34401a"
    assert data["new_in_subscriptions_count"] == 1
    assert data["new_in_subscriptions"][0]["id"] == "instruments/keysight/dsox1204a"

    # 2. Check badge
    badge_res = client.get("/store/badge")
    assert badge_res.status_code == 200
    badge_data = badge_res.json()
    assert badge_data["has_badge"] is True
    assert badge_data["total_badge_count"] == 2
    assert badge_data["updates_count"] == 1
    assert badge_data["new_in_subscriptions_count"] == 1

    # 3. Test subscribe / unsubscribe
    sub_res = client.post("/store/subscribe", json={
        "type": "vendor",
        "target": "thorlabs",
        "name": "Thorlabs",
        "subscribed": True
    })
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    targets = [s["target"] for s in sub_data["subscriptions"]["subscriptions"]]
    assert "thorlabs" in targets

    # Unsubscribe
    unsub_res = client.post("/store/subscribe", json={
        "type": "vendor",
        "target": "thorlabs",
        "subscribed": False
    })
    assert unsub_res.status_code == 200
    targets_after = [s["target"] for s in unsub_res.json()["subscriptions"]["subscriptions"]]
    assert "thorlabs" not in targets_after


def test_install_and_uninstall_package(tmp_path, monkeypatch):
    store_dir = tmp_path / "store"
    store_dir.mkdir(parents=True)
    installed_file = store_dir / "installed.json"
    subs_file = store_dir / "subscriptions.json"
    cache_file = store_dir / "catalog_cache.json"

    monkeypatch.setattr("backend.routers.store.get_store_dir", lambda: store_dir)
    monkeypatch.setattr("backend.routers.store.get_store_installed_file", lambda: installed_file)
    monkeypatch.setattr("backend.routers.store.get_store_subscriptions_file", lambda: subs_file)
    monkeypatch.setattr("backend.routers.store.get_store_catalog_cache_file", lambda: cache_file)

    mock_driver_code = "class MockDMM:\n    pass\n"
    mock_block_code = "from comfylab.blocks.base import BaseBlock\nclass MockBlock(BaseBlock):\n    pass\n"
    mock_manifest = json.dumps({"name": "Mock", "version": "1.0.0"})

    mock_pkg = {
        "id": "instruments/test/mock_dmm",
        "name": "Mock DMM",
        "vendor": "Test",
        "type": "instrument",
        "version": "1.0.0",
        "path": "instruments/test/mock_dmm",
        "files": ["manifest.json", "driver.py", "blocks.py"],
        "hashes": {
            "manifest.json": hashlib.sha256(mock_manifest.encode("utf-8")).hexdigest(),
            "driver.py": hashlib.sha256(mock_driver_code.encode("utf-8")).hexdigest(),
            "blocks.py": hashlib.sha256(mock_block_code.encode("utf-8")).hexdigest(),
        }
    }

    mock_catalog = {
        "schema_version": "1.0",
        "packages": [mock_pkg]
    }

    monkeypatch.setattr(
        "backend.routers.store.fetch_store_catalog",
        AsyncMock(return_value=mock_catalog)
    )

    # Mock httpx download responses
    class MockResponse:
        def __init__(self, content, status_code=200):
            self.content = content
            self.status_code = status_code

    async def mock_get(url):
        if "manifest.json" in url:
            return MockResponse(mock_manifest.encode("utf-8"))
        elif "driver.py" in url:
            return MockResponse(mock_driver_code.encode("utf-8"))
        elif "blocks.py" in url:
            return MockResponse(mock_block_code.encode("utf-8"))
        return MockResponse(b"", 404)

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=mock_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr("backend.routers.store.httpx.AsyncClient", lambda **kwargs: mock_client)

    # Also mock reload_registry so we don't reload during test
    monkeypatch.setattr("backend.routers.store.reload_registry", lambda: None)

    client = TestClient(app)

    # 1. Install package
    install_res = client.post("/store/install", json={"package_ids": ["instruments/test/mock_dmm"]})
    assert install_res.status_code == 200
    assert install_res.json()["status"] == "success"

    # Verify files written
    pkg_dir = store_dir / "instruments" / "test" / "mock_dmm"
    assert (pkg_dir / "manifest.json").exists()
    assert (pkg_dir / "driver.py").exists()
    assert (pkg_dir / "blocks.py").exists()

    # Verify python files were signed
    blocks_text = (pkg_dir / "blocks.py").read_text(encoding="utf-8")
    assert "# @signature:" in blocks_text

    # Verify installed.json
    installed_data = json.loads(installed_file.read_text(encoding="utf-8"))
    assert "instruments/test/mock_dmm" in installed_data

    # 2. Uninstall package
    uninst_res = client.post("/store/uninstall", json={"package_id": "instruments/test/mock_dmm"})
    assert uninst_res.status_code == 200
    assert not pkg_dir.exists()
    installed_data_after = json.loads(installed_file.read_text(encoding="utf-8"))
    assert "instruments/test/mock_dmm" not in installed_data_after


def test_store_relative_import_and_loader(tmp_path, monkeypatch):
    from comfylab.blocks.loader import load_blocks_from_directory
    from comfylab.engine.registry import BLOCK_REGISTRY

    pkg_dir = tmp_path / "instruments" / "test_store_vendor" / "device_x"
    pkg_dir.mkdir(parents=True)

    driver_code = """
class DeviceXDriver:
    def read_val(self):
        return 42
"""
    block_code = """
from comfylab.engine.registry import register_block
from comfylab.blocks.base import BaseBlock
from .driver import DeviceXDriver

@register_block("devices/test_store_vendor/device_x/read")
class DeviceXReadBlock(BaseBlock):
    pass
"""
    (pkg_dir / "driver.py").write_text(driver_code, encoding="utf-8")
    (pkg_dir / "blocks.py").write_text(block_code, encoding="utf-8")

    try:
        load_blocks_from_directory(str(pkg_dir))
        assert "devices/test_store_vendor/device_x/read" in BLOCK_REGISTRY
    finally:
        BLOCK_REGISTRY.pop("devices/test_store_vendor/device_x/read", None)
