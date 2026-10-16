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

class TestOrbisSend(unittest.TestCase):

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
        test_file = "/tmp/orbis_test.pkg"
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

if __name__ == "__main__":
    unittest.main()
