<p align="center">
  <img src="docs/logo.png" alt="TerraMaster" width="360">
</p>

<h1 align="center">TerraMaster NAS for Home Assistant</h1>

<p align="center">
  <a href="https://github.com/r0-prod/terramaster-hass/releases"><img src="https://img.shields.io/github/v/release/r0-prod/terramaster-hass?style=flat-square" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/r0-prod/terramaster-hass?style=flat-square" alt="License"></a>
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-custom-41BDF5?style=flat-square" alt="HACS"></a>
</p>

Monitor drive temperatures and storage on a TerraMaster NAS, and control its fan —
locally, with no cloud account.

## Features

- **Disks**: Per-drive temperature, power-on hours, health status, and capacity, for every bay (including NVMe).
- **System**: CPU and system temperature, CPU usage (with per-core breakdown), memory usage (percent and absolute), and a "hottest disk" sensor for automations.
- **Network**: IP address, link speed (in Mbit/s), and connection status for each network interface (e.g., `eth0`, `eth1`).
- **System Info**: TOS version, uptime, and device model.
- **Storage**: Volume and storage pool capacity and usage.
- **Fan Control**: Fan speed in RPM and a fan mode select (Automatic / Low / Medium / Full).
- **Overheat Protection**: Restores automatic fan control if the drives get too hot while in manual mode.
- **Local Polling**: Talks to the TOS web API (port 8181) — no TerraMaster account, nothing leaves your network.

## Supported models

Developed and tested:
- **F4-423** running **TOS 7**
- **F4-425** running **TOS 6**

The integration talks to the TOS web API rather than anything model-specific, so other TOS 6/7 units should work. The number of drive entities follows the number of bays.

TOS 5 and earlier are not supported.

## Installation

### HACS
1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/ananyevgv/terramaster-hass`, category **Integration**
3. Install **TerraMaster NAS**, then restart Home Assistant.

### Manual
Copy `custom_components/terramaster/` into your `config/custom_components/` directory and restart Home Assistant.

## Setup

**Settings → Devices & Services → Add Integration → TerraMaster NAS**

| Field | Value |
|---|---|
| Host | IP address or hostname of the NAS |
| Port | TOS web interface port, default `8181` |
| Username / Password | Any TOS account reads every sensor; **administrator** is only needed to change the fan mode |

Credentials are required — TOS has no anonymous read access. If you only want monitoring, use a non-administrator TOS account: all sensors work, and the fan mode control reports that it is not permitted rather than failing obscurely.

**Options** (⚙ on the integration) cover the polling interval and overheat protection. Reading temperatures runs SMART queries on the NAS and takes a few seconds, so the default interval is 60 seconds.

## Entities

### Sensors
| Entity | Description |
|---|---|
| `sensor.hdd_n_temperature` | Temperature of each drive |
| `sensor.hdd_n_power_on_hours` | SMART power-on hours |
| `sensor.hdd_n_capacity` | Drive capacity |
| `sensor.cpu_temperature` | CPU temperature |
| `sensor.system_temperature` | System temperature |
| `sensor.max_disk_temperature` | Hottest drive temperature |
| `sensor.cpu_usage` | CPU usage percentage (per-core in attributes) |
| `sensor.memory_usage` | Memory usage percentage |
| `sensor.memory_used` | Memory used in bytes (total in attributes) |
| `sensor.fan_speed` | Fan speed in RPM |
| `sensor.tos_version` | Installed TOS version |
| `sensor.uptime` | System uptime (hours) |
| `sensor.network_interface_ip` | IP address of each network interface |
| `sensor.network_interface_speed` | Link speed of each network interface (Mbit/s) |
| `sensor.volume_total` / `used` / `free` / `usage` | Volume capacity and usage |
| `sensor.pool_total` / `free` | Pool capacity (free may be 0 on btrfs/TRAID) |

### Binary Sensors
| Entity | Description |
|---|---|
| `binary_sensor.hdd_n_problem` | On when TOS reports a fault for the drive |

### Select
| Entity | Description |
|---|---|
| `select.fan_mode` | Fan mode: Automatic, Low, Medium, Full |

### Update (optional)
If you have added the update platform, `update.firmware` shows the installed TOS version and the latest available version (if check is supported by your NAS).

## Fan control

`Automatic` hands the fan to the NAS firmware, which ramps with temperature. The three fixed modes disable that ramp, so a fixed mode chosen in winter can run too slow in summer. Overheat protection guards against this: if the hottest drive reaches the threshold (default 55 °C, TerraMaster's own warning point) while a fixed mode is active, the integration switches the fan back to Automatic and logs a warning. It can be turned off in the options.

## Troubleshooting

Confirm the TOS web interface is reachable from Home Assistant at `http://<host>:8181`. Then enable debug logging:

```yaml
logger:
  logs:
    custom_components.terramaster: debug
```

After a TOS firmware update, the API may change — see
[docs/TOS_API.md](docs/TOS_API.md) and run `tools/probe_tos.py` to compare.

## Development

See [AGENTS.md](AGENTS.md) for the repository layout and workflow, and
[docs/TOS_API.md](docs/TOS_API.md) for the reverse-engineered protocol.

## License

[MIT](LICENSE)

## Disclaimer

Not affiliated with, endorsed by, or supported by TerraMaster. The TerraMaster name and
logo are trademarks of their respective owner and are used here only to identify the
supported hardware.
