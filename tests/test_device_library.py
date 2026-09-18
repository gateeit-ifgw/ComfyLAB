# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import pytest
from unittest.mock import MagicMock
import numpy as np

# Test pure Python driver imports
from comfylab.devices.tektronix.tbs1062 import TBS1062
from comfylab.devices.owon.dge2000 import DGE2000
from comfylab.devices.minipa.mfg4230 import MFG4230
from comfylab.devices.bk_precision.bk4052 import BK4052
from comfylab.devices.generic.esa import GenericESA
from comfylab.devices.generic.dmm import GenericDMM
from comfylab.devices.generic.power_supply import GenericPowerSupply
from comfylab.devices.generic.siggen import GenericSigGen
from comfylab.devices.generic.oscilloscope import GenericOscilloscope
from comfylab.devices.generic.camera import GenericCamera

# Phase 4 & Extended Device Driver Imports
from comfylab.devices.thorlabs.pm100d import ThorlabsPM100D
from comfylab.devices.keysight.agilent_816x import Agilent816x
from comfylab.devices.yokogawa.aq6370 import AQ6370
from comfylab.devices.keithley.k2400 import Keithley2400
from comfylab.devices.srs.sr830 import SR830

# Extended Commercial Instruments
from comfylab.devices.keysight.dsox_series import KeysightDSOX
from comfylab.devices.agilent.e4407b import AgilentE4407B
from comfylab.devices.agilent.hp34401a import HP34401A
from comfylab.devices.advantest.q8384 import AdvantestQ8384
from comfylab.devices.keopsys.edfa import KeopsysEDFA
from comfylab.devices.thorlabs.lts200 import ThorlabsLTS200
from comfylab.devices.thorlabs.mdt69x import ThorlabsMDT69X
from comfylab.devices.ni.nidaqmx_device import NIDAQmxDevice
from comfylab.devices.mcc.mcdaq1208ls import MCCDAQ1208LS
from comfylab.devices.coherent.ws1000a import WaveShaper1000A

from comfylab.engine.registry import BLOCK_REGISTRY


def test_tbs1062_driver_mock():
    mock_visa = MagicMock()
    mock_visa.query.side_effect = lambda cmd: {
        "WFMPRe:XINcr?": "1e-6",
        "WFMPRe:XZERo?": "0.0",
        "WFMPRe:YMUlt?": "0.01",
        "WFMPRe:YOFF?": "0.0",
        "WFMPRe:YZERo?": "0.0",
        "HORizontal:MAIn:SCALE?": "0.001",
    }.get(cmd, "0")

    mock_visa.read_raw.return_value = b"#10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

    drv = TBS1062(mock_visa)
    drv.set_timebase(scale=0.001, position=0.0)
    mock_visa.write.assert_any_call("HORizontal:MAIn:SCALE 0.001")

    drv.set_channel(channel=1, enable=True, scale=2.0)
    mock_visa.write.assert_any_call("CH1:SCALE 2.0")

    t, v = drv.acquire_waveform(channel=1)
    assert isinstance(t, np.ndarray)
    assert isinstance(v, np.ndarray)


def test_keysight_dsox_mock():
    mock_visa = MagicMock()
    mock_visa.query.side_effect = lambda cmd: {
        ":WAVeform:PREamble?": "1,0,1000,1,1e-6,0.0,0.0,0.01,0.0,0.0"
    }.get(cmd, "0")
    # 4 bytes = 2 uint16 numbers
    mock_visa.read_raw.return_value = b"#14\x00\x00\x01\x00"

    drv = KeysightDSOX(mock_visa)
    drv.set_timebase(scale=0.001)
    mock_visa.write.assert_any_call(":TIMebase:SCALe 0.001")

    t, v = drv.acquire_waveform(channel=1)
    assert len(v) == 2



def test_agilent_e4407b_mock():
    mock_visa = MagicMock()
    mock_visa.query.side_effect = lambda cmd: {
        ":SENSe:FREQuency:STARt?": "1000000000.0",
        ":SENSe:FREQuency:STOP?": "1100000000.0",
        ":TRACe:DATA? TRACE1": "-10.0, -15.0, -20.0"
    }.get(cmd, "0")

    drv = AgilentE4407B(mock_visa)
    drv.set_frequency(center_hz=1e9, span_hz=100e6)
    mock_visa.write.assert_any_call(":SENSe:FREQuency:CENTer 1000000000.0")

    f, p = drv.acquire_trace(1)
    assert len(f) == 3
    assert len(p) == 3


def test_hp34401a_mock():
    mock_visa = MagicMock()
    mock_visa.query.side_effect = lambda cmd: {
        "READ?": "3.14159",
        "FETC?": "1.23, 1.25"
    }.get(cmd, "0")

    drv = HP34401A(mock_visa)
    drv.configure("VOLT:DC")
    mock_visa.write.assert_any_call("CONF:VOLT:DC")

    v = drv.read_voltage_dc()
    assert v == 1.24


def test_advantest_q8384_mock():
    mock_visa = MagicMock()
    mock_visa.query.side_effect = lambda cmd: {
        "CNT?": "CNT 1550.0",
        "SPAN?": "SPAN 20.0",
        "LDAT": "-20.0, -10.0, -25.0"
    }.get(cmd, "0")

    drv = AdvantestQ8384(mock_visa)
    drv.set_sweep_config(center_nm=1550.0, span_nm=20.0)
    mock_visa.write.assert_any_call("CNT 1550.0")

    # Test sweep modes
    drv.sweep(mode="REPEAT")
    mock_visa.write.assert_any_call("SR")

    drv.sweep(mode="SINGLE", wait=True)
    mock_visa.write.assert_any_call("SI")
    mock_visa.write.assert_any_call("*WAI")

    drv.sweep(mode="STOP")
    mock_visa.write.assert_any_call("ST")

    # Test memory trace acquisition without sweep trigger
    wl, p = drv.get_trace()
    assert len(wl) == 3
    assert p[1] == -10.0


def test_yokogawa_aq6370_mock():
    mock_visa = MagicMock()
    mock_visa.query.side_effect = lambda cmd: {
        ":TRACe:X? TRC": "1545.0, 1550.0, 1555.0",
        ":TRACe:Y? TRC": "-15.0, -5.0, -20.0"
    }.get(cmd, "0")

    drv = AQ6370(mock_visa)
    drv.set_sweep_config(center_nm=1550.0, span_nm=10.0, rbw_nm=0.02, sens="NORM")
    mock_visa.write.assert_any_call(":SENSe:WAVelength:CENTer 1550.0NM")

    # Test sweep mode and trace fixing across TRA..TRG
    drv.sweep(mode="REPEAT", active_trace="TRC", fix_other_traces=True)
    mock_visa.write.assert_any_call(":TRACe:STATe:TRC WRITe")
    mock_visa.write.assert_any_call(":TRACe:STATe:TRA FIXed")
    mock_visa.write.assert_any_call(":TRACe:STATe:TRG FIXed")
    mock_visa.write.assert_any_call(":INITiate:SMODe REPEAT")
    mock_visa.write.assert_any_call(":INITiate:IMMediate")

    # Test memory read for trace C
    wl, p = drv.get_trace("TRC")
    assert len(wl) == 3
    assert wl[1] == 1550.0
    assert p[1] == -5.0


def test_keopsys_edfa_mock():
    mock_visa = MagicMock()
    mock_visa.query.side_effect = lambda cmd: {
        "TD2?": "TD2=2500"
    }.get(cmd, "0")

    drv = KeopsysEDFA(mock_visa)
    drv.set_pump_state(True)
    mock_visa.write.assert_any_call("K1")

    drv.set_control_mode("ACC")
    mock_visa.write.assert_any_call("ASS=1")

    t = drv.read_temperature()
    assert t == 25.0


def test_thorlabs_lts200_and_mdt69x_mock():
    mock_visa = MagicMock()
    mock_visa.query.side_effect = lambda cmd: {
        "pos": "pos 12.345",
        "xvoltage?": "xvoltage=[50.0]"
    }.get(cmd, "0")

    lts = ThorlabsLTS200(mock_visa)
    lts.move_absolute(12.345)
    mock_visa.write.assert_called_with("ma 12.345")

    p = lts.get_position()
    assert p == 12.345

    mdt = ThorlabsMDT69X(mock_visa)
    mdt.set_voltage("X", 50.0)
    mock_visa.write.assert_called_with("xvoltage=50.0")

    v = mdt.get_voltage("X")
    assert v == 50.0


def test_mcdaq1208ls_mock():
    mock_visa = MagicMock()
    mock_visa.query.side_effect = lambda cmd: {
        "AIN 0": "AIN 2.50"
    }.get(cmd, "0")

    mcc = MCCDAQ1208LS(mock_visa)
    val = mcc.read_analog_channel(0)
    assert val == 2.5


def test_nidaqmx_error_raising_when_uninstalled(monkeypatch):
    import comfylab.devices.ni.nidaqmx_device as ni_mod
    monkeypatch.setattr(ni_mod, "NIDAQMX_AVAILABLE", False)

    with pytest.raises(RuntimeError, match="not installed on this system"):
        ni_mod.NIDAQmxDevice("Dev1")


def test_block_registration_discovery():
    import comfylab.blocks.loader as loader
    import comfylab.blocks.devices as devices_pkg
    from pathlib import Path

    devices_dir = str(Path(devices_pkg.__path__[0]))
    loader.load_blocks_from_directory(devices_dir)

    registered = BLOCK_REGISTRY

    
    # Check block discovery for newly added devices and OSA blocks
    assert "devices/keysight/dsox_series/connect" in registered
    assert "devices/agilent/e4407b/connect" in registered
    assert "devices/agilent/hp34401a/connect" in registered
    assert "devices/advantest/q8384/sweep_config" in registered
    assert "devices/advantest/q8384/acquire" in registered
    assert "devices/advantest/q8384/sweep_and_acquire" in registered
    assert "devices/yokogawa/aq6370/connect" in registered
    assert "devices/yokogawa/aq6370/sweep_config" in registered
    assert "devices/yokogawa/aq6370/acquire" in registered
    assert "devices/yokogawa/aq6370/sweep_and_acquire" in registered

    assert "devices/keopsys/edfa/connect" in registered
    assert "devices/thorlabs/lts200/connect" in registered
    assert "devices/thorlabs/mdt69x/connect" in registered
    assert "devices/ni/nidaqmx/connect" in registered
    assert "devices/mcc/mcdaq1208ls/connect" in registered
    assert "devices/generic/oscilloscope/connect" in registered
    assert "devices/generic/camera/connect" in registered
    assert "devices/coherent/ws1000a/connect" in registered
    assert "devices/coherent/ws1000a/get_info" in registered
    assert "devices/coherent/ws1000a/predefined_filter" in registered
    assert "devices/coherent/ws1000a/custom_filter" in registered
    assert "devices/coherent/ws1000a/upload_file" in registered
    assert "devices/coherent/ws1000a/get_profile" in registered
    assert "devices/coherent/ws1000a/shutter" in registered


def test_extract_float_and_floats_robustness():
    from comfylab.devices.base import extract_float, extract_floats

    # SCPI headers & units
    assert extract_float(":WFMPRE:XINCR 1.25E-6") == 1.25e-6
    assert extract_float(":WFMPRE:XZERO -2.5E-4") == -2.5e-4
    assert extract_float("HORizontal:MAIn:SCALE 0.001") == 0.001
    assert extract_float(":TIMebase:SCALe 5.0E-3") == 5e-3
    assert extract_float("pos 12.345 mm") == 12.345
    assert extract_float("xvoltage=[50.0]") == 50.0
    assert extract_float("AIN 0 2.50") == 2.50
    assert extract_float("TD2=2500") == 2500.0
    assert extract_float("1550.0NM") == 1550.0
    assert extract_float("-12.34 dBm") == -12.34
    assert extract_float('"1.0e-5"') == 1e-5
    assert extract_float("", default=99.0) == 99.0
    assert extract_float(None, default=42.0) == 42.0
    assert extract_float(3.14) == 3.14

    # Multi-value extractions
    trace_str = ":TRACe:DATA TRACE1, -10.5, -15.2, -20.0, -25.8"
    assert extract_floats(trace_str) == [-10.5, -15.2, -20.0, -25.8]

    osa_x = ":TRAC:X 1545.0NM, 1550.0NM, 1555.0NM"
    assert extract_floats(osa_x) == [1545.0, 1550.0, 1555.0]

    dsox_pre = ":WAV:PRE +1,+0,+1000,+1,+1.00000000E-06,-2.00000000E-04,+0.00000000E+00,+4.00000000E-03,+0.00000000E+00,+0.00000000E+00"
    parsed_dsox = extract_floats(dsox_pre)
    assert len(parsed_dsox) == 10
    assert parsed_dsox[4] == 1e-6
    assert parsed_dsox[5] == -2e-4


def test_parse_ieee_block_robustness():
    from comfylab.devices.base import parse_ieee_block

    payload_data = b"Hello, VISA IEEE 488.2 block!"
    header = f"#{len(str(len(payload_data)))}{len(payload_data)}".encode('ascii')
    standard_block = header + payload_data

    # Standard block
    assert parse_ieee_block(standard_block) == payload_data

    # Block with leading SCPI response command
    prefixed_block = b":CURV " + standard_block + b"\n"
    assert parse_ieee_block(prefixed_block) == payload_data

    # Block with WAV:DATA prefix
    wav_block = b":WAV:DATA " + standard_block + b"\r\n"
    assert parse_ieee_block(wav_block) == payload_data

    # Indefinite length block
    indefinite_block = b"#0" + payload_data + b"\n"
    assert parse_ieee_block(indefinite_block) == payload_data

    # Plain data without #
    assert parse_ieee_block(b"plain data\n") == b"plain data"


def test_parse_tektronix_preamble():
    from comfylab.devices.base import parse_tektronix_preamble

    # Full Tektronix preamble with date and string in WFID (field 6)
    preamble_raw = (
        '1;8;BIN;RI;MSB;2500;'
        '"Ch1, DC coupling, 1.0E0 V/div, 5.0E-4 s/div, 2500 points, Sample mode, 14-Aug-26 11:00";'
        'Y;2.0E-7;0;-2.5E-4;"s";4.0E-3;0.0E0;0.0E0;"Volts"'
    )

    info = parse_tektronix_preamble(preamble_raw)
    assert info["byt_nr"] == 1
    assert info["bit_nr"] == 8
    assert info["encdg"] == "BIN"
    assert info["nr_pt"] == 2500
    assert "14-Aug-26" in info["wfid"]
    assert info["x_incr"] == 2.0e-7
    assert info["x_zero"] == -2.5e-4
    assert info["x_unit"] == "s"
    assert info["y_mult"] == 4.0e-3
    assert info["y_zero"] == 0.0
    assert info["y_unit"] == "Volts"

    # With :WFMPRE: prefix
    prefixed_preamble = ":WFMPRE:" + preamble_raw
    info2 = parse_tektronix_preamble(prefixed_preamble)
    assert info2["x_incr"] == 2.0e-7
    assert info2["nr_pt"] == 2500


def test_tbs1062_driver_with_scpi_headers():
    mock_visa = MagicMock()
    mock_visa.query.side_effect = lambda cmd: {
        "WFMPRe:XINcr?": ":WFMPRE:XINCR 2.0000E-7",
        "WFMPRe:XZERo?": ":WFMPRE:XZERO -2.5000E-4",
        "WFMPRe:YMUlt?": ":WFMPRE:YMULT 4.0000E-3",
        "WFMPRe:YOFF?": ":WFMPRE:YOFF 0.0000E0",
        "WFMPRe:YZERo?": ":WFMPRE:YZERO 0.0000E0",
        "HORizontal:MAIn:SCALE?": ":HORIZONTAL:MAIN:SCALE 5.0000E-4",
    }.get(cmd, "0")

    mock_visa.read_raw.return_value = b":CURV #14\x00\x10\x20\x30\n"

    drv = TBS1062(mock_visa)
    scale = drv.get_timebase_scale()
    assert scale == 5.0e-4

    t, v = drv.acquire_waveform(channel=1)
    assert len(t) == 4
    assert len(v) == 4
    assert t[0] == -2.5e-4


def test_other_devices_with_scpi_headers():
    mock_visa = MagicMock()

    # Generic Oscilloscope with headers
    mock_visa.query.side_effect = lambda cmd: {
        ":TIMebase:SCALe?": ":TIM:SCAL 2.5E-3",
    }.get(cmd, "0")
    mock_visa.read_raw.return_value = b":WAV:DATA #12\x80\x80\n"
    g_osc = GenericOscilloscope(mock_visa)
    t, v = g_osc.acquire_waveform(1)
    assert len(t) == 2
    assert len(v) == 2

    # Generic ESA with headers
    mock_visa.query.side_effect = lambda cmd: {
        ":FREQuency:STARt?": ":FREQ:STAR 1.0E9",
        ":FREQuency:STOP?": ":FREQ:STOP 2.0E9",
        ":TRACe:DATA? TRACE1": ":TRAC:DATA TRACE1, -10.0, -15.0, -20.0"
    }.get(cmd, "0")
    esa = GenericESA(mock_visa)
    f, p = esa.acquire_trace(1)
    assert len(f) == 3
    assert len(p) == 3
    assert p[0] == -10.0

    # Thorlabs PM100D with headers
    mock_visa.query.side_effect = lambda cmd: {
        ":SENS:POW:WAV?": ":SENS:POW:WAV 1.55000000E-06",
        ":READ?": ":READ +1.23450000E-03"
    }.get(cmd, "0")
    pm = ThorlabsPM100D(mock_visa)
    assert pm.get_wavelength() == 1550.0
    assert pm.read_power() == 1.2345e-3

    # Agilent 816x with headers
    mock_visa.query.side_effect = lambda cmd: {
        ":READ2:POWer?": ":READ2:POW 5.67E-4"
    }.get(cmd, "0")
    a816 = Agilent816x(mock_visa)
    assert a816.read_sensor_power(2) == 5.67e-4

    # Keithley 2400 with headers
    mock_visa.query.side_effect = lambda cmd: {
        ":READ?": ":READ +1.2345E+00,+5.6789E-03"
    }.get(cmd, "0")
    k24 = Keithley2400(mock_visa)
    volt, curr = k24.read_measurement()
    assert volt == 1.2345
    assert curr == 5.6789e-3

    # SRS SR830 with headers
    mock_visa.query.side_effect = lambda cmd: {
        "OUTP? 1": "OUTP 1, 0.500",
        "OUTP? 2": "OUTP 2, 0.250",
        "SNAP? 1,2,3,4": "0.500, 0.250, 0.559, 26.56"
    }.get(cmd, "0")
    sr = SR830(mock_visa)
    assert sr.read_ch1() == 0.500
    assert sr.read_ch2() == 0.250
    x, y, r, th = sr.snap_all()
    assert x == 0.500
    assert y == 0.250
    assert r == 0.559
    assert th == 26.56



