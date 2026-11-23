"""NetWing: an evidence-sufficiency controller for LLM network-diagnosis agents.

Layout
- `controller`  rule-based evidence ledger: when to stop, which claims to accept (the research core)
- `agent`       the diagnosis loop (model + tools + controller) and the per-run log
- `backend`     the tool interface; implementations: `sim` (simulator), `netns` (Linux namespaces), `kathara`
- `scenarios`, `scoring`   tickets with ground truth and deterministic scoring
- `runner`, `demo`, `budget`, `dryrun`   experiment matrix, CLI, cost caps, zero-cost stub client
- `final_report`, `belief`, `belief_report`, `strategy_replay`   offline analysis of saved logs
- `records`, `health`, `history`, `report`, `pdfexport`, `webui`   investigation UI and reports

Everything beyond the default rules is opt-in; see README.md for flags and results.
"""
