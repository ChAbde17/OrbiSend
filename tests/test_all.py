import os
import sys
import struct
import unittest
import urllib.request
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.parser import PKGParser
from core.network import NetworkManager
from core.server import PKGServerManager
from core.ps4_client import PS4Client

class TestOrbiSend(unittest.TestCase):

    def test_sfo_parser(self):
        # Create a synthetic valid param.sfo binary buffer
        # Header: magic="\x00PSF", version=0x00000101, key_table_offset=20+16, data_table_offset=20+16+10, num_entries=1
        magic = b"\x00PSF"
        version = 0x00000101
        
        # 1 entry: TITLE="Test Game"
        key = b"TITLE\x00"
        val = b"Test Game\x00"
        
        key_table_offset = 20 + 16
        data_table_offset = key_table_offset + len(key)
        num_entries = 1

        header = struct.pack("<4sIIII", magic, version, key_table_offset, data_table_offset, num_entries)
        entry = struct.pack("<HHIII", 0, 0x0204, len(val), len(val), 0)

        sfo_bytes = header + entry + key + val
        parsed = PKGParser.parse_sfo(sfo_bytes)

        self.assertIn("TITLE", parsed)
        self.assertEqual(parsed["TITLE"], "Test Game")

    def test_network_manager(self):
        ips = NetworkManager.list_all_local_ips()
        self.assertIsInstance(ips, list)
        self.assertGreater(len(ips), 0)

        best_ip = NetworkManager.get_local_ip_for_target("192.168.1.1")
        self.assertIsInstance(best_ip, str)

    def test_ps4_client_instantiation(self):
        client = PS4Client("192.168.1.34", 12800)
        self.assertEqual(client.ps4_ip, "192.168.1.34")
        self.assertEqual(client.port, 12800)

    def test_range_server_streaming(self):
        # Create a 1MB test file
        test_file = "/tmp/orbisend_test.pkg"
        test_content = b"0123456789ABCDEF" * (64 * 1024)  # 1MB
        with open(test_file, "wb") as f:
            f.write(test_content)

        test_port = 8899
        server = PKGServerManager(port=test_port, pkg_dir="/tmp")
        server.register_package("test1234", test_file)
        server.start()
        time.sleep(0.5)

        try:
            # Test Range request: bytes 10-25
            url = f"http://127.0.0.1:{test_port}/pkg/test1234.pkg"
            req = urllib.request.Request(url, headers={"Range": "bytes=10-25"})
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 206)
                self.assertEqual(resp.headers.get("Accept-Ranges"), "bytes")
                self.assertEqual(resp.headers.get("Content-Range"), "bytes 10-25/1048576")
                chunk = resp.read()
                self.assertEqual(chunk, test_content[10:26])
        finally:
            server.stop()
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_scan_directory_deep_and_shallow(self):
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp(prefix="orbisend_scan_test_")
        try:
            # Create files in root
            root_pkg = os.path.join(temp_dir, "game_root.pkg")
            txt_file = os.path.join(temp_dir, "notes.txt")
            with open(root_pkg, "wb") as f:
                f.write(b"PKG_DATA")
            with open(txt_file, "wb") as f:
                f.write(b"TEXT_DATA")

            # Create subdirectories with nested .pkg files
            sub_dir = os.path.join(temp_dir, "updates", "v1.01")
            os.makedirs(sub_dir, exist_ok=True)
            nested_pkg = os.path.join(sub_dir, "patch.pkg")
            with open(nested_pkg, "wb") as f:
                f.write(b"PATCH_DATA")

            # 1. Shallow Scan: Only game_root.pkg
            shallow_res = PKGParser.scan_directory(temp_dir, deep_scan=False)
            self.assertEqual(len(shallow_res), 1)
            self.assertEqual(os.path.basename(shallow_res[0]), "game_root.pkg")

            # 2. Deep Scan: Both game_root.pkg and patch.pkg
            deep_res = PKGParser.scan_directory(temp_dir, deep_scan=True)
            self.assertEqual(len(deep_res), 2)
            filenames = [os.path.basename(p) for p in deep_res]
            self.assertIn("game_root.pkg", filenames)
            self.assertIn("patch.pkg", filenames)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_streaming_stats_telemetry(self):
        from core.server import stats
        file_id = "test_fid_123"
        file_path = "/tmp/test_game.pkg"
        total_size = 100 * 1024 * 1024  # 100 MB

        # Record 10MB chunk sent at offset 0
        stats.record_chunk(file_id, file_path, 0, 10 * 1024 * 1024, total_size)
        st = stats.get_stats(file_id)
        self.assertIsNotNone(st)
        self.assertEqual(st["transferred"], 10 * 1024 * 1024)
        self.assertEqual(st["percentage"], 10.0)
        self.assertGreater(st["speed_mb"], 0.0)

        # Record another 15MB chunk sent at offset 10MB
        stats.record_chunk(file_id, file_path, 10 * 1024 * 1024, 15 * 1024 * 1024, total_size)
        st = stats.get_stats(file_id)
        self.assertEqual(st["transferred"], 25 * 1024 * 1024)
        self.assertEqual(st["percentage"], 25.0)

    def test_ps4_client_get_progress_parsing(self):
        client = PS4Client("127.0.0.1", 12800)
        # Mock _post response with flatz RPI hex & field combinations
        client._post = lambda endpoint, payload, timeout: {
            "status": "success",
            "error": 0,
            "transferred_total": "0x40000000",  # 1GB in hex
            "length_total": "0x100000000",      # 4GB in hex
            "transferred": 0,                   # current piece is 0
            "length": 1048576,                  # piece length
            "state": 1,
            "rest_sec": 120
        }
        res = client.get_progress(123)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["transferred"], 0x40000000)
        self.assertEqual(res["total"], 0x100000000)
        self.assertEqual(res["percentage"], 25.0)
        self.assertEqual(res["rest_sec"], 120)

if __name__ == "__main__":
    unittest.main()
