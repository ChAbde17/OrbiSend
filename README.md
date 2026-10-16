# 🚀 OrbisSend — High-Performance PS4 Remote PKG Manager

<p align="center">
  <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/solid/gamepad.svg" width="80" height="80" alt="OrbisSend Logo" />
</p>

<p align="center">
  <strong>A modern, zero-copy PlayStation 4 Remote Package Installer daemon & responsive Web Dashboard engineered for speed, stability, and elegance.</strong>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://www.kernel.org/"><img src="https://img.shields.io/badge/Kernel-Linux%20Zero--Copy%20sendfile(2)-orange.svg?logo=linux&logoColor=white" alt="Linux Zero-Copy"></a>
  <a href="https://github.com/GoldHEN/GoldHEN"><img src="https://img.shields.io/badge/Target-PS4%20GoldHEN%20%2F%20Flatz%20RPI-gold.svg?logo=playstation&logoColor=white" alt="PS4 RPI"></a>
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="#roadmap--cross-platform-expansion"><img src="https://img.shields.io/badge/Platform-Linux%20(Cross--Platform%20Planned)-purple.svg" alt="Platform"></a>
</p>

---

## 📑 Table of Contents

- [💡 Motivation & Problem Statement](#-motivation--problem-statement)
- [✨ Key Features](#-key-features)
- [📸 Screenshots & UI Showcase](#-screenshots--ui-showcase)
- [🏗️ Technical Architecture](#️-technical-architecture)
- [🚀 Quick Start](#-quick-start)
- [⚙️ Configuration](#️-configuration)
- [🗺️ Roadmap & Cross-Platform Expansion](#️-roadmap--cross-platform-expansion)
- [🌿 Git Workflow & Contributing](#-git-workflow--contributing)
- [🧪 Running Tests](#-running-tests)
- [📜 License](#-license)

---

## 💡 Motivation & Problem Statement

For years, the homebrew PlayStation 4 scene has relied heavily on legacy Remote Package Installers (RPI). However, everyday users and Linux power users face recurring roadblocks with existing tools:

### 1. The Wine / .NET Dependency Quagmire on Linux
Most popular GUI package senders (such as Modded PKG Sender v1/v2 or DirectPKG) are closed-source or written in legacy C# / .NET Windows Forms. On modern Linux distributions (Arch, CachyOS, Fedora, Ubuntu), running these applications via Wine or Mono leads to:
* Frequent GTK theme rendering glitches and unreadable text.
* Broken or frozen native file chooser dialogs.
* High background CPU and RAM utilization.

### 2. Slow Userspace Transfers Capping Gigabit & Wi-Fi Speeds
Conventional Python HTTP servers or generic file sharing scripts use standard user-space copy loops:
```python
# Naive approach: double context switches & user-space memory thrashing
while chunk := f.read(65536):
    socket.send(chunk)
```
Transferring 40GB–80GB retail package dumps using naive chunking incurs millions of user/kernel-space context switches. On high-speed Wi-Fi or Gigabit LAN, this bottlenecks transfer rates significantly below line speed.

### 3. Fragile Sony `sceHttp` URI Parser Failures
The PlayStation 4 internal HTTP download daemon (`sceHttp` / Flatz RPI) is notoriously brittle when parsing URLs:
* Package filenames containing spaces, brackets (`[CUSA00123]`), or non-ASCII characters frequently trigger silent installation failures, `0x809900xx` network errors, or console download freezes.
* Standard web servers serve files directly using their raw filesystem path, passing problematic query parameters or unencoded strings to the console.

### 4. Broken Pipe Exceptions & State Loss on Browser Refresh
Standard HTTP daemon servers crash or log noisy stack traces (`BrokenPipeError`) whenever a client terminates a connection prematurely (e.g., closing a browser tab or when the console pauses an active chunk). Furthermore, existing web tools track download progress purely in ephemeral browser memory; refreshing the page resets the progress bar and speedometer to zero, leaving the user with no visibility into the actual ongoing transfer.

### 🎯 The Solution: OrbisSend
**OrbisSend** was engineered from the ground up to solve every single one of these problems:
* **Zero Wine/Mono dependency**: Pure, asynchronous Python with zero heavy native build dependencies.
* **Kernel-level Zero-Copy Streaming**: Direct kernel-to-socket transfer via `os.sendfile(2)` and tuned 4MB TCP buffers (`SO_SNDBUF` & `TCP_NODELAY`).
* **Virtual Collision-Free Routing**: Aliased, sanitized endpoints (`/pkg/<file_id>.pkg`) guarantee 100% compatibility with Sony's URL parser.
* **Resilient State & Connection Handling**: Full suppression of client disconnect errors, graceful range recovery, and persistent transfer state that survives page refreshes and server reboots.
* **Universal Access**: A modern, responsive web application that runs headlessly on your PC, home server, or NAS, operable from your desktop browser or phone.

---

## ✨ Key Features

* **⚡ Ultra-Fast Zero-Copy Streaming**:
  Uses Linux `os.sendfile(2)` to stream bytes directly from disk storage to network sockets without touching userspace memory buffers.
* **🔍 On-the-Fly Binary PKG & SFO Inspection**:
  Parses raw `\x7FCNT` container headers directly on disk to read `param.sfo` metadata (Game Title, Title ID, Category, Software Version) and extracts embedded `icon0.png` cover art as base64 data URIs.
* **🌐 Intelligent Subnet & Interface Discovery**:
  Automatically probes local network routing tables to detect the true physical IP address matching the PS4's subnet, safely filtering out Docker, loopback, and virtual VM interfaces.
* **🛡️ Collision-Free Sanitized Aliasing**:
  Translates complex package filenames into clean `/pkg/<file_id>.pkg` routes, shielding the PS4's `sceHttp` client from encoding errors.
* **📊 Live Telemetry & Persistent Progress**:
  Real-time streaming metrics (Transferred bytes, Total size, Progress percentage, Speed in MB/s, and ETA). State is synced across both server and client `localStorage`.
* **📱 Responsive Dark Dashboard**:
  Tailwind CSS + Alpine.js single-page dashboard designed for desktops, laptops, tablets, and mobile phones.
* **🎮 GoldHEN & Remote Package Installer Compatible**:
  Native support for Flatz RPI protocol (port `12800`), compatible with PS4 firmware 5.05 through 11.00+ and GoldHEN v2.4b+.

---

## 📸 Screenshots & UI Showcase

> *Screenshots are stored in `docs/screenshots/` (placeholder assets below).*

### 1. Main Dashboard & Package Library
Browse your local package library with high-resolution game icons, Title IDs, version tags, and one-click installation triggers:

```
+-----------------------------------------------------------------------------------+
| 🎮 OrbisSend Pro                     [● PS4 Connected: 192.168.1.34]  [⚙ Settings] |
+-----------------------------------------------------------------------------------+
| [/home/abde/Documents/PKG                                ]  [🔍 Scan Directory]   |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  +--------------------+  +--------------------+  +--------------------+           |
|  | [ GAME COVER ART ] |  | [ GAME COVER ART ] |  | [ GAME COVER ART ] |           |
|  | Bloodborne         |  | Ghost of Tsushima  |  | Horizon Zero Dawn  |           |
|  | CUSA03173 • v01.00 |  | CUSA16972 • v02.18 |  | CUSA07320 • v01.52 |           |
|  | 29.83 GB           |  | 44.12 GB           |  | 48.16 GB           |           |
|  | [ Send to PS4 ]    |  | [ Send to PS4 ]    |  | [ Send to PS4 ]    |           |
|  +--------------------+  +--------------------+  +--------------------+           |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### 2. Live Transfer Monitor (Zero-Copy Sendfile)
Real-time transfer telemetry tracking kernel byte offsets, transfer speed, and remaining time:

```
+-----------------------------------------------------------------------------------+
| 🚀 Active Installation: Bloodborne (CUSA03173)                                    |
| [=======================================>-----------------------] 64.2%          |
| Transferred: 19.15 GB / 29.83 GB | Speed: 38.45 MB/s | ETA: 4m 38s                |
| [ ⏸ Pause ]  [ ▶ Resume ]  [ ⏹ Cancel ]                                         |
+-----------------------------------------------------------------------------------+
```

### 3. Connection & Configuration Modal
Easily configure console network endpoints and server parameters directly from the UI without modifying config files manually:

```
+----------------------------------------------------+
| ⚙️ PS4 Connection & Network Settings               |
+----------------------------------------------------+
| PS4 IP Address:        [ 192.168.1.34           ]  |
| PS4 RPI Port:          [ 12800                  ]  |
| Host Server IP:        [ 192.168.1.32           ]  |
| Streaming Port:        [ 5000                   ]  |
| Default PKG Directory: [ /home/abde/Documents/PKG] |
|                                                    |
| [ Test Connection ]                  [ Save Config ]|
+----------------------------------------------------+
```

---

## 🏗️ Technical Architecture

```
┌────────────────────────────────────────────────────────┐
│                      Web Browser                       │
│       (Desktop / Smartphone - Alpine.js + Tailwind)     │
└───────────────▲────────────────────────▲───────────────┘
                │ REST API               │ Status Polling
                ▼                        ▼
┌────────────────────────────────────────────────────────┐
│                   app.py (Orchestrator)                │
│   ├── /api/scan       - Directory Scanner & Parser     │
│   ├── /api/install    - RPI Handshake & Task Launcher  │
│   ├── /api/progress   - Real-Time Byte Offset Tracker  │
│   └── /api/config     - Live Configuration Manager     │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
       Invokes  ▼               Dispatches ▼ Handshake
┌────────────────────────┐      ┌────────────────────────┐
│   core/parser.py       │      │   core/ps4_client.py   │
│ ├── \x7FCNT Header     │      │ ├── Check API (12800)  │
│ ├── param.sfo Reader   │      │ ├── POST /install      │
│ └── icon0.png Extractor│      │ └── Task Management    │
└────────────────────────┘      └───────────┬────────────┘
                                            │
                                            ▼ Sends install payload
┌────────────────────────────────────────────────────────┐
│           PlayStation 4 (GoldHEN / Flatz RPI)          │
│               Internal `sceHttp` Client                │
└───────────────────────────┬────────────────────────────┘
                            │ GET /pkg/<id>.pkg (Range RFC 7233)
                            ▼
┌────────────────────────────────────────────────────────┐
│                   core/server.py                       │
│    Zero-Copy RFC 7233 HTTP Streaming Server            │
│    ├── os.sendfile(2) Kernel Bypass Loop               │
│    ├── 4MB Socket Tuning (SO_SNDBUF, TCP_NODELAY)      │
│    └── Silent Disconnect & Broken Pipe Suppression     │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
* **Operating System**: Linux (Kernel 3.0+ for `os.sendfile`), macOS / Windows support in progress.
* **Python**: Python 3.10 or higher.
* **Target PS4**: Jailbroken PS4 running GoldHEN v2.0+ with **Remote Package Installer** open or enabled in GoldHEN settings.

### 1. Clone & Set Up
```bash
git clone https://github.com/your-username/ps4-pkg-sender.git
cd "ps4-pkg-sender"

# Copy the sample configuration
cp config.example.json config.json
```

### 2. Launch the Application
```bash
python3 app.py
```

### 3. Open the Dashboard
Navigate to:
* **Local Machine**: [http://localhost:5000](http://localhost:5000)
* **Mobile / LAN Device**: `http://<YOUR_PC_IP>:5000` (e.g. `http://192.168.1.32:5000`)

---

## ⚙️ Configuration

Settings are saved in `config.json` and can be edited directly or through the Web Dashboard UI:

```json
{
  "ps4_ip": "192.168.1.34",
  "ps4_port": 12800,
  "server_ip": "192.168.1.32",
  "server_port": 5000,
  "pkg_directory": "/home/abde/Documents/PKG"
}
```

| Key | Description | Default |
| :--- | :--- | :--- |
| `ps4_ip` | LAN IP address of your PlayStation 4 | `192.168.1.34` |
| `ps4_port` | Remote Package Installer API port | `12800` |
| `server_ip` | Host PC IP address (auto-detected on launch) | `auto-detected` |
| `server_port` | Web dashboard & streaming server port | `5000` |
| `pkg_directory`| Default directory scanned for `.pkg` files | `~/Documents/PKG` |

---

## 🗺️ Roadmap & Cross-Platform Expansion

While OrbisSend was originally conceived to deliver first-class performance on **Linux**, active development is underway to expand its reach and user experience:

- [ ] **Cross-Platform Kernel Streaming**:
  - [x] Linux: Native `os.sendfile(2)` zero-copy support.
  - [ ] macOS: BSD `sendfile(2)` kernel streaming compatibility layer.
  - [ ] Windows: Windows Socket 2 `TransmitFile` / high-concurrency asynchronous I/O backend.
- [ ] **Standalone Desktop Packaging**:
  - [ ] **AppImage**: Single-click standalone executable for all Linux distributions without installing dependencies.
  - [ ] **Flatpak**: Sandboxed distribution via Flathub with native desktop portal integration.
  - [ ] **Native Desktop Shell**: Lightweight native application window using `pywebview` / Tauri v2 to eliminate the need for an external browser.
- [ ] **Enhanced Installation Queue**:
  - [ ] Drag-and-drop batch installation queue.
  - [ ] Automatic multi-part patch chaining (e.g. base game + v01.01 + DLC sequence).
  - [ ] Scheduled background installs with automatic PC shutdown upon completion.

---

## 🌿 Git Workflow & Contributing

We follow a strict **Git Flow** branching and **Conventional Commits** standard:

```
  main      ───●─────────────● (v1.0.0 Tagged Releases)
                ▲             ▲
                 \           /
  develop   ─────●───●──────●─── (Integration Branch)
                      \    /
  feature/*            ●──●     (Topic / Feature Branches)
```

### Branches
* **`main`**: Production-ready, stable releases tagged with Semantic Versioning (`vX.Y.Z`).
* **`develop`**: Primary integration branch for upcoming features and improvements.
* **`feature/<name>`** or **`docs/<name>`**: Dedicated branches for individual features or documentation updates.

### Commit Convention
Commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
* `feat(...)`: A new feature
* `fix(...)`: A bug fix
* `docs(...)`: Documentation changes
* `refactor(...)`: Code refactoring without behavior change
* `perf(...)`: Performance optimization
* `test(...)`: Adding or updating tests
* `chore(...)`: Maintenance or tooling updates

---

## 🧪 Running Tests

OrbisSend includes a fully automated unit test suite covering binary parsing, networking logic, API client structures, and HTTP range streaming:

```bash
python3 tests/test_all.py
```

---

## 📜 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Crafted with ❤️ for the PlayStation 4 homebrew community.
</p>
