"""Create a fictional price series with visible trends; no market data is downloaded."""
import csv
import math
from datetime import date, timedelta
from pathlib import Path

def generate():
    rows = []
    day = date(2025, 1, 1)
    while len(rows) < 260:
        if day.weekday() < 5:
            i = len(rows)
            close = 100 + 0.07 * i + 8 * math.sin(i / 14) + 2 * math.cos(i / 5)
            rows.append([str(day), f"{close:.2f}", 100000 + (i * 7919) % 90000])
        day += timedelta(days=1)
    return rows

if __name__ == "__main__":
    path = Path(__file__).resolve().parent / "data/demo_prices.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["date", "close", "volume"])
        writer.writerows(generate())
    print(f"Wrote {path}")
