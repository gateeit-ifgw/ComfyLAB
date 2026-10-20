# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import asyncio
import logging
from typing import Any, Dict, Optional

from comfylab.blocks.base import BaseBlock, ExecIn, ExecOut, DataIn, DataOut, ExecutionContext
from comfylab.blocks.visa import visa_rm_wrapper, locked_device, ManagedVISADevice

logger = logging.getLogger("comfylab.blocks.devices.base")


class BaseDeviceBlock(BaseBlock):
    """
    Base class for manufacturer-specific hardware instrument blocks in ComfyLAB.
    Sets is_device = True for dynamic library discovery and filtering.
    """
    is_device: bool = True


class BaseDeviceConnectBlock(BaseDeviceBlock):
    """
    Base class for device connect blocks in ComfyLAB.
    Opens a VISA connection to the configured address, runs `_device_initialize`,
    and on teardown executes `_device_teardown` before closing the connection.
    """
    icon = "🔗"
    display_name = "Device Connect"
    description = "Opens a VISA connection with device-specific init/teardown hooks."
    is_device: bool = True

    inputs_def = [
        ExecIn("Open"),
        DataIn("Address", type_hint=str, default="GPIB0::2::INSTR", widget="text"),
        DataIn("ReadTermination", type_hint=str, default="\n", optional=True),
        DataIn("WriteTermination", type_hint=str, default="\n", optional=True),
        DataIn("Timeout", type_hint=float, default=2.0, optional=True)
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Device", type_hint=Any)
    ]
    i18n = {
        "pt-BR": {
            "display_name": "Conectar Dispositivo",
            "description": "Abre uma conexão VISA com ganchos de inicialização/desconexão específicos do dispositivo.",
            "pins": {
                "Open": "Abrir",
                "Address": "Endereço",
                "Out": "Saída",
                "Device": "Dispositivo"
            }
        },
        "es": {
            "display_name": "Conectar Dispositivo",
            "description": "Abre una conexión VISA con ganchos de inicialización/desconexión específicos del dispositivo.",
            "pins": {
                "Open": "Abrir",
                "Address": "Dirección",
                "Out": "Salida",
                "Device": "Dispositivo"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._device = None
        self._lock_manager = None

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        address = await context.pull(self.id, "Address")
        if not address:
            raise ValueError("No address specified for Device Connect block.")

        read_term = await context.pull(self.id, "ReadTermination")
        write_term = await context.pull(self.id, "WriteTermination")
        timeout_sec = await context.pull(self.id, "Timeout")

        rm = visa_rm_wrapper.get_rm()

        # Build kwargs for open_resource
        kwargs = {}
        if read_term is not None and read_term != "":
            if isinstance(read_term, str):
                read_term = read_term.replace("\\r", "\r").replace("\\n", "\n")
            kwargs["read_termination"] = read_term
        if write_term is not None and write_term != "":
            if isinstance(write_term, str):
                write_term = write_term.replace("\\r", "\r").replace("\\n", "\n")
            kwargs["write_termination"] = write_term
        if timeout_sec is not None:
            kwargs["timeout"] = int(timeout_sec * 1000)

        # Open VISA resource under per-address resource lock
        async with context.lock_manager.acquire(address):
            if self._device is not None:
                try:
                    await asyncio.to_thread(self._device.close)
                except Exception:
                    pass
                self._device = None

            self._device = await asyncio.to_thread(ManagedVISADevice, rm, address, **kwargs)
            self._lock_manager = context.lock_manager
            await self._device_initialize(self._device)

        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Device":
            return self._device
        return None

    async def _device_initialize(self, device: Any) -> None:
        """Hook for subclasses to execute device setup after connection opens."""
        pass

    async def _device_teardown(self, device: Any, lock_manager: Any) -> None:
        """Hook for subclasses to send safety commands on teardown."""
        pass

    async def safe_state(self) -> None:
        """Sends the `_device_teardown` safety commands while keeping the connection open."""
        if self._device:
            await self._device_teardown(self._device, self._lock_manager)

    async def teardown(self) -> None:
        if self._device:
            try:
                await self.safe_state()
            except Exception as e:
                logger.warning(f"Error in device teardown hook: {e}")

            try:
                await asyncio.to_thread(self._device.close)
                logger.info("Closed device VISA session.")
            except Exception as e:
                logger.error(f"Error closing device VISA session: {e}")
            finally:
                self._device = None
