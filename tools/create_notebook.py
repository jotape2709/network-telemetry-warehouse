from pathlib import Path

import nbformat as nbf


root = Path(__file__).resolve().parents[1]
notebook = nbf.v4.new_notebook()
notebook["metadata"]["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
notebook["metadata"]["language_info"] = {"name": "python", "version": "3"}
notebook["cells"] = [
    nbf.v4.new_markdown_cell("# Network telemetry warehouse\n\n**Author:** João Pedro de Moura Lima\n\nA reproducible dimensional-modeling case study connecting network operations to analytical engineering."),
    nbf.v4.new_markdown_cell("## TL;DR\n\nThe pipeline turns deterministic synthetic flow telemetry into conformed dimensions, SCD2 device history, two fact tables and decision-ready daily marts. Every published metric is reconciled back to its raw input."),
    nbf.v4.new_markdown_cell("## Context & methods\n\nThe portfolio data is fictional by design. The grain of `fact_network_flow` is one observed flow; the grain of `fact_incident` is one incident. Device attributes are resolved as of event time through half-open SCD2 validity intervals."),
    nbf.v4.new_code_cell("from pathlib import Path\nimport json\nimport pandas as pd\nfrom IPython.display import Image, display\nroot = Path.cwd()\nif not (root / 'reports').exists():\n    root = root.parent\nsummary = json.loads((root / 'reports' / 'kpi_summary.json').read_text())\nquality = json.loads((root / 'reports' / 'data_quality.json').read_text())\nsummary"),
    nbf.v4.new_markdown_cell("## Data quality\n\nPrimary-key uniqueness, referential integrity, numeric bounds, SCD2 current-row rules, interval overlap and raw-to-warehouse row reconciliation are blocking tests."),
    nbf.v4.new_code_cell("pd.DataFrame([quality['reconciliation']]), quality['all_passed'], pd.Series(quality['failure_counts'], name='failures')"),
    nbf.v4.new_markdown_cell("## Results"),
    nbf.v4.new_code_cell("site_daily = pd.read_csv(root / 'reports' / 'site_daily_kpis.csv')\nsite_daily.groupby('site_name').agg(traffic_gb=('traffic_gb', 'sum'), p95_latency_ms=('p95_latency_ms', 'mean'), incidents=('incident_count', 'sum')).round(2)"),
    nbf.v4.new_code_cell("for name in ['daily_traffic_latency.png', 'site_service_quality.png', 'incident_downtime.png']:\n    display(Image(filename=str(root / 'reports' / 'figures' / name)))"),
    nbf.v4.new_markdown_cell("## Takeaways\n\n- The model preserves the device version that was valid when each event occurred.\n- Incident-day latency is deliberately higher in the synthetic generator, providing a known analytical signal that the warehouse must preserve.\n- Operational thresholds and the service-quality score are illustrative; production use requires service-specific SLOs and calibrated business weights.\n- No production telemetry or personally identifiable information is included."),
]
notebook["metadata"]["project_root"] = str(root)
output = root / "notebooks" / "01_warehouse_analysis.ipynb"
output.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, output)
print(output)

