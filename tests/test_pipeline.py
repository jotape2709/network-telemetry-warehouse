from pathlib import Path

from src.build_warehouse import build_warehouse
from src.generate_data import GenerationConfig, generate_all, write_raw


def test_generator_is_deterministic() -> None:
    config = GenerationConfig(seed=2709, n_devices=12, n_flows=1_000, n_incidents=20)
    first = generate_all(config)
    second = generate_all(config)
    assert first["flows"]["bytes"].sum() == second["flows"]["bytes"].sum()
    assert first["incidents"].equals(second["incidents"])


def test_scd2_has_one_current_row_and_non_overlapping_versions() -> None:
    history = generate_all(GenerationConfig(n_devices=20, n_flows=1_000, n_incidents=20))["device_history"]
    assert history.groupby("device_id")["is_current"].sum().eq(1).all()
    for _, group in history.sort_values("valid_from").groupby("device_id"):
        if len(group) > 1:
            assert (group["valid_to"].iloc[:-1].to_numpy() == group["valid_from"].iloc[1:].to_numpy()).all()


def test_end_to_end_reconciliation(tmp_path: Path) -> None:
    config = GenerationConfig(seed=42, n_devices=16, n_flows=3_000, n_incidents=30)
    write_raw(generate_all(config), tmp_path / "data" / "raw")
    project_root = Path(__file__).resolve().parents[1]
    (tmp_path / "sql").symlink_to(project_root / "sql", target_is_directory=True)
    summary, quality = build_warehouse(tmp_path)
    assert summary["flows"] == config.n_flows
    assert summary["incidents"] == config.n_incidents
    assert quality["all_passed"] is True

