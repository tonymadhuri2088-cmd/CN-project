# Changelog

## Unreleased
- Opt-in `--mask-aware` (`Controller(mask_aware=True)`): a port_blocked claim is not accepted while a route failure on the target stands, which fixes the route-only false positive. Default behaviour and all published results are unchanged; not yet evaluated with a model (needs a new pre-registered suite and approval for paid runs).
- `.gitattributes`: dropped the `-text` rules for run logs (they made git see CRLF working copies as modified).
- Property-based tests (Hypothesis) for controller invariants.
- MIT licence; CITATION.cff; CONTRIBUTING; Makefile; pre-commit; Dependabot; CodeQL; issue/PR templates; `.gitattributes` protecting run logs.
- Reproducibility: 44 documented numbers (adds the two fresh3 suspected-fault counts).
- docs/ARCHITECTURE.md and docs/research/08-netwing-2-roadmap.md.

## 0.1.0 — Mini Project 2 (frozen baseline)
- Controller, simulated and network-namespace backends, opt-in strategies, frozen evaluation suites, live read-only demo.
- Suggested tag: `mini2-final`. NetWing 2.0 work builds on top without changing this baseline's behaviour or logs.
