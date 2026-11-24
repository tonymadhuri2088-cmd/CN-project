# Architecture

NetWing sits between an LLM diagnosis agent and the network. The model proposes tests and claims; the controller owns the stopping decision and which claims are accepted.

```mermaid
flowchart LR
    A[LLM agent] -->|tool call| B[Backend]
    B -->|ToolResult| C[Evidence ledger E1..En]
    C --> D{decide}
    D -->|reproduced failure and connectivity, dns, port tried| F[STOP_FAULT]
    D -->|clean and covered| H[STOP_HEALTHY]
    D -->|12 tests| X[STOP_CAP]
    D -->|otherwise| N[CONTINUE]
    A -->|claim + cited ids| G[allow_claim]
    C --> G
    G -->|accepted or rejected with reason| A
```

Decision order: healthy, fault, cap, continue. The ledger is append-only, so the verdict after k results depends only on the first k results (a property test checks this).

```mermaid
flowchart TB
    subgraph Backends
      S[SimNetwork] --- Nn[NetnsNetwork, WSL 2] --- K[Kathara, not yet run]
    end
    subgraph Evidence
      R[reproduce.py + claims.json] --> CI[CI strict check]
    end
    Backends --> Controller --> Evidence
```

Opt-in extensions (off by default): `--auto-cite`, `--guide-citations`, `--allow-inconclusive`, `--retest-hint`, `--healthy-strategy hybrid`, `--validate-claims`, `--tier-claims`.
