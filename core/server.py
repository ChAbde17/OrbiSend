import os
import re
import time
import socket
import threading
from urllib.parse import unquote
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

class SilentThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that suppresses BrokenPipeError tracebacks on client disconnect."""
    def handle_error(self, request, client_address):
        ex_type, ex_val, _ = sys.exc_info()
        if ex_type in (BrokenPipeError, ConnectionResetError):
            return
        super().handle_error(request, client_address)

class StreamingStats:
    """Thread-safe statistics tracking for active transfers."""
    def __init__(self):
        self._lock = threading.Lock()
        self.active_transfers = {}

    def update(self, transfer_id: str, bytes_sent: int, total_bytes: int, speed_mb: float, current_offset: int = 0, file_size: int = 0):
        with self._lock:
            total = file_size or total_bytes
            pct = round((current_offset / total * 100), 2) if total > 0 else 0.0
            self.active_transfers[transfer_id] = {
                "bytes_sent": bytes_sent,
                "current_offset": current_offset,
                "file_size": total,
                "total_bytes": total_bytes,
                "speed_mb": round(speed_mb, 1),
                "percentage": pct,
                "updated_at": time.time(),
            }

    def remove(self, transfer_id: str):
        with self._lock:
            self.active_transfers.pop(transfer_id, None)

    def get_latest(self):
        with self._lock:
            now = time.time()
            valid = {k: v for k, v in self.active_transfers.items() if now - v["updated_at"] <= 10}
            if not valid:
                return None
            # Return the transfer updated most recently
            latest_key = max(valid.keys(), key=lambda k: valid[k]["updated_at"])
            return valid[latest_key]

    def get_all(self):
        with self._lock:
            now = time.time()
            stale = [k for k, v in self.active_transfers.items() if now - v["updated_at"] > 10]
            for k in stale:
                del self.active_transfers[k]
            return dict(self.active_transfers)

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

    def translate_path(self, path: str) -> str:
        clean = unquote(path.split("?")[0].split("#")[0]).lstrip("/")

        # Check registered alias: /pkg/<id>.pkg
        if clean.startswith("pkg/"):
            file_id = clean[4:].rstrip(".pkg")
            if file_id in self.file_registry:
                return self.file_registry[file_id]

        # Check directly in default PKG directory
        direct_path = os.path.join(self.pkg_directory, clean)
        if os.path.isfile(direct_path):
            return direct_path

        return direct_path

    def do_HEAD(self):
        self.handle_file_request(send_body=False)

    def do_GET(self):
        self.handle_file_request(send_body=True)

    def handle_file_request(self, send_body=True):
        filepath = self.translate_path(self.path)

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

        transfer_id = os.path.basename(filepath)
        sock_fd = self.connection.fileno()

        start_time = time.time()
        last_log = start_time
        bytes_transferred = 0

        try:
            with open(filepath, "rb") as f:
                file_fd = f.fileno()
                current_offset = start
                remaining = content_length

                # Try zero-copy kernel sendfile first
                has_sendfile = hasattr(os, "sendfile")

                while remaining > 0:
                    chunk_to_send = min(remaining, 8 * 1024 * 1024)  # 8MB bursts
                    
                    if has_sendfile:
                        try:
                            sent = os.sendfile(sock_fd, file_fd, current_offset, chunk_to_send)
                            if sent == 0:
                                break
                            current_offset += sent
                            bytes_transferred += sent
                            remaining -= sent
                        except (OSError, AttributeError):
                            # Fallback to buffered transfer if sendfile unsupported on socket
                            has_sendfile = False
                    
                    if not has_sendfile:
                        f.seek(current_offset)
                        chunk = f.read(min(remaining, 2 * 1024 * 1024))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        current_offset += len(chunk)
                        bytes_transferred += len(chunk)
                        remaining -= len(chunk)

                    now = time.time()
                    if now - last_log >= 0.5:
                        elapsed = max(now - start_time, 0.001)
                        speed_mb = (bytes_transferred / (1024**2)) / elapsed
                        stats.update(
                            transfer_id=transfer_id,
                            bytes_sent=bytes_transferred,
                            total_bytes=content_length,
                            speed_mb=speed_mb,
                            current_offset=current_offset,
                            file_size=file_size
                        )
                        last_log = now

        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            stats.remove(transfer_id)

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
