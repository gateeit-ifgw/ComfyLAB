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

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal, Optional

class LinkModel(BaseModel):
    """Represents a connection (execution or data wire) between two pins."""
    id: str
    type: Literal["exec", "data"]
    source_block: str
    source_pin: str
    target_block: str
    target_pin: str


class BlockModel(BaseModel):
    """Represents a serialized block in the blueprint."""
    id: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    position: Optional[Dict[str, float]] = None


class BlueprintModel(BaseModel):
    """Represents the complete graph schema containing blocks and links."""
    blocks: List[BlockModel]
    links: List[LinkModel]


# --- Cluster Definition Models ---

class BoundaryMappingModel(BaseModel):
    """Maps a boundary pin to an internal block pin."""
    block_id: str
    pin: str


class BoundaryExecInModel(BaseModel):
    name: str
    maps_to: BoundaryMappingModel


class BoundaryExecOutModel(BaseModel):
    name: str
    maps_from: BoundaryMappingModel


class BoundaryDataInModel(BaseModel):
    name: str
    type: str = "any"
    widget: Optional[str] = None
    default: Any = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    options: Optional[List[Any]] = None
    optional: bool = False
    maps_to: BoundaryMappingModel


class BoundaryDataOutModel(BaseModel):
    name: str
    type: str = "any"
    maps_from: BoundaryMappingModel


class BoundaryPinsModel(BaseModel):
    exec_ins: List[BoundaryExecInModel] = Field(default_factory=list)
    exec_outs: List[BoundaryExecOutModel] = Field(default_factory=list)
    data_ins: List[BoundaryDataInModel] = Field(default_factory=list)
    data_outs: List[BoundaryDataOutModel] = Field(default_factory=list)


class ClusterDefinitionModel(BaseModel):
    """Represents a cluster (.cluster.json) definition file."""
    name: str
    type_name: str
    category: str = "User/Clusters"
    icon: str = "📦"
    display_name: str
    description: str = ""
    internal_blueprint: BlueprintModel
    boundary_pins: BoundaryPinsModel
    i18n: Optional[Dict[str, Any]] = None
