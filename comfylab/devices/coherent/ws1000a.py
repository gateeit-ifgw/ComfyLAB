# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Coherent / Finisar WaveShaper 1000A Programmable Optical Filter Driver.
Pure Python instrument driver with zero ComfyLAB visual engine dependencies.

Communicates with the instrument over Ethernet/LAN or USB Ethernet gadget via
the embedded HTTP RESTful web API (port 80).

Supports:
- Device identification and operating band parameters (/waveshaper/devinfo)
- Predefined filter profiles (Bandpass, Bandstop, Gaussian, Transmit, Blockall)
- Arbitrary filter profiles (WSP array generation and upload via /waveshaper/loadprofile)
- Loading preset .wsp and .ucf files from disk
- Retrieving the active filter profile (/waveshaper/getprofile)
- Transparent high-precision conversion between Wavelength (nm) and Frequency (THz)
"""

import os
import json
import logging
import requests
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np

logger = logging.getLogger("comfylab.devices.coherent.ws1000a")

# Exact speed of light in vacuum constant for conversions:
# c = 299,792,458 m/s = 299,792.458 GHz * nm = 299,792.458 THz * nm
SPEED_OF_LIGHT_NM_THZ = 299792.458


class WaveShaper1000A:
    """
    Driver for the Coherent / Finisar WaveShaper 1000A Programmable Optical Filter / Processor.
    Interacts directly with the device's HTTP REST API.
    """

    def __init__(self, host: str = "169.254.6.8", port: int = 80, timeout: float = 5.0):
        """
        Initializes connection parameters to the WaveShaper 1000A.

        Args:
            host: IP address or hostname of the WaveShaper (default is factory fallback '169.254.6.8').
            port: HTTP port (default is 80).
            timeout: Network request timeout in seconds.
        """
        # Clean host if schema or trailing slashes were accidentally provided
        clean_host = str(host).strip()
        if clean_host.startswith("http://"):
            clean_host = clean_host[7:]
        elif clean_host.startswith("https://"):
            clean_host = clean_host[8:]
        clean_host = clean_host.rstrip("/")

        # Check if port was specified in host string (e.g. 192.168.1.50:80)
        if ":" in clean_host:
            parts = clean_host.split(":")
            clean_host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                pass

        self.host: str = clean_host
        self.port: int = int(port)
        self.timeout: float = float(timeout)
        self.base_url: str = f"http://{self.host}:{self.port}"
        self.session: requests.Session = requests.Session()

    @property
    def resource_name(self) -> str:
        """Resource URI for locking and session tracking."""
        return self.base_url

    # =========================================================================
    # Optical Unit Conversion Helpers
    # =========================================================================

    @staticmethod
    def nm_to_thz(wavelength_nm: Union[float, np.ndarray, Sequence[float]]) -> Union[float, np.ndarray]:
        """
        Converts optical wavelength (nm) to frequency (THz).
        f(THz) = 299792.458 / lambda(nm)
        """
        if isinstance(wavelength_nm, (list, tuple, np.ndarray)):
            arr = np.asarray(wavelength_nm, dtype=float)
            with np.errstate(divide="ignore", invalid="ignore"):
                return SPEED_OF_LIGHT_NM_THZ / arr
        wl = float(wavelength_nm)
        if wl <= 0:
            raise ValueError(f"Wavelength must be positive, got {wl} nm")
        return SPEED_OF_LIGHT_NM_THZ / wl

    @staticmethod
    def thz_to_nm(frequency_thz: Union[float, np.ndarray, Sequence[float]]) -> Union[float, np.ndarray]:
        """
        Converts optical frequency (THz) to wavelength (nm).
        lambda(nm) = 299792.458 / f(THz)
        """
        if isinstance(frequency_thz, (list, tuple, np.ndarray)):
            arr = np.asarray(frequency_thz, dtype=float)
            with np.errstate(divide="ignore", invalid="ignore"):
                return SPEED_OF_LIGHT_NM_THZ / arr
        freq = float(frequency_thz)
        if freq <= 0:
            raise ValueError(f"Frequency must be positive, got {freq} THz")
        return SPEED_OF_LIGHT_NM_THZ / freq

    @staticmethod
    def nm_bandwidth_to_thz(center_nm: float, span_nm: float) -> float:
        """
        Calculates the exact optical frequency bandwidth (THz) corresponding to
        a spectral span (nm) centered at center_nm.
        """
        c_nm = float(center_nm)
        s_nm = abs(float(span_nm))
        wl_low = max(1e-3, c_nm - s_nm / 2.0)
        wl_high = c_nm + s_nm / 2.0
        f_high = SPEED_OF_LIGHT_NM_THZ / wl_low
        f_low = SPEED_OF_LIGHT_NM_THZ / wl_high
        return abs(f_high - f_low)

    @staticmethod
    def thz_bandwidth_to_nm(center_thz: float, span_thz: float) -> float:
        """
        Calculates the exact wavelength bandwidth (nm) corresponding to
        a spectral span (THz) centered at center_thz.
        """
        c_thz = float(center_thz)
        s_thz = abs(float(span_thz))
        f_low = max(1e-3, c_thz - s_thz / 2.0)
        f_high = c_thz + s_thz / 2.0
        wl_high = SPEED_OF_LIGHT_NM_THZ / f_low
        wl_low = SPEED_OF_LIGHT_NM_THZ / f_high
        return abs(wl_high - wl_low)

    # =========================================================================
    # Device Information & Status
    # =========================================================================

    def get_devinfo(self) -> Dict[str, Any]:
        """
        Queries device identification, operational band limits, and port count.
        Endpoint: GET /waveshaper/devinfo
        """
        url = f"{self.base_url}/waveshaper/devinfo"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data
        except requests.RequestException as e:
            logger.error(f"Failed to fetch devinfo from {url}: {e}")
            raise ConnectionError(f"WaveShaper 1000A connection error at {url}: {e}") from e

    def get_wavelength_range(self) -> Tuple[float, float]:
        """
        Returns the calibrated operating wavelength limits (min_nm, max_nm) of the instrument.
        """
        info = self.get_devinfo()
        start_thz = float(info.get("startfreq", 191.250))
        stop_thz = float(info.get("stopfreq", 196.275))
        min_wl = float(self.thz_to_nm(max(start_thz, stop_thz)))
        max_wl = float(self.thz_to_nm(min(start_thz, stop_thz)))
        return min_wl, max_wl

    # =========================================================================
    # Profile Uploads
    # =========================================================================

    def load_predefined_profile(
        self,
        filter_type: str,
        center: Optional[float] = None,
        bandwidth: Optional[float] = None,
        attn_db: float = 0.0,
        port: int = 1,
        unit: str = "nm"
    ) -> Dict[str, Any]:
        """
        Configures the WaveShaper with a predefined optical filter profile.
        Endpoint: POST /waveshaper/loadprofile

        Args:
            filter_type: 'bandpass', 'bandstop', 'gaussian', 'transmit', or 'blockall'.
            center: Center wavelength in nm (if unit="nm") or center frequency in THz (if unit="THz").
            bandwidth: Filter bandwidth in nm (if unit="nm") or bandwidth in THz (if unit="THz").
            attn_db: Attenuation in the passband (0 to 40 dB).
            port: Output port (1 for pass-through on 1000A, 0 for block).
            unit: 'nm' (default) or 'THz'.
        """
        f_type = filter_type.strip().lower()
        valid_types = {"bandpass", "bandstop", "gaussian", "transmit", "blockall"}
        if f_type not in valid_types:
            raise ValueError(f"Invalid filter type '{filter_type}'. Must be one of: {sorted(list(valid_types))}")

        url = f"{self.base_url}/waveshaper/loadprofile"

        if f_type in ("transmit", "blockall"):
            payload = {"type": f_type}
        else:
            if center is None or bandwidth is None:
                raise ValueError(f"Parameters 'center' and 'bandwidth' are required for '{filter_type}' filter.")

            if unit.lower() in ("nm", "nanometer", "nanometers", "wavelength"):
                center_thz = float(self.nm_to_thz(center))
                bandwidth_thz = float(self.nm_bandwidth_to_thz(center, bandwidth))
            else:
                center_thz = float(center)
                bandwidth_thz = float(bandwidth)

            # Clamp attenuation
            clamped_attn = max(0.0, min(40.0, float(attn_db)))

            payload = {
                "type": f_type,
                "port": int(port),
                "center": round(center_thz, 4),
                "bandwidth": round(bandwidth_thz, 4),
                "attn": round(clamped_attn, 2)
            }

        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("rc", 0) != 0:
                msg = data.get("msg", "Unknown error")
                logger.warning(f"WaveShaper returned non-zero rc: {data}")
                raise RuntimeError(f"WaveShaper error loading profile: {msg} (rc={data.get('rc')})")
            return data
        except requests.RequestException as e:
            logger.error(f"Failed to post predefined profile to {url}: {e}")
            raise ConnectionError(f"WaveShaper communication failed: {e}") from e

    def load_wsp_string(self, wsp_content: str) -> Dict[str, Any]:
        """
        Uploads an arbitrary WSP (WaveShaper Preset) filter profile string to the device.
        Endpoint: POST /waveshaper/loadprofile with JSON body {"type": "wsp", "wsp": "<string>"}
        """
        clean_wsp = wsp_content.strip()
        if not clean_wsp:
            raise ValueError("WSP profile string cannot be empty.")

        url = f"{self.base_url}/waveshaper/loadprofile"
        payload = {
            "type": "wsp",
            "wsp": clean_wsp
        }

        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("rc", 0) != 0:
                msg = data.get("msg", "Unknown error")
                logger.warning(f"WaveShaper returned non-zero rc: {data}")
                raise RuntimeError(f"WaveShaper error loading WSP profile: {msg} (rc={data.get('rc')})")
            return data
        except requests.RequestException as e:
            logger.error(f"Failed to upload WSP string to {url}: {e}")
            raise ConnectionError(f"WaveShaper communication failed: {e}") from e

    @staticmethod
    def create_wsp_string(
        frequencies_thz: Sequence[float],
        attenuations_db: Sequence[float],
        phases_rad: Optional[Sequence[float]] = None,
        ports: Optional[Sequence[int]] = None,
        default_port: int = 1
    ) -> str:
        """
        Builds a standard tab-delimited WSP file format string from coordinate arrays.
        Format per line: Frequency(THz)\tAttenuation(dB)\tPhase(Rad)\tPort\n
        Frequencies are sorted in ascending order.
        """
        f_arr = np.asarray(frequencies_thz, dtype=float).flatten()
        a_arr = np.asarray(attenuations_db, dtype=float).flatten()

        if len(f_arr) == 0 or len(a_arr) == 0:
            raise ValueError("Frequency and attenuation arrays must not be empty.")

        if len(f_arr) != len(a_arr):
            raise ValueError(f"Array length mismatch: {len(f_arr)} frequencies vs {len(a_arr)} attenuations.")

        if phases_rad is not None:
            p_arr = np.asarray(phases_rad, dtype=float).flatten()
            if len(p_arr) != len(f_arr):
                raise ValueError(f"Array length mismatch: {len(p_arr)} phases vs {len(f_arr)} frequencies.")
            # Phase is modulo 2*pi
            p_arr = np.mod(p_arr, 2.0 * np.pi)
        else:
            p_arr = np.zeros(len(f_arr), dtype=float)

        if ports is not None:
            port_arr = np.asarray(ports, dtype=int).flatten()
            if len(port_arr) != len(f_arr):
                raise ValueError(f"Array length mismatch: {len(port_arr)} ports vs {len(f_arr)} frequencies.")
        else:
            port_arr = np.full(len(f_arr), default_port, dtype=int)

        # Sort by frequency ascending (required by WaveShaper hardware)
        sort_indices = np.argsort(f_arr)
        f_sorted = f_arr[sort_indices]
        a_sorted = a_arr[sort_indices]
        p_sorted = p_arr[sort_indices]
        port_sorted = port_arr[sort_indices]

        # Clamp attenuation between 0 and 60 dB
        a_sorted = np.clip(a_sorted, 0.0, 60.0)

        lines = [
            f"{f:.4f}\t{a:.2f}\t{p:.4f}\t{int(pt)}"
            for f, a, p, pt in zip(f_sorted, a_sorted, p_sorted, port_sorted)
        ]
        return "\n".join(lines) + "\n"

    def load_profile_arrays(
        self,
        frequencies_or_wavelengths: Sequence[float],
        attenuations_db: Sequence[float],
        phases_rad: Optional[Sequence[float]] = None,
        unit: str = "nm",
        port: int = 1
    ) -> Dict[str, Any]:
        """
        Constructs a WSP profile from input 1D arrays and uploads it directly to the WaveShaper.

        Args:
            frequencies_or_wavelengths: 1D array of spectral points (nm or THz).
            attenuations_db: 1D array of attenuation in dB.
            phases_rad: Optional 1D array of phase in radians.
            unit: 'nm' (default) or 'THz'.
            port: Output port (1 or 0).
        """
        arr = np.asarray(frequencies_or_wavelengths, dtype=float).flatten()
        if unit.lower() in ("nm", "nanometer", "nanometers", "wavelength"):
            f_thz = self.nm_to_thz(arr)
        else:
            f_thz = arr

        wsp_string = self.create_wsp_string(
            frequencies_thz=f_thz,
            attenuations_db=attenuations_db,
            phases_rad=phases_rad,
            default_port=port
        )
        return self.load_wsp_string(wsp_string)

    def load_wsp_file(self, file_path: str) -> Dict[str, Any]:
        """
        Loads a pre-existing .wsp or .ucf filter profile file from disk and uploads it.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"WaveShaper profile file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        clean = content.strip()
        if not clean:
            raise ValueError(f"Profile file is empty: {file_path}")

        # Check if UCF format (Frequency Offset, Attenuation, Phase - 3 columns)
        # Convert to WSP if needed using center frequency from device
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".ucf":
            content = self._convert_ucf_to_wsp(content)

        return self.load_wsp_string(content)

    def _convert_ucf_to_wsp(self, ucf_content: str) -> str:
        """Converts a 3-column UCF file into a 4-column WSP string centered in the operating band."""
        info = self.get_devinfo()
        start_f = float(info.get("startfreq", 191.250))
        stop_f = float(info.get("stopfreq", 196.275))
        center_f = (start_f + stop_f) / 2.0

        wsp_lines = []
        for line in ucf_content.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            parts = line_str.replace(",", "\t").split("\t")
            if len(parts) >= 2:
                try:
                    f_offset = float(parts[0])
                    attn = float(parts[1])
                    phase = float(parts[2]) if len(parts) >= 3 else 0.0
                    abs_freq = center_f + f_offset
                    wsp_lines.append(f"{abs_freq:.4f}\t{attn:.2f}\t{phase:.4f}\t1")
                except ValueError:
                    continue
        if not wsp_lines:
            raise ValueError("Could not parse valid data rows from UCF file.")
        return "\n".join(wsp_lines) + "\n"

    # =========================================================================
    # Profile Retrieval & Parsing
    # =========================================================================

    def get_profile(self) -> str:
        """
        Retrieves the currently loaded filter profile from the WaveShaper.
        Endpoint: GET /waveshaper/getprofile
        Returns: Raw WSP string format.
        """
        url = f"{self.base_url}/waveshaper/getprofile"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch active profile from {url}: {e}")
            raise ConnectionError(f"WaveShaper communication failed: {e}") from e

    def parse_wsp_string(
        self, wsp_content: str
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Parses a WSP string into structured NumPy 1D arrays:
        (frequencies_thz, wavelengths_nm, attenuations_db, phases_rad, ports)
        """
        freqs: List[float] = []
        attns: List[float] = []
        phases: List[float] = []
        ports: List[int] = []

        for line in wsp_content.splitlines():
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue
            cols = clean.replace(",", "\t").split()
            if len(cols) >= 2:
                try:
                    f = float(cols[0])
                    a = float(cols[1])
                    p = float(cols[2]) if len(cols) >= 3 else 0.0
                    pt = int(float(cols[3])) if len(cols) >= 4 else 1
                    freqs.append(f)
                    attns.append(a)
                    phases.append(p)
                    ports.append(pt)
                except ValueError:
                    continue

        f_arr = np.array(freqs, dtype=float)
        if len(f_arr) > 0:
            wl_arr = np.array(self.thz_to_nm(f_arr), dtype=float)
        else:
            wl_arr = np.array([], dtype=float)
        a_arr = np.array(attns, dtype=float)
        p_arr = np.array(phases, dtype=float)
        pt_arr = np.array(ports, dtype=int)

        return f_arr, wl_arr, a_arr, p_arr, pt_arr

    # =========================================================================
    # Convenient Quick Controls
    # =========================================================================

    def set_block_all(self) -> Dict[str, Any]:
        """Blocks all optical transmission (>50 dB attenuation across entire band)."""
        return self.load_predefined_profile("blockall")

    def set_transmit_all(self) -> Dict[str, Any]:
        """Sets full optical transmission (0 dB attenuation across entire band)."""
        return self.load_predefined_profile("transmit")

    def close(self) -> None:
        """Closes the HTTP session."""
        try:
            self.session.close()
        except Exception:
            pass
