# FToE SO(10) scalar-potential source audit

Status: REVIEW. This file records what is source-complete versus what remains unconstructed. It is not a publication-readiness certificate.

## 1. Frozen core scalar content

The current gauge branch requires the non-supersymmetric SO(10) core

- `45_H`,
- complex `126_H` (with its conjugate in the potential),
- complex `10_C,H`,

plus `210_H` for the selected SO(10) -> G422 breaking route and a separately protected informational sector.

The requirement that the Yukawa-sector 10 be complex is not optional if this branch claims the standard realistic renormalizable `10 + 126` Yukawa structure. In the explicit non-supersymmetric `45 + 126 + 10_C` analysis of Jarkovska, Malinsky and Susic, arXiv:2304.14227, the complex 10 is emphasized as equivalent to two real 10s and supplies two SM-doublet copies before mixing.

## 2. Complete renormalizable `45 + 126 + 10_C` sub-potential

A source-complete invariant basis already exists for the `45 + 126 + 10_C` sector: arXiv:2304.14227, Eqs. (2)-(7). That work decomposes the potential as

`V0 = V45 + V126 + Vmix(45,126) + V10 + Vmix(45,126,10)`

and explicitly lists every quadratic, cubic and quartic invariant, including all complex-conjugate structures. The authors report an independent completeness check: the invariants are linearly independent and their number agrees with Hilbert-series counting.

This closes only the **source-provenance sub-gate** for the `45 + 126 + 10_C` core. It does not freeze the FToE UV action because two sectors are still absent from that basis:

1. `210_H` and every renormalizable invariant coupling it to `45_H`, `126_H` and `10_C,H`;
2. the protected informational sector and every allowed renormalizable portal connecting it to the GUT sector.

Treating the known `45 + 126 + 10_C` potential as if it were already the full FToE potential would therefore be a false closure.

## 3. Perturbativity warning inherited from the non-supersymmetric core

arXiv:2304.14227 identifies a broad tension in the minimal `45 + 126 + 10_C` theory between obtaining an SM-like light Higgs doublet and remaining perturbative. That result is directly relevant as an adversarial prior, but it is **not** imported as a no-go theorem for the current branch because FToE additionally contains `210_H` and a separate protected sector. Those extra interactions can change the doublet mass matrix and vacuum constraints. The correct status is therefore `WARNING / MUST_RETEST`, not `FAIL`.

Required FToE gate: after the full invariant basis is frozen, derive the doublet mass matrix and verify that the SM Higgs mode and the informational ~13.49 TeV mode arise without nonperturbative couplings or post-result tuning.

## 4. Pseudo-Goldstone protection benchmark

A concrete SO(10) proof of principle for naturally light pseudo-Goldstone electroweak doublets exists in the **supersymmetric** construction arXiv:1803.11164. Its protection architecture uses `45_H + 16_H + 16bar_H`, additional singlets, and `U(1)_A x Z_4` symmetries. The mechanism produces an accidental global symmetry, permits controlled explicit breaking, and obtains a TeV-scale mu term with an all-order hierarchy.

For the scale formula quoted in that construction,

`mu ~ (Lambda / v_R)^4 * O(M_*)`

when the order-one coupling combination and `v_R ~ V_{B-L}` are suppressed into the overall coefficient. Setting `mu = 9.54 TeV` and `M_* = 2.4e18 GeV` requires

`Lambda / v_R ~ (9.54e3 / 2.4e18)^(1/4) ~= 2.51e-4`,

which is numerically in the same range used in the published SUSY example for TeV-scale pseudo-Goldstone masses.

This is useful as a **mechanism benchmark**, not as a transplantable solution. It relies on supersymmetry, `16 + 16bar`, singlets and extra symmetries absent from the frozen FToE branch. Importing it directly would violate the current no-new-representation rule and would constitute a new theory branch.

## 5. Current falsification state

### PASS

- Independent G422 beta coefficients from the frozen interval spectrum.
- Source-complete renormalizable invariant basis for the `45 + 126 + 10_C` core is available externally and can be used as a checksum when implementing the FToE action.
- A concrete SO(10) pseudo-Goldstone precedent demonstrates that TeV-scale doublets can be symmetry-generated in principle, but only in a materially different SUSY field/symmetry architecture.

### REVIEW

- Full `210 + 45 + 126 + 10_C` invariant inventory.
- Exact protected informational representation and symmetry.
- Complete portal inventory and proof that lower-order mass-generating terms are absent or collectively suppressed.
- Vacuum equations, Hessian, physical scalar spectrum and derived heavy thresholds.
- Re-test of the light-Higgs perturbativity problem after adding `210_H` and the protected sector.

### Existing FAIL branches preserved

- Unprotected embedded informational doublet.
- Ordinary phase-only `Z_N` protection of `I^dagger I` and norm portals.
- Single ordinary GUT-scale gauge-spurion pNGB protection.

## 6. Next executable gate

Do not scan masses. First build a machine-readable invariant registry for all renormalizable operators containing `210_H` and for all operators containing the chosen informational multiplet. Every invariant must carry: fields, tensor channel, canonical dimension, coefficient, symmetry status, and whether it contributes to (a) the vacuum, (b) the SM Higgs doublet matrix, (c) the informational-doublet mass, or (d) heavy thresholds.

Only after that registry is complete should the vacuum and Hessian be generated. Any lower-order allowed informational mass/portal term that cannot be removed by the frozen protection symmetry is a hard L1 falsification.

## Primary sources

- K. Jarkovska, M. Malinsky, V. Susic, `The trouble with the minimal renormalizable SO(10) GUT`, arXiv:2304.14227.
- Z. Tavartkiladze, `Light Pseudo-Goldstone Higgs Boson from SO(10) GUT with Realistic Phenomenology`, arXiv:1803.11164.
- L. Graf, M. Malinsky, T. Mede, V. Susic, `One-loop pseudo-Goldstone masses in the minimal SO(10) Higgs model`, arXiv:1611.01021.
