import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from indicators import ROOT, calculate_indicators, load_prices, run

class IndicatorTests(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame({"date": pd.date_range("2025-01-01", periods=8),
                             "close": [3., 2., 1., 2., 3., 2., 1., 2.]})

    def test_hand_calculated_crossovers_and_warmup(self):
        result = calculate_indicators(self.fixture(), fast=2, slow=3)
        self.assertAlmostEqual(result.sma_slow.iloc[2], 2)
        self.assertEqual(result.signal.tolist(),
                         ["NONE", "NONE", "NONE", "NONE", "BUY", "NONE", "SELL", "NONE"])
        self.assertEqual(result.trend.iloc[0], "WARMUP")
        self.assertAlmostEqual(result.daily_return.iloc[1], -1 / 3)
        self.assertAlmostEqual(result.drawdown.min(), -2 / 3)

    def test_future_prices_do_not_change_past_signals(self):
        original = load_prices(ROOT / "data/demo_prices.csv")
        changed = original.copy()
        changed.loc[200:, "close"] *= 4
        before = calculate_indicators(original).iloc[:200]
        after = calculate_indicators(changed).iloc[:200]
        pd.testing.assert_frame_equal(before, after)

    def test_constant_prices_have_no_events(self):
        data = self.fixture()
        data["close"] = 10.0
        result = calculate_indicators(data, 2, 3)
        self.assertTrue(result.signal.eq("NONE").all())
        self.assertTrue(result.drawdown.eq(0).all())

    def test_invalid_windows_and_prices_are_rejected(self):
        with self.assertRaises(ValueError):
            calculate_indicators(self.fixture(), 3, 2)
        with self.assertRaises(ValueError):
            calculate_indicators(self.fixture(), 2, 10)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            for content in ["date,close\n2025-01-01,0\n",
                            "date,close\n2025-01-01,10\n2025-01-01,11\n",
                            "date,close\n2025-01-01,inf\n"]:
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_prices(path)

    def test_report_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run(output_dir=directory)
            self.assertEqual(len(result), 260)
            self.assertTrue((Path(directory) / "market_overview.png").is_file())

if __name__ == "__main__":
    unittest.main()
