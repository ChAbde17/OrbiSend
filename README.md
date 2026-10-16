# OrbisSend — High-Performance PS4 PKG Manager (Pro)

A modern, lightweight PlayStation 4 Remote Package Installer application engineered specifically for Linux, featuring:

* **Zero-Copy Streaming**: Leverages Linux kernel `os.sendfile(2)` and tuned 4MB socket buffers (`SO_SNDBUF` & `TCP_NODELAY`) to maximize Wi-Fi and Gigabit LAN throughput.
* **PKG & SFO Metadata Extraction**: Automatically parses `\x7FCNT` headers, reads `param.sfo` (Game Title, Title ID, Version, Category), and extracts `icon0.png` cover art.
* **Automatic Route Resolution**: Intelligently identifies your primary LAN IP (`192.168.1.32`) to prevent invalid loopback or Docker IP assignments.
* **Collision-Free Aliased URLs**: Packages are served over clean `/pkg/<id>.pkg` routes, avoiding any URL-encoding bugs or unescaped bracket crashes with Sony's `sceHttp` parser.
* **Persistent Configuration**: Stores your PS4 IP and preferences in `config.json`, which can be viewed and edited in real time directly from the Web Dashboard.
* **Modern Web Dashboard**: Single-page dark UI (Tailwind CSS + Alpine.js) accessible from your PC browser or smartphone.

---

## Quick Start

### 1. Launch the Application
Run the main script from your terminal:
```bash
python3 app.py
```

### 2. Access the Dashboard
Open your browser to:
* **Local PC**: [http://localhost:5000](http://localhost:5000)
* **Mobile / LAN**: `http://192.168.1.32:5000`

---

## Dashboard Features

1. **PS4 Connection Pill**:
   * Shows a live green status when Flatz's Remote Package Installer is open on the PS4.
   * Click the pill or the settings icon to adjust your PS4 IP (`192.168.1.34`), ports, or network interface.
2. **Directory Scanner & Custom Paths**:
   * Scans `/home/abde/Documents/PKG` by default.
   * Type any custom folder path into the input bar and click **Scan Directory** to load packages from external drives or alternate folders.
3. **One-Click Installation**:
   * Click **Send to PS4** on any game card.
   * The app registers the task, triggers the PS4's `start_task` and `resume_task`, and displays live metrics:
     * **Speed (MB/s)**
     * **Percentage (%)**
     * **Transferred / Total Size (GB)**
     * **Estimated Time Remaining (ETA)**
4. **Task Controls**:
   * Pause, Resume, or Cancel active downloads directly from the web interface.

---

## Project Structure

```text
PS4 PKG Sender/
├── app.py              # Main application entry point & Web Dashboard REST API
├── config.json         # Persistent user settings (PS4 IP, ports, paths)
├── core/
│   ├── parser.py       # Binary PKG & param.sfo parser, icon0.png extractor
│   ├── server.py       # Zero-copy os.sendfile RFC 7233 Range HTTP server
│   ├── ps4_client.py   # Flatz RPI JSON REST API client
│   └── network.py      # LAN IP auto-detection & PS4 connection diagnostics
├── web/
│   └── index.html      # Single-page modern reactive web dashboard
└── tests/
    └── test_all.py     # Automated unit test suite
```

---

## Running Unit Tests
To verify the core engine:
```bash
python3 tests/test_all.py
```
