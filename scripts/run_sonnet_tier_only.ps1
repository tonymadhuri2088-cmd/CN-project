# Re-run ONLY the tier arm of the Sonnet fresh3 check (first attempt stopped after 4 runs on a connection error;
# that partial log is kept as results/fresh3_sonnet_tier_partial_connerr.jsonl). Costs about $2; capped at $3.
# Run from the repo root in PowerShell with $env:ANTHROPIC_API_KEY already set to a valid key.
$ErrorActionPreference = "Stop"
if (-not (Test-Path "netwing")) { throw "Run this from the repo root." }
if (-not ($env:ANTHROPIC_API_KEY -and $env:ANTHROPIC_API_KEY.StartsWith("sk-ant-"))) { throw "Set ANTHROPIC_API_KEY first." }
$out = "results/fresh3_sonnet_tier.jsonl"
if (Test-Path $out) { throw "$out already exists" }
try {
  python -m netwing.demo --backend sim --suite fresh3 --modes netwing --repeats 8 --cap 3 --model claude-sonnet-5-5 --tier-claims --out $out
  git add -f $out
} finally {
  Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
  Write-Host "API key cleared from this session."
}
