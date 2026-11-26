# Handoff to the Major project: open items after Mini Project 2 (2026-11-26)

Each item names why it is open, what it needs, and whether it needs approval first. Nothing here changes a default or a published number.

## Open scientific items
1. **Second-fault under-confirmation (main weakness).** The stop rule ends the run once one fault is reproduced and ping/DNS/port were tried, so both faults are confirmed in about 25% of double-fault runs (Haiku 15/59, Sonnet 5/21). `--cover-areas` reached both areas in 60/60 runs vs 16/60 but did not move the pre-registered completeness measure (metric saturated at 59/60). Needs: a new frozen suite with confirmation scoring (`--validate-claims`) or a second model. Needs approval before any paid run or architecture change.
2. **One model for the main results.** Haiku 5.5 throughout; Sonnet 5.5 checked on fresh3 only (original arm complete 56/56; tier arm 36 of 56, stopped by a network error). Finishing the tier arm costs about $0.8 (remaining runs) and needs a valid key and approval.
3. **Real-network coverage.** Only the `easy` suite has a real (namespace) lab; hard, flaky, multi, campus and lab suites are simulator-only. Needs real labs for those scenarios.
4. **Kathara never run.** `scripts/kathara_smoke.sh` is ready; it needs Docker Desktop with WSL integration and Kathara installed. Paste the output so `build_exec_cmd` can be fixed if needed.
5. **Small samples.** Most intervals are wide (n of 20 to 60); 30+ repeats for the headline claims.
6. **Tuning risk.** Rules and `--auto-cite` were refined on earlier suites; later frozen suites are independent. Held-out checks for `--auto-cite` remain.
7. **Not supported, not promoted:** strict claim validation, tiering (on Haiku and on Sonnet, C3 not met), `--cover-areas`, `--mask-aware` (v1 harmful), `--mask-reproduced` (v2 no gain).

## Housekeeping
- `claims_v2.json` now holds 14 numbers (fresh5 off/cover, fresh3 Sonnet original); add maskaware and fresh4 numbers when their documents quote counts the logs reproduce.
- Delete the merged `v2-dev` branch; merge the Dependabot PRs.
- Related-work abstention sentence: check with the co-author.
- Change the Ubuntu password; rotate any API key that was ever pasted into a screenshot or chat.
- Sections 11 onward of the Mini Project 2 instruction file were never received.
