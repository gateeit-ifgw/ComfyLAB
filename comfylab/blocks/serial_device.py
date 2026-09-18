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

import sys
import time
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Union

import serial
import serial.tools.list_ports

from comfylab.engine.registry import register_block
from comfylab.blocks.base import BaseBlock, ExecIn, ExecOut, DataIn, DataOut, ExecutionContext
from comfylab.blocks.visa import locked_device

logger = logging.getLogger("comfylab.blocks.serial")


def normalize_serial_port(port_str: str) -> str:
    """
    Normalizes a port name or VISA alias to a canonical serial port path.
    Examples:
      - 'ASRL/dev/ttyUSB0::INSTR' -> '/dev/ttyUSB0'
      - 'ASRL::COM3::INSTR' -> 'COM3'
      - 'ASRL3::INSTR' -> 'COM3' (on Windows) or '/dev/ttyS2' (on Linux)
      - 'com1' -> 'COM1'
      - '/dev/ttyACM0' -> '/dev/ttyACM0'
    """
    if not port_str:
        return port_str
    clean = str(port_str).strip()

    # ASRL/dev/ttyUSB0::INSTR -> /dev/ttyUSB0
    m_dev = re.match(r"^ASRL(/dev/[^:]+)(?:::[^:]+)?$", clean, re.IGNORECASE)
    if m_dev:
        return m_dev.group(1)

    # ASRL::COM1::INSTR -> COM1
    m_com = re.match(r"^ASRL::(COM\d+)(?:::[^:]+)?$", clean, re.IGNORECASE)
    if m_com:
        return m_com.group(1).upper()

    # ASRL1::INSTR -> COM1 on Windows, /dev/ttyS0 on Linux
    m_asrl = re.match(r"^ASRL(\d+)(?:::[^:]+)?$", clean, re.IGNORECASE)
    if m_asrl:
        num = int(m_asrl.group(1))
        if sys.platform == "win32":
            return f"COM{num}"
        else:
            return f"/dev/ttyS{num - 1}" if num >= 1 else f"/dev/ttyS{num}"

    # Standard COM1 -> COM1
    if re.match(r"^COM\d+$", clean, re.IGNORECASE):
        return clean.upper()

    return clean


BYTESIZE_MAP = {
    8: serial.EIGHTBITS,
    7: serial.SEVENBITS,
    6: serial.SIXBITS,
    5: serial.FIVEBITS,
}

PARITY_MAP = {
    "None": serial.PARITY_NONE,
    "Odd": serial.PARITY_ODD,
    "Even": serial.PARITY_EVEN,
    "Mark": serial.PARITY_MARK,
    "Space": serial.PARITY_SPACE,
}

STOPBITS_MAP = {
    "1": serial.STOPBITS_ONE,
    "1.5": serial.STOPBITS_ONE_POINT_FIVE,
    "2": serial.STOPBITS_TWO,
}


class ManagedSerialDevice:
    """
    Resilient wrapper around a PySerial Serial handle.
    Provides:
    1. Full control of baud rate, data bits, parity, stop bits, flow control, and line terminators.
    2. Duck-type compatibility with ComfyLAB's PyVISA instruments:
       implements write(), read(), read_raw(), query(), clear(), and resource_name.
    3. Thread-safe resource locking integration.
    4. Auto-reconnect capabilities if connection is dropped or cable is re-plugged.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        bytesize: int = 8,
        parity: str = "None",
        stopbits: str = "1",
        flow_control: str = "None",
        read_termination: str = "\n",
        write_termination: str = "\n",
        timeout: float = 2.0,
        dtr: Optional[bool] = None,
        rts: Optional[bool] = None,
    ):
        self.port = normalize_serial_port(port)
        self.baudrate = int(baudrate)
        self.bytesize_val = bytesize
        self.parity_val = parity
        self.stopbits_val = stopbits
        self.flow_control_val = flow_control
        self.read_termination = read_termination
        self.write_termination = write_termination
        self.timeout = float(timeout)
        self.dtr_val = dtr
        self.rts_val = rts

        self._ser: Optional[serial.Serial] = None
        self._open()

    def _open(self) -> serial.Serial:
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

        bytesize = BYTESIZE_MAP.get(int(self.bytesize_val), serial.EIGHTBITS)
        parity = PARITY_MAP.get(str(self.parity_val).capitalize(), serial.PARITY_NONE)
        stopbits = STOPBITS_MAP.get(str(self.stopbits_val), serial.STOPBITS_ONE)

        fc = str(self.flow_control_val).upper()
        xonxoff = "XON" in fc
        rtscts = "RTS" in fc or "CTS" in fc
        dsrdtr = "DSR" in fc or "DTR" in fc

        ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=self.timeout,
            write_timeout=self.timeout,
            xonxoff=xonxoff,
            rtscts=rtscts,
            dsrdtr=dsrdtr,
        )

        if self.dtr_val is not None:
            try:
                ser.dtr = bool(self.dtr_val)
            except Exception as e:
                logger.debug(f"Could not set DTR on {self.port}: {e}")

        if self.rts_val is not None:
            try:
                ser.rts = bool(self.rts_val)
            except Exception as e:
                logger.debug(f"Could not set RTS on {self.port}: {e}")

        self._ser = ser
        logger.info(f"Opened serial connection on {self.port} at {self.baudrate} baud.")
        return ser

    @property
    def resource_name(self) -> str:
        return self.port

    @property
    def raw_device(self) -> Optional[serial.Serial]:
        return self._ser

    def is_alive(self) -> bool:
        return self._ser is not None and getattr(self._ser, "is_open", False)

    def reconnect(self) -> serial.Serial:
        logger.info(f"Reconnecting serial port at {self.port}...")
        return self._open()

    def clear(self) -> bool:
        """Flushes both input and output serial buffers."""
        if self._ser is None:
            return False
        try:
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            return True
        except Exception as e:
            logger.debug(f"Serial clear failed on {self.port}: {e}")
            return False

    def close(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception as e:
                logger.debug(f"Error closing serial port {self.port}: {e}")
            finally:
                self._ser = None

    def write(self, data: Union[str, bytes]) -> int:
        """
        Writes data to the serial port.
        If a string is passed, automatically appends write_termination and encodes as UTF-8.
        """
        if self._ser is None or not self._ser.is_open:
            raise ConnectionError(f"Serial port {self.port} is not open.")

        if isinstance(data, str):
            payload = data
            if self.write_termination and not payload.endswith(self.write_termination):
                payload += self.write_termination
            raw = payload.encode("utf-8", errors="replace")
        elif isinstance(data, (bytes, bytearray)):
            raw = bytes(data)
        else:
            raw = str(data).encode("utf-8", errors="replace")

        try:
            bytes_written = self._ser.write(raw)
            self._ser.flush()
            return bytes_written
        except Exception as e:
            logger.warning(f"Error writing to serial port {self.port}: {e}. Attempting buffer clear.")
            self.clear()
            raise e

    def read(self) -> str:
        """
        Reads from the serial port until read_termination is encountered or timeout occurs.
        Returns the decoded string response.
        """
        if self._ser is None or not self._ser.is_open:
            raise ConnectionError(f"Serial port {self.port} is not open.")

        term_bytes = self.read_termination.encode("utf-8", errors="replace") if self.read_termination else b"\n"
        try:
            raw = self._ser.read_until(expected=term_bytes)
            if not raw:
                raise TimeoutError(f"Serial read timed out on {self.port} after {self.timeout}s.")
            text = raw.decode("utf-8", errors="replace")
            if self.read_termination and text.endswith(self.read_termination):
                text = text[:-len(self.read_termination)]
            return text
        except Exception as e:
            logger.warning(f"Error reading from serial port {self.port}: {e}")
            self.clear()
            raise e

    def read_raw(self, size: Optional[int] = None) -> bytes:
        """Reads raw bytes directly from the serial port."""
        if self._ser is None or not self._ser.is_open:
            raise ConnectionError(f"Serial port {self.port} is not open.")

        try:
            if size is not None and size > 0:
                return self._ser.read(size)
            waiting = self._ser.in_waiting
            if waiting > 0:
                return self._ser.read(waiting)
            # Default read up to standard buffer or 1 byte if waiting is 0
            return self._ser.read(1)
        except Exception as e:
            logger.warning(f"Error reading raw bytes from serial port {self.port}: {e}")
            self.clear()
            raise e

    def query(self, command: str, delay_sec: float = 0.0) -> str:
        """Writes command, waits optional delay, and reads response line."""
        self.write(command)
        if delay_sec > 0:
            time.sleep(delay_sec)
        return self.read()

    def __getattr__(self, name: str) -> Any:
        if self._ser is not None and hasattr(self._ser, name):
            return getattr(self._ser, name)
        raise AttributeError(f"'ManagedSerialDevice' has no attribute '{name}'")


# ---------------------------------------------------------------------------
# BLOCK DEFINITIONS
# ---------------------------------------------------------------------------

@register_block("serial/core/device")
class SerialDeviceBlock(BaseBlock):
    """Opens a serial port (RS-232/USB-UART/COM) with configurable baud rate and framing."""
    icon = "🔌"
    category = "Instruments/Serial"
    display_name = "Serial Device"
    description = "Opens a connection to a serial COM/tty port and outputs the device connection handle."

    inputs_def = [
        ExecIn("Open"),
        # Only Port and BaudRate are non-optional (visible by default)
        DataIn(
            "Port",
            type_hint=str,
            default="COM1" if sys.platform == "win32" else "/dev/ttyUSB0",
            widget="text",
            optional=False
        ),
        DataIn(
            "BaudRate",
            type_hint=int,
            default=115200,
            widget="dropdown",
            options=[9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600],
            optional=False
        ),
        # Advanced/rarely modified framing settings are optional
        DataIn(
            "DataBits",
            type_hint=int,
            default=8,
            widget="dropdown",
            options=[8, 7, 6, 5],
            optional=True
        ),
        DataIn(
            "StopBits",
            type_hint=str,
            default="1",
            widget="dropdown",
            options=["1", "1.5", "2"],
            optional=True
        ),
        DataIn(
            "Parity",
            type_hint=str,
            default="None",
            widget="dropdown",
            options=["None", "Odd", "Even", "Mark", "Space"],
            optional=True
        ),
        DataIn(
            "FlowControl",
            type_hint=str,
            default="None",
            widget="dropdown",
            options=["None", "RTS/CTS", "XON/XOFF", "DSR/DTR"],
            optional=True
        ),
        DataIn("ReadTermination", type_hint=str, default="\n", widget="text", optional=True),
        DataIn("WriteTermination", type_hint=str, default="\n", widget="text", optional=True),
        DataIn("Timeout", type_hint=float, default=2.0, widget="number", optional=True),
        DataIn("DTR", type_hint=bool, default=True, widget="toggle", optional=True),
        DataIn("RTS", type_hint=bool, default=True, widget="toggle", optional=True),
    ]

    outputs_def = [
        ExecOut("Out"),
        DataOut("Device", type_hint=Any),
        DataOut("Port", type_hint=str),
    ]

    i18n = {
        "pt-BR": {
            "display_name": "Dispositivo Serial",
            "description": "Abre uma conexão com uma porta serial COM/tty e fornece o identificador de conexão.",
            "category": "Instrumentos/Serial",
            "pins": {
                "Open": "Abrir",
                "Port": "Porta",
                "BaudRate": "Taxa de Baud",
                "DataBits": "Bits de Dados",
                "StopBits": "Bits de Parada",
                "Parity": "Paridade",
                "FlowControl": "Controle de Fluxo",
                "ReadTermination": "Terminação de Leitura",
                "WriteTermination": "Terminação de Escrita",
                "Timeout": "Tempo Limite",
                "DTR": "DTR",
                "RTS": "RTS",
                "Out": "Saída",
                "Device": "Dispositivo"
            }
        },
        "es": {
            "display_name": "Dispositivo Serial",
            "description": "Abre una conexión con un puerto serie COM/tty y emite el identificador de conexión del dispositivo.",
            "category": "Instrumentos/Serial",
            "pins": {
                "Open": "Abrir",
                "Port": "Puerto",
                "BaudRate": "Tasa de Baudios",
                "DataBits": "Bits de Datos",
                "StopBits": "Bits de Parada",
                "Parity": "Paridad",
                "FlowControl": "Control de Flujo",
                "ReadTermination": "Terminación de Lectura",
                "WriteTermination": "Terminación de Escritura",
                "Timeout": "Tiempo de Espera",
                "DTR": "DTR",
                "RTS": "RTS",
                "Out": "Salida",
                "Device": "Dispositivo"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._device: Optional[ManagedSerialDevice] = None
        self._port_name: str = ""

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        port = await context.pull(self.id, "Port")
        if not port:
            raise ValueError("No port specified for Serial Device block.")

        baud = await context.pull(self.id, "BaudRate") or 115200
        data_bits = await context.pull(self.id, "DataBits") or 8
        stop_bits = await context.pull(self.id, "StopBits") or "1"
        parity = await context.pull(self.id, "Parity") or "None"
        flow = await context.pull(self.id, "FlowControl") or "None"
        read_term = await context.pull(self.id, "ReadTermination")
        write_term = await context.pull(self.id, "WriteTermination")
        timeout = await context.pull(self.id, "Timeout")
        dtr = await context.pull(self.id, "DTR")
        rts = await context.pull(self.id, "RTS")

        if read_term is None:
            read_term = "\n"
        elif isinstance(read_term, str):
            read_term = read_term.replace("\\r", "\r").replace("\\n", "\n")

        if write_term is None:
            write_term = "\n"
        elif isinstance(write_term, str):
            write_term = write_term.replace("\\r", "\r").replace("\\n", "\n")

        timeout_sec = float(timeout) if timeout is not None else 2.0
        norm_port = normalize_serial_port(port)
        self._port_name = norm_port

        # Open serial port safely under per-port resource lock
        async with context.lock_manager.acquire(norm_port):
            if self._device is not None:
                try:
                    await asyncio.to_thread(self._device.close)
                except Exception:
                    pass
                self._device = None

            self._device = await asyncio.to_thread(
                ManagedSerialDevice,
                port=norm_port,
                baudrate=int(baud),
                bytesize=int(data_bits),
                parity=str(parity),
                stopbits=str(stop_bits),
                flow_control=str(flow),
                read_termination=read_term,
                write_termination=write_term,
                timeout=timeout_sec,
                dtr=dtr,
                rts=rts,
            )

        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Device":
            return self._device
        elif pin_name == "Port":
            return self._port_name
        return None

    async def teardown(self):
        if self._device is not None:
            try:
                await asyncio.to_thread(self._device.close)
                logger.info(f"Closed serial port {self._port_name} on teardown.")
            except Exception as e:
                logger.error(f"Error closing serial port on teardown: {e}")
            finally:
                self._device = None


@register_block("serial/core/write")
class SerialWriteBlock(BaseBlock):
    """Sends raw text or bytes to an open serial device."""
    icon = "✍️"
    category = "Instruments/Serial"
    display_name = "Serial Write"
    description = "Writes a string or data to the given Serial/VISA device handle."

    inputs_def = [
        ExecIn("In"),
        DataIn("Device", type_hint=Any),
        DataIn("Data", type_hint=str, default="", widget="text"),
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Device", type_hint=Any),
        DataOut("BytesWritten", type_hint=int),
    ]

    i18n = {
        "pt-BR": {
            "display_name": "Escrita Serial",
            "description": "Escreve uma string ou dados no handle do dispositivo Serial/VISA fornecido.",
            "category": "Instrumentos/Serial",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "Data": "Dados",
                "Out": "Saída",
                "BytesWritten": "Bytes Escritos"
            }
        },
        "es": {
            "display_name": "Escritura Serial",
            "description": "Escribe una cadena o datos en el identificador del dispositivo Serial/VISA proporcionado.",
            "category": "Instrumentos/Serial",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "Data": "Datos",
                "Out": "Salida",
                "BytesWritten": "Bytes Escritos"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._bytes_written = 0

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        device = await context.pull(self.id, "Device")
        data = await context.pull(self.id, "Data")
        if data is None:
            data = ""

        async with locked_device(context, device, "Serial Write") as dev:
            res = await asyncio.to_thread(dev.write, data)
            self._bytes_written = res if isinstance(res, int) else len(str(data))

        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Device":
            return await context.pull(self.id, "Device")
        elif pin_name == "BytesWritten":
            return self._bytes_written
        return None


@register_block("serial/core/read")
class SerialReadBlock(BaseBlock):
    """Reads response data from an open serial device."""
    icon = "📖"
    category = "Instruments/Serial"
    display_name = "Serial Read"
    description = "Reads a line or raw bytes from the given Serial/VISA device handle."

    inputs_def = [
        ExecIn("In"),
        DataIn("Device", type_hint=Any),
        DataIn(
            "Mode",
            type_hint=str,
            default="Line",
            widget="dropdown",
            options=["Line", "Raw Bytes", "All Available"],
            optional=True
        ),
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Response", type_hint=str),
        DataOut("RawBytes", type_hint=bytes),
        DataOut("Device", type_hint=Any),
    ]

    i18n = {
        "pt-BR": {
            "display_name": "Leitura Serial",
            "description": "Lê uma linha ou bytes brutos do handle do dispositivo Serial/VISA fornecido.",
            "category": "Instrumentos/Serial",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "Mode": "Modo",
                "Out": "Saída",
                "Response": "Resposta",
                "RawBytes": "Bytes Brutos"
            }
        },
        "es": {
            "display_name": "Lectura Serial",
            "description": "Lee una línea o bytes sin procesar del identificador del dispositivo Serial/VISA proporcionado.",
            "category": "Instrumentos/Serial",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "Mode": "Modo",
                "Out": "Salida",
                "Response": "Respuesta",
                "RawBytes": "Bytes Crudos"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._last_response = ""
        self._last_raw = b""

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        device = await context.pull(self.id, "Device")
        mode = await context.pull(self.id, "Mode") or "Line"

        async with locked_device(context, device, "Serial Read") as dev:
            if mode == "Raw Bytes" and hasattr(dev, "read_raw"):
                raw = await asyncio.to_thread(dev.read_raw)
                self._last_raw = raw
                self._last_response = raw.decode("utf-8", errors="replace")
            elif mode == "All Available" and hasattr(dev, "raw_device") and hasattr(dev.raw_device, "in_waiting"):
                waiting = dev.raw_device.in_waiting
                raw = await asyncio.to_thread(dev.read_raw, waiting) if waiting > 0 else b""
                self._last_raw = raw
                self._last_response = raw.decode("utf-8", errors="replace")
            else:
                resp = await asyncio.to_thread(dev.read)
                self._last_response = resp
                self._last_raw = resp.encode("utf-8", errors="replace")

        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Response":
            return self._last_response
        elif pin_name == "RawBytes":
            return self._last_raw
        elif pin_name == "Device":
            return await context.pull(self.id, "Device")
        return None


@register_block("serial/core/query")
class SerialQueryBlock(BaseBlock):
    """Writes a command to a serial device and reads back the response line."""
    icon = "❓"
    category = "Instruments/Serial"
    display_name = "Serial Query"
    description = "Writes a command to a Serial/VISA device and reads the response line."

    inputs_def = [
        ExecIn("In"),
        DataIn("Device", type_hint=Any),
        DataIn("Command", type_hint=str, default="", widget="text"),
        DataIn("Delay", type_hint=float, default=0.0, widget="number", optional=True),
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Response", type_hint=str),
        DataOut("Device", type_hint=Any),
    ]

    i18n = {
        "pt-BR": {
            "display_name": "Consulta Serial",
            "description": "Envia um comando para um dispositivo Serial/VISA e lê a linha de resposta.",
            "category": "Instrumentos/Serial",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "Command": "Comando",
                "Delay": "Atraso",
                "Out": "Saída",
                "Response": "Resposta"
            }
        },
        "es": {
            "display_name": "Consulta Serial",
            "description": "Envía un comando a un dispositivo Serial/VISA y lee la línea de respuesta.",
            "category": "Instrumentos/Serial",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "Command": "Comando",
                "Delay": "Retardo",
                "Out": "Salida",
                "Response": "Respuesta"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._last_response = ""

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        device = await context.pull(self.id, "Device")
        command = await context.pull(self.id, "Command")
        delay = await context.pull(self.id, "Delay") or 0.0

        if not command:
            raise ValueError("No command string supplied to Serial Query block.")

        async with locked_device(context, device, "Serial Query") as dev:
            if hasattr(dev, "query"):
                # If ManagedSerialDevice with delay support
                if isinstance(dev, ManagedSerialDevice):
                    self._last_response = await asyncio.to_thread(dev.query, command, float(delay))
                else:
                    if float(delay) > 0:
                        await asyncio.to_thread(dev.write, command)
                        await asyncio.sleep(float(delay))
                        self._last_response = await asyncio.to_thread(dev.read)
                    else:
                        self._last_response = await asyncio.to_thread(dev.query, command)
            else:
                await asyncio.to_thread(dev.write, command)
                if float(delay) > 0:
                    await asyncio.sleep(float(delay))
                self._last_response = await asyncio.to_thread(dev.read)

        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Response":
            return self._last_response
        elif pin_name == "Device":
            return await context.pull(self.id, "Device")
        return None


def get_available_serial_ports(filter_mode: str = "All") -> List[Dict[str, Any]]:
    """
    Scans the system for serial ports using serial.tools.list_ports.comports().
    Supports fast filtering:
      - 'All': Returns all detected COM/tty ports.
      - 'USB Only': Returns ports containing USB in hardware ID or description.
      - 'USB, FTDI, Arduino': Prioritizes USB-serial converters, FTDI, CP210x, CH340, Arduino.
    """
    raw_ports = serial.tools.list_ports.comports()
    results = []
    filter_mode_clean = (filter_mode or "All").strip().lower()

    for p in raw_ports:
        dev = p.device or ""
        desc = p.description or ""
        hwid = p.hwid or ""
        mfr = p.manufacturer or ""
        full_info = f"{dev} {desc} {hwid} {mfr}".lower()

        # Filtering logic
        if filter_mode_clean == "all":
            include = True
        elif filter_mode_clean == "usb only":
            include = "usb" in full_info
        else:  # "usb, ftdi, arduino" or default
            include = any(k in full_info for k in ["usb", "ftdi", "ch340", "cp210", "arduino", "acm", "prolific"])
            # If nothing matched and dev starts with /dev/ttyUSB or /dev/ttyACM or COM, include
            if not include and (dev.startswith("/dev/ttyUSB") or dev.startswith("/dev/ttyACM") or re.match(r"^COM\d+$", dev, re.IGNORECASE)):
                include = True

        if include:
            results.append({
                "port": dev,
                "description": desc,
                "hwid": hwid,
                "manufacturer": mfr,
                "vid": getattr(p, "vid", None),
                "pid": getattr(p, "pid", None),
            })

    return results


@register_block("serial/core/list_ports")
class SerialListPortsBlock(BaseBlock):
    """Enumerates connected serial / COM / USB-UART ports on the system."""
    icon = "📋"
    category = "Instruments/Serial"
    display_name = "Serial List Ports"
    description = "Queries the operating system and outputs a list of available serial COM and tty ports."

    inputs_def = [
        ExecIn("In"),
        DataIn(
            "Filter",
            type_hint=str,
            default="USB, FTDI, Arduino",
            widget="dropdown",
            options=["USB, FTDI, Arduino", "USB Only", "All"],
            optional=True
        ),
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Ports", type_hint=list),
        DataOut("PortDetails", type_hint=list),
        DataOut("FirstPort", type_hint=str),
    ]

    i18n = {
        "pt-BR": {
            "display_name": "Listar Portas Seriais",
            "description": "Consulta o sistema operacional e retorna uma lista de portas seriais COM e tty disponíveis.",
            "category": "Instrumentos/Serial",
            "pins": {
                "In": "Entrada",
                "Filter": "Filtro",
                "Out": "Saída",
                "Ports": "Portas",
                "PortDetails": "Detalhes das Portas",
                "FirstPort": "Primeira Porta"
            }
        },
        "es": {
            "display_name": "Listar Puertos Serie",
            "description": "Consulta el sistema operativo y devuelve una lista de puertos serie COM y tty disponibles.",
            "category": "Instrumentos/Serial",
            "pins": {
                "In": "Entrada",
                "Filter": "Filtro",
                "Out": "Salida",
                "Ports": "Puertos",
                "PortDetails": "Detalles de Puertos",
                "FirstPort": "Primer Puerto"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._ports: List[str] = []
        self._details: List[Dict[str, Any]] = []
        self._first_port: str = ""

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        filter_mode = await context.pull(self.id, "Filter") or "USB, FTDI, Arduino"
        details = await asyncio.to_thread(get_available_serial_ports, filter_mode)
        self._details = details
        self._ports = [d["port"] for d in details]
        self._first_port = self._ports[0] if self._ports else ""
        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Ports":
            return self._ports
        elif pin_name == "PortDetails":
            return self._details
        elif pin_name == "FirstPort":
            return self._first_port
        return None

    async def clear_data(self) -> None:
        self._ports = []
        self._details = []
        self._first_port = ""
