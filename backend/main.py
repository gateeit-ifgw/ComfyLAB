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
import asyncio
import socket
import struct
import subprocess
import logging
import secrets
import base64
import shutil
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.routers.execution import router as execution_router
from backend.routers.settings import router as settings_router
from backend.routers.diagnostics import router as diagnostics_router
from backend.routers.workspace import router as workspace_router
from backend.routers.packages import router as packages_router
from backend.routers.blocks import router as blocks_router
from backend.routers.updates import router as updates_router
from backend.routers.store import router as store_router
import comfylab.engine.config as config_module
from comfylab.engine.config import get_config
from comfylab.engine.registry import BLOCK_REGISTRY, load_all_clusters_deferred
from backend.workspace import set_workspace_path
from backend.auth import verify_access_token, verify_user_password
from backend.ratelimit import is_blocked, record_failure, record_success, block_remaining, remaining_attempts, is_first_attempt
from comfylab.engine.logging import setup_logging

# Initialize structured logging first thing on startup
setup_logging()
logger = logging.getLogger("backend.main")

# Word lists directory (relative to this file)
_WORD_DIR = Path(__file__).parent

def _load_wordlist(filename):
    path = _WORD_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    try:
        import importlib.resources as pkg_resources
        content = pkg_resources.files("backend").joinpath(filename).read_text(encoding="utf-8")
        return [line.strip() for line in content.splitlines() if line.strip()]
    except Exception:
        pass
    return ["comfy", "lab"]

# Generate adjective-noun remote access token
def generate_server_token():
    adjectives = _load_wordlist("adjectives.txt")
    nouns = _load_wordlist("nouns.txt")
    # secrets.choice: token is a security credential, so use a CSPRNG
    return f"{secrets.choice(adjectives)}-{secrets.choice(nouns)}"


SERVER_TOKEN = generate_server_token()
config_module.SESSION_TOKEN = SERVER_TOKEN

app = FastAPI(
    title="ComfyLAB Virtual Sandbox API",
    description="Backend API serving the ComfyLAB push/pull block execution engine and WebSocket telemetry."
)

API_PATHS = {"/run", "/pause", "/resume", "/abort", "/status", "/blocks", "/parse_script", "/validate_script", "/workspace", "/settings", "/restart", "/updates"}

def is_test_environment() -> bool:
    """Checks if the application is running under an active test runner (pytest/unittest)."""
    return (
        os.getenv("COMFYLAB_TESTING") == "1"
        or os.getenv("PYTEST_CURRENT_TEST") is not None
        or any("pytest" in arg.lower() for arg in sys.argv)
    )

def get_frontend_dist_path() -> Path:
    """Resolves the pre-compiled frontend assets directory across development, production, wheel, and frozen standalone modes."""
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            dist = Path(meipass) / "frontend" / "dist"
            if dist.exists():
                return dist
        exe_dist = Path(sys.executable).parent / "frontend" / "dist"
        if exe_dist.exists():
            return exe_dist

    current_dir = Path(__file__).parent.resolve()
    source_dist = current_dir.parent / "frontend" / "dist"
    if source_dist.exists():
        return source_dist

    try:
        import importlib.resources as pkg_resources
        for pkg_name in ("frontend", "comfylab"):
            try:
                pkg_dist = Path(str(pkg_resources.files(pkg_name).joinpath("dist" if pkg_name == "frontend" else "frontend/dist")))
                if pkg_dist.exists():
                    return pkg_dist
            except Exception:
                pass
    except Exception:
        pass

    cwd_dist = Path.cwd() / "frontend" / "dist"
    if cwd_dist.exists():
        return cwd_dist

    return source_dist

def get_frontend_port() -> int:
    """Returns the port through which users access the frontend UI."""
    if "COMFYLAB_FRONTEND_PORT" in os.environ:
        try:
            return int(os.environ["COMFYLAB_FRONTEND_PORT"])
        except ValueError:
            pass
    frontend_dist = get_frontend_dist_path()
    if frontend_dist.exists() and not is_test_environment():
        return int(os.environ.get("COMFYLAB_PORT", 8000))
    else:
        return 5173

def get_system_search_domains() -> list:
    """Extracts system DNS search domains from /etc/resolv.conf (Unix) or Windows Registry (Windows)."""
    domains = []
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters") as key:
                for val_name in ("Domain", "DhcpDomain"):
                    try:
                        val, _ = winreg.QueryValueEx(key, val_name)
                        if val and val.strip() and val.strip() not in domains:
                            domains.append(val.strip())
                    except Exception:
                        pass
                try:
                    search_list, _ = winreg.QueryValueEx(key, "SearchList")
                    if search_list:
                        for s in search_list.split(","):
                            s = s.strip()
                            if s and s not in domains:
                                domains.append(s)
                except Exception:
                    pass
        except Exception:
            pass
    else:
        resolv_file = Path("/etc/resolv.conf")
        if resolv_file.exists():
            try:
                for line in resolv_file.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("domain ") or line.startswith("search "):
                        for part in line.split()[1:]:
                            part = part.strip()
                            if part and part not in domains:
                                domains.append(part)
            except Exception:
                pass
    return domains

def get_dns_nameservers() -> list:
    """Returns a list of active system DNS server IP addresses."""
    servers = []
    if sys.platform != "win32":
        resolv_file = Path("/etc/resolv.conf")
        if resolv_file.exists():
            try:
                for line in resolv_file.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("nameserver "):
                        parts = line.split()
                        if len(parts) > 1 and parts[1] not in servers:
                            servers.append(parts[1])
            except Exception:
                pass
    if not servers:
        servers = ["127.0.0.53", "127.0.0.1", "1.1.1.1", "8.8.8.8"]
    return servers

def query_dns_ptr_raw(ip: str, dns_server: str, timeout: float = 0.4) -> str:
    """Performs a direct UDP DNS PTR query for an IPv4 address to a specific DNS server."""
    parts = ip.split(".")
    if len(parts) != 4:
        return ""
    arpa_domain = ".".join(reversed(parts)) + ".in-addr.arpa"

    packet = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    for part in arpa_domain.split("."):
        packet += bytes([len(part)]) + part.encode("ascii")
    packet += b"\x00"
    packet += struct.pack(">HH", 12, 1)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.sendto(packet, (dns_server, 53))
            data, _ = s.recvfrom(512)

        idx = 12
        while idx < len(data) and data[idx] != 0:
            if (data[idx] & 0xC0) == 0xC0:
                idx += 2
                break
            idx += data[idx] + 1
        if idx < len(data) and data[idx] == 0:
            idx += 1
        idx += 4

        while idx < len(data):
            if (data[idx] & 0xC0) == 0xC0:
                idx += 2
            else:
                while idx < len(data) and data[idx] != 0:
                    idx += data[idx] + 1
                idx += 1
            if idx + 10 > len(data):
                break
            rtype, rclass, ttl, rdlength = struct.unpack(">HHIH", data[idx:idx+10])
            idx += 10
            if rtype == 12:  # PTR record
                ptr_labels = []
                r_end = idx + rdlength
                curr = idx
                while curr < r_end:
                    length = data[curr]
                    if length == 0:
                        break
                    if (length & 0xC0) == 0xC0:
                        ptr_offset = struct.unpack(">H", data[curr:curr+2])[0] & 0x3FFF
                        curr_ptr = ptr_offset
                        while curr_ptr < len(data) and data[curr_ptr] != 0:
                            l = data[curr_ptr]
                            ptr_labels.append(data[curr_ptr+1:curr_ptr+1+l].decode("ascii", errors="ignore"))
                            curr_ptr += l + 1
                        break
                    else:
                        ptr_labels.append(data[curr+1:curr+1+length].decode("ascii", errors="ignore"))
                        curr += length + 1
                if ptr_labels:
                    return ".".join(ptr_labels).rstrip(".")
    except Exception:
        pass
    return ""

def get_network_fqdn_for_ip(ip: str, is_primary: bool = False) -> str:
    """Queries DNS PTR records and system search domains to find the true network-assigned FQDN for an IP."""
    # 1. Try system CLI utilities (host / nslookup) if available
    if shutil.which("host"):
        try:
            proc = subprocess.run(["host", "-W", "1", ip], capture_output=True, text=True, timeout=1.0)
            if proc.returncode == 0 and "domain name pointer " in proc.stdout:
                name = proc.stdout.split("domain name pointer ")[-1].strip().rstrip(".")
                if name and name != ip and "." in name and not name.endswith(".local"):
                    return name
        except Exception:
            pass

    if shutil.which("nslookup"):
        try:
            proc = subprocess.run(["nslookup", "-timeout=1", ip], capture_output=True, text=True, timeout=1.0)
            if proc.returncode == 0 and "name = " in proc.stdout:
                name = proc.stdout.split("name = ")[-1].splitlines()[0].strip().rstrip(".")
                if name and name != ip and "." in name and not name.endswith(".local"):
                    return name
        except Exception:
            pass

    # 2. Direct UDP DNS PTR query to system DNS servers
    for ns in get_dns_nameservers():
        ptr_name = query_dns_ptr_raw(ip, ns)
        if ptr_name and ptr_name != ip and "." in ptr_name and not ptr_name.endswith(".local"):
            return ptr_name

    # 3. Fallback to system search domains
    search_domains = get_system_search_domains()
    hostname = socket.gethostname()
    if search_domains:
        for sd in search_domains:
            candidate = f"{hostname}.{sd}"
            try:
                if socket.gethostbyname(candidate) == ip:
                    return candidate
            except Exception:
                pass
        if is_primary:
            return f"{hostname}.{search_domains[0]}"

    return ""

def get_local_ip_addresses() -> list:
    """
    Retrieves all non-loopback IPv4 addresses assigned to local network interfaces
    and resolves network-assigned FQDN hostnames for each interface.
    Returns a list of tuples: (ip_address, fqdn_hostname).
    """
    ips = []
    # Primary outbound IP
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    # Hostname resolution
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    # Addrinfo fallback
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = item[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    results = []
    for idx, ip in enumerate(ips):
        is_primary = (idx == 0)
        fqdn = get_network_fqdn_for_ip(ip, is_primary=is_primary)
        results.append((ip, fqdn))

    return results

# Security middleware to enforce remote access token verification
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Bypass OPTIONS (CORS preflight)
    if request.method == "OPTIONS":
        return await call_next(request)
        
    path = request.url.path
    is_api = any(path == p or path.startswith(p + "/") for p in API_PATHS)

    client_host = request.client.host if request.client else "127.0.0.1"
    is_testing = is_test_environment()
    is_local = is_testing or client_host in ("127.0.0.1", "::1", "localhost", "testserver")
    
    if is_api and not is_local:
        if is_blocked(client_host):
            record_failure(client_host)
            retry = block_remaining(client_host)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Too many failed attempts. Try again in {retry}s.",
                    "retry_after_seconds": retry
                },
                headers={"Retry-After": str(retry)}
            )
        # Check authentication token/credentials
        token = ""
        auth_header = request.headers.get("Authorization", "")
        
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                username, password = decoded.split(":", 1)
                if verify_user_password(username, password):
                    record_success(client_host)
                    return await call_next(request)
            except Exception:
                pass
                
        if not token:
            token = request.headers.get("X-ComfyLAB-Auth", "").strip()
            
        if not token:
            token = request.query_params.get("token", "").strip()
            
        # Validate token against SESSION_TOKEN or custom_users
        is_valid = verify_access_token(token)
                    
        if not is_valid:
            if is_first_attempt(client_host):
                print(f"\033[1;35m[ComfyLAB] Remote Access Token: {SERVER_TOKEN}\033[0m")
            record_failure(client_host)
            if is_blocked(client_host):
                retry = block_remaining(client_host)
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Too many failed attempts. Try again in {retry}s.",
                        "retry_after_seconds": retry
                    },
                    headers={"Retry-After": str(retry)}
                )
            retry_hint = f" {remaining_attempts(client_host)} attempt(s) remaining before temporary block."
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: Invalid or missing remote access token/credentials." + retry_hint}
            )

    record_success(client_host)
    return await call_next(request)

# Enable CORS for frontend cross-origin requests (must be outermost so error responses get CORS headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(execution_router)
app.include_router(settings_router)
app.include_router(diagnostics_router)
app.include_router(workspace_router)
app.include_router(packages_router)
app.include_router(blocks_router)
app.include_router(updates_router)
app.include_router(store_router)

@app.on_event("startup")
async def startup_event():
    config = get_config()
    last_ws = config.get("last_workspace", "")
    if last_ws:
        try:
            ws_path = Path(last_ws)
            set_workspace_path(last_ws)
            logger.info(f"Auto-restored last workspace: {last_ws}")
            
            # Clean up temporary package files on server startup
            for subdir in ["blueprints", "blocks", "clusters"]:
                temp_dir = ws_path / subdir / ".temp"
                if temp_dir.exists():
                    try:
                        shutil.rmtree(temp_dir)
                        logger.info(f"Purged temporary directory on startup: {temp_dir}")
                    except Exception as purge_err:
                        logger.error(f"Failed to purge temporary directory {temp_dir} on startup: {purge_err}")
            tmp_dir = ws_path / ".tmp"
            if tmp_dir.exists():
                try:
                    shutil.rmtree(tmp_dir)
                    logger.info(f"Purged runtime temp directory on startup: {tmp_dir}")
                except Exception as purge_err:
                    logger.error(f"Failed to purge runtime temp directory {tmp_dir} on startup: {purge_err}")
        except Exception as e:
            logger.error(f"Failed to auto-restore last workspace {last_ws}: {e}")
    try:
        load_all_clusters_deferred()
        logger.info(f"Cluster loading complete. Total registered blocks: {len(BLOCK_REGISTRY)}")
    except Exception as e:
        logger.error(f"Cluster loading skipped (will retry on reload): {e}")

    # Auto-sync Store subscriptions in the background if enabled
    async def _bg_store_sync():
        await asyncio.sleep(2.0)  # Defer slightly so server finishes binding
        try:
            from backend.routers.store import load_subscriptions, sync_subscriptions
            subs = load_subscriptions()
            if subs.get("auto_sync_on_startup", True) and subs.get("subscriptions"):
                await sync_subscriptions()
        except Exception as err:
            logger.debug(f"Store background startup sync completed or skipped: {err}")

    if not is_test_environment():
        asyncio.create_task(_bg_store_sync())

    if not is_test_environment():
        port = get_frontend_port()
        remote_ips = get_local_ip_addresses()

        max_target_len = max(
            [len(f"http://{ip}:{port} ({fqdn})") if fqdn else len(f"http://{ip}:{port}") for ip, fqdn in remote_ips]
            + [len(f"http://127.0.0.1:{port}")]
        )
        width = max(64, max_target_len + 26)

        print("\033[1;35m")
        print("  " + "=" * width)
        print(f"   [ComfyLAB Security] Remote Access Token: {SERVER_TOKEN}")
        print("  " + "-" * width)
        print(f"   Local browser access: http://127.0.0.1:{port}")
        if remote_ips:
            first_ip, first_host = remote_ips[0]
            first_target = f"http://{first_ip}:{port}" + (f" ({first_host})" if first_host else "")
            print(f"   Remote access:        {first_target}")
            for ip, host in remote_ips[1:]:
                target = f"http://{ip}:{port}" + (f" ({host})" if host else "")
                print(f"                         {target}")
        print("  " + "=" * width)
        print("\033[0m")

IS_TESTING = is_test_environment()
FRONTEND_DIST = get_frontend_dist_path()

if FRONTEND_DIST.exists() and not IS_TESTING:
    logger.info(f"Serving pre-compiled frontend from: {FRONTEND_DIST}")
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")
else:
    logger.info("Pre-compiled frontend not found or in testing mode. Fallback API route active.")
    @app.get("/")
    async def read_root():
        return {
            "status": "online",
            "service": "ComfyLAB Core Engine API"
        }
