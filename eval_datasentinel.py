"""
Evaluate DataSentinel's deterministic checks against SEEDED defects.
Run from the repo root:  python scripts/eval_datasentinel.py
Uses only profiling.py (no LLM/API key needed), so numbers are reproducible.
"""
import sys, time, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd
from datasentinel.profiling import profile_dataframe

random.seed(0); np.random.seed(0)

def make_clean(n=2000):
    """Clean synthetic telemetry matching the columns profiling.py expects."""
    t0 = pd.Timestamp("2026-01-01", tz="UTC")
    rows = []
    for i in range(n):
        et = t0 + pd.Timedelta(seconds=int(np.random.randint(0, 86400 * 7)))
        platform = random.choice(["ios", "android", "web"])
        version = random.choice(["1.0", "1.1", "1.2"])
        rows.append({
            "event_id": f"e{i}", "event_time": et,
            "ingested_at": et + pd.Timedelta(seconds=int(np.random.randint(1, 60))),
            "user_id": f"u{np.random.randint(0, 300)}",
            "session_id": f"s{np.random.randint(0, 600)}",
            "event_name": random.choice(["page_view", "click", "checkout_started"]),
            "platform": platform, "app_version": version,
            "product_id": f"p{np.random.randint(0, 50)}", "productId": np.nan,
            "endpoint": "/api/cart", "status_code": 200,
            "latency_ms": float(np.random.randint(50, 400)),
        })
    # healthy funnel: every checkout_started session also completes a purchase
    for r in [x for x in rows if x["event_name"] == "checkout_started"]:
        done = dict(r); done["event_id"] = r["event_id"] + "_p"
        done["event_name"] = "purchase_completed"; rows.append(done)
    df = pd.DataFrame(rows)
    df["productId"] = df["productId"].astype(object)
    return df

def inject(df):
    """Seed 5 defect types; return (df, set of expected finding types)."""
    df = df.copy(); expected = set()
    idx = df.sample(40, random_state=1).index
    df.loc[idx, "event_id"] = np.nan; expected.add("required_field_missing")
    dup = df.sample(30, random_state=2).index
    df.loc[dup, "event_id"] = "e_dup"; expected.add("duplicate_event_delivery")
    drift = df[(df.platform == "android") & (df.app_version == "1.2")].index[:50]
    df.loc[drift, "productId"] = df.loc[drift, "product_id"]
    df.loc[drift, "product_id"] = np.nan; expected.add("schema_drift")
    lag = df[(df.platform == "ios") & (df.app_version == "1.1")].index
    df.loc[lag, "ingested_at"] = df.loc[lag, "event_time"] + pd.Timedelta(seconds=900)
    expected.add("ingestion_delay")
    bad = df[(df.platform == "web") & (df.app_version == "1.0")].index
    df.loc[bad, "status_code"] = 503; expected.add("api_error_spike")
    return df, expected

if __name__ == "__main__":
    runs, tp, fp, fn = 5, 0, 0, 0
    clean_flags = []
    times = []
    for r in range(runs):
        random.seed(r); np.random.seed(r)
        clean = make_clean()
        clean_found = {f["type"] for f in profile_dataframe(clean, include_findings=True)}
        clean_flags.append(clean_found)
        dirty, expected = inject(clean)
        s = time.perf_counter()
        found = {f["type"] for f in profile_dataframe(dirty, include_findings=True)}
        times.append(time.perf_counter() - s)
        tp += len(expected & found); fn += len(expected - found)
        fp += len(found - expected)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    print(f"Runs: {runs} | rows/run: 2000 | defect types seeded/run: 5")
    print(f"Precision: {prec:.0%}  Recall: {rec:.0%}  (tp={tp}, fp={fp}, fn={fn})")
    print(f"Avg scan time: {np.mean(times)*1000:.0f} ms")
    print("False alarms on CLEAN data:", [sorted(c) for c in clean_flags])
