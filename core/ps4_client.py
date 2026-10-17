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
        res = self._post("/api/get_task_progress", {"task_id": task_id}, timeout=3.0)

        def parse_val(v):
            if v is None:
                return 0
            if isinstance(v, (int, float)):
                return int(v)
            if isinstance(v, str):
                v = v.strip()
                if not v:
                    return 0
                if v.startswith("0x") or v.startswith("0X"):
                    try:
                        return int(v, 16)
                    except ValueError:
                        return 0
                try:
                    return int(v)
                except ValueError:
                    try:
                        return int(v, 16)
                    except ValueError:
                        return 0
            return 0

        # Check all possible fields and pick the maximum non-zero value
        t_total = parse_val(res.get("transferred_total"))
        t_trans = parse_val(res.get("transferred"))
        t_bytes = parse_val(res.get("trans_bytes"))
        transferred = max(t_total, t_trans, t_bytes)

        l_total = parse_val(res.get("length_total"))
        l_len = parse_val(res.get("length"))
        l_bytes = parse_val(res.get("total_bytes"))
        total = max(l_total, l_len, l_bytes)

        error = parse_val(res.get("error", 0))
        state = parse_val(res.get("state", 0))
        rest_sec = parse_val(res.get("rest_sec", 0))

        percentage = round((transferred / total * 100), 2) if total > 0 else 0.0

        return {
            "status": "success" if error == 0 else "fail",
            "task_id": task_id,
            "transferred": transferred,
            "total": total,
            "percentage": percentage,
            "state": state,
            "rest_sec": rest_sec,
            "error": error,
            "raw": res
        }
