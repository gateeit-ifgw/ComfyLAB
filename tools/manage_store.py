#!/usr/bin/env python3
# Copyright (C) 2026 Paulo Felipe Jarschel
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
ComfyLAB Store Package Manager & Catalog Builder
------------------------------------------------
Scans store packages (instruments, blocks, clusters, blueprints),
signs code/cluster assets using the Store Master Key, calculates SHA-256 hashes,
updates manifest.json files, and rebuilds the digitally signed catalog.json.

Usage:
    python tools/manage_store.py
    python tools/manage_store.py --store-dir dist/comfylab-store
    python tools/manage_store.py --check
"""

import os
import sys
import json
import base64
import hashlib
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Add src to sys.path to access engine modules if needed
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


def get_store_signing_key() -> Tuple[ed25519.Ed25519PrivateKey, str]:
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


def sign_python_file(filepath: Path, priv_key: ed25519.Ed25519PrivateKey, pub_hex: str):
    """Signs a python source file with the master key."""
    code_lines = filepath.read_text(encoding="utf-8").splitlines()
    clean_lines = [
        l for l in code_lines 
        if not (l.startswith("# @creator_identity:") or l.startswith("# @signature:"))
    ]
    clean_code = "\n".join(clean_lines).rstrip()

    sig_bytes = priv_key.sign(clean_code.encode("utf-8"))
    sig_b64 = base64.b64encode(sig_bytes).decode("utf-8")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(clean_code + "\n\n")
        f.write(f"# @creator_identity: {pub_hex}\n")
        f.write(f"# @signature: {sig_b64}\n")


def sign_json_data(data: Dict[str, Any], priv_key: ed25519.Ed25519PrivateKey, pub_hex: str) -> Dict[str, Any]:
    """Digitally signs a dictionary payload."""
    clean_data = {k: v for k, v in data.items() if k not in ("signature", "creator_identity")}
    canonical = json.dumps(clean_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig_bytes = priv_key.sign(canonical)
    signed = dict(clean_data)
    signed["creator_identity"] = pub_hex
    signed["signature"] = base64.b64encode(sig_bytes).decode("utf-8")
    return signed


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    h.update(filepath.read_bytes())
    return h.hexdigest()


def discover_packages(store_root: Path) -> List[Path]:
    """Finds all subdirectories containing a manifest.json file."""
    packages = []
    for manifest_path in store_root.glob("**/manifest.json"):
        pkg_dir = manifest_path.parent
        if pkg_dir != store_root and not any(part.startswith(".") for part in pkg_dir.parts):
            packages.append(pkg_dir)
    return sorted(packages)


def process_package(pkg_dir: Path, store_root: Path, priv_key, pub_hex: str) -> Dict[str, Any]:
    manifest_path = pkg_dir / "manifest.json"
    manifest: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))

    rel_path = str(pkg_dir.relative_to(store_root)).replace("\\", "/")
    manifest["path"] = rel_path
    if "id" not in manifest or not manifest["id"]:
        manifest["id"] = rel_path

    # Sign files inside package if necessary
    for p in pkg_dir.iterdir():
        if p.is_file():
            if p.suffix == ".py":
                sign_python_file(p, priv_key, pub_hex)
            elif p.name.endswith(".cluster.json"):
                try:
                    cdata = json.loads(p.read_text(encoding="utf-8"))
                    signed_cdata = sign_json_data(cdata, priv_key, pub_hex)
                    p.write_text(json.dumps(signed_cdata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                except Exception as e:
                    print(f"Warning: could not sign cluster {p.name}: {e}")

    # Discover all package files
    all_files = sorted([f.name for f in pkg_dir.iterdir() if f.is_file() and not f.name.startswith(".")])
    manifest["files"] = all_files

    # Calculate hashes for non-manifest files
    non_manifest_hashes = {}
    for fname in all_files:
        if fname != "manifest.json":
            non_manifest_hashes[fname] = sha256_file(pkg_dir / fname)

    # Save manifest with non-manifest hashes
    manifest["hashes"] = non_manifest_hashes
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # In the catalog package entry, we include hashes for ALL files, including manifest.json
    catalog_pkg = dict(manifest)
    catalog_hashes = dict(non_manifest_hashes)
    catalog_hashes["manifest.json"] = sha256_file(manifest_path)
    catalog_pkg["hashes"] = catalog_hashes

    return catalog_pkg


def build_catalog(store_root: Path, priv_key, pub_hex: str) -> Path:
    packages_dirs = discover_packages(store_root)
    print(f"[Store Manager] Discovered {len(packages_dirs)} packages in {store_root}")

    catalog_packages = []
    for pdir in packages_dirs:
        catalog_pkg = process_package(pdir, store_root, priv_key, pub_hex)
        catalog_packages.append(catalog_pkg)
        print(f"  ✓ Processed & signed: {catalog_pkg.get('id')} (v{catalog_pkg.get('version')})")

    # Sort packages by id
    catalog_packages.sort(key=lambda p: p.get("id", ""))

    catalog = {
        "schema_version": "1.0",
        "store_name": "ComfyLAB Official Store",
        "official_public_key": pub_hex,
        "categories": ["instruments", "blocks", "clusters", "blueprints"],
        "packages": catalog_packages
    }

    signed_catalog = sign_json_data(catalog, priv_key, pub_hex)
    catalog_path = store_root / "catalog.json"
    catalog_path.write_text(json.dumps(signed_catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n[Store Manager] Successfully assembled and signed master catalog:")
    print(f"  -> File: {catalog_path}")
    print(f"  -> Packages: {len(catalog_packages)}")
    print(f"  -> Master Key: {pub_hex}")
    return catalog_path


def check_catalog(store_root: Path) -> bool:
    catalog_path = store_root / "catalog.json"
    if not catalog_path.exists():
        print(f"Error: {catalog_path} does not exist.")
        return False

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    pub_hex = catalog.get("creator_identity")
    sig_b64 = catalog.get("signature")

    if not pub_hex or not sig_b64:
        print("Error: catalog.json is not signed.")
        return False

    clean_catalog = {k: v for k, v in catalog.items() if k not in ("signature", "creator_identity")}
    canonical = json.dumps(clean_catalog, sort_keys=True, separators=(",", ":")).encode("utf-8")

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
    try:
        pub_key.verify(base64.b64decode(sig_b64), canonical)
        print("✓ Catalog digital signature is valid!")
    except Exception as e:
        print(f"✗ Catalog signature verification failed: {e}")
        return False

    packages = catalog.get("packages", [])
    errors = 0
    for pkg in packages:
        pdir = store_root / pkg["path"]
        if not pdir.exists():
            print(f"✗ Missing directory: {pdir}")
            errors += 1
            continue
        for fname, exp_hash in pkg.get("hashes", {}).items():
            fpath = pdir / fname
            if not fpath.exists():
                print(f"✗ Missing file: {fpath}")
                errors += 1
                continue
            act_hash = sha256_file(fpath)
            if act_hash != exp_hash:
                print(f"✗ Hash mismatch in {fpath}: expected {exp_hash[:8]}..., got {act_hash[:8]}...")
                errors += 1

    if errors == 0:
        print(f"✓ All {len(packages)} packages verified with 0 errors!")
        return True
    else:
        print(f"✗ Found {errors} validation errors.")
        return False


def main():
    parser = argparse.ArgumentParser(description="ComfyLAB Store Package Manager & Catalog Builder")
    parser.add_argument(
        "--store-dir",
        type=str,
        default=str(SRC_DIR / "dist" / "comfylab-store"),
        help="Path to the store repository root directory (default: src/dist/comfylab-store)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only verify signatures and hashes without modifying files"
    )
    args = parser.parse_args()

    store_root = Path(args.store_dir).resolve()
    if not store_root.exists():
        print(f"Error: Store directory not found: {store_root}")
        sys.exit(1)

    if args.check:
        success = check_catalog(store_root)
        sys.exit(0 if success else 1)

    priv_key, pub_hex = get_store_signing_key()
    build_catalog(store_root, priv_key, pub_hex)
    print("\nVerifying resulting catalog...")
    success = check_catalog(store_root)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
