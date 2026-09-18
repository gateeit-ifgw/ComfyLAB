# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# Test suite to verify all newly added instrument drivers and blocks.

import sys
import os
import asyncio
from pathlib import Path
import numpy as np

# Ensure src is in sys.path
src_dir = Path(__file__).resolve().parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Mock pyvisa if needed for testing
class MockVisaResource:
    def __init__(self, resource_name="GPIB0::1::INSTR"):
        self.resource_name = resource_name
        self.timeout = 2000
        self.chunk_size = 40960
        self.written_commands = []
        self._mock_responses = {
            "*IDN?": "Mock Instrument IDN",
            "VOLTage?": "5.0000",
            "CURRent?": "0.1000",
            "MEASure:VOLTage?": "5.0123",
            "MEASure:CURRent?": "0.0987",
            "MEASure:VOLTage? CH1": "5.0123",
            "MEASure:CURRent? CH1": "0.0987",
            "MEASure:VOLTage? CH2": "12.045",
            "MEASure:CURRent? CH2": "0.5012",
            "MEASure:VOLTage? CH3": "3.301",
            "MEASure:CURRent? CH3": "0.2001",
            ":TIMebase:SCALe?": "1.0E-3",
            ":WAVeform:PREamble?": "1,0,1000,1,1.0e-6,0.0,0,0.01,0.0,0",
            "WFMOPre:XINcr?": "1.0E-6",
            "WFMOPre:XZERo?": "0.0",
            "WFMOPre:YMUlt?": "0.01",
            "WFMOPre:YOFF?": "0.0",
            "WFMOPre:YZERo?": "0.0",
            "WFMOUTPRE:XINCR?": "1.0E-6",
            "WFMOUTPRE:XZERO?": "0.0",
            "WFMOUTPRE:YMULT?": "0.01",
            "WFMOUTPRE:YOFF?": "0.0",
            "WFMOUTPRE:YZERO?": "0.0",
            "WFMOUTPRE:NR_PT?": "1000",
            "HORizontal:MODE:RECOrdlength?": "1000",
            "MEASUrement:IMMed:VALue?": "3.3",
            "MEASUREMENT:IMMed:VALue?": "3.3",
            ":MEASure:VPP? CHANnel1": "3.3",
            ":MEASure:FREQuency? CHANnel1": "1000000.0"
        }

    def write(self, cmd):
        self.written_commands.append(cmd)
        return len(cmd)

    def query(self, cmd):
        self.written_commands.append(cmd)
        for k, v in self._mock_responses.items():
            if k in cmd:
                return v
        return "0.0"

    def query_raw(self, cmd):
        self.written_commands.append(cmd)
        # Return IEEE 488.2 block header: #41000 + 1000 bytes
        raw_data = bytes([128] * 1000)
        header = f"#{len(str(len(raw_data)))}{len(raw_data)}".encode('ascii')
        return header + raw_data + b"\n"

    def read_raw(self):
        raw_data = bytes([128] * 1000)
        header = f"#{len(str(len(raw_data)))}{len(raw_data)}".encode('ascii')
        return header + raw_data + b"\n"

    def close(self):
        pass


def _get_driver(vendor: str, model: str, class_name: str):
    try:
        mod = __import__(f"comfylab.devices.{vendor}.{model}", fromlist=[class_name])
        return getattr(mod, class_name, None)
    except ModuleNotFoundError:
        pass
    candidates = [
        Path.home() / ".comfylab" / "store" / "instruments" / vendor / model / "driver.py",
        Path(__file__).resolve().parent.parent / "dist" / "comfylab-store" / "instruments" / vendor / model / "driver.py",
    ]
    for c in candidates:
        if c.exists():
            from comfylab.blocks.loader import load_module_from_filepath
            mod = load_module_from_filepath(str(c))
            return getattr(mod, class_name, None)
    return None


def test_imports_and_drivers():
    print("Testing Driver imports and methods...")
    mock_dev = MockVisaResource()

    # 1. Keithley 2231A
    Keithley2231A = _get_driver("keithley", "k2231a", "Keithley2231A")
    if not Keithley2231A:
        pytest.skip("Keithley2231A not available")
    k2231 = Keithley2231A(mock_dev)
    k2231.set_channel(1, 5.0, 1.0)
    k2231.set_output(True)
    v1 = k2231.measure_voltage(1)
    i1 = k2231.measure_current(1)
    all_meas = k2231.measure_all()
    assert len(all_meas) == 3
    print("  ✓ Keithley2231A driver OK")

    # 2. Tektronix MSO24
    TektronixMSO24 = _get_driver("tektronix", "mso24", "TektronixMSO24")
    mso24 = TektronixMSO24(mock_dev)
    mso24.set_timebase(1e-3, 0.0)
    mso24.set_channel(1, True, 1.0, 0.0, 0.0, "DC")
    mso24.set_trigger("CH1", 0.5, "RISE", "AUTO")
    t, v = mso24.acquire_waveform(1)
    assert len(t) > 0 and len(v) > 0
    m_val = mso24.measure(1, "PK2PK")
    print("  ✓ TektronixMSO24 driver OK")

    # 3. Keysight DSOX 3024A
    KeysightDSOX3024A = _get_driver("keysight", "dsox3024a", "KeysightDSOX3024A")
    dsox3024 = KeysightDSOX3024A(mock_dev)
    dsox3024.set_timebase(1e-3, 0.0)
    dsox3024.set_channel(1, True, 1.0, 0.0, "DC", True)
    dsox3024.set_trigger("CHAN1", 0.5, "POS", "AUTO")
    t, v = dsox3024.acquire_waveform(1)
    assert len(t) > 0 and len(v) > 0
    m_val = dsox3024.measure(1, "VPP")
    print("  ✓ KeysightDSOX3024A driver OK")

    # 4. Agilent 33220A
    Agilent33220A = _get_driver("agilent", "a33220a", "Agilent33220A")
    a33220 = Agilent33220A(mock_dev)
    a33220.set_wave("SIN", 1000.0, 2.0, 0.0)
    a33220.set_pulse(1e-3, 1e-4, 1e-8)
    a33220.set_output(True, "50")
    a33220.set_sweep(100.0, 10000.0, 1.0, "LIN", True)
    print("  ✓ Agilent33220A driver OK")

    # 5. Tektronix MDO3040
    TektronixMDO3040 = _get_driver("tektronix", "mdo3040", "TektronixMDO3040")
    mdo3040 = TektronixMDO3040(mock_dev)
    mdo3040.set_timebase(1e-3, 0.0)
    mdo3040.set_channel(1, True, 1.0, 0.0, 0.0, "DC")
    mdo3040.set_rf(True, 1e9, 1e7, 0.0)
    t, v = mdo3040.acquire_waveform(1)
    assert len(t) > 0 and len(v) > 0
    f, p = mdo3040.acquire_rf_trace("NORMAL")
    assert len(f) > 0 and len(p) > 0
    print("  ✓ TektronixMDO3040 driver OK")

    # 6. Keysight DSOX 1204A
    KeysightDSOX1204A = _get_driver("keysight", "dsox1204a", "KeysightDSOX1204A")
    dsox1204 = KeysightDSOX1204A(mock_dev)
    dsox1204.set_timebase(1e-3, 0.0)
    dsox1204.set_channel(1, True, 1.0, 0.0, "DC", 10.0)
    dsox1204.set_wavegen("SIN", 1000.0, 1.0, 0.0, True)
    t, v = dsox1204.acquire_waveform(1)
    assert len(t) > 0 and len(v) > 0
    print("  ✓ KeysightDSOX1204A driver OK")

    # 7. Horiba VUV Excitation
    HoribaVUVExcitation = _get_driver("horiba", "vuv_excitation", "HoribaVUVExcitation")
    horiba = HoribaVUVExcitation(simulate=True)
    horiba.initialize()
    horiba.set_wavelength(250.0)
    wl = horiba.get_current_wavelength()
    assert abs(wl - 250.0) < 1e-3
    horiba.set_current_grating_turret(1)
    grats = horiba.get_gratings()
    assert len(grats) > 0
    horiba.set_slit_width(0, 1.2)
    sw = horiba.get_slit_width(0)
    assert abs(sw - 1.2) < 1e-3
    horiba.set_mirror_position(0, 1)
    mp = horiba.get_mirror_position(0)
    assert mp == 1
    horiba.close()
    print("  ✓ HoribaVUVExcitation driver OK")

    # 8. CAEN DT5720B
    CAENDT5720B = _get_driver("caen", "dt5720b", "CAENDT5720B")
    caen = CAENDT5720B(simulate=True)
    caen.open(simulate=True)
    caen.set_record_length(1024)
    caen.set_post_trigger_size(50.0)
    caen.set_channel(0, enable=True, dc_offset_percent=50.0, trigger_threshold_dac=2000, trigger_slope="FALLING", dynamic_range_vpp=2.0)
    caen.start_acquisition()
    t_arr, v_arr = caen.acquire_event(0)
    assert len(t_arr) == 1024 and len(v_arr) == 1024
    stats = CAENDT5720B.calculate_pulse_stats(t_arr, v_arr)
    assert "peak_amplitude" in stats and "pulse_area" in stats
    caen.stop_acquisition()
    caen.close()
    print("  ✓ CAENDT5720B driver OK")

    # 9. Keysight E36234A
    KeysightE36234A = _get_driver("keysight", "e36234a", "KeysightE36234A")
    e36234 = KeysightE36234A(mock_dev)
    e36234.set_channel(1, 12.0, 2.5)
    e36234.set_output(True, 1)
    e36234.set_protection(1, ovp_voltage=15.0, ocp_enable=True)
    e36234.set_pairing_mode("SERIES")
    v = e36234.measure_voltage(1)
    i = e36234.measure_current(1)
    p = e36234.measure_power(1)
    all_res = e36234.measure_all()
    assert len(all_res) == 2
    print("  ✓ KeysightE36234A driver OK")


def test_registry_loading():
    print("\nTesting Block Registry auto-discovery & loading...")
    from comfylab.blocks.loader import load_all_blocks, load_blocks_from_directory
    from comfylab.engine.registry import BLOCK_REGISTRY

    load_all_blocks()
    store_dir = Path(__file__).resolve().parent.parent / "dist" / "comfylab-store" / "instruments"
    if store_dir.exists():
        load_blocks_from_directory(str(store_dir))

    expected_block_types = [
        # Keithley 2231A
        "devices/keithley/k2231a/connect",
        "devices/keithley/k2231a/channel",
        "devices/keithley/k2231a/output",
        "devices/keithley/k2231a/measure",
        "devices/keithley/k2231a/measure_all",

        # Tektronix MSO24
        "devices/tektronix/mso24/connect",
        "devices/tektronix/mso24/timebase",
        "devices/tektronix/mso24/channel",
        "devices/tektronix/mso24/trigger",
        "devices/tektronix/mso24/acquire",
        "devices/tektronix/mso24/measure",

        # Keysight DSOX 3024A
        "devices/keysight/dsox3024a/connect",
        "devices/keysight/dsox3024a/timebase",
        "devices/keysight/dsox3024a/channel",
        "devices/keysight/dsox3024a/trigger",
        "devices/keysight/dsox3024a/acquire",
        "devices/keysight/dsox3024a/measure",

        # Agilent 33220A
        "devices/agilent/a33220a/connect",
        "devices/agilent/a33220a/wave",
        "devices/agilent/a33220a/output",
        "devices/agilent/a33220a/pulse",
        "devices/agilent/a33220a/sweep",

        # Tektronix MDO3040
        "devices/tektronix/mdo3040/connect",
        "devices/tektronix/mdo3040/timebase",
        "devices/tektronix/mdo3040/channel",
        "devices/tektronix/mdo3040/trigger",
        "devices/tektronix/mdo3040/acquire",
        "devices/tektronix/mdo3040/measure",
        "devices/tektronix/mdo3040/rf_acquire",

        # Keysight DSOX 1204A
        "devices/keysight/dsox1204a/connect",
        "devices/keysight/dsox1204a/timebase",
        "devices/keysight/dsox1204a/channel",
        "devices/keysight/dsox1204a/trigger",
        "devices/keysight/dsox1204a/acquire",
        "devices/keysight/dsox1204a/measure",
        "devices/keysight/dsox1204a/wavegen",

        # Horiba VUV
        "devices/horiba/vuv_excitation/connect",
        "devices/horiba/vuv_excitation/wavelength",
        "devices/horiba/vuv_excitation/grating",
        "devices/horiba/vuv_excitation/slit",
        "devices/horiba/vuv_excitation/mirror",

        # CAEN DT5720B
        "devices/caen/dt5720b/connect",
        "devices/caen/dt5720b/configure",
        "devices/caen/dt5720b/channel",
        "devices/caen/dt5720b/acquire",
        "devices/caen/dt5720b/pulse_stats",

        # Keysight E36234A
        "devices/keysight/e36234a/connect",
        "devices/keysight/e36234a/channel",
        "devices/keysight/e36234a/output",
        "devices/keysight/e36234a/measure",
        "devices/keysight/e36234a/measure_all",
        "devices/keysight/e36234a/pairing",
    ]

    for btype in expected_block_types:
        assert btype in BLOCK_REGISTRY, f"Block type '{btype}' was NOT found in BLOCK_REGISTRY!"
        block_cls = BLOCK_REGISTRY[btype]
        assert hasattr(block_cls, "inputs_def")
        assert hasattr(block_cls, "outputs_def")
        assert hasattr(block_cls, "i18n")
        assert "pt-BR" in block_cls.i18n
        assert "es" in block_cls.i18n
        print(f"  ✓ Registered block: {btype} ({block_cls.display_name})")

    print(f"\nALL {len(expected_block_types)} new block types verified and registered successfully!")


if __name__ == "__main__":
    test_imports_and_drivers()
    test_registry_loading()
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉")
