import os
import re
import time
import socket
import threading
from urllib.parse import unquote
import sys
import hashlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

class SilentThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that suppresses BrokenPipeError tracebacks on client disconnect."""
    def handle_error(self, request, client_address):
        ex_type, ex_val, _ = sys.exc_info()
        if ex_type in (BrokenPipeError, ConnectionResetError):
            return
        super().handle_error(request, client_address)

class StreamingStats:
    """Thread-safe statistics tracking for active transfers using sliding-window throughput."""
    def __init__(self):
        self._lock = threading.Lock()
        self.transfers = {}  # file_id -> dict
        self._history = []   # list of (timestamp, byte_count) for sliding-window speed
        self._active_file_id = None

    def record_chunk(self, file_id: str, file_path: str, offset: int, chunk_len: int, total_size: int):
        now = time.time()
        with self._lock:
            self._active_file_id = file_id
            self._history.append((now, chunk_len))

            # Prune samples older than 2.0 seconds
            cutoff = now - 2.0
            self._history = [h for h in self._history if h[0] >= cutoff]

            t = self.transfers.setdefault(file_id, {
                "file_id": file_id,
                "file_path": file_path,
                "filename": os.path.basename(file_path),
                "file_size": total_size,
                "transferred": 0,
                "max_offset": 0,
                "speed_mb": 0.0,
                "percentage": 0.0,
                "last_update": now,
            })

            t["max_offset"] = max(t["max_offset"], offset + chunk_len)
            t["transferred"] = t["max_offset"]
            if total_size > 0:
                t["file_size"] = total_size
            t["last_update"] = now

            if t["file_size"] > 0:
                t["percentage"] = min(round((t["transferred"] / t["file_size"]) * 100, 2), 100.0)

            # Instantaneous speed over sliding window (last 2 seconds)
            if self._history:
                window_bytes = sum(h[1] for h in self._history)
                dt = max(now - self._history[0][0], 0.3)
                t["speed_mb"] = round((window_bytes / (1024 * 1024)) / dt, 1)

    def update(self, transfer_id: str, bytes_sent: int, total_bytes: int, speed_mb: float, current_offset: int = 0, file_size: int = 0):
        """Compatibility wrapper for update."""
        self.record_chunk(transfer_id, transfer_id, current_offset, bytes_sent, file_size or total_bytes)

    def remove(self, transfer_id: str):
        """No-op to prevent wiping transfer telemetry on socket renegotiation."""
        pass

    def get_stats(self, file_id: str = None) -> dict:
        now = time.time()
        with self._lock:
            target_id = file_id or self._active_file_id
            if not target_id or target_id not in self.transfers:
                if self.transfers:
                    target_id = max(self.transfers.keys(), key=lambda k: self.transfers[k]["last_update"])
                else:
                    return None

            t = dict(self.transfers[target_id])
            # If no bytes received in last 2.5 seconds, instantaneous speed is 0
            if now - t["last_update"] > 2.5:
                t["speed_mb"] = 0.0
            t["current_offset"] = t["transferred"]
            return t

    def get_latest(self) -> dict:
        return self.get_stats()

    def get_all(self) -> dict:
        with self._lock:
            return {k: self.get_stats(k) for k in self.transfers}

stats = StreamingStats()

class HighPerformanceRangeHandler(BaseHTTPRequestHandler):
    """
    Zero-copy RFC 7233 Byte Range HTTP server.
    Uses Linux kernel os.sendfile(2) with 4MB TCP buffers for maximum Wi-Fi/LAN throughput.
    """
    # Registered routes: file_id -> absolute path
    file_registry = {}
    pkg_directory = "/home/abde/Documents/PKG"

    def log_message(self, format, *args):
        # Suppress verbose standard HTTP request logs to keep terminal clean
        pass

    def resolve_file(self, path: str):
        clean = unquote(path.split("?")[0].split("#")[0]).lstrip("/")

        # Check registered alias: /pkg/<id>.pkg
        if clean.startswith("pkg/"):
            file_id = clean[4:].removesuffix(".pkg")
            if file_id in self.file_registry:
                return file_id, self.file_registry[file_id]

        # Check directly in default PKG directory
        direct_path = os.path.join(self.pkg_directory, clean)
        file_id = hashlib.md5(direct_path.encode("utf-8")).hexdigest()[:12]
        return file_id, direct_path

    def translate_path(self, path: str) -> str:
        _, filepath = self.resolve_file(path)
        return filepath

    def do_HEAD(self):
        self.handle_file_request(send_body=False)

    def do_GET(self):
        self.handle_file_request(send_body=True)

    def handle_file_request(self, send_body=True):
        file_id, filepath = self.resolve_file(self.path)

        if not os.path.isfile(filepath):
            self.send_error(404, "File not found")
            return

        try:
            file_size = os.path.getsize(filepath)
        except OSError:
            self.send_error(500, "Unable to access file")
            return

        range_header = self.headers.get("Range")
        start = 0
        end = file_size - 1
        is_range = False

        if range_header:
            match = re.match(r"^bytes=(\d*)-(\d*)$", range_header.strip())
            if match:
                s_str, e_str = match.groups()
                if s_str:
                    start = int(s_str)
                if e_str:
                    end = int(e_str)

                if start > end or start >= file_size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.end_headers()
                    return

                if end >= file_size:
                    end = file_size - 1

                is_range = True

        content_length = end - start + 1
        status_code = 206 if is_range else 200

        self.send_response(status_code)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        if is_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(content_length))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        if not send_body:
            return

        # Tune TCP socket for high throughput
        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # Increase send buffer to 4MB for high-speed Wi-Fi / LAN
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        except Exception:
            pass

        sock_fd = self.connection.fileno()

        try:
            with open(filepath, "rb") as f:
                file_fd = f.fileno()
                current_offset = start
                remaining = content_length

                # Try zero-copy kernel sendfile first
                has_sendfile = hasattr(os, "sendfile")

                while remaining > 0:
                    chunk_to_send = min(remaining, 4 * 1024 * 1024)  # 4MB bursts
                    sent = 0

                    if has_sendfile:
                        try:
                            sent = os.sendfile(sock_fd, file_fd, current_offset, chunk_to_send)
                            if sent == 0:
                                break
                        except (BrokenPipeError, ConnectionResetError):
                            break
                        except (OSError, AttributeError):
                            has_sendfile = False

                    if not has_sendfile:
                        try:
                            f.seek(current_offset)
                            chunk = f.read(min(remaining, 1024 * 1024))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            sent = len(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            break

                    if sent > 0:
                        stats.record_chunk(file_id, filepath, current_offset, sent, file_size)
                        current_offset += sent
                        remaining -= sent

        except (BrokenPipeError, ConnectionResetError):
            pass

class PKGServerManager:
    """Manages the background HTTP file streaming server thread."""
    def __init__(self, port: int = 8080, pkg_dir: str = "/home/abde/Documents/PKG"):
        self.port = port
        self.pkg_dir = pkg_dir
        self.httpd = None
        self.thread = None
        self.running = False

    def register_package(self, pkg_id: str, file_path: str):
        HighPerformanceRangeHandler.file_registry[pkg_id] = file_path

    def start(self):
        if self.running:
            return
        HighPerformanceRangeHandler.pkg_directory = self.pkg_dir
        server_address = ("0.0.0.0", self.port)
        self.httpd = SilentThreadingHTTPServer(server_address, HighPerformanceRangeHandler)
        self.httpd.allow_reuse_address = True
        self.running = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        print(f"[+] File Streaming Server active on port {self.port} (Zero-Copy enabled)")

    def stop(self):
        if self.httpd and self.running:
            self.httpd.shutdown()
            self.running = False
