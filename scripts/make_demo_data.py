"""Regenerate data/demo_app_telemetry.csv (synthetic, deliberately seeded defects)."""
import random, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_datasentinel import make_clean, inject

random.seed(42); np.random.seed(42)
df, _ = inject(make_clean(400))
out = Path(__file__).resolve().parent.parent / "data" / "demo_app_telemetry.csv"
df.to_csv(out, index=False)
print(f"Wrote {len(df)} rows to {out}")
