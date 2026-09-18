# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Test suite for Coherent / Finisar WaveShaper 1000A driver and visual automation blocks.
"""

import sys
import os
import asyncio
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
import pytest
import numpy as np
import requests

from comfylab.blocks.base import ExecutionContext
from comfylab.engine.locks import ResourceLockManager
from comfylab.blocks.loader import load_module_from_filepath

try:
    from comfylab.devices.coherent.ws1000a import (
        WaveShaper1000A,
        SPEED_OF_LIGHT_NM_THZ
    )
    from comfylab.blocks.devices.coherent.ws1000a_blocks import (
        WaveShaper1000AConnectBlock,
        WaveShaper1000AGetInfoBlock,
        WaveShaper1000APredefinedFilterBlock,
        WaveShaper1000ACustomFilterBlock,
        WaveShaper1000AUploadFileBlock,
        WaveShaper1000AGetProfileBlock,
        WaveShaper1000AShutterBlock
    )
except ModuleNotFoundError:
    store_candidates = [
        Path.home() / ".comfylab" / "store" / "instruments" / "coherent" / "ws1000a",
        Path(__file__).resolve().parent.parent / "dist" / "comfylab-store" / "instruments" / "coherent" / "ws1000a",
    ]
    cand = next((c for c in store_candidates if (c / "driver.py").exists()), None)
    if cand:
        drv_mod = load_module_from_filepath(str(cand / "driver.py"))
        blk_mod = load_module_from_filepath(str(cand / "blocks.py"))
        WaveShaper1000A = getattr(drv_mod, "WaveShaper1000A", None)
        SPEED_OF_LIGHT_NM_THZ = getattr(drv_mod, "SPEED_OF_LIGHT_NM_THZ", 299792.458)
        WaveShaper1000AConnectBlock = getattr(blk_mod, "WaveShaper1000AConnectBlock", None)
        WaveShaper1000AGetInfoBlock = getattr(blk_mod, "WaveShaper1000AGetInfoBlock", None)
        WaveShaper1000APredefinedFilterBlock = getattr(blk_mod, "WaveShaper1000APredefinedFilterBlock", None)
        WaveShaper1000ACustomFilterBlock = getattr(blk_mod, "WaveShaper1000ACustomFilterBlock", None)
        WaveShaper1000AUploadFileBlock = getattr(blk_mod, "WaveShaper1000AUploadFileBlock", None)
        WaveShaper1000AGetProfileBlock = getattr(blk_mod, "WaveShaper1000AGetProfileBlock", None)
        WaveShaper1000AShutterBlock = getattr(blk_mod, "WaveShaper1000AShutterBlock", None)
    else:
        pytestmark = pytest.mark.skip(reason="Coherent WaveShaper 1000A store package not available")


# =============================================================================
# 1. Optical Conversions & WSP Utilities Tests
# =============================================================================

def test_optical_conversions():
    # 1550 nm -> ~193.414 THz
    f = WaveShaper1000A.nm_to_thz(1550.0)
    assert abs(f - 193.414489) < 1e-3

    # Invert back
    wl = WaveShaper1000A.thz_to_nm(f)
    assert abs(wl - 1550.0) < 1e-6

    # Array conversions
    wls = [1530.0, 1550.0, 1570.0]
    freqs = WaveShaper1000A.nm_to_thz(wls)
    assert len(freqs) == 3
    wls_back = WaveShaper1000A.thz_to_nm(freqs)
    np.testing.assert_allclose(wls, wls_back, rtol=1e-6)

    # Invalid inputs
    with pytest.raises(ValueError):
        WaveShaper1000A.nm_to_thz(0.0)
    with pytest.raises(ValueError):
        WaveShaper1000A.thz_to_nm(-10.0)


def test_bandwidth_conversions():
    center_nm = 1550.0
    span_nm = 1.0
    bw_thz = WaveShaper1000A.nm_bandwidth_to_thz(center_nm, span_nm)
    assert bw_thz > 0

    center_thz = WaveShaper1000A.nm_to_thz(center_nm)
    bw_nm_back = WaveShaper1000A.thz_bandwidth_to_nm(center_thz, bw_thz)
    assert abs(bw_nm_back - span_nm) < 1e-4


def test_create_and_parse_wsp_string():
    # Test unsorted arrays and phase modulo
    freqs = [194.0, 192.0, 193.0]
    attns = [10.0, 5.0, 0.0]
    phases = [0.0, 2.0 * np.pi + 1.0, 0.5]
    ports = [1, 1, 1]

    wsp_str = WaveShaper1000A.create_wsp_string(
        frequencies_thz=freqs,
        attenuations_db=attns,
        phases_rad=phases,
        ports=ports
    )
    assert isinstance(wsp_str, str)
    lines = [line.strip() for line in wsp_str.strip().split("\n")]
    assert len(lines) == 3

    # Check ascending sort
    first_col_freq = float(lines[0].split()[0])
    second_col_freq = float(lines[1].split()[0])
    third_col_freq = float(lines[2].split()[0])
    assert first_col_freq == 192.0
    assert second_col_freq == 193.0
    assert third_col_freq == 194.0

    # Parse back
    drv = WaveShaper1000A("127.0.0.1")
    f_arr, wl_arr, a_arr, p_arr, pt_arr = drv.parse_wsp_string(wsp_str)
    assert len(f_arr) == 3
    assert f_arr[0] == 192.0
    assert a_arr[0] == 5.0
    assert abs(p_arr[0] - 1.0) < 1e-3  # 2*pi + 1.0 modulo 2*pi is 1.0
    assert pt_arr[0] == 1
    assert abs(wl_arr[0] - WaveShaper1000A.thz_to_nm(192.0)) < 1e-6


def test_create_wsp_mismatched_lengths():
    with pytest.raises(ValueError, match="Array length mismatch"):
        WaveShaper1000A.create_wsp_string(
            frequencies_thz=[192.0, 193.0],
            attenuations_db=[5.0]
        )


# =============================================================================
# 2. Standalone Driver Mocked HTTP Tests
# =============================================================================

@patch("requests.Session.get")
def test_driver_get_devinfo(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "WaveShaper 1000A",
        "sno": "WS-1000A-9999",
        "ver": "2.4.1",
        "startfreq": 191.250,
        "stopfreq": 196.275,
        "ip": "169.254.6.8",
        "portcount": 1,
        "msg": "OK"
    }
    mock_get.return_value = mock_resp

    drv = WaveShaper1000A(host="169.254.6.8", port=80)
    info = drv.get_devinfo()
    assert info["model"] == "WaveShaper 1000A"
    assert info["startfreq"] == 191.250

    min_nm, max_nm = drv.get_wavelength_range()
    assert min_nm < max_nm
    assert abs(min_nm - WaveShaper1000A.thz_to_nm(196.275)) < 1e-3
    assert abs(max_nm - WaveShaper1000A.thz_to_nm(191.250)) < 1e-3


@patch("requests.Session.post")
def test_driver_load_predefined_profile_nm(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"rc": 0, "msg": "OK", "sno": "WS123"}
    mock_post.return_value = mock_resp

    drv = WaveShaper1000A("169.254.6.8")
    res = drv.load_predefined_profile(
        filter_type="bandpass",
        center=1550.0,
        bandwidth=2.0,
        attn_db=3.0,
        port=1,
        unit="nm"
    )
    assert res["rc"] == 0

    # Verify posted JSON
    args, kwargs = mock_post.call_args
    posted_json = kwargs["json"]
    assert posted_json["type"] == "bandpass"
    assert posted_json["port"] == 1
    assert abs(posted_json["center"] - 193.4145) < 0.01
    assert posted_json["attn"] == 3.0


@patch("requests.Session.post")
def test_driver_load_predefined_transmit_and_blockall(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"rc": 0, "msg": "OK"}
    mock_post.return_value = mock_resp

    drv = WaveShaper1000A("169.254.6.8")
    drv.set_transmit_all()
    _, kwargs1 = mock_post.call_args
    assert kwargs1["json"] == {"type": "transmit"}

    drv.set_block_all()
    _, kwargs2 = mock_post.call_args
    assert kwargs2["json"] == {"type": "blockall"}


@patch("requests.Session.post")
def test_driver_load_profile_arrays(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"rc": 0, "msg": "OK"}
    mock_post.return_value = mock_resp

    drv = WaveShaper1000A("169.254.6.8")
    wls = [1540.0, 1550.0, 1560.0]
    attns = [10.0, 0.0, 10.0]

    drv.load_profile_arrays(frequencies_or_wavelengths=wls, attenuations_db=attns, unit="nm")
    _, kwargs = mock_post.call_args
    posted = kwargs["json"]
    assert posted["type"] == "wsp"
    assert "wsp" in posted
    lines = posted["wsp"].strip().split("\n")
    assert len(lines) == 3


@patch("requests.Session.post")
def test_driver_load_wsp_file(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"rc": 0, "msg": "OK"}
    mock_post.return_value = mock_resp

    drv = WaveShaper1000A("169.254.6.8")

    with tempfile.NamedTemporaryFile("w", suffix=".wsp", delete=False) as f:
        f.write("193.1000\t0.00\t0.0000\t1\n193.2000\t5.00\t0.0000\t1\n")
        temp_path = f.name

    try:
        drv.load_wsp_file(temp_path)
        _, kwargs = mock_post.call_args
        assert "193.1000" in kwargs["json"]["wsp"]
    finally:
        os.unlink(temp_path)


@patch("requests.Session.get")
def test_driver_get_profile(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "193.0000\t0.00\t0.0000\t1\n194.0000\t10.00\t0.0000\t1\n"
    mock_get.return_value = mock_resp

    drv = WaveShaper1000A("169.254.6.8")
    profile = drv.get_profile()
    assert "193.0000" in profile
    f_arr, wl_arr, a_arr, _, _ = drv.parse_wsp_string(profile)
    assert len(f_arr) == 2
    assert a_arr[1] == 10.0


# =============================================================================
# 3. ComfyLAB Visual Blocks Async Execution Tests
# =============================================================================

class SimpleMockContext(ExecutionContext):
    def __init__(self, data_map):
        self.lock_manager = ResourceLockManager()
        self.data_map = data_map

    async def pull(self, block_id: str, pin_name: str) -> Any:
        return self.data_map.get((block_id, pin_name), self.data_map.get(pin_name))

    async def push(self, block_id: str, pin_name: str, value: Any) -> None:
        self.data_map[(block_id, pin_name)] = value


@pytest.mark.asyncio
async def test_connect_and_teardown_blocks():
    blk = WaveShaper1000AConnectBlock("connect_1")

    context = SimpleMockContext({
        "Host": "192.168.1.100",
        "Port": 80,
        "Timeout": 2.0,
        "SafetyBlockOnTeardown": True
    })

    with patch.object(WaveShaper1000A, "get_devinfo", return_value={
        "model": "WaveShaper 1000A",
        "sno": "WS12345",
        "startfreq": 191.250,
        "stopfreq": 196.275
    }):
        out_pin = await blk.execute(context, "Open")
        assert out_pin == "Out"

        dev = await blk.pull_data(context, "Device")
        assert isinstance(dev, WaveShaper1000A)
        assert await blk.pull_data(context, "Model") == "WaveShaper 1000A"
        assert await blk.pull_data(context, "Serial") == "WS12345"
        assert await blk.pull_data(context, "StartFreqTHz") == 191.250
        assert await blk.pull_data(context, "StopFreqTHz") == 196.275
        assert await blk.pull_data(context, "StartWavelengthNM") > 1520.0
        assert await blk.pull_data(context, "StopWavelengthNM") > 1550.0

    # Teardown with safety block
    with patch.object(WaveShaper1000A, "set_block_all") as mock_safety:
        await blk.teardown()
        mock_safety.assert_called_once()


@pytest.mark.asyncio
async def test_get_info_block():
    blk = WaveShaper1000AGetInfoBlock("info_1")
    drv = WaveShaper1000A("169.254.6.8")

    context = SimpleMockContext({
        "Device": drv
    })

    with patch.object(WaveShaper1000A, "get_devinfo", return_value={
        "model": "WaveShaper 1000A",
        "sno": "WS54321",
        "ver": "3.0.0",
        "portcount": 1,
        "startfreq": 191.250,
        "stopfreq": 196.275
    }):
        out_pin = await blk.execute(context, "In")
        assert out_pin == "Out"
        assert await blk.pull_data(context, "Model") == "WaveShaper 1000A"
        assert await blk.pull_data(context, "Serial") == "WS54321"
        assert await blk.pull_data(context, "Firmware") == "3.0.0"
        assert await blk.pull_data(context, "PortCount") == 1


@pytest.mark.asyncio
async def test_predefined_filter_block():
    blk = WaveShaper1000APredefinedFilterBlock("predef_1")
    drv = WaveShaper1000A("169.254.6.8")

    context = SimpleMockContext({
        "Device": drv,
        "FilterType": "bandpass",
        "Unit": "nm",
        "Center": 1550.0,
        "Bandwidth": 1.0,
        "Attenuation": 2.5,
        "Port": 1
    })

    with patch.object(WaveShaper1000A, "load_predefined_profile", return_value={"rc": 0}) as mock_load:
        out_pin = await blk.execute(context, "In")
        assert out_pin == "Out"
        assert await blk.pull_data(context, "Success") is True
        mock_load.assert_called_once_with(
            filter_type="bandpass",
            center=1550.0,
            bandwidth=1.0,
            attn_db=2.5,
            port=1,
            unit="nm"
        )


@pytest.mark.asyncio
async def test_custom_filter_block():
    blk = WaveShaper1000ACustomFilterBlock("custom_1")
    drv = WaveShaper1000A("169.254.6.8")

    context = SimpleMockContext({
        "Device": drv,
        "SpectralPoints": [1540.0, 1550.0, 1560.0],
        "Attenuation": [10.0, 0.0, 10.0],
        "Phase": [0.0, 0.0, 0.0],
        "Unit": "nm",
        "Port": 1
    })

    with patch.object(WaveShaper1000A, "load_profile_arrays", return_value={"rc": 0}) as mock_load:
        out_pin = await blk.execute(context, "In")
        assert out_pin == "Out"
        assert await blk.pull_data(context, "Success") is True
        mock_load.assert_called_once()


@pytest.mark.asyncio
async def test_upload_file_block():
    blk = WaveShaper1000AUploadFileBlock("upload_1")
    drv = WaveShaper1000A("169.254.6.8")

    context = SimpleMockContext({
        "Device": drv,
        "FilePath": "",
        "WspString": "193.1000\t0.00\t0.0000\t1\n"
    })

    with patch.object(WaveShaper1000A, "load_wsp_string", return_value={"rc": 0}) as mock_load:
        out_pin = await blk.execute(context, "In")
        assert out_pin == "Out"
        assert await blk.pull_data(context, "Success") is True
        mock_load.assert_called_once_with("193.1000\t0.00\t0.0000\t1\n")


@pytest.mark.asyncio
async def test_get_profile_block():
    blk = WaveShaper1000AGetProfileBlock("get_prof_1")
    drv = WaveShaper1000A("169.254.6.8")

    context = SimpleMockContext({
        "Device": drv
    })

    mock_wsp = "193.0000\t0.00\t0.0000\t1\n194.0000\t15.00\t1.5700\t1\n"
    with patch.object(WaveShaper1000A, "get_profile", return_value=mock_wsp):
        out_pin = await blk.execute(context, "In")
        assert out_pin == "Out"

        f_arr = await blk.pull_data(context, "FrequencyTHz")
        wl_arr = await blk.pull_data(context, "WavelengthNM")
        a_arr = await blk.pull_data(context, "AttenuationDB")
        p_arr = await blk.pull_data(context, "PhaseRad")
        wsp_text = await blk.pull_data(context, "WspString")

        assert len(f_arr) == 2
        assert len(wl_arr) == 2
        assert a_arr[1] == 15.0
        assert wsp_text == mock_wsp


@pytest.mark.asyncio
async def test_shutter_block():
    blk = WaveShaper1000AShutterBlock("shutter_1")
    drv = WaveShaper1000A("169.254.6.8")

    # Transmit All
    context1 = SimpleMockContext({
        "Device": drv,
        "State": "Transmit All"
    })
    with patch.object(WaveShaper1000A, "set_transmit_all", return_value={"rc": 0}) as mock_tx:
        out_pin = await blk.execute(context1, "In")
        assert out_pin == "Out"
        assert await blk.pull_data(context1, "Success") is True
        mock_tx.assert_called_once()

    # Block All
    context2 = SimpleMockContext({
        "Device": drv,
        "State": "Block All"
    })
    with patch.object(WaveShaper1000A, "set_block_all", return_value={"rc": 0}) as mock_block:
        out_pin = await blk.execute(context2, "In")
        assert out_pin == "Out"
        assert await blk.pull_data(context2, "Success") is True
        mock_block.assert_called_once()
