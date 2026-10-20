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

import contextvars
import math
from typing import Any, Dict, List, Optional


def format_output(res: Any) -> Any:
    """Sanitizes numeric block outputs: NaN/inf are clamped to JSON-safe values."""
    import numpy as np
    if isinstance(res, np.ndarray):
        res = np.nan_to_num(res, nan=0.0, posinf=1e99, neginf=-1e99)
        if res.ndim == 0:
            return float(res)
        return res
    elif isinstance(res, float):
        if math.isnan(res): return 0.0
        if math.isinf(res): return 1e99 if res > 0 else -1e99
        return res
    return res


def make_dynamic_item_inputs(block: "BaseBlock", prefix: str, default_count: int,
                             type_hint: Any = None, default: Any = None) -> None:
    """
    Populates a block's inputs with numbered dynamic item pins ("<prefix> 0..N")
    driven by the block's "itemCount" property.
    """
    item_count = int(block.properties.get("itemCount", default_count))
    for i in range(item_count):
        block.inputs[f"{prefix} {i}"] = DataIn(f"{prefix} {i}", type_hint=type_hint, default=default)


def parse_shape(shape_raw: Any) -> List[int]:
    """
    Parses an array shape from a string ("100,100"), a list/tuple/ndarray, or a scalar.
    Falls back to [100] for empty/invalid input.
    """
    import numpy as np
    shape = []
    if isinstance(shape_raw, str):
        try:
            shape = [int(x.strip()) for x in shape_raw.split(',') if x.strip()]
        except Exception:
            shape = [100]
    elif isinstance(shape_raw, (list, tuple, np.ndarray)):
        shape = [int(x) for x in shape_raw]
    elif isinstance(shape_raw, (int, float)):
        shape = [int(shape_raw)]

    if not shape:
        shape = [100]
    return shape


class Pin:
    """Base class for all input/output pins on a block."""
    def __init__(self, name: str, direction: str, pin_type: str):
        self.name = name
        self.direction = direction  # 'in' or 'out'
        self.pin_type = pin_type      # 'exec' or 'data'


class ExecIn(Pin):
    """Execution Input pin. Receives execution tokens."""
    def __init__(self, name: str):
        super().__init__(name, 'in', 'exec')


class ExecOut(Pin):
    """Execution Output pin. Propagates execution tokens."""
    def __init__(self, name: str):
        super().__init__(name, 'out', 'exec')


class DataIn(Pin):
    """Data Input pin. Receives data from connected DataOut pins."""
    def __init__(self, name: str, type_hint: Any = None, default: Any = None,
                 widget: Optional[str] = None, min_val: Optional[float] = None,
                 max_val: Optional[float] = None, step: Optional[float] = None,
                 options: Optional[List[Any]] = None, optional: bool = False):
        super().__init__(name, 'in', 'data')
        self.type_hint = type_hint
        self.default = default
        self.widget = widget
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.options = options
        self.optional = optional


class DataOut(Pin):
    """Data Output pin. Serves lazy-evaluated data to connected DataIn pins."""
    def __init__(self, name: str, type_hint: Any = None):
        super().__init__(name, 'out', 'data')
        self.type_hint = type_hint


class ExecutionContext:
    """
    State manager for a single graph execution run.
    Contains cache for pulled data and access to the VISA resource lock manager.
    """
    def __init__(self, engine: Any, run_id: str, lock_manager: Any):
        self.engine = engine
        self.run_id = run_id
        self.lock_manager = lock_manager
        # contextvars to hold task-local data cache:
        self._data_cache_var = contextvars.ContextVar("data_cache", default=None)
        self._data_cache_override: Optional[Dict[str, Dict[str, Any]]] = None

    @property
    def _data_cache(self) -> Dict[str, Dict[str, Any]]:
        if self._data_cache_override is not None:
            return self._data_cache_override
        cache = self._data_cache_var.get()
        if cache is None:
            cache = {}
            self._data_cache_var.set(cache)
        return cache

    @_data_cache.setter
    def _data_cache(self, value):
        self._data_cache_override = value

    async def pull(self, block_id: str, input_pin_name: str) -> Any:
        """
        Pulls data from the connection connected to the input pin on block_id.
        If no connection exists, returns the default value of the pin.
        """
        return await self.engine.pull_data(block_id, input_pin_name, self)

    def cache_value(self, block_id: str, pin_name: str, value: Any):
        """Caches a pulled output pin value for the current step."""
        if block_id not in self._data_cache:
            self._data_cache[block_id] = {}
        self._data_cache[block_id][pin_name] = value

    def get_cached(self, block_id: str, pin_name: str) -> tuple[bool, Any]:
        """Checks the cache and returns (found, value)."""
        if block_id in self._data_cache and pin_name in self._data_cache[block_id]:
            return True, self._data_cache[block_id][pin_name]
        return False, None

    def clear_cache(self):
        """Clears all cached data pulled values (typically done at the end of a execution step)."""
        self._data_cache.clear()

    async def send_telemetry(self, block_id: str, data: Any):
        """Broadcasts custom telemetry data to active subscribers."""
        if hasattr(self.engine, "send_telemetry"):
            await self.engine.send_telemetry(self.run_id, block_id, data)


class BaseBlock:
    """
    Abstract base class for all ComfyLAB blocks.
    Subclasses must define inputs_def and outputs_def and implement execute/pull_data/teardown.
    """
    category: str = "Logic"
    icon: str = "⚙️"
    display_name: str = ""
    description: str = ""
    author: str = ""

    inputs_def: List[Pin] = []
    outputs_def: List[Pin] = []
    
    # Embedded translations per block, e.g. {"en": {"display_name": "..."}, "pt-BR": {...}}
    i18n: Dict[str, Dict[str, Any]] = {}
    
    # Allows blocks to dictate frontend behaviors (e.g., {"suppress_value_msg": True})
    ui_behavior: Dict[str, Any] = {}

    # Distinguishes manufacturer-specific hardware instruments from general blocks
    is_device: bool = False

    def __init__(self, block_id: str, properties: Optional[Dict[str, Any]] = None):
        self.id = block_id
        self.properties = properties or {}
        # Instantiate inputs and outputs based on class definitions
        self.inputs = {pin.name: pin for pin in self.inputs_def}
        self.outputs = {pin.name: pin for pin in self.outputs_def}

    async def execute(self, context: ExecutionContext, trigger_pin: str) -> Optional[str]:
        """
        Executed when an execution token reaches this block.
        trigger_pin: The name of the ExecIn pin that was triggered.
        Returns: The name of the ExecOut pin to fire next, or None to stop.
        """
        return None

    async def pull_data(self, context: ExecutionContext, pin_name: str) -> Any:
        """
        Lazy-evaluated callback to retrieve the value of a DataOut pin.
        pin_name: The name of the DataOut pin being pulled.
        Returns: The computed value.
        """
        return None

    async def teardown(self):
        """
        Safely stops any ongoing tasks, releases resources, and transitions
        associated hardware to a safe state. Must be idempotent.
        """
        pass

    async def safe_state(self) -> None:
        """
        Transitions associated hardware to a safe state WITHOUT releasing it.
        Called on abort/error for persistent blocks, whose full teardown is skipped so
        their connections survive between runs. Must be idempotent. Default is a no-op.
        """
        pass

    async def clear_data(self) -> None:
        """
        Resets any transient execution or output data stored on the block.
        Can be overridden by subclasses to reset custom internal attributes.
        """
        if hasattr(self, "_outputs"):
            self._outputs.clear()


    async def _device_initialize(self, context: "ExecutionContext", device: Any) -> None:
        """
        Optional hook for device-connecting blocks. Called after a VISA/connection
        handle has been established. Override to send device-specific setup commands
        (e.g. reset, clear status). Default is a no-op.
        """
        pass

    async def _device_teardown(self, device: Any, lock_manager: Any) -> None:
        """
        Optional hook for device-connecting blocks. Called during teardown,
        before the connection handle is closed. Override to send device-specific
        safety commands (e.g. stop acquisition, disable output). Use the provided
        lock_manager to safely acquire the device's address lock. Default is a no-op.
        """
        pass
