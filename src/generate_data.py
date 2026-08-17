from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class GenerationConfig:
    seed: int = 2709
    n_devices: int = 80
    n_flows: int = 120_000
    n_incidents: int = 220
    start: str = "2026-01-01"
    end: str = "2026-04-01"


def reference_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    sites = pd.DataFrame(
        [
            (1, "SITE-SP", "São Paulo Core", "Southeast", 1000),
            (2, "SITE-RJ", "Rio Edge", "Southeast", 750),
            (3, "SITE-BSB", "Brasília Hub", "Central-West", 600),
            (4, "SITE-REC", "Recife Edge", "Northeast", 500),
        ],
        columns=["site_key", "site_id", "site_name", "region", "capacity_mbps"],
    )
    protocols = pd.DataFrame(
        [
            (1, "HTTPS", 443, "Application"),
            (2, "HTTP", 80, "Application"),
            (3, "DNS", 53, "Infrastructure"),
            (4, "SSH", 22, "Management"),
            (5, "SNMP", 161, "Monitoring"),
            (6, "NTP", 123, "Infrastructure"),
        ],
        columns=["protocol_key", "protocol_name", "port", "traffic_class"],
    )
    return sites, protocols


def device_tables(config: GenerationConfig, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    device_ids = np.array([f"DEV-{i:03d}" for i in range(1, config.n_devices + 1)])
    device_types = rng.choice(["router", "switch", "firewall", "access_point"], config.n_devices, p=[0.2, 0.38, 0.17, 0.25])
    site_keys = rng.choice([1, 2, 3, 4], config.n_devices, p=[0.36, 0.25, 0.21, 0.18])
    vendors = rng.choice(["Arista", "Cisco", "Fortinet", "Juniper"], config.n_devices)
    devices = pd.DataFrame({"device_id": device_ids, "device_type": device_types, "site_key": site_keys, "vendor": vendors})
    change_count = max(1, int(round(config.n_devices * 0.30)))
    changed = set(rng.choice(device_ids, change_count, replace=False))
    rows: list[tuple[object, ...]] = []
    start = pd.Timestamp(config.start)
    end = pd.Timestamp(config.end)
    for row in devices.itertuples(index=False):
        old_version = f"{rng.integers(7, 10)}.{rng.integers(0, 5)}"
        if row.device_id in changed:
            change_at = start + pd.Timedelta(days=int(rng.integers(28, (end - start).days - 12)))
            major, minor = old_version.split(".")
            new_version = f"{major}.{int(minor) + 1}"
            rows.append((row.device_id, row.device_type, row.site_key, row.vendor, old_version, start, change_at, False))
            rows.append((row.device_id, row.device_type, row.site_key, row.vendor, new_version, change_at, pd.NaT, True))
        else:
            rows.append((row.device_id, row.device_type, row.site_key, row.vendor, old_version, start, pd.NaT, True))
    history = pd.DataFrame(rows, columns=["device_id", "device_type", "site_key", "vendor", "firmware_version", "valid_from", "valid_to", "is_current"])
    return devices, history


def incident_table(config: GenerationConfig, devices: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    start = pd.Timestamp(config.start)
    seconds = int((pd.Timestamp(config.end) - start).total_seconds())
    severity = rng.choice(["low", "medium", "high", "critical"], config.n_incidents, p=[0.42, 0.34, 0.19, 0.05])
    duration_ranges = {"low": (5, 35), "medium": (20, 100), "high": (60, 260), "critical": (180, 600)}
    durations = np.array([rng.integers(*duration_ranges[level]) for level in severity], dtype=int)
    started_at = start + pd.to_timedelta(rng.integers(0, seconds, config.n_incidents), unit="s")
    device_id = rng.choice(devices["device_id"], config.n_incidents)
    site_lookup = devices.set_index("device_id")["site_key"]
    incidents = pd.DataFrame(
        {
            "incident_id": [f"INC-{i:05d}" for i in range(1, config.n_incidents + 1)],
            "device_id": device_id,
            "site_key": pd.Series(device_id).map(site_lookup).to_numpy(),
            "started_at": started_at,
            "ended_at": started_at + pd.to_timedelta(durations, unit="m"),
            "severity": severity,
            "category": rng.choice(["packet_loss", "latency", "link_down", "configuration"], config.n_incidents, p=[0.31, 0.29, 0.24, 0.16]),
            "downtime_minutes": durations,
        }
    )
    return incidents.sort_values("started_at").reset_index(drop=True)


def flow_table(config: GenerationConfig, devices: pd.DataFrame, incidents: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    start = pd.Timestamp(config.start)
    seconds = int((pd.Timestamp(config.end) - start).total_seconds())
    observed_at = start + pd.to_timedelta(rng.integers(0, seconds, config.n_flows), unit="s")
    device_id = rng.choice(devices["device_id"], config.n_flows)
    protocol_key = rng.choice([1, 2, 3, 4, 5, 6], config.n_flows, p=[0.52, 0.15, 0.15, 0.05, 0.08, 0.05])
    protocol_scale = np.array([2.2, 1.8, 0.12, 0.32, 0.08, 0.05])
    hour = pd.DatetimeIndex(observed_at).hour.to_numpy()
    weekday = pd.DatetimeIndex(observed_at).dayofweek.to_numpy()
    peak = np.where((hour >= 8) & (hour <= 18) & (weekday < 5), 1.38, 0.82)
    byte_count = np.maximum(512, rng.lognormal(13.0, 1.12, config.n_flows) * protocol_scale[protocol_key - 1] * peak).astype("int64")
    duration_seconds = np.maximum(0.05, rng.lognormal(1.25, 0.72, config.n_flows))
    throughput_mbps = byte_count * 8 / duration_seconds / 1_000_000
    site_lookup = devices.set_index("device_id")["site_key"]
    site_key = pd.Series(device_id).map(site_lookup).to_numpy()
    site_latency = np.array([7.0, 10.0, 17.0, 23.0])
    latency_ms = rng.lognormal(np.log(site_latency[site_key - 1] + 4), 0.34)
    loss = rng.beta(0.75, 90, config.n_flows) * 100
    incident_pairs = pd.MultiIndex.from_frame(incidents.assign(event_date=incidents["started_at"].dt.normalize())[["device_id", "event_date"]]).unique()
    flow_pairs = pd.MultiIndex.from_arrays([device_id, pd.DatetimeIndex(observed_at).normalize()])
    incident_day = flow_pairs.isin(incident_pairs)
    latency_ms = latency_ms * np.where(incident_day, rng.uniform(1.8, 3.1, config.n_flows), 1.0)
    loss = np.clip(loss + np.where(incident_day, rng.uniform(0.35, 2.0, config.n_flows), 0.0), 0, 100)
    packet_size = rng.integers(650, 1450, config.n_flows)
    packets = np.maximum(1, np.ceil(byte_count / packet_size)).astype("int64")
    flows = pd.DataFrame(
        {
            "flow_id": [f"FLOW-{i:07d}" for i in range(1, config.n_flows + 1)],
            "observed_at": observed_at,
            "device_id": device_id,
            "site_key": site_key,
            "protocol_key": protocol_key,
            "bytes": byte_count,
            "packets": packets,
            "duration_seconds": duration_seconds.round(4),
            "throughput_mbps": throughput_mbps.round(4),
            "latency_ms": latency_ms.round(4),
            "packet_loss_pct": loss.round(4),
        }
    )
    return flows.sort_values("observed_at").reset_index(drop=True)


def generate_all(config: GenerationConfig = GenerationConfig()) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(config.seed)
    sites, protocols = reference_tables()
    devices, history = device_tables(config, rng)
    incidents = incident_table(config, devices, rng)
    flows = flow_table(config, devices, incidents, rng)
    return {"sites": sites, "protocols": protocols, "device_history": history, "flows": flows, "incidents": incidents}


def write_raw(tables: dict[str, pd.DataFrame], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    config = GenerationConfig()
    tables = generate_all(config)
    write_raw(tables, root / "data" / "raw")
    print(f"Generated {len(tables['flows']):,} flows, {config.n_devices} devices and {len(tables['incidents']):,} incidents with seed {config.seed}.")


if __name__ == "__main__":
    main()

