"""Calculate moving averages and historical crossover events on daily prices."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent

def load_prices(path):
    data = pd.read_csv(path)
    if not {"date", "close"}.issubset(data.columns):
        raise ValueError("CSV must contain date and close columns.")
    data["date"] = pd.to_datetime(data["date"], format="%Y-%m-%d", errors="raise")
    data["close"] = pd.to_numeric(data["close"], errors="raise")
    if data["date"].isna().any() or data["date"].duplicated().any():
        raise ValueError("Dates must be present and unique; supply one asset at a time.")
    if not np.isfinite(data["close"]).all() or not data["close"].gt(0).all():
        raise ValueError("Every close must be finite and greater than zero.")
    return data.sort_values("date").reset_index(drop=True)

def calculate_indicators(data, fast=20, slow=50):
    if not isinstance(fast, int) or not isinstance(slow, int) or not 1 <= fast < slow:
        raise ValueError("Windows must be integers satisfying 1 <= fast < slow.")
    if len(data) < slow + 1:
        raise ValueError(f"Need at least {slow + 1} daily observations.")
    result = data.copy()
    # Trailing windows include only this observation and earlier observations.
    result["sma_fast"] = result["close"].rolling(fast, min_periods=fast).mean()
    result["sma_slow"] = result["close"].rolling(slow, min_periods=slow).mean()
    result["daily_return"] = result["close"].pct_change(fill_method=None)
    result["cumulative_price_return"] = result["close"] / result["close"].iloc[0] - 1
    result["drawdown"] = result["close"] / result["close"].cummax() - 1
    result["rolling_volatility_20"] = result["daily_return"].rolling(20).std(ddof=1) * np.sqrt(252)
    spread = result["sma_fast"] - result["sma_slow"]
    previous = spread.shift(1)
    ready = spread.notna() & previous.notna()
    result["signal"] = "NONE"
    result.loc[ready & spread.gt(0) & previous.le(0), "signal"] = "BUY"
    result.loc[ready & spread.lt(0) & previous.ge(0), "signal"] = "SELL"
    result["trend"] = "WARMUP"
    result.loc[spread.gt(0), "trend"] = "ABOVE"
    result.loc[spread.lt(0), "trend"] = "BELOW"
    result.loc[spread.eq(0), "trend"] = "EQUAL"
    return result

def summarize(result):
    return {
        "observations": len(result),
        "start": str(result.date.iloc[0].date()),
        "end": str(result.date.iloc[-1].date()),
        "price_return_pct": float(result.cumulative_price_return.iloc[-1] * 100),
        "annualized_volatility_pct": float(result.daily_return.std(ddof=1) * np.sqrt(252) * 100),
        "max_drawdown_pct": float(result.drawdown.min() * 100),
        "buy_crossovers": int(result.signal.eq("BUY").sum()),
        "sell_crossovers": int(result.signal.eq("SELL").sum()),
        "latest_trend": str(result.trend.iloc[-1]),
        "latest_crossover": str(result.signal.iloc[-1]),
    }

def run(input_path=ROOT / "data/demo_prices.csv", output_dir=ROOT / "outputs", fast=20, slow=50):
    result = calculate_indicators(load_prices(input_path), fast, slow)
    summary = summarize(result)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_dir / "indicators.csv", index=False)
    result.loc[result.signal.ne("NONE")].to_csv(output_dir / "crossovers.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(result.date, result.close, label="Close", color="#283342", alpha=0.7)
    axes[0].plot(result.date, result.sma_fast, label=f"{fast}-observation SMA", color="#246b74")
    axes[0].plot(result.date, result.sma_slow, label=f"{slow}-observation SMA", color="#d67b36")
    for event, marker, color in [("BUY", "^", "#168264"), ("SELL", "v", "#b63d3d")]:
        points = result.loc[result.signal.eq(event)]
        axes[0].scatter(points.date, points.close, marker=marker, color=color, s=65, label=event, zorder=4)
    axes[0].set(title="Historical moving-average crossover events", ylabel="Price units")
    axes[0].legend(ncol=3, fontsize=8)
    axes[1].fill_between(result.date, result.drawdown * 100, 0, color="#b63d3d", alpha=0.25)
    axes[1].set(title="Decline from the highest closing price so far", ylabel="Drawdown (%)", xlabel="Date")
    fig.tight_layout()
    fig.savefig(output_dir / "market_overview.png", dpi=160)
    plt.close(fig)
    report = (
        "# Market indicator findings\n\n"
        f"Input: {Path(input_path).name}. Windows: {fast} and {slow} observations.\n\n"
        "The bundled DEMO dataset is simulated; it is not an actual stock.\n\n"
        f"- Period: {summary['start']} to {summary['end']}\n"
        f"- Closing-price return: {summary['price_return_pct']:.2f}%\n"
        f"- Annualized daily volatility (252-observation convention): {summary['annualized_volatility_pct']:.2f}%\n"
        f"- Maximum drawdown: {summary['max_drawdown_pct']:.2f}%\n"
        f"- BUY / SELL crossover events: {summary['buy_crossovers']} / {summary['sell_crossovers']}\n\n"
        "These are descriptive price statistics, not strategy returns. Signals are known only after the "
        "observation's close. No orders, execution prices, fees, dividends, or trading results are modeled.\n")
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/demo_prices.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs")
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=50)
    args = parser.parse_args()
    try:
        run(args.input, args.output, args.fast, args.slow)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Error: {error}\n")
