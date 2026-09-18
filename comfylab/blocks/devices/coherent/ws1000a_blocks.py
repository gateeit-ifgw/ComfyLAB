# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
ComfyLAB Visual Automation Blocks for the Coherent / Finisar WaveShaper 1000A Optical Filter.
Provides drag-and-drop nodes for connecting, configuring filters, uploading profiles, and reading spectrum states.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Sequence
import numpy as np

from comfylab.engine.registry import register_block
from comfylab.blocks.base import BaseBlock, ExecIn, ExecOut, DataIn, DataOut, ExecutionContext
from comfylab.blocks.devices.base import BaseDeviceBlock, locked_device
from comfylab.devices.coherent.ws1000a import WaveShaper1000A

logger = logging.getLogger("comfylab.blocks.devices.coherent.ws1000a")


@register_block("devices/coherent/ws1000a/connect")
class WaveShaper1000AConnectBlock(BaseDeviceBlock):
    """Opens a connection to a Coherent / Finisar WaveShaper 1000A Optical Filter via HTTP web API."""
    icon = "🌈"
    display_name = "Coherent WaveShaper 1000A Connect"
    description = "Opens a connection to a Coherent / Finisar WaveShaper 1000A Optical Filter via its embedded HTTP web API."

    inputs_def = [
        ExecIn("Open"),
        DataIn("Host", type_hint=str, default="169.254.6.8", widget="text"),
        DataIn("Port", type_hint=int, default=80, optional=True),
        DataIn("Timeout", type_hint=float, default=5.0, optional=True),
        DataIn("SafetyBlockOnTeardown", type_hint=bool, default=False, widget="checkbox", optional=True)
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Device", type_hint=Any),
        DataOut("Model", type_hint=str),
        DataOut("Serial", type_hint=str),
        DataOut("StartWavelengthNM", type_hint=float),
        DataOut("StopWavelengthNM", type_hint=float),
        DataOut("StartFreqTHz", type_hint=float),
        DataOut("StopFreqTHz", type_hint=float)
    ]

    i18n = {
        "pt-BR": {
            "category": "Instrumentos/Coherent",
            "display_name": "Conectar Coherent WaveShaper 1000A",
            "description": "Abre conexão com o Filtro Óptico Programável Coherent / Finisar WaveShaper 1000A via API web HTTP.",
            "pins": {
                "Open": "Abrir",
                "Host": "IP / Host",
                "Port": "Porta HTTP",
                "Timeout": "Tempo Limite (s)",
                "SafetyBlockOnTeardown": "Bloquear na Desconexão (Segurança)",
                "Out": "Saída",
                "Device": "Dispositivo",
                "Model": "Modelo",
                "Serial": "Número de Série",
                "StartWavelengthNM": "Comp. Onda Inicial (nm)",
                "StopWavelengthNM": "Comp. Onda Final (nm)",
                "StartFreqTHz": "Freq. Inicial (THz)",
                "StopFreqTHz": "Freq. Final (THz)"
            }
        },
        "es": {
            "category": "Instrumentos/Coherent",
            "display_name": "Conectar Coherent WaveShaper 1000A",
            "description": "Abre conexión con el Filtro Óptico Programable Coherent / Finisar WaveShaper 1000A vía API web HTTP.",
            "pins": {
                "Open": "Abrir",
                "Host": "IP / Host",
                "Port": "Puerto HTTP",
                "Timeout": "Tiempo Límite (s)",
                "SafetyBlockOnTeardown": "Bloquear al Desconectar (Seguridad)",
                "Out": "Salida",
                "Device": "Dispositivo",
                "Model": "Modelo",
                "Serial": "Número de Serie",
                "StartWavelengthNM": "Long. Onda Inicial (nm)",
                "StopWavelengthNM": "Long. Onda Final (nm)",
                "StartFreqTHz": "Frec. Inicial (THz)",
                "StopFreqTHz": "Frec. Final (THz)"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._device: Optional[WaveShaper1000A] = None
        self._model: str = ""
        self._sno: str = ""
        self._start_wl_nm: float = 0.0
        self._stop_wl_nm: float = 0.0
        self._start_freq_thz: float = 0.0
        self._stop_freq_thz: float = 0.0
        self._safety_block: bool = False
        self._lock_manager: Any = None

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        host = await context.pull(self.id, "Host")
        port = await context.pull(self.id, "Port")
        timeout = await context.pull(self.id, "Timeout")
        safety_block = await context.pull(self.id, "SafetyBlockOnTeardown")

        if not host:
            host = "169.254.6.8"
        p_val = int(port) if port is not None else 80
        t_val = float(timeout) if timeout is not None else 5.0

        self._safety_block = bool(safety_block)
        self._lock_manager = context.lock_manager

        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None

        drv = WaveShaper1000A(host=str(host), port=p_val, timeout=t_val)

        # Query device info to verify connection and store limits
        async with context.lock_manager.acquire(drv.resource_name):
            info = await asyncio.to_thread(drv.get_devinfo)

        self._device = drv
        self._model = str(info.get("model", "WaveShaper 1000A"))
        self._sno = str(info.get("sno", ""))
        self._start_freq_thz = float(info.get("startfreq", 191.250))
        self._stop_freq_thz = float(info.get("stopfreq", 196.275))

        # High frequency corresponds to short wavelength
        f_min = min(self._start_freq_thz, self._stop_freq_thz)
        f_max = max(self._start_freq_thz, self._stop_freq_thz)
        self._start_wl_nm = float(WaveShaper1000A.thz_to_nm(f_max))
        self._stop_wl_nm = float(WaveShaper1000A.thz_to_nm(f_min))

        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Device":
            return self._device
        elif pin_name == "Model":
            return self._model
        elif pin_name == "Serial":
            return self._sno
        elif pin_name == "StartWavelengthNM":
            return self._start_wl_nm
        elif pin_name == "StopWavelengthNM":
            return self._stop_wl_nm
        elif pin_name == "StartFreqTHz":
            return self._start_freq_thz
        elif pin_name == "StopFreqTHz":
            return self._stop_freq_thz
        return None

    async def teardown(self) -> None:
        if self._device:
            try:
                if self._safety_block and self._lock_manager:
                    async with self._lock_manager.acquire(self._device.resource_name, timeout=3.0):
                        await asyncio.to_thread(self._device.set_block_all)
                        logger.info("Safety block-all command sent to WaveShaper on teardown.")
            except Exception as e:
                logger.warning(f"Error executing safety teardown on WaveShaper: {e}")
            try:
                await asyncio.to_thread(self._device.close)
            except Exception:
                pass
            finally:
                self._device = None


@register_block("devices/coherent/ws1000a/get_info")
class WaveShaper1000AGetInfoBlock(BaseBlock):
    """Queries device parameters, serial number, firmware version, and optical bandwidth limits."""
    icon = "ℹ️"
    display_name = "WaveShaper 1000A Info"
    description = "Queries operating band limits, serial number, and firmware version from a WaveShaper 1000A."

    inputs_def = [
        ExecIn("In"),
        DataIn("Device", type_hint=Any)
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Device", type_hint=Any),
        DataOut("StartWavelengthNM", type_hint=float),
        DataOut("StopWavelengthNM", type_hint=float),
        DataOut("StartFreqTHz", type_hint=float),
        DataOut("StopFreqTHz", type_hint=float),
        DataOut("Model", type_hint=str),
        DataOut("Serial", type_hint=str),
        DataOut("Firmware", type_hint=str),
        DataOut("PortCount", type_hint=int)
    ]

    i18n = {
        "pt-BR": {
            "category": "Instrumentos/Coherent",
            "display_name": "Informações WaveShaper 1000A",
            "description": "Consulta os limites operacionais, número de série e versão de firmware de um WaveShaper 1000A.",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "Out": "Saída",
                "StartWavelengthNM": "Comp. Onda Inicial (nm)",
                "StopWavelengthNM": "Comp. Onda Final (nm)",
                "StartFreqTHz": "Freq. Inicial (THz)",
                "StopFreqTHz": "Freq. Final (THz)",
                "Model": "Modelo",
                "Serial": "Número de Série",
                "Firmware": "Versão Firmware",
                "PortCount": "Qtd. Portas"
            }
        },
        "es": {
            "category": "Instrumentos/Coherent",
            "display_name": "Información WaveShaper 1000A",
            "description": "Consulta los límites operativos, número de serie y versión de firmware de un WaveShaper 1000A.",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "Out": "Salida",
                "StartWavelengthNM": "Long. Onda Inicial (nm)",
                "StopWavelengthNM": "Long. Onda Final (nm)",
                "StartFreqTHz": "Frec. Inicial (THz)",
                "StopFreqTHz": "Frec. Final (THz)",
                "Model": "Modelo",
                "Serial": "Número de Serie",
                "Firmware": "Versión Firmware",
                "PortCount": "Cant. Puertos"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._start_wl_nm: float = 0.0
        self._stop_wl_nm: float = 0.0
        self._start_freq_thz: float = 0.0
        self._stop_freq_thz: float = 0.0
        self._model: str = ""
        self._sno: str = ""
        self._ver: str = ""
        self._port_count: int = 1

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        device = await context.pull(self.id, "Device")
        drv = device if isinstance(device, WaveShaper1000A) else WaveShaper1000A(str(device))

        async with locked_device(context, drv, "WaveShaper 1000A Info"):
            info = await asyncio.to_thread(drv.get_devinfo)

        self._model = str(info.get("model", "WaveShaper 1000A"))
        self._sno = str(info.get("sno", ""))
        self._ver = str(info.get("ver", ""))
        self._port_count = int(info.get("portcount", 1))
        self._start_freq_thz = float(info.get("startfreq", 191.250))
        self._stop_freq_thz = float(info.get("stopfreq", 196.275))

        f_min = min(self._start_freq_thz, self._stop_freq_thz)
        f_max = max(self._start_freq_thz, self._stop_freq_thz)
        self._start_wl_nm = float(WaveShaper1000A.thz_to_nm(f_max))
        self._stop_wl_nm = float(WaveShaper1000A.thz_to_nm(f_min))

        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Device":
            return await context.pull(self.id, "Device")
        elif pin_name == "StartWavelengthNM":
            return self._start_wl_nm
        elif pin_name == "StopWavelengthNM":
            return self._stop_wl_nm
        elif pin_name == "StartFreqTHz":
            return self._start_freq_thz
        elif pin_name == "StopFreqTHz":
            return self._stop_freq_thz
        elif pin_name == "Model":
            return self._model
        elif pin_name == "Serial":
            return self._sno
        elif pin_name == "Firmware":
            return self._ver
        elif pin_name == "PortCount":
            return self._port_count
        return None


@register_block("devices/coherent/ws1000a/predefined_filter")
class WaveShaper1000APredefinedFilterBlock(BaseBlock):
    """Configures predefined filter profiles (Bandpass, Bandstop, Gaussian, Transmit, Blockall) on a WaveShaper 1000A."""
    icon = "🎛️"
    display_name = "WaveShaper 1000A Predefined Filter"
    description = "Configures a standard optical filter profile (Bandpass, Bandstop, Gaussian, Transmit, or Blockall)."

    inputs_def = [
        ExecIn("In"),
        DataIn("Device", type_hint=Any),
        DataIn("FilterType", type_hint=str, default="bandpass", widget="dropdown", options=["bandpass", "bandstop", "gaussian", "transmit", "blockall"]),
        DataIn("Unit", type_hint=str, default="nm", widget="dropdown", options=["nm", "THz"]),
        DataIn("Center", type_hint=float, default=1550.0),
        DataIn("Bandwidth", type_hint=float, default=1.0),
        DataIn("Attenuation", type_hint=float, default=0.0),
        DataIn("Port", type_hint=int, default=1, widget="dropdown", options=[1, 0])
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Device", type_hint=Any),
        DataOut("Success", type_hint=bool)
    ]

    i18n = {
        "pt-BR": {
            "category": "Instrumentos/Coherent",
            "display_name": "Filtro Predefinido WaveShaper 1000A",
            "description": "Aplica um perfil de filtro óptico predefinido (Passa-faixa, Rejeita-faixa, Gaussiano, Transmitir Tudo, Bloquear Tudo).",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "FilterType": "Tipo de Filtro",
                "Unit": "Unidade",
                "Center": "Centro (nm ou THz)",
                "Bandwidth": "Largura de Banda",
                "Attenuation": "Atenuação (dB)",
                "Port": "Porta (1: Passa, 0: Bloqueio)",
                "Out": "Saída",
                "Success": "Sucesso"
            }
        },
        "es": {
            "category": "Instrumentos/Coherent",
            "display_name": "Filtro Predefinido WaveShaper 1000A",
            "description": "Aplica un perfil de filtro óptico predefinido (Pasa-banda, Rechaza-banda, Gaussiano, Transmitir Todo, Bloquear Todo).",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "FilterType": "Tipo de Filtro",
                "Unit": "Unidad",
                "Center": "Centro (nm o THz)",
                "Bandwidth": "Ancho de Banda",
                "Attenuation": "Atenuación (dB)",
                "Port": "Puerto (1: Pasa, 0: Bloqueo)",
                "Out": "Salida",
                "Success": "Éxito"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._success: bool = False

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        device = await context.pull(self.id, "Device")
        f_type = await context.pull(self.id, "FilterType")
        unit = await context.pull(self.id, "Unit")
        center = await context.pull(self.id, "Center")
        bandwidth = await context.pull(self.id, "Bandwidth")
        attn = await context.pull(self.id, "Attenuation")
        port = await context.pull(self.id, "Port")

        drv = device if isinstance(device, WaveShaper1000A) else WaveShaper1000A(str(device))
        unit_str = str(unit) if unit else "nm"
        p_val = int(port) if port is not None else 1
        a_val = float(attn) if attn is not None else 0.0

        async with locked_device(context, drv, "WaveShaper 1000A Predefined Filter"):
            await asyncio.to_thread(
                drv.load_predefined_profile,
                filter_type=str(f_type) if f_type else "bandpass",
                center=float(center) if center is not None else 1550.0,
                bandwidth=float(bandwidth) if bandwidth is not None else 1.0,
                attn_db=a_val,
                port=p_val,
                unit=unit_str
            )

        self._success = True
        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Device":
            return await context.pull(self.id, "Device")
        elif pin_name == "Success":
            return self._success
        return None


@register_block("devices/coherent/ws1000a/custom_filter")
class WaveShaper1000ACustomFilterBlock(BaseBlock):
    """Uploads an arbitrary optical filter profile from spectral and attenuation arrays to a WaveShaper 1000A."""
    icon = "📈"
    display_name = "WaveShaper 1000A Custom Filter"
    description = "Uploads an arbitrary optical filter profile defined by wavelength/frequency, attenuation, and phase arrays."

    inputs_def = [
        ExecIn("In"),
        DataIn("Device", type_hint=Any),
        DataIn("SpectralPoints", type_hint=Any, default=[]),
        DataIn("Attenuation", type_hint=Any, default=[]),
        DataIn("Phase", type_hint=Any, default=[], optional=True),
        DataIn("Unit", type_hint=str, default="nm", widget="dropdown", options=["nm", "THz"]),
        DataIn("Port", type_hint=int, default=1, widget="dropdown", options=[1, 0])
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Device", type_hint=Any),
        DataOut("Success", type_hint=bool)
    ]

    i18n = {
        "pt-BR": {
            "category": "Instrumentos/Coherent",
            "display_name": "Filtro Personalizado WaveShaper 1000A",
            "description": "Carrega um perfil de filtro óptico arbitrário a partir de vetores de comprimento de onda/frequência, atenuação e fase.",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "SpectralPoints": "Pontos Espectrais (nm ou THz)",
                "Attenuation": "Atenuação (dB)",
                "Phase": "Fase (rad)",
                "Unit": "Unidade",
                "Port": "Porta",
                "Out": "Saída",
                "Success": "Sucesso"
            }
        },
        "es": {
            "category": "Instrumentos/Coherent",
            "display_name": "Filtro Personalizado WaveShaper 1000A",
            "description": "Carga un perfil de filtro óptico arbitrario a partir de matrices de longitud de onda/frecuencia, atenuación y fase.",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "SpectralPoints": "Puntos Espectrales (nm o THz)",
                "Attenuation": "Atenuación (dB)",
                "Phase": "Fase (rad)",
                "Unit": "Unidad",
                "Port": "Puerto",
                "Out": "Salida",
                "Success": "Éxito"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._success: bool = False

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        device = await context.pull(self.id, "Device")
        points = await context.pull(self.id, "SpectralPoints")
        attn = await context.pull(self.id, "Attenuation")
        phase = await context.pull(self.id, "Phase")
        unit = await context.pull(self.id, "Unit")
        port = await context.pull(self.id, "Port")

        drv = device if isinstance(device, WaveShaper1000A) else WaveShaper1000A(str(device))
        unit_str = str(unit) if unit else "nm"
        p_val = int(port) if port is not None else 1

        phase_seq = phase if (phase is not None and len(phase) > 0) else None

        async with locked_device(context, drv, "WaveShaper 1000A Custom Filter"):
            await asyncio.to_thread(
                drv.load_profile_arrays,
                frequencies_or_wavelengths=points,
                attenuations_db=attn,
                phases_rad=phase_seq,
                unit=unit_str,
                port=p_val
            )

        self._success = True
        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Device":
            return await context.pull(self.id, "Device")
        elif pin_name == "Success":
            return self._success
        return None


@register_block("devices/coherent/ws1000a/upload_file")
class WaveShaper1000AUploadFileBlock(BaseBlock):
    """Uploads an existing WaveShaper Preset (*.wsp) or User Configurable Filter (*.ucf) file to a WaveShaper 1000A."""
    icon = "📁"
    display_name = "WaveShaper 1000A Upload File"
    description = "Uploads a .wsp or .ucf profile file or raw WSP text string directly to the WaveShaper."

    inputs_def = [
        ExecIn("In"),
        DataIn("Device", type_hint=Any),
        DataIn("FilePath", type_hint=str, default="", widget="file_open"),
        DataIn("WspString", type_hint=str, default="", optional=True)
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Device", type_hint=Any),
        DataOut("Success", type_hint=bool)
    ]

    i18n = {
        "pt-BR": {
            "category": "Instrumentos/Coherent",
            "display_name": "Carregar Arquivo WaveShaper 1000A",
            "description": "Envia um arquivo de perfil .wsp ou .ucf, ou texto WSP bruto, para o WaveShaper.",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "FilePath": "Caminho do Arquivo",
                "WspString": "Texto WSP (Opcional)",
                "Out": "Saída",
                "Success": "Sucesso"
            }
        },
        "es": {
            "category": "Instrumentos/Coherent",
            "display_name": "Cargar Archivo WaveShaper 1000A",
            "description": "Envía un archivo de perfil .wsp o .ucf, o texto WSP sin formato, al WaveShaper.",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "FilePath": "Ruta de Archivo",
                "WspString": "Texto WSP (Opcional)",
                "Out": "Salida",
                "Success": "Éxito"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._success: bool = False

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        device = await context.pull(self.id, "Device")
        file_path = await context.pull(self.id, "FilePath")
        wsp_string = await context.pull(self.id, "WspString")

        drv = device if isinstance(device, WaveShaper1000A) else WaveShaper1000A(str(device))

        async with locked_device(context, drv, "WaveShaper 1000A Upload File"):
            if wsp_string and str(wsp_string).strip():
                await asyncio.to_thread(drv.load_wsp_string, str(wsp_string))
            elif file_path and str(file_path).strip():
                await asyncio.to_thread(drv.load_wsp_file, str(file_path).strip())
            else:
                raise ValueError("Either FilePath or WspString must be provided to upload to WaveShaper 1000A.")

        self._success = True
        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Device":
            return await context.pull(self.id, "Device")
        elif pin_name == "Success":
            return self._success
        return None


@register_block("devices/coherent/ws1000a/get_profile")
class WaveShaper1000AGetProfileBlock(BaseBlock):
    """Retrieves the currently loaded optical filter profile from the WaveShaper 1000A."""
    icon = "📊"
    display_name = "WaveShaper 1000A Get Profile"
    description = "Queries the currently active optical filter profile from the instrument as NumPy coordinate arrays."

    inputs_def = [
        ExecIn("In"),
        DataIn("Device", type_hint=Any)
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Device", type_hint=Any),
        DataOut("WavelengthNM", type_hint=Any),
        DataOut("FrequencyTHz", type_hint=Any),
        DataOut("AttenuationDB", type_hint=Any),
        DataOut("PhaseRad", type_hint=Any),
        DataOut("Port", type_hint=Any),
        DataOut("WspString", type_hint=str)
    ]

    i18n = {
        "pt-BR": {
            "category": "Instrumentos/Coherent",
            "display_name": "Obter Perfil WaveShaper 1000A",
            "description": "Obtém o perfil de filtro óptico atualmente ativo no instrumento como vetores NumPy para gráficos ou análise.",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "Out": "Saída",
                "WavelengthNM": "Comprimento de Onda (nm)",
                "FrequencyTHz": "Frequência (THz)",
                "AttenuationDB": "Atenuação (dB)",
                "PhaseRad": "Fase (rad)",
                "Port": "Porta",
                "WspString": "Texto WSP"
            }
        },
        "es": {
            "category": "Instrumentos/Coherent",
            "display_name": "Obtener Perfil WaveShaper 1000A",
            "description": "Obtiene el perfil de filtro óptico actualmente activo en el instrumento como matrices NumPy para gráficos o análisis.",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "Out": "Salida",
                "WavelengthNM": "Longitud de Onda (nm)",
                "FrequencyTHz": "Frecuencia (THz)",
                "AttenuationDB": "Atenuación (dB)",
                "PhaseRad": "Fase (rad)",
                "Port": "Puerto",
                "WspString": "Texto WSP"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._wsp_raw: str = ""
        self._freqs: np.ndarray = np.array([])
        self._wls: np.ndarray = np.array([])
        self._attns: np.ndarray = np.array([])
        self._phases: np.ndarray = np.array([])
        self._ports: np.ndarray = np.array([])

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        device = await context.pull(self.id, "Device")
        drv = device if isinstance(device, WaveShaper1000A) else WaveShaper1000A(str(device))

        async with locked_device(context, drv, "WaveShaper 1000A Get Profile"):
            self._wsp_raw = await asyncio.to_thread(drv.get_profile)
            f_arr, wl_arr, a_arr, p_arr, pt_arr = await asyncio.to_thread(
                drv.parse_wsp_string, self._wsp_raw
            )

        self._freqs = f_arr
        self._wls = wl_arr
        self._attns = a_arr
        self._phases = p_arr
        self._ports = pt_arr

        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Device":
            return await context.pull(self.id, "Device")
        elif pin_name == "WavelengthNM":
            return self._wls
        elif pin_name == "FrequencyTHz":
            return self._freqs
        elif pin_name == "AttenuationDB":
            return self._attns
        elif pin_name == "PhaseRad":
            return self._phases
        elif pin_name == "Port":
            return self._ports
        elif pin_name == "WspString":
            return self._wsp_raw
        return None


@register_block("devices/coherent/ws1000a/shutter")
class WaveShaper1000AShutterBlock(BaseBlock):
    """Controls optical pass-through / shutter state (Transmit All vs Block All) on a WaveShaper 1000A."""
    icon = "🚪"
    display_name = "WaveShaper 1000A Shutter"
    description = "Quick optical shutter control: Transmit All (0 dB loss) or Block All (>50 dB attenuation)."

    inputs_def = [
        ExecIn("In"),
        DataIn("Device", type_hint=Any),
        DataIn("State", type_hint=str, default="Transmit All", widget="dropdown", options=["Transmit All", "Block All"])
    ]
    outputs_def = [
        ExecOut("Out"),
        DataOut("Device", type_hint=Any),
        DataOut("Success", type_hint=bool)
    ]

    i18n = {
        "pt-BR": {
            "category": "Instrumentos/Coherent",
            "display_name": "Obturador WaveShaper 1000A",
            "description": "Controle rápido do obturador óptico: Transmitir Tudo (0 dB de perda) ou Bloquear Tudo (>50 dB de atenuação).",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "State": "Estado",
                "Out": "Saída",
                "Success": "Sucesso"
            }
        },
        "es": {
            "category": "Instrumentos/Coherent",
            "display_name": "Obturador WaveShaper 1000A",
            "description": "Control rápido del obturador óptico: Transmitir Todo (0 dB de pérdida) o Bloquear Todo (>50 dB de atenuación).",
            "pins": {
                "In": "Entrada",
                "Device": "Dispositivo",
                "State": "Estado",
                "Out": "Salida",
                "Success": "Éxito"
            }
        }
    }

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        super().__init__(block_id, properties)
        self._success: bool = False

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        device = await context.pull(self.id, "Device")
        state = await context.pull(self.id, "State")

        drv = device if isinstance(device, WaveShaper1000A) else WaveShaper1000A(str(device))
        state_str = str(state).lower()

        async with locked_device(context, drv, "WaveShaper 1000A Shutter"):
            if "block" in state_str:
                await asyncio.to_thread(drv.set_block_all)
            else:
                await asyncio.to_thread(drv.set_transmit_all)

        self._success = True
        return "Out"

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        if pin_name == "Device":
            return await context.pull(self.id, "Device")
        elif pin_name == "Success":
            return self._success
        return None
