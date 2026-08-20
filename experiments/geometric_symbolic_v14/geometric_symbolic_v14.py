"""v14 upper-midpoint singleton-anchor dose test.

Reuses the exact v11 model/data/training/evaluation implementation, changing only
preregistered anchor rate and fresh random seeds. This brackets the transition
between the v11 10% PASS and v13 5% FAIL without changing scientific thresholds.
"""

import importlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

v11 = importlib.import_module(
    "experiments.geometric_symbolic_v11.geometric_symbolic_v11"
)

v11.ANCHOR_RATE = 0.075
v11.SEEDS = (120, 121, 122)

if __name__ == "__main__":
    v11.main()
