"""
export_ifcjson.py — PINN localization results → ifcJSON schema for SHM Digital Twin
Paper: shm-pinn-bolted | Phase: COMPUTE T3

Reads:  data/processed/pinn_localization_results.csv
Writes: data/processed/ifc_export_sample.json
"""

import argparse
import csv
import json
import uuid
from pathlib import Path


DEFAULT_INPUT = Path("data/processed/pinn_localization_results.csv")
DEFAULT_OUTPUT = Path("data/processed/ifc_export_sample.json")

SCENARIOS = ["intact", "loose_25", "loose_50", "full_loose"]


def load_csv(input_path: Path) -> list[dict]:
    """Load localization results CSV and return list of row dicts."""
    rows = []
    with open(input_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def build_ifc_entry(i: int, row: dict) -> dict:
    """Map one CSV row to an IfcStructuralPointAction entry."""
    scenario = row["scenario"]
    torque_loss = float(row["torque_loss_pct"])
    pred_x = float(row["pred_x"])
    pred_y = float(row["pred_y"])
    source_x = float(row["source_x"])
    source_y = float(row["source_y"])
    error_mm = float(row["error_mm"])

    return {
        "type": "IfcStructuralPointAction",
        "globalId": str(uuid.uuid4()),
        "name": f"AE_Source_{i}",
        "description": f"scenario={scenario}, torque_loss={torque_loss:.1f}%",
        "appliedLoad": {
            "type": "IfcStructuralLoad",
            "name": "AELoad",
            "ae_source_x_m": round(pred_x, 6),
            "ae_source_y_m": round(pred_y, 6),
            "localization_error_mm": round(error_mm, 4),
        },
        "damage_state": {
            "scenario": scenario,
            "torque_loss_pct": torque_loss,
            "ground_truth_x_m": round(source_x, 6),
            "ground_truth_y_m": round(source_y, 6),
        },
    }


def compute_summary(rows: list[dict]) -> dict:
    """Compute global MAE and per-scenario MAE."""
    errors = [float(r["error_mm"]) for r in rows]
    global_mae = sum(errors) / len(errors) if errors else 0.0

    mae_by_scenario: dict[str, float] = {}
    for scenario in SCENARIOS:
        scenario_errors = [
            float(r["error_mm"]) for r in rows if r["scenario"] == scenario
        ]
        mae_by_scenario[scenario] = (
            round(sum(scenario_errors) / len(scenario_errors), 4)
            if scenario_errors
            else None
        )

    # Include any scenario present in data but not in the predefined list
    present_scenarios = sorted({r["scenario"] for r in rows})
    for sc in present_scenarios:
        if sc not in mae_by_scenario:
            sc_errors = [float(r["error_mm"]) for r in rows if r["scenario"] == sc]
            mae_by_scenario[sc] = round(sum(sc_errors) / len(sc_errors), 4)

    return {
        "total_events": len(rows),
        "scenarios": present_scenarios,
        "mean_localization_error_mm": round(global_mae, 4),
        "mae_by_scenario": mae_by_scenario,
    }


def export(input_path: Path, output_path: Path) -> dict:
    """Main export function. Returns summary dict."""
    rows = load_csv(input_path)

    data_entries = [build_ifc_entry(i, row) for i, row in enumerate(rows)]
    summary = compute_summary(rows)

    ifc_doc = {
        "type": "ifcJSON",
        "version": "0.0.1",
        "schemaIdentifier": "IFC4",
        "description": "AE source localization results — shm-pinn-bolted",
        "data": data_entries,
        "summary": summary,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(ifc_doc, fh, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Export PINN localization results to ifcJSON for SHM Digital Twin"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input CSV path (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    summary = export(args.input, args.output)
    print(f"Exported {summary['total_events']} events → {args.output}")
    print(f"  mean_localization_error_mm : {summary['mean_localization_error_mm']}")
    print(f"  mae_by_scenario            : {summary['mae_by_scenario']}")


if __name__ == "__main__":
    main()
