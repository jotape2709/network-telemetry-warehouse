from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


root = Path(__file__).resolve().parents[1]
raw = root / "data" / "raw"
reports = root / "reports"
figures = reports / "figures"
figures.mkdir(parents=True, exist_ok=True)
flows = pd.read_csv(raw / "flows.csv", parse_dates=["observed_at"])
incidents = pd.read_csv(raw / "incidents.csv", parse_dates=["started_at", "ended_at"])
history = pd.read_csv(raw / "device_history.csv", parse_dates=["valid_from", "valid_to"])
sites = pd.read_csv(raw / "sites.csv")
protocols = pd.read_csv(raw / "protocols.csv")
current_failures = int(history.groupby("device_id")["is_current"].sum().ne(1).sum())
overlaps = 0
for _, group in history.sort_values("valid_from").groupby("device_id"):
    versions = list(group.itertuples(index=False))
    for index, left in enumerate(versions):
        for right in versions[index + 1 :]:
            left_end = left.valid_to if pd.notna(left.valid_to) else pd.Timestamp.max
            right_end = right.valid_to if pd.notna(right.valid_to) else pd.Timestamp.max
            overlaps += int(left.valid_from < right_end and right.valid_from < left_end)
version_matches = flows[["flow_id", "device_id", "observed_at"]].merge(history[["device_id", "valid_from", "valid_to"]], on="device_id", how="left")
version_matches = version_matches[(version_matches["observed_at"] >= version_matches["valid_from"]) & (version_matches["valid_to"].isna() | (version_matches["observed_at"] < version_matches["valid_to"]))]
unmatched_versions = int(len(flows) - version_matches["flow_id"].nunique())
duplicate_versions = int((version_matches.groupby("flow_id").size() > 1).sum())
failure_counts = {
    "flow_primary_key_duplicates": int(flows["flow_id"].duplicated().sum()),
    "incident_primary_key_duplicates": int(incidents["incident_id"].duplicated().sum()),
    "flow_orphan_device": unmatched_versions + duplicate_versions,
    "flow_orphan_site": int((~flows["site_key"].isin(sites["site_key"])).sum()),
    "flow_orphan_protocol": int((~flows["protocol_key"].isin(protocols["protocol_key"])).sum()),
    "invalid_measure_bounds": int(((flows["bytes"] < 0) | (flows["packets"] < 0) | (flows["latency_ms"] < 0) | ~flows["packet_loss_pct"].between(0, 100)).sum()),
    "multiple_current_device_rows": current_failures,
    "overlapping_device_versions": overlaps,
}
quality = {
    "all_passed": all(value == 0 for value in failure_counts.values()),
    "reconciliation": {
        "raw_flows": len(flows),
        "warehouse_flows": len(version_matches),
        "raw_incidents": len(incidents),
        "warehouse_incidents": len(incidents),
    },
    "failure_counts": failure_counts,
}
flow_day = flows.assign(date_key=flows["observed_at"].dt.strftime("%Y%m%d").astype(int))
incident_day = incidents.assign(date_key=incidents["started_at"].dt.strftime("%Y%m%d").astype(int))
incident_pairs = incident_day[["date_key", "device_id"]].drop_duplicates().assign(incident_day=True)
contrast = flow_day.merge(incident_pairs, on=["date_key", "device_id"], how="left")
incident_latency = contrast.loc[contrast["incident_day"].eq(True), "latency_ms"].mean()
clean_latency = contrast.loc[contrast["incident_day"].isna(), "latency_ms"].mean()
summary = {
    "flows": len(flows),
    "traffic_tb": round(float(flows["bytes"].sum() / 1_000_000_000_000), 4),
    "avg_latency_ms": round(float(flows["latency_ms"].mean()), 4),
    "p95_latency_ms": round(float(flows["latency_ms"].quantile(0.95)), 4),
    "avg_packet_loss_pct": round(float(flows["packet_loss_pct"].mean()), 4),
    "sla_risk_rate": round(float(((flows["latency_ms"] > 120) | (flows["packet_loss_pct"] > 1)).mean()), 6),
    "incidents": len(incidents),
    "downtime_minutes": round(float(incidents["downtime_minutes"].sum()), 2),
    "incident_day_latency_ms": round(float(incident_latency), 4),
    "clean_day_latency_ms": round(float(clean_latency), 4),
    "incident_day_latency_lift": round(float(incident_latency / clean_latency - 1), 6),
}
flow_site_daily = (
    flow_day.groupby(["date_key", "site_key"], as_index=False)
    .agg(
        flow_count=("flow_id", "size"),
        traffic_gb=("bytes", lambda values: values.sum() / 1_000_000_000),
        avg_latency_ms=("latency_ms", "mean"),
        p95_latency_ms=("latency_ms", lambda values: values.quantile(0.95)),
        avg_packet_loss_pct=("packet_loss_pct", "mean"),
    )
)
incident_site_daily = incident_day.groupby(["date_key", "site_key"], as_index=False).agg(incident_count=("incident_id", "size"), observed_downtime_minutes=("downtime_minutes", "sum"))
site_daily = flow_site_daily.merge(incident_site_daily, on=["date_key", "site_key"], how="left").merge(sites[["site_key", "site_name"]], on="site_key")
site_daily["full_date"] = pd.to_datetime(site_daily["date_key"].astype(str))
site_daily[["full_date", "site_name", "flow_count", "traffic_gb", "avg_latency_ms", "p95_latency_ms", "avg_packet_loss_pct", "incident_count"]].sort_values(["full_date", "site_name"]).to_csv(reports / "site_daily_kpis.csv", index=False)
(reports / "kpi_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(reports / "data_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
sns.set_theme(style="whitegrid", context="talk")
daily = site_daily.groupby("full_date", as_index=False).agg(traffic_gb=("traffic_gb", "sum"), p95_latency_ms=("p95_latency_ms", "mean"))
fig, ax1 = plt.subplots(figsize=(12, 6))
ax1.plot(daily["full_date"], daily["traffic_gb"], color="#2563eb", linewidth=2)
ax1.set(ylabel="Traffic (GB)", xlabel="", title="Daily traffic and tail latency")
ax2 = ax1.twinx()
ax2.plot(daily["full_date"], daily["p95_latency_ms"], color="#dc2626", linewidth=2)
ax2.set_ylabel("P95 latency (ms)")
fig.tight_layout()
fig.savefig(figures / "daily_traffic_latency.png", dpi=160, bbox_inches="tight")
plt.close(fig)
site = site_daily.groupby("site_name", as_index=False).agg(p95_latency_ms=("p95_latency_ms", "mean"), packet_loss_pct=("avg_packet_loss_pct", "mean"))
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
sns.barplot(data=site, x="p95_latency_ms", y="site_name", color="#2563eb", ax=axes[0])
sns.barplot(data=site, x="packet_loss_pct", y="site_name", color="#f59e0b", ax=axes[1])
axes[0].set(title="Mean daily P95 latency", xlabel="Milliseconds", ylabel="")
axes[1].set(title="Mean packet loss", xlabel="Percent", ylabel="")
fig.tight_layout()
fig.savefig(figures / "site_service_quality.png", dpi=160, bbox_inches="tight")
plt.close(fig)
severity = incidents.groupby("severity", as_index=False).agg(downtime_minutes=("downtime_minutes", "sum"))
fig, ax = plt.subplots(figsize=(9, 5))
sns.barplot(data=severity, x="severity", y="downtime_minutes", order=["low", "medium", "high", "critical"], color="#7c3aed", ax=ax)
ax.set(title="Downtime concentration by severity", xlabel="Severity", ylabel="Downtime (minutes)")
fig.tight_layout()
fig.savefig(figures / "incident_downtime.png", dpi=160, bbox_inches="tight")
plt.close(fig)
print(json.dumps({"summary": summary, "quality": quality}, indent=2))
