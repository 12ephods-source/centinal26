"""v12 low-dose singleton-anchor stress test.

Reuses the exact v11 model/data/training/evaluation implementation, changing only
preregistered anchor rate and fresh random seeds. This tests whether the v11
mechanism survives a five-fold reduction in singleton-anchor frequency.
"""
from experiments.geometric_symbolic_v11 import geometric_symbolic_v11 as v11

v11.ANCHOR_RATE = 0.02
v11.SEEDS = (100, 101, 102)

if __name__ == "__main__":
    v11.main()
