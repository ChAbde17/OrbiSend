import os
import sys
import json
import time
import hashlib
import threading
from urllib.parse import parse_qs, urlparse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

# Import our custom modules
from core.parser import PKGParser
from core.network import NetworkManager
from core.server import PKGServerManager, stats, SilentThreadingHTTPServer
from core.ps4_client import PS4Client

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

def load_config() -> dict:
    defaults = {
        "ps4_ip": "192.168.1.34",
        "ps4_port": 12800,
        "server_ip": "192.168.1.32",
        "server_port": 8080,
        "web_port": 5000,
        "pkg_directory": "/home/abde/Documents/PKG",
        "deep_scan": False
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception as e:
            print(f"[!] Warning: Could not read {CONFIG_FILE}: {e}")
    return defaults

def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: Could not save {CONFIG_FILE}: {e}")

class AppState:
    def __init__(self):
        self.config = load_config()
        self.stream_server = PKGServerManager(
            port=self.config["server_port"],
            pkg_dir=self.config["pkg_directory"]
        )
        self.ps4 = PS4Client(
            ps4_ip=self.config["ps4_ip"],
            port=self.config["ps4_port"]
        )
        self.pkg_cache = {}
        self.task_history = {}
        self.active_task = None
        self._lock = threading.Lock()

    def update_config(self, new_cfg: dict):
        with self._lock:
            self.config.update(new_cfg)
            save_config(self.config)
            self.ps4.ps4_ip = self.config["ps4_ip"]
            self.ps4.port = self.config["ps4_port"]
            self.stream_server.pkg_dir = self.config["pkg_directory"]

state = AppState()

class WebDashboardHandler(SimpleHTTPRequestHandler):
    """Handles REST API and static Web UI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        # Only log non-polling API calls to prevent clutter
        if "api" in self.path and "progress" not in self.path and "status" not in self.path:
            sys.stdout.write(f"[Web API] {self.command} {self.path} - {args[1]}\n")

    def send_json(self, data: dict, status: int = 200):
        try:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Client browser refreshed or closed tab - safely ignore
            pass

    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path

        if path == "/api/config":
            self.send_json(state.config)
            return

        if path == "/api/status":
            ps4_res = NetworkManager.check_ps4_status(
                state.config["ps4_ip"],
                state.config["ps4_port"],
                timeout=2.0
            )
            local_ips = NetworkManager.list_all_local_ips()
            if not state.config.get("server_ip") or state.config["server_ip"] == "127.0.0.1":
                state.config["server_ip"] = NetworkManager.get_local_ip_for_target(state.config["ps4_ip"])

            self.send_json({
                "ps4_online": ps4_res["online"],
                "ps4_details": ps4_res,
                "local_ips": local_ips,
                "current_server_ip": state.config["server_ip"]
            })
            return

        if path == "/api/active_task":
            # Returns currently persisted active task (survives browser refresh)
            self.send_json(state.active_task or {"running": False})
            return

        if path == "/api/progress":
            query = parse_qs(url.query)
            task_id = int(query.get("task_id", [0])[0])
            if not task_id:
                self.send_json({"error": "Missing task_id"}, 400)
                return

            # 1. Query PS4 status
            ps4_res = state.ps4.get_progress(task_id)

            # 2. Query our zero-copy streaming stats directly from kernel socket
            active_stream = stats.get_latest()

            res = {
                "status": "success",
                "task_id": task_id,
                "transferred": 0,
                "total": 0,
                "percentage": 0.0,
                "speed_mb": 0.0,
                "rest_sec": 0,
                "state": ps4_res.get("state", 0),
                "ps4_raw": ps4_res
            }

            # Prioritize live socket statistics if active
            if active_stream:
                res["transferred"] = active_stream.get("current_offset", 0)
                res["total"] = active_stream.get("file_size", 0)
                res["percentage"] = active_stream.get("percentage", 0.0)
                res["speed_mb"] = active_stream.get("speed_mb", 0.0)

            # If PS4 reports data, combine or override if higher
            ps4_transferred = ps4_res.get("transferred", 0)
            ps4_total = ps4_res.get("total", 0)
            if ps4_transferred > res["transferred"]:
                res["transferred"] = ps4_transferred
            if ps4_total > res["total"]:
                res["total"] = ps4_total
            if res["total"] > 0:
                res["percentage"] = round((res["transferred"] / res["total"]) * 100, 2)

            # Fallback speed calculation based on delta transferred
            now = time.time()
            if res["speed_mb"] <= 0:
                hist = state.task_history.get(task_id, {"bytes": res["transferred"], "time": now, "speed": 0.0})
                elapsed = max(now - hist["time"], 0.001)
                delta = max(res["transferred"] - hist["bytes"], 0)
                if elapsed >= 0.8:
                    calc_speed = round((delta / (1024**2)) / elapsed, 1)
                    res["speed_mb"] = calc_speed
                    state.task_history[task_id] = {"bytes": res["transferred"], "time": now, "speed": calc_speed}
                else:
                    res["speed_mb"] = hist.get("speed", 0.0)

            # Calculate ETA
            if res["speed_mb"] > 0 and res["total"] > res["transferred"]:
                rem_bytes = res["total"] - res["transferred"]
                res["rest_sec"] = int(rem_bytes / (res["speed_mb"] * 1024 * 1024))
            elif ps4_res.get("rest_sec"):
                res["rest_sec"] = ps4_res["rest_sec"]

            # Update state.active_task so state is seamlessly preserved on browser refresh
            if state.active_task and (state.active_task.get("task_id") == task_id or not state.active_task.get("task_id")):
                state.active_task["task_id"] = task_id
                state.active_task["percentage"] = res["percentage"]
                state.active_task["speed_mb"] = res["speed_mb"]
                state.active_task["transferred_gb"] = f"{res['transferred'] / (1024**3):.2f}"
                state.active_task["total_gb"] = f"{res['total'] / (1024**3):.2f}"
                
                if res["rest_sec"] > 0:
                    m = res["rest_sec"] // 60
                    s = res["rest_sec"] % 60
                    state.active_task["eta"] = f"{m}m {s}s"
                else:
                    state.active_task["eta"] = "--"

                # Check completion
                if res["percentage"] >= 100 or ps4_res.get("state") in (3, 5):
                    res["completed"] = True
                    state.active_task["running"] = False

            self.send_json(res)
            return

        # Serve static Web Dashboard index.html
        if path == "/" or not os.path.exists(os.path.join(WEB_DIR, path.lstrip("/"))):
            self.path = "/index.html"
            try:
                return super().do_GET()
            except (BrokenPipeError, ConnectionResetError):
                return

        try:
            return super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/config":
            state.update_config(payload)
            self.send_json({"status": "success", "config": state.config})
            return

        if path == "/api/scan":
            scan_dir = payload.get("directory", state.config["pkg_directory"])
            deep_scan = payload.get("deep_scan", state.config.get("deep_scan", False))
            if not os.path.isdir(scan_dir):
                self.send_json({"error": f"Directory not found: {scan_dir}", "packages": []}, 404)
                return

            packages = []
            try:
                pkg_files = PKGParser.scan_directory(scan_dir, deep_scan=deep_scan)
                for full_path in pkg_files:
                    meta = PKGParser.parse_pkg(full_path, extract_icon=True)
                    file_id = hashlib.md5(full_path.encode("utf-8")).hexdigest()[:12]
                    state.stream_server.register_package(file_id, full_path)
                    meta["file_id"] = file_id
                    rel_path = os.path.relpath(full_path, scan_dir)
                    meta["rel_path"] = rel_path
                    meta["subdir"] = os.path.dirname(rel_path) if os.path.dirname(rel_path) else ""
                    packages.append(meta)
            except Exception as e:
                self.send_json({"error": str(e), "packages": []}, 500)
                return

            self.send_json({"status": "success", "packages": packages, "count": len(packages), "deep_scan": deep_scan})
            return

        if path == "/api/install":
            file_path = payload.get("path")
            if not file_path or not os.path.isfile(file_path):
                self.send_json({"error": "Invalid or missing file path", "status": "fail"}, 400)
                return

            file_id = hashlib.md5(file_path.encode("utf-8")).hexdigest()[:12]
            state.stream_server.register_package(file_id, file_path)

            server_ip = state.config.get("server_ip") or NetworkManager.get_local_ip_for_target(state.config["ps4_ip"])
            port = state.config.get("server_port", 8080)
            
            clean_url = f"http://{server_ip}:{port}/pkg/{file_id}.pkg"
            print(f"\n[+] Initiating Install: {clean_url} -> PS4 ({state.config['ps4_ip']})")

            install_res = state.ps4.install([clean_url], timeout=120.0)
            task_id = install_res.get("task_id")

            if task_id is not None:
                state.ps4.start_task(task_id)
                state.ps4.resume_task(task_id)

                meta = PKGParser.parse_pkg(file_path, extract_icon=True)
                fsize = os.path.getsize(file_path)
                filename = os.path.basename(file_path)

                # Persist active task in backend
                state.active_task = {
                    "running": True,
                    "task_id": task_id,
                    "title": meta.get("title") or filename,
                    "title_id": meta.get("title_id", ""),
                    "category": meta.get("category", "Package"),
                    "filename": filename,
                    "file_path": file_path,
                    "file_size": fsize,
                    "icon": meta.get("icon_base64"),
                    "percentage": 0.0,
                    "speed_mb": 0.0,
                    "transferred_gb": "0.00",
                    "total_gb": f"{fsize / (1024**3):.2f}",
                    "eta": "Calculating...",
                    "start_time": time.time()
                }

                self.send_json({
                    "status": "success",
                    "task_id": task_id,
                    "url": clean_url,
                    "active_task": state.active_task,
                    "details": install_res
                })
            else:
                self.send_json({
                    "status": "fail",
                    "error": install_res.get("error", "PS4 rejected the install request."),
                    "details": install_res
                }, 500)
            return

        if path == "/api/task/control":
            action = payload.get("action")
            task_id = payload.get("task_id")
            if not task_id or not action:
                self.send_json({"error": "Missing task_id or action"}, 400)
                return

            if action == "pause":
                res = state.ps4.pause_task(task_id)
            elif action == "resume":
                res = state.ps4.resume_task(task_id)
            elif action == "stop":
                res = state.ps4.stop_task(task_id)
                if state.active_task:
                    state.active_task["running"] = False
            else:
                res = {"error": "Invalid action"}

            self.send_json(res)
            return

        self.send_json({"error": "Endpoint not found"}, 404)

def run_app():
    cfg = state.config
    
    # 1. Start Zero-Copy Background HTTP Streaming Server
    state.stream_server.start()

    # 2. Start Dashboard Web Server using SilentThreadingHTTPServer
    web_port = cfg.get("web_port", 5000)
    server_address = ("0.0.0.0", web_port)
    dashboard_server = SilentThreadingHTTPServer(server_address, WebDashboardHandler)
    dashboard_server.allow_reuse_address = True

    local_ip = cfg.get("server_ip") or NetworkManager.get_local_ip_for_target(cfg["ps4_ip"])

    print("\n" + "=" * 60)
    print("  OrbisSend — PS4 Remote PKG Manager (Pro)")
    print("=" * 60)
    print(f"  Web Dashboard:  http://localhost:{web_port}")
    print(f"  LAN Access:     http://{local_ip}:{web_port}")
    print(f"  Streaming Port: {cfg['server_port']} (Zero-Copy sendfile enabled)")
    print(f"  Target PS4:     {cfg['ps4_ip']}:{cfg['ps4_port']}")
    print("=" * 60)
    print("  Open the Web Dashboard link in your browser to manage PKGs.\n")

    try:
        dashboard_server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down OrbisSend...")
        state.stream_server.stop()
        dashboard_server.shutdown()
        print("Done.")

if __name__ == "__main__":
    run_app()
