import json
import urllib.request
import urllib.error

class PS4Client:
    """Client for flatz Remote Package Installer JSON REST API on port 12800."""

    def __init__(self, ps4_ip: str = "192.168.1.34", port: int = 12800):
        self.ps4_ip = ps4_ip
        self.port = port

    def _post(self, endpoint: str, payload: dict = None, timeout: float = 30.0) -> dict:
        url = f"http://{self.ps4_ip}:{self.port}{endpoint}"
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="ignore")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="ignore")
            try:
                err_data = json.loads(raw)
                return {"error": err_data.get("error", f"HTTP {e.code}"), "status": "fail"}
            except Exception:
                return {"error": f"HTTP {e.code}: {raw}", "status": "fail"}
        except Exception as e:
            return {"error": str(e), "status": "fail"}

    def is_exists(self, title_id: str = "CUSA00000") -> dict:
        return self._post("/api/is_exists", {"title_id": title_id}, timeout=5.0)

    def install(self, package_urls: list, timeout: float = 120.0) -> dict:
        """Dispatches /api/install with a generous 120s timeout for disk allocation."""
        payload = {
            "type": "direct",
            "packages": package_urls
        }
        return self._post("/api/install", payload, timeout=timeout)

    def start_task(self, task_id: int) -> dict:
        return self._post("/api/start_task", {"task_id": task_id}, timeout=10.0)

    def resume_task(self, task_id: int) -> dict:
        return self._post("/api/resume_task", {"task_id": task_id}, timeout=10.0)

    def pause_task(self, task_id: int) -> dict:
        return self._post("/api/pause_task", {"task_id": task_id}, timeout=10.0)

    def stop_task(self, task_id: int) -> dict:
        return self._post("/api/stop_task", {"task_id": task_id}, timeout=10.0)

    def unregister_task(self, task_id: int) -> dict:
        return self._post("/api/unregister_task", {"task_id": task_id}, timeout=10.0)

    def get_progress(self, task_id: int) -> dict:
        res = self._post("/api/get_task_progress", {"task_id": task_id}, timeout=5.0)
        
        # If explicit error or failure reported by PS4
        if res.get("status") == "fail" and res.get("error", 0) not in (0, "0", None):
            return res

        def parse_val(v):
            if isinstance(v, int):
                return v
            if isinstance(v, str):
                try:
                    return int(v, 16 if v.startswith("0x") else 10)
                except ValueError:
                    return 0
            return 0

        # Support all field variants (transferred, transferred_total, trans_bytes)
        transferred = parse_val(res.get("transferred") or res.get("transferred_total") or res.get("trans_bytes") or 0)
        total = parse_val(res.get("length") or res.get("length_total") or res.get("total") or res.get("total_bytes") or 0)
        error = parse_val(res.get("error", 0))
        state = parse_val(res.get("state", 0))
        rest_sec = parse_val(res.get("rest_sec", 0))

        percentage = (transferred / total * 100) if total > 0 else 0.0

        return {
            "status": "success",
            "task_id": task_id,
            "transferred": transferred,
            "total": total,
            "percentage": round(percentage, 2),
            "state": state,
            "rest_sec": rest_sec,
            "error": error,
            "raw": res
        }
