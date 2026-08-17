from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


DATETIME_COLUMNS = {
    "device_history": ["valid_from", "valid_to"],
    "flows": ["observed_at"],
    "incidents": ["started_at", "ended_at"],
}


def load_raw(raw_dir: Path) -> dict[str, pd.DataFrame]:
    names = ["sites", "protocols", "device_history", "flows", "incidents"]
    return {name: pd.read_csv(raw_dir / f"{name}.csv", parse_dates=DATETIME_COLUMNS.get(name)) for name in names}


def register_raw(connection: duckdb.DuckDBPyConnection, tables: dict[str, pd.DataFrame], start: pd.Timestamp, end: pd.Timestamp) -> None:
    for name, frame in tables.items():
        connection.register(f"raw_{name}", frame)
    raw_dates = pd.DataFrame({"full_date": pd.date_range(start.normalize(), end.normalize() - timedelta(days=1), freq="D")})
    connection.register("raw_dates", raw_dates)


def execute_sql_files(connection: duckdb.DuckDBPyConnection, sql_dir: Path) -> None:
    for name in ["01_dimensions.sql", "02_facts.sql", "03_marts.sql"]:
        connection.execute((sql_dir / name).read_text(encoding="utf-8"))


def quality_checks(connection: duckdb.DuckDBPyConnection, expected_flows: int, expected_incidents: int, sql_dir: Path) -> dict[str, object]:
    checks = connection.execute((sql_dir / "04_quality_checks.sql").read_text(encoding="utf-8")).fetchdf()
    failures = {row.check_name: int(row.failures) for row in checks.itertuples(index=False)}
    actual_flows = int(connection.execute("SELECT count(*) FROM fact_network_flow").fetchone()[0])
    actual_incidents = int(connection.execute("SELECT count(*) FROM fact_incident").fetchone()[0])
    result = {
        "all_passed": all(value == 0 for value in failures.values()) and actual_flows == expected_flows and actual_incidents == expected_incidents,
        "reconciliation": {
            "raw_flows": expected_flows,
            "warehouse_flows": actual_flows,
            "raw_incidents": expected_incidents,
            "warehouse_incidents": actual_incidents,
        },
        "failure_counts": failures,
    }
    if not result["all_passed"]:
        raise ValueError(json.dumps(result, indent=2))
    return result


def kpi_summary(connection: duckdb.DuckDBPyConnection) -> dict[str, object]:
    base = connection.execute(
        """
        SELECT
            count(*) AS flows,
            sum(bytes) / 1000000000000.0 AS traffic_tb,
            avg(latency_ms) AS avg_latency_ms,
            quantile_cont(latency_ms, 0.95) AS p95_latency_ms,
            avg(packet_loss_pct) AS avg_packet_loss_pct,
            avg(CASE WHEN latency_ms > 120 OR packet_loss_pct > 1 THEN 1.0 ELSE 0.0 END) AS sla_risk_rate
        FROM fact_network_flow
        """
    ).fetchdf().iloc[0]
    incident = connection.execute("SELECT count(*) incidents, sum(downtime_minutes) downtime_minutes FROM fact_incident").fetchdf().iloc[0]
    contrast = connection.execute(
        """
        WITH incident_days AS (SELECT DISTINCT date_key, device_key FROM fact_incident)
        SELECT
            avg(CASE WHEN i.device_key IS NOT NULL THEN f.latency_ms END) AS incident_day_latency_ms,
            avg(CASE WHEN i.device_key IS NULL THEN f.latency_ms END) AS clean_day_latency_ms
        FROM fact_network_flow f
        LEFT JOIN incident_days i USING (date_key, device_key)
        """
    ).fetchdf().iloc[0]
    return {
        "flows": int(base["flows"]),
        "traffic_tb": round(float(base["traffic_tb"]), 4),
        "avg_latency_ms": round(float(base["avg_latency_ms"]), 4),
        "p95_latency_ms": round(float(base["p95_latency_ms"]), 4),
        "avg_packet_loss_pct": round(float(base["avg_packet_loss_pct"]), 4),
        "sla_risk_rate": round(float(base["sla_risk_rate"]), 6),
        "incidents": int(incident["incidents"]),
        "downtime_minutes": round(float(incident["downtime_minutes"]), 2),
        "incident_day_latency_ms": round(float(contrast["incident_day_latency_ms"]), 4),
        "clean_day_latency_ms": round(float(contrast["clean_day_latency_ms"]), 4),
        "incident_day_latency_lift": round(float(contrast["incident_day_latency_ms"] / contrast["clean_day_latency_ms"] - 1), 6),
    }


def create_reports(connection: duckdb.DuckDBPyConnection, report_dir: Path, summary: dict[str, object], quality: dict[str, object]) -> None:
    figure_dir = report_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    site_daily = connection.execute(
        """
        SELECT d.full_date, s.site_name, m.flow_count, m.traffic_gb, m.avg_latency_ms, m.p95_latency_ms, m.avg_packet_loss_pct, m.incident_count
        FROM mart_site_daily m JOIN dim_date d USING (date_key) JOIN dim_site s USING (site_key)
        ORDER BY 1, 2
        """
    ).fetchdf()
    site_daily.to_csv(report_dir / "site_daily_kpis.csv", index=False)
    (report_dir / "kpi_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (report_dir / "data_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    sns.set_theme(style="whitegrid", context="talk")
    daily = site_daily.groupby("full_date", as_index=False).agg(traffic_gb=("traffic_gb", "sum"), p95_latency_ms=("p95_latency_ms", "mean"))
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(daily["full_date"], daily["traffic_gb"], color="#2563eb", linewidth=2, label="Traffic (GB)")
    ax1.set_ylabel("Traffic (GB)", color="#2563eb")
    ax1.set_xlabel("")
    ax2 = ax1.twinx()
    ax2.plot(daily["full_date"], daily["p95_latency_ms"], color="#dc2626", linewidth=2, label="P95 latency")
    ax2.set_ylabel("P95 latency (ms)", color="#dc2626")
    ax1.set_title("Daily traffic and tail latency")
    fig.tight_layout()
    fig.savefig(figure_dir / "daily_traffic_latency.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    site = site_daily.groupby("site_name", as_index=False).agg(p95_latency_ms=("p95_latency_ms", "mean"), packet_loss_pct=("avg_packet_loss_pct", "mean"))
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    sns.barplot(data=site, x="p95_latency_ms", y="site_name", color="#2563eb", ax=axes[0])
    sns.barplot(data=site, x="packet_loss_pct", y="site_name", color="#f59e0b", ax=axes[1])
    axes[0].set(title="Mean daily P95 latency", xlabel="Milliseconds", ylabel="")
    axes[1].set(title="Mean packet loss", xlabel="Percent", ylabel="")
    fig.tight_layout()
    fig.savefig(figure_dir / "site_service_quality.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    severity = connection.execute("SELECT severity, count(*) incidents, sum(downtime_minutes) downtime_minutes FROM fact_incident GROUP BY 1").fetchdf()
    order = ["low", "medium", "high", "critical"]
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=severity, x="severity", y="downtime_minutes", order=order, color="#7c3aed", ax=ax)
    ax.set(title="Downtime concentration by severity", xlabel="Severity", ylabel="Downtime (minutes)")
    fig.tight_layout()
    fig.savefig(figure_dir / "incident_downtime.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def build_warehouse(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    raw_dir = root / "data" / "raw"
    tables = load_raw(raw_dir)
    warehouse_dir = root / "warehouse"
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(warehouse_dir / "network_telemetry.duckdb"))
    try:
        start = tables["flows"]["observed_at"].min()
        end = tables["flows"]["observed_at"].max() + timedelta(days=1)
        register_raw(connection, tables, start, end)
        execute_sql_files(connection, root / "sql")
        quality = quality_checks(connection, len(tables["flows"]), len(tables["incidents"]), root / "sql")
        summary = kpi_summary(connection)
        create_reports(connection, root / "reports", summary, quality)
    finally:
        connection.close()
    return summary, quality


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    summary, quality = build_warehouse(root)
    print(json.dumps({"summary": summary, "quality": quality}, indent=2))


if __name__ == "__main__":
    main()
