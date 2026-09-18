#!/usr/bin/env python3
# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import json
import re
import shutil
import hashlib
import base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent
STORE_DIR = SRC_DIR / "dist" / "comfylab-store"
CLUSTERS_CORE_DIR = SRC_DIR / "comfylab" / "clusters"
EXAMPLES_CORE_DIR = SRC_DIR / "comfylab" / "examples"

KEY_FILE = Path.home() / ".comfylab" / "store_master_key.pem"
if not KEY_FILE.exists():
    raise FileNotFoundError(f"Store master key not found at {KEY_FILE}")

pem = KEY_FILE.read_bytes()
priv_key = serialization.load_pem_private_key(pem, password=None)
pub_bytes = priv_key.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
)
PUB_HEX = pub_bytes.hex()
print(f"[Store Key] Loaded master identity: {PUB_HEX}")


def sign_json_data(data: dict) -> dict:
    content = data.copy()
    content.pop("creator_identity", None)
    content.pop("signature", None)
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig_bytes = priv_key.sign(canonical)
    signed = data.copy()
    signed["creator_identity"] = PUB_HEX
    signed["signature"] = base64.b64encode(sig_bytes).decode("utf-8")
    return signed


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    h.update(filepath.read_bytes())
    return h.hexdigest()


def extract_provides_from_pkg(pkg_dir: Path, pkg_type: str) -> list[str]:
    provides = []
    if pkg_type == "instrument":
        blocks_file = pkg_dir / "blocks.py"
        if blocks_file.exists():
            text = blocks_file.read_text(encoding="utf-8")
            for match in re.finditer(r'@register_block\(["\']([^"\']+)["\']\)', text):
                provides.append(match.group(1))
    elif pkg_type == "cluster":
        for cf in pkg_dir.glob("*.cluster.json"):
            try:
                data = json.loads(cf.read_text(encoding="utf-8"))
                if "type_name" in data:
                    provides.append(data["type_name"])
            except Exception:
                pass
    return sorted(list(set(provides)))


def main():
    # 1. Prepare clusters/bode/physical_setup
    bode_cluster_dir = STORE_DIR / "clusters" / "bode" / "physical_setup"
    bode_cluster_dir.mkdir(parents=True, exist_ok=True)
    bode_cluster_files = ["bode_setup_instruments.cluster.json", "bode_measure_point.cluster.json"]
    for cf in bode_cluster_files:
        src_path = CLUSTERS_CORE_DIR / cf
        if src_path.exists():
            data = json.loads(src_path.read_text(encoding="utf-8"))
            signed = sign_json_data(data)
            (bode_cluster_dir / cf).write_text(json.dumps(signed, indent=2), encoding="utf-8")
    
    bode_cluster_manifest = {
        "id": "clusters/bode/physical_setup",
        "name": "Bode Physical Setup Clusters",
        "vendor": "Academic / IFGW",
        "vendor_slug": "ifgw",
        "type": "cluster",
        "version": "1.0.0",
        "description": "Instrument setup and point measurement clusters for Bode Plot using Minipa MFG-4230 and Tektronix TBS-1062.",
        "author": "Paulo Felipe Jarschel",
        "dependencies": [
            "instruments/minipa/mfg4230",
            "instruments/tektronix/tbs1062"
        ],
        "provides": [
            "builtin/cluster/bode_setup_instruments",
            "builtin/cluster/bode_measure_point"
        ],
        "files": ["manifest.json"] + bode_cluster_files
    }
    (bode_cluster_dir / "manifest.json").write_text(json.dumps(bode_cluster_manifest, indent=2), encoding="utf-8")

    # 2. Prepare clusters/horiba/vuv_spectroscopy
    horiba_cluster_dir = STORE_DIR / "clusters" / "horiba" / "vuv_spectroscopy"
    horiba_cluster_dir.mkdir(parents=True, exist_ok=True)
    horiba_cluster_files = [
        "vuv_setup_instruments.cluster.json",
        "vuv_measure_point.cluster.json",
        "vuv_accumulate_data.cluster.json",
        "vuv_export_dataset.cluster.json"
    ]
    for cf in horiba_cluster_files:
        src_path = CLUSTERS_CORE_DIR / cf
        if src_path.exists():
            data = json.loads(src_path.read_text(encoding="utf-8"))
            signed = sign_json_data(data)
            (horiba_cluster_dir / cf).write_text(json.dumps(signed, indent=2), encoding="utf-8")

    horiba_cluster_manifest = {
        "id": "clusters/horiba/vuv_spectroscopy",
        "name": "Horiba VUV Spectroscopy Clusters",
        "vendor": "Academic / IFGW",
        "vendor_slug": "ifgw",
        "type": "cluster",
        "version": "1.0.0",
        "description": "Setup, measurement, accumulation, and export clusters for Horiba H20 UVL monochromator and Tektronix MDO-3040.",
        "author": "Paulo Felipe Jarschel",
        "dependencies": [
            "instruments/horiba/vuv_excitation",
            "instruments/tektronix/mdo3040"
        ],
        "provides": [
            "builtin/cluster/vuv_setup_instruments",
            "builtin/cluster/vuv_measure_point",
            "builtin/cluster/vuv_accumulate_data",
            "builtin/cluster/vuv_export_dataset"
        ],
        "files": ["manifest.json"] + horiba_cluster_files
    }
    (horiba_cluster_dir / "manifest.json").write_text(json.dumps(horiba_cluster_manifest, indent=2), encoding="utf-8")

    # 3. Prepare blueprints/bode/physical_bode_plot
    bode_bp_dir = STORE_DIR / "blueprints" / "bode" / "physical_bode_plot"
    bode_bp_dir.mkdir(parents=True, exist_ok=True)
    bode_bp_file = "Bode_Plot_Example.json"
    src_bode_bp = EXAMPLES_CORE_DIR / bode_bp_file
    if src_bode_bp.exists():
        data = json.loads(src_bode_bp.read_text(encoding="utf-8"))
        signed = sign_json_data(data)
        (bode_bp_dir / bode_bp_file).write_text(json.dumps(signed, indent=2), encoding="utf-8")

    bode_bp_manifest = {
        "id": "blueprints/bode/physical_bode_plot",
        "name": "Bode Plot Measurement (Physical)",
        "vendor": "Academic / IFGW",
        "vendor_slug": "ifgw",
        "type": "blueprint",
        "version": "1.0.0",
        "description": "Complete automated Bode Plot frequency response measurement workflow using Minipa MFG-4230 and Tektronix TBS-1062.",
        "author": "Paulo Felipe Jarschel",
        "dependencies": [
            "clusters/bode/physical_setup",
            "instruments/minipa/mfg4230",
            "instruments/tektronix/tbs1062"
        ],
        "files": ["manifest.json", bode_bp_file]
    }
    (bode_bp_dir / "manifest.json").write_text(json.dumps(bode_bp_manifest, indent=2), encoding="utf-8")

    # 4. Prepare blueprints/horiba/vuv_spectroscopy
    horiba_bp_dir = STORE_DIR / "blueprints" / "horiba" / "vuv_spectroscopy"
    horiba_bp_dir.mkdir(parents=True, exist_ok=True)
    horiba_bp_file = "Horiba_H20_UVL_Spectroscopy.json"
    src_horiba_bp = EXAMPLES_CORE_DIR / horiba_bp_file
    if src_horiba_bp.exists():
        data = json.loads(src_horiba_bp.read_text(encoding="utf-8"))
        signed = sign_json_data(data)
        (horiba_bp_dir / horiba_bp_file).write_text(json.dumps(signed, indent=2), encoding="utf-8")

    horiba_bp_manifest = {
        "id": "blueprints/horiba/vuv_spectroscopy",
        "name": "Horiba H20 UVL VUV Spectroscopy",
        "vendor": "Academic / IFGW",
        "vendor_slug": "ifgw",
        "type": "blueprint",
        "version": "1.0.0",
        "description": "Automated VUV excitation and fluorescence spectroscopy workflow using Horiba H20 UVL monochromator and Tektronix MDO-3040.",
        "author": "Paulo Felipe Jarschel",
        "dependencies": [
            "clusters/horiba/vuv_spectroscopy",
            "instruments/horiba/vuv_excitation",
            "instruments/tektronix/mdo3040"
        ],
        "files": ["manifest.json", horiba_bp_file]
    }
    (horiba_bp_dir / "manifest.json").write_text(json.dumps(horiba_bp_manifest, indent=2), encoding="utf-8")

    # 5. Prepare clusters/ifgw/franck_hertz
    fh_cluster_dir = STORE_DIR / "clusters" / "ifgw" / "franck_hertz"
    fh_cluster_dir.mkdir(parents=True, exist_ok=True)
    fh_cluster_files = [
        "fh_setup_instruments.cluster.json",
        "fh_measure_point.cluster.json",
        "fh_check_limits.cluster.json",
        "fh_accumulate_data.cluster.json",
        "fh_export_dataset.cluster.json"
    ]
    for cf in fh_cluster_files:
        src_path = CLUSTERS_CORE_DIR / cf
        if src_path.exists():
            data = json.loads(src_path.read_text(encoding="utf-8"))
            if cf == "fh_setup_instruments.cluster.json":
                # Convert VISA to Serial blocks with requested parameters:
                # baudrate: 57600, data_bits: 8, parity: "None", stop_bits: 1, flow_control: "None", read_delay_ms: 13.0, timeout: 1.0
                data["description"] = "Initializes Serial connection for Franck-Hertz apparatus (/dev/ttyUSB0 or COM port) with selectable Simulation / Real Hardware switch."
                for b in data.get("internal_blueprint", {}).get("blocks", []):
                    if b["id"] == "boundary_in_addr":
                        b["properties"] = {"Name": "Port", "Type": "data", "DataType": "text"}
                    elif b["id"] == "block_visa_dev":
                        b["id"] = "block_serial_dev"
                        b["type"] = "serial/core/device"
                        b["properties"] = {
                            "Port": "/dev/ttyUSB0",
                            "BaudRate": 57600,
                            "DataBits": 8,
                            "StopBits": "1",
                            "Parity": "None",
                            "FlowControl": "None",
                            "ReadDelayMs": 13.0,
                            "Timeout": 1.0,
                            "ReadTermination": "",
                            "WriteTermination": "\n"
                        }
                    elif b["id"] in ("block_write_safe_d", "block_write_safe_p", "block_write_start_s"):
                        b["type"] = "serial/core/write"
                        cmd = b.get("properties", {}).get("Command", "")
                        b["properties"] = {"Data": cmd, "Command": cmd}
                for l in data.get("internal_blueprint", {}).get("links", []):
                    if l.get("source_block") == "block_visa_dev":
                        l["source_block"] = "block_serial_dev"
                    if l.get("target_block") == "block_visa_dev":
                        l["target_block"] = "block_serial_dev"
                    if l["id"] == "link_bin_addr_to_visa_addr":
                        l["target_pin"] = "Port"
                for pin in data.get("boundary_pins", {}).get("data_ins", []):
                    if pin.get("name") == "Address":
                        pin["name"] = "Port"
                        pin["default"] = "/dev/ttyUSB0"

            elif cf == "fh_measure_point.cluster.json":
                data["description"] = "Acquires accelerating voltage (Ua), collector current (Is), retarding voltage (Us), and temperature (T) via serial hardware queries or physics simulation mode."
                for b in data.get("internal_blueprint", {}).get("blocks", []):
                    if b["id"] in ("block_query_ua", "block_query_is", "block_query_us", "block_query_temp"):
                        b["type"] = "serial/core/query"

            signed = sign_json_data(data)
            (fh_cluster_dir / cf).write_text(json.dumps(signed, indent=2), encoding="utf-8")

    fh_cluster_manifest = {
        "id": "clusters/ifgw/franck_hertz",
        "name": "Franck-Hertz Experiment Clusters",
        "vendor": "Academic / IFGW",
        "vendor_slug": "ifgw",
        "type": "cluster",
        "version": "1.0.0",
        "description": "Setup, point acquisition, limit checking, array accumulation, and dataset export clusters for the IFGW F-740 Franck-Hertz experiment using serial communication.",
        "author": "Paulo Felipe Jarschel",
        "dependencies": [],
        "provides": [
            "builtin/cluster/fh_setup_instruments",
            "builtin/cluster/fh_measure_point",
            "builtin/cluster/fh_check_limits",
            "builtin/cluster/fh_accumulate_data",
            "builtin/cluster/fh_export_dataset"
        ],
        "files": ["manifest.json"] + fh_cluster_files
    }
    (fh_cluster_dir / "manifest.json").write_text(json.dumps(fh_cluster_manifest, indent=2), encoding="utf-8")

    # 6. Prepare blueprints/ifgw/franck_hertz
    fh_bp_dir = STORE_DIR / "blueprints" / "ifgw" / "franck_hertz"
    fh_bp_dir.mkdir(parents=True, exist_ok=True)
    fh_bp_file = "IFGW-F740_FranckHertz.json"
    src_fh_bp = EXAMPLES_CORE_DIR / fh_bp_file
    if src_fh_bp.exists():
        data = json.loads(src_fh_bp.read_text(encoding="utf-8"))
        for b in data.get("blocks", []):
            if b.get("id") == "cluster_setup":
                node_data = b.get("data", {})
                if "Address" in node_data:
                    node_data.pop("Address", None)
                node_data["Port"] = "/dev/ttyUSB0"
        signed = sign_json_data(data)
        (fh_bp_dir / fh_bp_file).write_text(json.dumps(signed, indent=2), encoding="utf-8")

    fh_bp_manifest = {
        "id": "blueprints/ifgw/franck_hertz",
        "name": "IFGW F-740 Franck-Hertz Experiment",
        "vendor": "Academic / IFGW",
        "vendor_slug": "ifgw",
        "type": "blueprint",
        "version": "1.0.0",
        "description": "Complete automated Franck-Hertz mercury resonance curve measurement workflow with real-time plotting, safety limit monitoring, and dataset export.",
        "author": "Paulo Felipe Jarschel",
        "dependencies": [
            "clusters/ifgw/franck_hertz"
        ],
        "files": ["manifest.json", fh_bp_file]
    }
    (fh_bp_dir / "manifest.json").write_text(json.dumps(fh_bp_manifest, indent=2), encoding="utf-8")

    # 7. Load and Rebuild catalog.json
    catalog_file = STORE_DIR / "catalog.json"
    existing_catalog = json.loads(catalog_file.read_text(encoding="utf-8")) if catalog_file.exists() else {}
    packages_map = {p["id"]: p for p in existing_catalog.get("packages", [])}

    # Add or update the new packages
    new_packages = [
        (bode_cluster_manifest, bode_cluster_dir),
        (horiba_cluster_manifest, horiba_cluster_dir),
        (bode_bp_manifest, bode_bp_dir),
        (horiba_bp_manifest, horiba_bp_dir),
        (fh_cluster_manifest, fh_cluster_dir),
        (fh_bp_manifest, fh_bp_dir),
    ]

    for manifest, pdir in new_packages:
        pkg_id = manifest["id"]
        hashes = {f: sha256_file(pdir / f) for f in manifest["files"]}
        entry = {
            "id": pkg_id,
            "name": manifest["name"],
            "vendor": manifest["vendor"],
            "vendor_slug": manifest["vendor_slug"],
            "type": manifest["type"],
            "version": manifest["version"],
            "description": manifest["description"],
            "author": manifest["author"],
            "path": pkg_id,
            "dependencies": manifest.get("dependencies", []),
            "provides": manifest.get("provides", []),
            "files": manifest["files"],
            "hashes": hashes
        }
        packages_map[pkg_id] = entry

    # For all existing packages, ensure provides and hashes match
    for pkg_id, entry in packages_map.items():
        pdir = STORE_DIR / entry["path"]
        if pdir.exists():
            hashes = {}
            for f in entry.get("files", []):
                target = pdir / f
                if target.exists():
                    hashes[f] = sha256_file(target)
            entry["hashes"] = hashes
            if not entry.get("provides"):
                prov = extract_provides_from_pkg(pdir, entry.get("type", "instrument"))
                if prov:
                    entry["provides"] = prov
            if "dependencies" not in entry:
                entry["dependencies"] = []

    # Sort packages alphabetically by id
    sorted_packages = [packages_map[k] for k in sorted(packages_map.keys())]

    updated_catalog = {
        "schema_version": "1.0",
        "store_name": "ComfyLAB Official Store",
        "official_public_key": PUB_HEX,
        "categories": ["instruments", "blocks", "clusters", "blueprints"],
        "packages": sorted_packages
    }

    signed_catalog = sign_json_data(updated_catalog)
    catalog_file.write_text(json.dumps(signed_catalog, indent=2), encoding="utf-8")
    print(f"[Migration] Successfully rebuilt and signed catalog.json with {len(sorted_packages)} packages!")

    # 8. Delete migrated files from Core
    for cf in bode_cluster_files + horiba_cluster_files + fh_cluster_files:
        core_f = CLUSTERS_CORE_DIR / cf
        if core_f.exists():
            core_f.unlink()
            print(f"[Core Cleanup] Removed {cf} from comfylab/clusters/")

    for bf in [bode_bp_file, horiba_bp_file, fh_bp_file]:
        core_bf = EXAMPLES_CORE_DIR / bf
        if core_bf.exists():
            core_bf.unlink()
            print(f"[Core Cleanup] Removed {bf} from comfylab/examples/")


if __name__ == "__main__":
    main()
