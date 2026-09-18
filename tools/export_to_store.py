#!/usr/bin/env python3
# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
ComfyLAB Store Exporter & Migration Tool
Extracts all vendor-specific instrument drivers and UI blocks from ComfyLAB core
into the structured, self-contained layout required by the gateeit-ifgw/comfylab-store repository.
"""

import os
import re
import sys
import json
import shutil
import hashlib
from pathlib import Path

# Add src to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from comfylab.engine.security import sign_data, get_private_key_path

VENDOR_DISPLAY_NAMES = {
    "advantest": "Advantest",
    "agilent": "Agilent Technologies",
    "bk_precision": "BK Precision",
    "caen": "CAEN",
    "horiba": "Horiba",
    "keithley": "Keithley Instruments",
    "keopsys": "Keopsys",
    "keysight": "Keysight Technologies",
    "mcc": "Measurement Computing (MCC)",
    "minipa": "Minipa",
    "ni": "National Instruments",
    "owon": "OWON",
    "srs": "Stanford Research Systems",
    "tektronix": "Tektronix",
    "thorlabs": "Thorlabs",
    "yokogawa": "Yokogawa",
}


def get_store_signing_key():
    """Loads store master key if present, otherwise local private key."""
    master_key_file = Path.home() / ".comfylab" / "store_master_key.pem"
    if master_key_file.exists():
        pem = master_key_file.read_bytes()
        priv_key = serialization.load_pem_private_key(pem, password=None)
        pub_bytes = priv_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return priv_key, pub_bytes.hex()

    # Fallback to local host key
    from comfylab.engine.security import get_private_key, get_creator_identity
    return get_private_key(), get_creator_identity()


def sign_file_with_key(filepath: Path, priv_key, pub_hex: str):
    code_lines = filepath.read_text(encoding="utf-8").splitlines()
    clean_lines = [
        l for l in code_lines 
        if not (l.startswith("# @creator_identity:") or l.startswith("# @signature:"))
    ]
    clean_code = "\n".join(clean_lines).rstrip()

    import base64
    sig_bytes = priv_key.sign(clean_code.encode("utf-8"))
    sig_b64 = base64.b64encode(sig_bytes).decode("utf-8")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(clean_code + "\n\n")
        f.write(f"# @creator_identity: {pub_hex}\n")
        f.write(f"# @signature: {sig_b64}\n")


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    h.update(filepath.read_bytes())
    return h.hexdigest()


def extract_title_and_desc(block_text: str, default_name: str):
    name = default_name
    desc = f"Driver and UI blocks for {default_name}."

    # Look for display_name = "..."
    disp_match = re.search(r'display_name\s*=\s*["\']([^"\']+)["\']', block_text)
    if disp_match:
        name = disp_match.group(1).replace(" Connect", "").strip()

    # Look for description = "..."
    desc_match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', block_text)
    if desc_match:
        desc = desc_match.group(1).strip()

    return name, desc


def main():
    out_dir = SRC_DIR / "dist" / "comfylab-store"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    priv_key, pub_hex = get_store_signing_key()
    print(f"[Store Exporter] Using signing identity: {pub_hex}")

    devices_dir = SRC_DIR / "comfylab" / "devices"
    blocks_devices_dir = SRC_DIR / "comfylab" / "blocks" / "devices"

    packages = []

    # Scan vendors
    for vendor_dir in sorted(devices_dir.iterdir()):
        if not vendor_dir.is_dir():
            continue
        vendor_slug = vendor_dir.name
        if vendor_slug in ("generic", "virtual", "__pycache__"):
            continue  # Generic and virtual stay in core

        vendor_blocks_dir = blocks_devices_dir / vendor_slug
        vendor_name = VENDOR_DISPLAY_NAMES.get(vendor_slug, vendor_slug.capitalize())

        # For each driver in this vendor
        for driver_file in sorted(vendor_dir.glob("*.py")):
            if driver_file.name.startswith("__"):
                continue

            model_slug = driver_file.stem
            # Find matching block file
            # E.g. hp34401a.py -> hp34401a_blocks.py or same stem
            candidate_block_files = [
                vendor_blocks_dir / f"{model_slug}_blocks.py",
                vendor_blocks_dir / f"{model_slug}.py",
                vendor_blocks_dir / f"{model_slug.replace('_device', '')}_blocks.py",
            ]
            block_file = None
            for cand in candidate_block_files:
                if cand.exists():
                    block_file = cand
                    break

            if not block_file:
                print(f" -> Skipping {vendor_slug}/{model_slug} (no matching block file found)")
                continue

            pkg_rel_path = f"instruments/{vendor_slug}/{model_slug}"
            pkg_out_dir = out_dir / pkg_rel_path
            pkg_out_dir.mkdir(parents=True, exist_ok=True)

            # Copy driver
            dest_driver = pkg_out_dir / "driver.py"
            driver_text = driver_file.read_text(encoding="utf-8")
            dest_driver.write_text(driver_text, encoding="utf-8")
            sign_file_with_key(dest_driver, priv_key, pub_hex)

            # Copy blocks and adjust import
            dest_blocks = pkg_out_dir / "blocks.py"
            blocks_text = block_file.read_text(encoding="utf-8")

            # Replace from comfylab.devices.<vendor>.<model> import X with from .driver import X
            adjusted_blocks_text = re.sub(
                rf"from\s+comfylab\.devices\.{vendor_slug}\.{model_slug}\s+import\s+",
                "from .driver import ",
                blocks_text
            )
            # In case generic driver imports exist
            dest_blocks.write_text(adjusted_blocks_text, encoding="utf-8")
            sign_file_with_key(dest_blocks, priv_key, pub_hex)

            # Extract title and description
            display_name, description = extract_title_and_desc(blocks_text, f"{vendor_name} {model_slug.upper()}")

            # Create manifest.json
            manifest = {
                "id": pkg_rel_path,
                "name": display_name,
                "vendor": vendor_name,
                "vendor_slug": vendor_slug,
                "model": model_slug,
                "type": "instrument",
                "version": "1.0.0",
                "description": description,
                "author": "Paulo Felipe Jarschel",
                "min_comfylab_version": "0.4.0",
                "files": ["manifest.json", "driver.py", "blocks.py"]
            }

            dest_manifest = pkg_out_dir / "manifest.json"
            dest_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            hashes = {
                "manifest.json": sha256_file(dest_manifest),
                "driver.py": sha256_file(dest_driver),
                "blocks.py": sha256_file(dest_blocks),
            }

            pkg_entry = {
                "id": pkg_rel_path,
                "name": display_name,
                "vendor": vendor_name,
                "vendor_slug": vendor_slug,
                "type": "instrument",
                "version": "1.0.0",
                "description": description,
                "author": "Paulo Felipe Jarschel",
                "path": pkg_rel_path,
                "files": ["manifest.json", "driver.py", "blocks.py"],
                "hashes": hashes
            }
            packages.append(pkg_entry)
            print(f"  + Exported {pkg_rel_path}: {display_name}")

    # Generate master catalog.json
    catalog = {
        "schema_version": "1.0",
        "store_name": "ComfyLAB Official Store",
        "official_public_key": pub_hex,
        "categories": ["instruments", "blocks", "clusters", "blueprints"],
        "packages": packages
    }

    # Digitally sign catalog.json
    import base64
    content = catalog.copy()
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig_bytes = priv_key.sign(canonical)
    catalog["creator_identity"] = pub_hex
    catalog["signature"] = base64.b64encode(sig_bytes).decode("utf-8")

    catalog_file = out_dir / "catalog.json"
    catalog_file.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"\n[Store Exporter] Generated signed master catalog.json with {len(packages)} packages.")

    # Generate GitHub Actions workflow for comfylab-store
    workflows_dir = out_dir / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    workflow_content = """name: Validate and Sign Store Packages

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  validate-and-sign:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout store repository
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install cryptography
        run: pip install cryptography

      - name: Validate and Rebuild Catalog
        run: |
          python3 -c '
          import json, hashlib, base64
          from pathlib import Path
          from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

          root = Path(".")
          catalog_file = root / "catalog.json"
          if not catalog_file.exists():
              print("catalog.json not found, skipping verification")
              exit(0)

          catalog = json.loads(catalog_file.read_text())
          packages = catalog.get("packages", [])
          print(f"Validating {len(packages)} packages...")

          # Verify catalog digital signature
          pub_key_hex = catalog.get("creator_identity")
          sig_b64 = catalog.get("signature")
          if pub_key_hex and sig_b64:
              clean_catalog = {k: v for k, v in catalog.items() if k not in ("signature", "creator_identity")}
              canonical = json.dumps(clean_catalog, sort_keys=True, separators=(",", ":")).encode("utf-8")
              pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_key_hex))
              pub_key.verify(base64.b64decode(sig_b64), canonical)
              print("Catalog digital signature verified!")
          
          for pkg in packages:
              pkg_dir = root / pkg["path"]
              assert pkg_dir.exists(), f"Missing directory: {pkg_dir}"
              for f, expected_hash in pkg.get("hashes", {}).items():
                  target = pkg_dir / f
                  assert target.exists(), f"Missing file: {target}"
                  actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                  assert actual_hash == expected_hash, f"Hash mismatch for {target}"

          print("All packages verified successfully!")
          '
"""
    (workflows_dir / "sign-and-release.yml").write_text(workflow_content, encoding="utf-8")

    # Generate README.md for the store
    readme_content = f"""# ComfyLAB Store

Official repository for modular instruments, blocks, clusters, and blueprints for [ComfyLAB](https://github.com/gateeit-ifgw/ComfyLAB).

## Official Store Signing Key
All official packages in this repository are cryptographically signed using Ed25519.
- **Official Public Key:** `{pub_hex}`

## Directory Structure
- `instruments/`: Vendor-specific instrument drivers and UI blocks.
- `blocks/`: General domain-specific processing blocks.
- `clusters/`: Reusable compound cluster graphs.
- `blueprints/`: Complete automated test-and-measurement blueprints.

## Contributing a New Instrument
1. Create a directory: `instruments/<vendor>/<model>/`
2. Add `manifest.json`, `driver.py`, and `blocks.py`.
3. Open a Pull Request!
"""
    (out_dir / "README.md").write_text(readme_content, encoding="utf-8")

    print(f"\n[Store Exporter] Completed! Exported to: {out_dir}")
    print(f"You can now push the contents of {out_dir} directly to https://github.com/gateeit-ifgw/comfylab-store !")


if __name__ == "__main__":
    main()
