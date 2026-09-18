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
from unittest.mock import MagicMock, patch
import pytest

from comfylab.engine.executor import ExecutionEngine
from comfylab.engine.registry import get_all_blocks_schema
from comfylab.blocks.serial_device import (
    normalize_serial_port,
    ManagedSerialDevice,
    get_available_serial_ports,
)


def test_serial_blocks_registration():
    schema = get_all_blocks_schema()

    assert "serial/core/device" in schema
    assert "serial/core/write" in schema
    assert "serial/core/read" in schema
    assert "serial/core/query" in schema
    assert "serial/core/list_ports" in schema

    dev_schema = schema["serial/core/device"]
    assert dev_schema["name"] == "Serial Device"
    assert dev_schema["category"] == "INSTRUMENTS/Serial"
    assert dev_schema["icon"] == "🔌"

    # Verify input pins: Port and BaudRate are non-optional; others are optional
    data_ins = {pin["name"]: pin for pin in dev_schema["dataIns"]}
    assert "Port" in data_ins
    assert data_ins["Port"]["optional"] is False

    assert "BaudRate" in data_ins
    assert data_ins["BaudRate"]["optional"] is False
    assert 115200 in data_ins["BaudRate"]["options"]

    # Framing inputs must be marked optional
    for optional_pin in ["DataBits", "StopBits", "Parity", "FlowControl", "ReadTermination", "WriteTermination", "Timeout", "DTR", "RTS"]:
        assert optional_pin in data_ins
        assert data_ins[optional_pin]["optional"] is True


def test_normalize_serial_port():
    assert normalize_serial_port("/dev/ttyUSB0") == "/dev/ttyUSB0"
    assert normalize_serial_port("/dev/ttyACM1") == "/dev/ttyACM1"
    assert normalize_serial_port("ASRL/dev/ttyUSB0::INSTR") == "/dev/ttyUSB0"
    assert normalize_serial_port("ASRL::COM3::INSTR") == "COM3"
    assert normalize_serial_port("com4") == "COM4"
    assert normalize_serial_port("COM2") == "COM2"
    if sys.platform == "win32":
        assert normalize_serial_port("ASRL5::INSTR") == "COM5"
    else:
        assert normalize_serial_port("ASRL1::INSTR") == "/dev/ttyS0"


def test_managed_serial_device_pty():
    if sys.platform == "win32":
        pytest.skip("PTY testing is only supported on Unix platforms.")

    import pty

    master, slave = pty.openpty()
    slave_name = os.ttyname(slave)

    try:
        dev = ManagedSerialDevice(
            port=slave_name,
            baudrate=115200,
            timeout=1.0,
            read_termination="\n",
            write_termination="\n",
        )
        assert dev.is_alive() is True
        assert dev.resource_name == slave_name

        # Test write from dev -> read on master
        dev.write("PING")
        received = os.read(master, 1024)
        assert received == b"PING\n"

        # Test write to master -> read on dev
        os.write(master, b"PONG\n")
        reply = dev.read()
        assert reply == "PONG"

        # Test query
        def echo_worker():
            cmd = os.read(master, 1024)
            if cmd.strip() == b"*IDN?":
                os.write(master, b"TEST,DEVICE,1234,1.0\n")

        import threading
        t = threading.Thread(target=echo_worker)
        t.start()

        idn = dev.query("*IDN?")
        t.join(timeout=1.0)
        assert idn == "TEST,DEVICE,1234,1.0"

        # Test clear
        assert dev.clear() is True

        dev.close()
        assert dev.is_alive() is False
    finally:
        os.close(master)
        os.close(slave)


@pytest.mark.asyncio
async def test_serial_blocks_mock_execution():
    with patch("comfylab.blocks.serial_device.serial.Serial") as mock_serial_cls:
        mock_ser = MagicMock()
        mock_ser.is_open = True
        mock_ser.write.return_value = 5
        mock_ser.read_until.return_value = b"RESP_OK\n"
        mock_ser.in_waiting = 0
        mock_serial_cls.return_value = mock_ser

        blueprint = {
            "blocks": [
                {
                    "id": "ser_dev",
                    "type": "serial/core/device",
                    "properties": {
                        "Port": "/dev/ttyUSB0",
                        "BaudRate": 115200,
                        "Timeout": 1.0,
                    }
                },
                {
                    "id": "ser_write",
                    "type": "serial/core/write",
                    "properties": {
                        "Data": "SET_VOLT 5.0"
                    }
                },
                {
                    "id": "ser_query",
                    "type": "serial/core/query",
                    "properties": {
                        "Command": "GET_VOLT?"
                    }
                },
                {
                    "id": "print",
                    "type": "outputs/basic/print",
                    "properties": {}
                }
            ],
            "links": [
                {"id": "l1", "type": "exec", "source_block": "ser_dev", "source_pin": "Out", "target_block": "ser_write", "target_pin": "In"},
                {"id": "l2", "type": "data", "source_block": "ser_dev", "source_pin": "Device", "target_block": "ser_write", "target_pin": "Device"},
                {"id": "l3", "type": "exec", "source_block": "ser_write", "source_pin": "Out", "target_block": "ser_query", "target_pin": "In"},
                {"id": "l4", "type": "data", "source_block": "ser_write", "source_pin": "Device", "target_block": "ser_query", "target_pin": "Device"},
                {"id": "l5", "type": "exec", "source_block": "ser_query", "source_pin": "Out", "target_block": "print", "target_pin": "In"},
                {"id": "l6", "type": "data", "source_block": "ser_query", "source_pin": "Response", "target_block": "print", "target_pin": "Value"},
            ]
        }

        engine = ExecutionEngine()
        engine.load_blueprint(blueprint)
        await engine.run(start_block_id="ser_dev", start_pin_name="Open")

        print_block = engine.blocks["print"]
        assert print_block.last_printed == "RESP_OK"
        mock_ser.close.assert_called()


@pytest.mark.asyncio
async def test_serial_visa_interoperability():
    """
    Verifies that the Device handle from Serial Device can be fed directly
    into VISA Query without modification or failure.
    """
    with patch("comfylab.blocks.serial_device.serial.Serial") as mock_serial_cls:
        mock_ser = MagicMock()
        mock_ser.is_open = True
        mock_ser.write.return_value = 6
        mock_ser.read_until.return_value = b"ACME,DMM,001,v2\n"
        mock_serial_cls.return_value = mock_ser

        blueprint = {
            "blocks": [
                {
                    "id": "ser_dev",
                    "type": "serial/core/device",
                    "properties": {
                        "Port": "COM3",
                        "BaudRate": 57600,
                    }
                },
                {
                    "id": "visa_query",
                    "type": "visa/core/query",
                    "properties": {
                        "Command": "*IDN?"
                    }
                },
                {
                    "id": "print",
                    "type": "outputs/basic/print",
                    "properties": {}
                }
            ],
            "links": [
                {"id": "l1", "type": "exec", "source_block": "ser_dev", "source_pin": "Out", "target_block": "visa_query", "target_pin": "In"},
                {"id": "l2", "type": "data", "source_block": "ser_dev", "source_pin": "Device", "target_block": "visa_query", "target_pin": "Device"},
                {"id": "l3", "type": "exec", "source_block": "visa_query", "source_pin": "Out", "target_block": "print", "target_pin": "In"},
                {"id": "l4", "type": "data", "source_block": "visa_query", "source_pin": "Response", "target_block": "print", "target_pin": "Value"},
            ]
        }

        engine = ExecutionEngine()
        engine.load_blueprint(blueprint)
        await engine.run(start_block_id="ser_dev", start_pin_name="Open")

        print_block = engine.blocks["print"]
        assert print_block.last_printed == "ACME,DMM,001,v2"
        mock_ser.close.assert_called()


@pytest.mark.asyncio
async def test_serial_list_ports_block():
    fake_port = MagicMock()
    fake_port.device = "/dev/ttyUSB0"
    fake_port.description = "FTDI USB Serial Device"
    fake_port.hwid = "USB VID:PID=0403:6001"
    fake_port.manufacturer = "FTDI"
    fake_port.vid = 0x0403
    fake_port.pid = 0x6001

    with patch("comfylab.blocks.serial_device.serial.tools.list_ports.comports", return_value=[fake_port]):
        ports = get_available_serial_ports("All")
        assert len(ports) == 1
        assert ports[0]["port"] == "/dev/ttyUSB0"

        blueprint = {
            "blocks": [
                {
                    "id": "list_block",
                    "type": "serial/core/list_ports",
                    "properties": {
                        "Filter": "All"
                    }
                },
                {
                    "id": "print",
                    "type": "outputs/basic/print",
                    "properties": {}
                }
            ],
            "links": [
                {"id": "l1", "type": "exec", "source_block": "list_block", "source_pin": "Out", "target_block": "print", "target_pin": "In"},
                {"id": "l2", "type": "data", "source_block": "list_block", "source_pin": "FirstPort", "target_block": "print", "target_pin": "Value"},
            ]
        }

        engine = ExecutionEngine()
        engine.load_blueprint(blueprint)
        await engine.run(start_block_id="list_block", start_pin_name="In")

        print_block = engine.blocks["print"]
        assert print_block.last_printed == "/dev/ttyUSB0"
