import json
import os
from datetime import datetime


# ─────────────────────────────────────────────
# BUG 6 FIX: json.dump crashes if report contains pandas Timestamp or numpy
# int64/float64 values (e.g. from date columns in the report dict).
# Added a custom serialiser that handles these gracefully.
# ─────────────────────────────────────────────
class _SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            import numpy as np
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        try:
            import pandas as pd
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
        except ImportError:
            pass
        return str(obj)  # fallback: stringify unknown types


def save_log(report, log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    filename = os.path.join(log_dir, f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(filename, "w") as f:
        json.dump(report, f, indent=4, cls=_SafeEncoder)
