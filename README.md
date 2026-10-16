# 🌐 D IP Monitor

A modern, high-performance, enterprise-grade network host and IP infrastructure monitoring suite built with Python and PyQt6. Engineered with a cyber-glassmorphic UI, real-time concurrent ICMP ping engine, multi-channel alerting (Email, Sound, System Popups, Discord/Slack/Teams Webhooks), live latency trend tracking with dynamic crosshairs, and a desktop floating Mini HUD.

---

## 📖 About The Project

**D IP Monitor** (*IP Monitoring Tool by D*) is an advanced, standalone network observability and host availability platform designed for network engineers, system administrators, and DevOps teams.

Equipped with an asynchronous multi-threaded ping engine and a high-DPI dark/light neon visual system, **D IP Monitor** continuously monitors the reachability, response times, and packet stability of mission-critical servers, switches, routers, cameras, and IoT endpoints.

Whether running minimized in the system tray, docked to your primary desktop with the glassmorphic **Mini HUD**, or operating full-screen with interactive live latency graphs, **D IP Monitor** guarantees immediate detection and instant escalation of network incidents across multiple communication channels.

---

## ✨ Comprehensive Feature Details

### ⚡ 1. High-Concurrency Ping Engine & Packet Metrics
- **Asynchronous Multi-Threaded Engine**: Powered by an independent `QThread` engine executing non-blocking ICMP pings across hundreds of target IPs simultaneously.
- **5% Granular Rolling Packet Loss**: Employs a 20-sample rolling buffer calculating exact 5% increments (`0%, 5%, 10%, 15% ... 100%`) for precise packet degradation detection.
- **Accurate Latency Telemetry**: Microsecond-precision timestamp tracking measuring instantaneous, minimum, maximum, and rolling average latency.
- **State Transition Guard**: Built-in consecutive unreachable thresholding prevents transient network noise from causing false-positive alarm fatigue.

### 📈 2. Interactive Live Latency Trend & Hover Inspector
- **Dynamic Crosshair Tracking**: Hovering anywhere across the sparkline curve activates an interactive vertical crosshair tracking line locked to the nearest ping sample.
- **Point Halo Ring & Floating Chip**: Highlights the selected sample with a glowing neon halo ring and renders an on-canvas badge displaying the exact latency (`14.2ms` or `LOST`).
- **Dynamic Sub-Header & Rich Tooltip**: Displays the sample index (`#4 of 30`), relative time (`Latest Ping` or `X pings ago`), target host name, and real-time operational status.
- **Smooth Gradient Fill**: High-DPI anti-aliased canvas rendering with cyan accent fills and responsive resizing.

### 🔔 3. Multi-Channel Alert & Escalation Matrix
- **Automated Email Notifications**: SMTP SSL/TLS notification dispatcher sending structured HTML alerts upon host failure and recovery.
- **Multi-Platform Webhooks**: Built-in support for **Discord, Slack, Microsoft Teams, Telegram**, and generic custom HTTP JSON webhooks with independent per-platform URL endpoints.
- **Per-IP Granular Control**: Individual toggle switches in the host table allow selectively enabling or disabling Email, Sound, Popup, and Webhook alerts per IP address.
- **Audio Cue System & Mute Control**: Audio alerts on connection drop/restore with instant one-click master mute directly from the System Tray or settings.
- **Desktop Toast Popups**: Unobtrusive native desktop alerts keeping you informed while working in other applications.

### 🖥️ 4. Floating Mini HUD (Heads-Up Display)
- **Always-on-Top Glassmorphic Widget**: A stylish, semi-transparent desktop overlay displaying critical network vitals at a glance.
- **Real-Time Health & Status Counters**: Live chips indicating `UP` count (green), `DOWN` count (red), `AVG LATENCY` (cyan), and total `HEALTH %` (purple).
- **Official Brand Mark**: Embedded official **D IP Monitor** brand logo in the top-left header with seamless frameless drag-and-drop repositioning.
- **One-Click Toggle**: Quickly show or hide the HUD via the System Tray context menu or main toolbar.

### 🗂️ 5. Group Organization, Dynamic Dropdown & Instant Search
- **Group Categorization Dropdown**: Replaces cluttered tab bars with a compact, auto-discovering **Group Filter Dropdown** (`All`, `General`, `Network`, `Servers`, etc.).
- **Zero-Latency Real-Time Search**: Instant fuzzy filtering across IP addresses, host descriptions, tags, and status states without UI stutter.
- **Customizable Table Columns**: Hide or display any column (**IP, Description, Tag, Status, Uptime, Downtime, Packet Loss, Latency, Email, Popup, Sound, Webhook**) with persistent preferences.

### 🛠️ 6. Diagnostic Toolkit & Discovery Utilities
- **Batch IP Subnet Scanner**: High-speed network subnet discovery tool to scan IP ranges (e.g., `192.168.1.1/24`), identify active hosts, and batch-import them directly.
- **Integrated Diagnostics**: Right-click context menu offering instant **Ping**, **Traceroute**, and multi-port **Port Scanning** without leaving the app.
- **Profile Backup & Restore**: One-click JSON backup and restoration for seamless profile sharing and environment migration.
- **CSV Data Exchange**: Export complete host telemetry and import legacy target spreadsheets effortlessly.

### 🎨 7. Theme Engine & Tray Integration
- **Cyber Dark & Clean Light Modes**: Handcrafted QSS themes engineered with deep obsidian palettes, neon cyan accents (`#00e5ff`), and crisp typography.
- **System Tray Operations**: Minimizes smoothly to the Windows system tray with active tooltips, quick status overviews, master mute, and background persistence.
- **Audit Logging**: Comprehensive logging system with hourly rotation and direct Windows Explorer folder navigation to incident records.

---

## 📊 Feature & Alert Channel Matrix

| Feature / Metric | Description | Supported Modes | Configurable |
| :--- | :--- | :---: | :---: |
| **ICMP Ping Interval** | Frequency of ping attempts per host | Asynchronous / Non-blocking | `1s - 3600s` |
| **Packet Loss Steps** | 20-sample rolling window | `0%, 5%, 10% ... 100%` | Automatic |
| **Email Alerts** | SMTP notification on UP / DOWN | SSL / TLS / STARTTLS | Per-IP + Global |
| **Webhooks** | Discord, Slack, Teams, Telegram, Generic | HTTP POST (JSON Payload) | Per-IP + Global |
| **Sound Alerts** | Audio cue on state transition | `.wav` / System Chime | Per-IP + Global |
| **Desktop Popups** | Native Windows toast notifications | Non-stealing dialogs | Per-IP + Global |
| **Live Sparkline** | Interactive latency curve with hover crosshair | Last 30 rolling samples | Live Inspector |
| **Mini Desktop HUD** | Frameless floating glass widget | Always-on-top | Draggable |
| **Diagnostics** | Ping, Traceroute, Port Scanner | Built-in CLI wrapper | Right-Click Menu |

---

## 🖥️ User Interface Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│  🌐 D IP Monitor  [ v2.0 Enterprise ]           [ - ] [ □ ] [ ✕ ]      │
├────────────────────────────────────────────────────────────────────────┤
│  [ UP: 18 ]  [ DOWN: 2 ]  [ AVG: 14.8 ms ]  [ HEALTH: 90.0% ]          │
├────────────────────────────────────────────────────────────────────────┤
│  Live Latency Trend: 192.168.1.1 (Gateway)                             │
│  Sample #14/30 (16 pings ago): 12.4ms  |  Avg: 11.8ms  |  Min: 9.2ms   │
│  ──────────────────────────┼──────────────────────────────────         │
│                            │ [ 12.4ms ]                                │
├────────────────────────────────────────────────────────────────────────┤
│  Group: [ All       ▼ ]  Search: [ Filter hosts...         ]  [⚙ Cols] │
├──────────────┬─────────────┬──────────┬──────────┬──────────┬──────────┤
│ IP Address   │ Description │ Tag      │ Status   │ Loss     │ Latency  │
├──────────────┼─────────────┼──────────┼──────────┼──────────┼──────────┤
│ 192.168.1.1  │ Core Router │ Network  │ ● ONLINE │ 0%       │ 12.4 ms  │
│ 10.0.0.5     │ File Server │ Servers  │ ● OFFLINE│ 100%     │ —        │
│ 8.8.8.8      │ Google DNS  │ External │ ● ONLINE │ 0%       │ 14.8 ms  │
└──────────────┴─────────────┴──────────┴──────────┴──────────┴──────────┘
```

---

## 🚀 Download & Installation

### Option A: Standalone Windows Executable (Recommended)
Download the pre-compiled, self-contained Windows executable from the Releases page:

📦 **Latest Release**: [Download D IP Monitor Releases](https://github.com/Ronak-Patra/D-IP-Monitor/releases)

1. Download `D IP Monitor.exe`.
2. Place it in your preferred directory.
3. Run the application (no Python installation or dependencies required).

---

### Option B: Running from Source

#### Prerequisites
- **Python**: Version `3.10` or higher
- **Operating System**: Windows 10 / 11, Linux, or macOS

#### 1. Clone the Repository
```bash
git clone https://github.com/Ronak-Patra/D-IP-Monitor.git
cd D-IP-Monitor
```

#### 2. Install Dependencies
```bash
pip install PyQt6
```

#### 3. Configure Settings
Copy the provided sample configuration template:
```bash
copy settings.example.ini settings.ini
```
Edit `settings.ini` to configure your SMTP email credentials, webhook URLs, and ping thresholds.

#### 4. Launch Application
```bash
python main.py
```

---

## 🔨 Compiling Standalone Executable (.exe)

You can package the application into a single standalone `.exe` using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm main.spec
```

The compiled standalone executable will be generated in the `dist/` directory:
```
dist/
└── D IP Monitor.exe
```

---

## 🛠️ Built With

- **Core GUI**: [PyQt6](https://pypi.org/project/PyQt6/) (High-DPI, Qt6 platform binding)
- **Concurrency**: Python `QThread` Worker Model & Async Queues
- **Networking**: Raw Socket ICMP Subsystem & Native Windows CLI Wrappers
- **Alert Dispatcher**: Python `smtplib`, `ssl`, and `urllib.request`
- **Audio Subsystem**: `winsound` & Qt Multimedia Audio
- **Packaging**: [PyInstaller](https://pyinstaller.org/)

---

## ⚖️ Disclaimer

> [!NOTE]
> **D IP Monitor** is developed for authorized infrastructure monitoring, network diagnostics, and systems administration. Ensure you have appropriate permissions before monitoring external networks, scanning IP ranges, or auditing third-party endpoints.
