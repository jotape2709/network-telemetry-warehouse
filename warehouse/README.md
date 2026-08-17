# Warehouse output

`python -m src.build_warehouse` materializes `network_telemetry.duckdb` here. The database is excluded from Git because it is reproducible from the deterministic raw layer and SQL transformations.

Published analytical outputs live under `reports/`.

