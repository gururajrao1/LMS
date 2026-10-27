import argparse
import csv
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path


parser = argparse.ArgumentParser(description="Compare Anthropic dashboard costs with PharmaLearn logs.")
parser.add_argument("csv", type=Path)
parser.add_argument("--data-dir", type=Path, default=Path(".pharmalearn"))
parser.add_argument("--local-total", type=Decimal, help="Use a captured local total when old logs were removed.")
args = parser.parse_args()

with args.csv.open(newline="") as file:
    dashboard = sum((Decimal(row["cost_usd"]) for row in csv.DictReader(file)), Decimal())

if args.local_total is None:
    local = sum(
        (Decimal(str(json.loads(path.read_text()).get("spent_usd", 0))) for path in args.data_dir.glob("logs/*/usage.json")),
        Decimal(),
    )
else:
    local = args.local_total

value = {
    "source": str(args.csv.resolve()),
    "reconciled_at": datetime.now(UTC).isoformat(),
    "anthropic_dashboard_usd": float(dashboard),
    "locally_recorded_usd": float(local),
    "unreconciled_usd": float(dashboard - local),
    "dashboard_is_authoritative": True,
}
output = args.data_dir / "billing" / f"{args.csv.stem}.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(value, indent=2) + "\n")
print(json.dumps(value, indent=2))
