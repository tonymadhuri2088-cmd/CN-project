# Re-run ONLY the tier arm of the Sonnet fresh3 check (first attempt stopped after 4 runs on a connection error;
# that partial log is kept as results/fresh3_sonnet_tier_partial_connerr.jsonl). Costs about $2; capped at $3.
# Run from the repo root in PowerShell with $env:ANTHROPIC_API_KEY already set to a valid key.
$ErrorActionPreference = "Stop"
if (-not (Test-Path "netwing")) { throw "Run this from the repo root." }
if (-not ($env:ANTHROPIC_API_KEY -and $env:ANTHROPIC_API_KEY.StartsWith("sk-ant-"))) {
  Read-Host "Now COPY the API key (Ctrl+C) from where you keep it, then come back here and press Enter" | Out-Null
  $env:ANTHROPIC_API_KEY = (Get-Clipboard -Raw).Trim()
}
Write-Host ("key length: " + $env:ANTHROPIC_API_KEY.Length + "  starts with sk-ant-: " + $env:ANTHROPIC_API_KEY.StartsWith("sk-ant-"))
if (-not $env:ANTHROPIC_API_KEY.StartsWith("sk-ant-")) { Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue; throw "That is not an Anthropic key (it should start with sk-ant-). Nothing was run." }
$out = "results/fresh3_sonnet_tier.jsonl"
if (Test-Path $out) { throw "$out already exists" }
try {
  python -m netwing.demo --backend sim --suite fresh3 --modes netwing --repeats 8 --cap 3 --model claude-sonnet-5-5 --tier-claims --out $out
  git add -f $out
} finally {
  Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
  Write-Host "API key cleared from this session."
}
