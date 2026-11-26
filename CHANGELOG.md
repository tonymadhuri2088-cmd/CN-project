# Changelog

## Unreleased
- fresh6 (pre-registered, run once): `--cover-areas` with `--tier-claims` raises both-faults-confirmed from 27% to 98% on 60 double-fault runs (M, H, C met); stays opt-in. See `docs/research/19`.
- fresh5 results (`docs/research/15-...`): `--cover-areas` meets no-harm (H) and cost (C) but not the +15-point completeness criterion (M; baseline already 98%, ceiling). Exploratory: both faulty areas reproduced in 60/60 double-fault runs vs 16/60. Stays opt-in.
- Opt-in `--cover-areas` (layer-coverage stopping rule): do not stop on a fault while another area has a failure seen only once. Frozen suite `fresh5` and pre-registration (`docs/research/13-...`), 13 new tests; not yet run with a model. Pre-registered cross-model check of fresh3 on Sonnet 5.5 (`docs/research/14-...`), with a corrected cost estimate (about $4.5, not $0.50).
- fresh4 results (`docs/research/12-fresh4-results.md`): `--mask-reproduced` matches the default on port-blip and route-only runs (criteria B and R met; S not informative); `--mask-aware` v1 reproduced its blip defect (60% no-answer).
- Opt-in `--mask-reproduced` (masking v2): only a reproduced connectivity failure masks port claims; masked secondary port claims are dropped and logged. Frozen suite `fresh4` and its pre-registration. `--mask-aware` (v1) stays as is and is documented as a negative result (live run: blip scenario 10 of 10 no-answers).
- Opt-in `--mask-aware` (`Controller(mask_aware=True)`): a port_blocked claim is not accepted while a route failure on the target stands, which fixes the route-only false positive. Default behaviour and all published results are unchanged; not yet evaluated with a model (needs a new pre-registered suite and approval for paid runs).
- `.gitattributes`: dropped the `-text` rules for run logs (they made git see CRLF working copies as modified).
- Property-based tests (Hypothesis) for controller invariants.
- MIT licence; CITATION.cff; CONTRIBUTING; Makefile; pre-commit; Dependabot; CodeQL; issue/PR templates; `.gitattributes` protecting run logs.
- Reproducibility: 44 documented numbers (adds the two fresh3 suspected-fault counts).
- docs/ARCHITECTURE.md and docs/research/08-netwing-2-roadmap.md.

## 0.1.0 — Mini Project 2 (frozen baseline)
- Controller, simulated and network-namespace backends, opt-in strategies, frozen evaluation suites, live read-only demo.
- Suggested tag: `mini2-final`. NetWing 2.0 work builds on top without changing this baseline's behaviour or logs.
