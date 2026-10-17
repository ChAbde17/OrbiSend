import os
import struct
import base64

class PKGParser:
    """
    High-performance parser for PS4 Fake PKG (fPKG) containers.
    Extracts Content ID, Title ID, Game Title, Version, Category, and icon0.png.
    """

    MAGIC_PKG = b"\x7FCNT"
    MAGIC_SFO = b"\x00PSF"

    ENTRY_PARAM_SFO = 0x1000
    ENTRY_ICON0_PNG = 0x1200

    CATEGORY_MAP = {
        "gd": "Base Game",
        "gp": "Update / Patch",
        "ac": "Add-on / DLC",
        "gda": "System App",
        "gde": "Digital Edition",
    }

    @staticmethod
    def parse_sfo(data: bytes) -> dict:
        """Parses a param.sfo binary buffer into a key-value dictionary."""
        if len(data) < 20 or data[:4] != PKGParser.MAGIC_SFO:
            return {}

        magic, version, key_table_offset, data_table_offset, num_entries = struct.unpack("<IIIII", data[:20])
        entries = []
        offset = 20

        for _ in range(num_entries):
            if offset + 16 > len(data):
                break
            key_off, data_fmt, data_len, max_len, data_off = struct.unpack("<HHIII", data[offset:offset+16])
            entries.append((key_off, data_fmt, data_len, data_off))
            offset += 16

        result = {}
        for key_off, data_fmt, data_len, data_off in entries:
            # Read key from key table
            k_start = key_table_offset + key_off
            k_end = data.find(b"\x00", k_start)
            if k_end == -1:
                k_end = len(data)
            key = data[k_start:k_end].decode("utf-8", errors="ignore")

            # Read value from data table
            v_start = data_table_offset + data_off
            v_data = data[v_start:v_start + data_len]

            if data_fmt in (0x0204, 0x0004):  # UTF-8 string
                val = v_data.rstrip(b"\x00").decode("utf-8", errors="ignore")
            elif data_fmt == 0x0404:          # Integer (32-bit LE)
                val = struct.unpack("<I", v_data[:4])[0] if len(v_data) >= 4 else 0
            else:
                val = v_data

            result[key] = val

        return result

    @classmethod
    def parse_pkg(cls, file_path: str, extract_icon: bool = True) -> dict:
        """Reads PKG header and extracts metadata + icon0."""
        if not os.path.isfile(file_path):
            return {"error": "File not found"}

        file_size = os.path.getsize(file_path)
        if file_size < 0x1000:
            return {"error": "File too small to be a valid PKG"}

        meta = {
            "file_path": file_path,
            "filename": os.path.basename(file_path),
            "file_size": file_size,
            "content_id": "",
            "title_id": "",
            "title": "",
            "version": "",
            "category": "Unknown",
            "category_code": "",
            "min_fw": "",
            "icon_base64": None,
            "is_valid": False,
        }

        try:
            with open(file_path, "rb") as f:
                header = f.read(0x1000)
                if len(header) < 0x1000 or header[:4] != cls.MAGIC_PKG:
                    meta["error"] = "Invalid PKG magic (expected \\x7FCNT)"
                    meta["title"] = meta["filename"]
                    return meta

                meta["is_valid"] = True

                # Content ID is at offset 0x40 (36 bytes)
                cid_raw = header[0x40:0x40 + 36].rstrip(b"\x00")
                meta["content_id"] = cid_raw.decode("ascii", errors="ignore")

                # Entry table descriptors
                entry_count = struct.unpack(">I", header[0x10:0x14])[0]
                table_offset = struct.unpack(">I", header[0x18:0x1C])[0]
                table_size = struct.unpack(">I", header[0x1C:0x20])[0]

                # Seek to Entry Table
                f.seek(table_offset)
                table_data = f.read(table_size)

                sfo_offset = 0
                sfo_size = 0
                icon_offset = 0
                icon_size = 0

                # Each entry is 32 bytes (0x20)
                for i in range(entry_count):
                    e_start = i * 32
                    if e_start + 32 > len(table_data):
                        break
                    entry_id, fn_off, f1, f2, ent_off, ent_sz = struct.unpack(">IIIIII", table_data[e_start:e_start+24])

                    if entry_id == cls.ENTRY_PARAM_SFO:
                        sfo_offset = ent_off
                        sfo_size = ent_sz
                    elif entry_id == cls.ENTRY_ICON0_PNG and extract_icon:
                        icon_offset = ent_off
                        icon_size = ent_sz

                # Extract and parse param.sfo
                if sfo_offset > 0 and sfo_size > 0 and sfo_size < 1024 * 1024:
                    f.seek(sfo_offset)
                    sfo_data = f.read(sfo_size)
                    sfo_dict = cls.parse_sfo(sfo_data)

                    meta["title"] = sfo_dict.get("TITLE", meta["filename"])
                    meta["title_id"] = sfo_dict.get("TITLE_ID", "")
                    meta["version"] = sfo_dict.get("APP_VER", "1.00")
                    cat_code = sfo_dict.get("CATEGORY", "")
                    meta["category_code"] = cat_code
                    meta["category"] = cls.CATEGORY_MAP.get(cat_code, cat_code or "Unknown")

                    sys_ver = sfo_dict.get("SYSTEM_VER", 0)
                    if isinstance(sys_ver, int) and sys_ver > 0:
                        # Convert e.g. 0x0B000000 -> 11.00
                        major = (sys_ver >> 24) & 0xFF
                        minor = (sys_ver >> 16) & 0xFF
                        meta["min_fw"] = f"{major:02x}.{minor:02x}"

                # Extract icon0.png
                if icon_offset > 0 and icon_size > 0 and icon_size < 5 * 1024 * 1024:
                    f.seek(icon_offset)
                    icon_data = f.read(icon_size)
                    if icon_data.startswith(b"\x89PNG"):
                        meta["icon_base64"] = f"data:image/png;base64,{base64.b64encode(icon_data).decode('ascii')}"

        except Exception as e:
            meta["error"] = str(e)
            if not meta["title"]:
                meta["title"] = meta["filename"]

        if not meta["title"]:
            meta["title"] = meta["filename"]
        if not meta["title_id"] and len(meta["content_id"]) >= 16:
            # Derive Title ID from Content ID (e.g. EP0001-CUSA44372_00-...)
            parts = meta["content_id"].split("-")
            if len(parts) > 1 and "_" in parts[1]:
                meta["title_id"] = parts[1].split("_")[0]

        return meta

    @classmethod
    def scan_directory(cls, directory: str, deep_scan: bool = False) -> list[str]:
        """
        Scans a directory for .pkg files.
        If deep_scan is True, recursively searches all subdirectories.
        """
        if not os.path.isdir(directory):
            return []

        pkg_files = []
        if deep_scan:
            for root, _, filenames in os.walk(directory):
                for fn in filenames:
                    if fn.lower().endswith(".pkg"):
                        pkg_files.append(os.path.join(root, fn))
        else:
            for fn in os.listdir(directory):
                full_path = os.path.join(directory, fn)
                if os.path.isfile(full_path) and fn.lower().endswith(".pkg"):
                    pkg_files.append(full_path)

        pkg_files.sort()
        return pkg_files
