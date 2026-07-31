# BYD Vehicle Bridge — MCP Server

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io)
[![Docker](https://img.shields.io/badge/docker-ready-2496ed.svg)](https://docker.com)
[![Tests](https://github.com/pavelpervi/byd-vehicle-bridge/actions/workflows/tests.yml/badge.svg)](https://github.com/pavelpervi/byd-vehicle-bridge/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A secure, read-only **MCP (Model Context Protocol) server** that connects to your **BYD electric vehicle** via the BYD cloud API. Designed for AI agents (like OpenClaw, Claude Code, or any MCP client) to query real-time vehicle data — battery SOC, range, tire pressures, door states, GPS, and more — while keeping your credentials safe on your own infrastructure.

Built with Python, pyBYD, and the MCP SDK.

---

## Architecture

```
┌─────────────────────── Host Machine ──────────────────────────┐
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Docker Network: byd-internal (172.28.0.0/16)           │  │
│  │                                                         │  │
│  │  ┌──────────────────────┐    MCP (SSE)   ┌──────────┐  │  │
│  │  │  AI Agent            │◄──────────────►│  BYD     │  │  │
│  │  │  (OpenClaw / Claude) │                │  Bridge  │  │  │
│  │  │                      │                │          │  │  │
│  │  │  Tools:              │                │  Tools:  │  │  │
│  │  │  · get_battery()     │                │  · poll  │  │  │
│  │  │  · get_vehicle()     │                │  · cache │  │  │
│  │  │  · get_all_data()    │                │  · serve │  │  │
│  │  │  · get_health()      │                │          │  │  │
│  │  └──────────────────────┘                └─────┬────┘  │  │
│  │                                                 │      │  │
│  │                                        BYD Cloud API    │  │
│  │                                                 │      │  │
│  │                                            ┌────▼────┐ │  │
│  │                                            │  BYD    │ │  │
│  │                                            │  Cloud  │ │  │
│  │                                            └─────────┘ │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  Credentials stored in .env — never leave this machine        │
└───────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **MCP over REST** | AI agents discover tools natively via the Model Context Protocol. No manual URL memorization, no raw HTTP parsing. |
| **SSE transport** | Server-Sent Events over HTTP — standard MCP transport, compatible with all MCP clients. |
| **Background polling** | The server polls the BYD API every 60s and caches results. Tools return instant cached data, never block on the network. |
| **Internal Docker network** | The bridge container exposes zero ports to the host. Only containers on the same Docker network can reach it. |
| **Read-only by design** | Remote commands (lock/unlock, AC control, windows) are intentionally excluded. This bridge reads, never writes. |
| **Dual mode** | `minimal` mode for privacy-sensitive users (no GPS, no door states). `full` mode for complete telemetry. |

---

## Features

- **🔋 Battery Monitoring** — State of charge (SOC %), estimated range, charging status
- **🚗 Driving Data** — Speed, power (kW), odometer, outside/cabin temperature
- **🔌 Charging Details** — Voltage, current, charge rate, time to full (full mode)
- **🛞 Tire Pressures** — All four wheels with units (full mode)
- **🚪 Door & Window States** — Open/closed status, lock state (full mode)
- **📍 GPS Location** — Latitude, longitude, heading (full mode)
- **🌡️ HVAC Status** — AC on/off, target temperature, fan speed (full mode)
- **🔒 Read-Only** — No remote commands. No write access. Ever.
- **🐳 Dockerized** — Single container, minimal footprint, non-root user
- **🔐 Credentials Safe** — BYD username/password never leave your VPS

---

## MCP Tools

| Tool | Mode | Description |
|------|------|-------------|
| `get_battery()` | both | Battery SOC %, charging status, range, mileage, temps, speed, power |
| `get_vehicle()` | both | VIN, model, brand, plate, energy type |
| `get_all_data()` | both | Everything available (mode-dependent) |
| `get_health()` | both | Connection status, mode, poll interval |

### Tool Output Example

```json
// get_battery() response
{
  "soc_percent": 73,
  "charging_status": "disconnected",
  "estimated_range_km": 280,
  "mileage_km": 12450,
  "outside_temp_c": 31.5,
  "cabin_temp_c": 28.0,
  "speed_kmh": 0,
  "engine_power_kw": 0.0,
  "fuel_percent": null,
  "last_updated": "2026-07-31T08:30:00+00:00"
}
```

---

## Quick Start

### Prerequisites

- A BYD electric vehicle with an active BYD account
- A server with Docker and Docker Compose installed
- An MCP client (OpenClaw, Claude Code, etc.)

### 1. Configure

```bash
git clone https://github.com/your-username/byd-vehicle-bridge.git
cd byd-vehicle-bridge

cp .env.example .env
nano .env
```

Set your credentials in `.env`:

```ini
BYD_USERNAME=your@email.com
BYD_PASSWORD=your-password
BYD_COUNTRY=IL
BYD_MODE=minimal   # or "full"
```

### 2. Deploy

```bash
docker compose up -d
```

### 3. Connect Your MCP Client

The bridge exposes an MCP server on port 8000 via SSE transport. Configure your MCP client to connect to it.

**For OpenClaw**, add to `openclaw.json`:

```json
{
  "mcp": {
    "servers": {
      "byd-bridge": {
        "url": "http://byd-bridge:8000",
        "transport": "sse",
        "timeout": 30
      }
    }
  }
}
```

Then connect the OpenClaw container to the bridge network:

```bash
docker network connect byd-internal openclaw-container
```

Reload OpenClaw, and the tools appear automatically.

**For Claude Code** or any stdio MCP client:

```json
{
  "mcpServers": {
    "byd-bridge": {
      "command": "docker",
      "args": ["exec", "-i", "byd-bridge", "python3", "-m", "mcp", "run", "app.py"]
    }
  }
}
```

### 4. Verify

```bash
# Check the container is running
docker ps | grep byd-bridge

# View logs
docker logs byd-bridge

# Or check health via the MCP server
docker exec byd-bridge python3 -c "
import urllib.request
r = urllib.request.urlopen('http://localhost:8000/health')
print(r.read().decode())
"
```

---

## Security

### What's Protected

| Concern | How It's Addressed |
|---------|-------------------|
| **Credentials** | BYD username/password stored in `.env` on your VPS only. Never sent to the AI agent. |
| **Network Exposure** | Zero ports published to the host. Only accessible on the internal Docker network. |
| **Write Access** | No remote commands implemented. The bridge reads data only. |
| **Privilege Escalation** | Container runs as non-root user, read-only filesystem, all Linux capabilities dropped. |
| **GPS Privacy** | GPS data only available in `full` mode. Default `minimal` mode excludes it. |

### Minimal vs Full Mode

| Data Point | `minimal` | `full` |
|-----------|-----------|--------|
| Battery SOC, range, charging | ✅ | ✅ |
| Speed, power, mileage | ✅ | ✅ |
| Outside/cabin temperature | ✅ | ✅ |
| Vehicle info (VIN, model) | ✅ | ✅ |
| Tire pressures | ❌ | ✅ |
| Door/window states | ❌ | ✅ |
| GPS location | ❌ | ✅ |
| Charging voltage/current | ❌ | ✅ |
| HVAC status | ❌ | ✅ |

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `BYD_USERNAME` | — | BYD account email or phone (required) |
| `BYD_PASSWORD` | — | BYD account password (required) |
| `BYD_COUNTRY` | `IL` | ISO country code for API region |
| `BYD_MODE` | `minimal` | `minimal` or `full` data scope |
| `POLL_INTERVAL` | `60` | Seconds between BYD API polls |

---

## Project Structure

```
byd-vehicle-bridge/
├── app.py              # MCP server — tools, poller, state
├── Dockerfile          # Container build
├── docker-compose.yml  # Deployment config
├── requirements.txt    # Python dependencies
├── .env.example        # Credential template
└── README.md           # This file
```

---

## How It Works

### Background Polling

When the server starts, a daemon thread launches an async event loop that:

1. Authenticates to the BYD cloud API using pyBYD
2. Fetches the vehicle list and real-time data
3. In `full` mode, also fetches GPS, charging details, and HVAC status
4. Caches everything in memory
5. Sleeps for `POLL_INTERVAL` seconds, then repeats

### MCP Tool Calls

When an AI agent calls a tool (e.g., `get_battery()`):

1. The MCP server receives the request
2. Looks up the cached data from the latest poll
3. Returns the data immediately — no network call to BYD
4. The agent receives structured, typed data

This means tool calls are instant (single-digit milliseconds) — the latency lives in the background poller, not in the agent's request.

### Why SSE Transport?

MCP supports three transports:

| Transport | Use Case |
|-----------|----------|
| **stdio** | Local subprocess — server runs as a child of the MCP client |
| **SSE** | Remote server — HTTP with Server-Sent Events (what we use) |
| **Streamable HTTP** | Newer HTTP transport — simpler than SSE |

SSE is the standard choice for a Docker-deployed MCP server. It requires no special client configuration beyond the URL.

---

## Tech Stack

- **[Python 3.12](https://www.python.org/)** — Core language
- **[pyBYD](https://github.com/jkaberg/pyBYD)** — Async Python client for the BYD vehicle API
- **[MCP SDK](https://github.com/modelcontextprotocol/python-sdk)** — Model Context Protocol server framework
- **[FastMCP](https://github.com/modelcontextprotocol/python-sdk)** — Simplified MCP server API
- **[Docker](https://docker.com)** — Containerization
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** — Environment variable management

---

## Acknowledgements

- [pyBYD](https://github.com/jkaberg/pyBYD) — The excellent Python library that makes BYD API access possible
- [hass-byd-vehicle](https://github.com/jkaberg/hass-byd-vehicle) — Home Assistant integration that inspired this project
- [Model Context Protocol](https://modelcontextprotocol.io) — The protocol standardizing AI-tool communication

---

## License

MIT