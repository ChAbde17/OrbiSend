import socket
import urllib.request
import json

class NetworkManager:
    """Handles LAN IP detection and PS4 connection diagnostics."""

    @staticmethod
    def get_local_ip_for_target(target_ip: str) -> str:
        """Determines the best local IPv4 address used to route to the target IP."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Does not send actual packets; kernel resolves interface routing table
            s.connect((target_ip, 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = "127.0.0.1"
        finally:
            s.close()
        return local_ip

    @staticmethod
    def list_all_local_ips() -> list:
        """Finds all non-loopback IPv4 addresses on the host system."""
        ips = set()
        try:
            # Method 1: Hostname lookup
            host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
            for ip in host_ips:
                if not ip.startswith("127."):
                    ips.add(ip)
        except Exception:
            pass

        # Method 2: Common subnet probing
        for test_target in ["8.8.8.8", "192.168.1.1", "192.168.0.1", "10.0.0.1"]:
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect((test_target, 80))
                ip = s.getsockname()[0]
                if not ip.startswith("127."):
                    ips.add(ip)
            except Exception:
                pass
            finally:
                if s:
                    s.close()

        res = list(ips)
        # Filter out common docker / virtual interfaces if possible
        res.sort(key=lambda x: (not x.startswith("192.168."), not x.startswith("10."), x))
        return res if res else ["127.0.0.1"]

    @staticmethod
    def check_ps4_status(ps4_ip: str, port: int = 12800, timeout: float = 3.0) -> dict:
        """Checks if Flatz Remote Package Installer is running on the PS4."""
        url = f"http://{ps4_ip}:{port}/api/is_exists"
        req = urllib.request.Request(
            url,
            data=b'{"title_id":"CUSA00000"}',
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8", errors="ignore"))
                    return {
                        "online": True,
                        "status": "connected",
                        "message": "Remote Package Installer is online and responsive.",
                        "details": data
                    }
        except urllib.error.HTTPError as e:
            # Even a 400/500 from the RPI daemon proves port 12800 is alive
            return {
                "online": True,
                "status": "reachable",
                "message": f"PS4 responded with HTTP {e.code}.",
                "details": {}
            }
        except socket.timeout:
            return {
                "online": False,
                "status": "timeout",
                "message": "Connection timed out. Ensure Remote Package Installer is open on your PS4."
            }
        except ConnectionRefusedError:
            return {
                "online": False,
                "status": "refused",
                "message": "Connection refused on port 12800. Is the RPI app open on the PS4?"
            }
        except Exception as e:
            return {
                "online": False,
                "status": "offline",
                "message": str(e)
            }
        return {"online": False, "status": "unknown", "message": "Unknown status"}
