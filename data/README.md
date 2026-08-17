# Data contract

The raw layer is generated locally with a fixed random seed. It contains no customer, employee, address, credential, IP address or production-network data.

Run `python -m src.generate_data` to create:

- `sites.csv`: four fictional operating sites and their nominal capacity;
- `protocols.csv`: protocol reference data;
- `device_history.csv`: type-2 slowly changing device attributes;
- `flows.csv`: deterministic flow-level telemetry;
- `incidents.csv`: deterministic operational incidents.

Raw CSV files are excluded from Git because they are reproducible build inputs. The default generator produces 120,000 flows, 80 devices and 220 incidents for 2026 Q1.

