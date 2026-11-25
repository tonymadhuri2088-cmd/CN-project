# Cross-model check of fresh3 on Sonnet 5.5 (pre-registration: docs/research/14). Costs about $4.5; each log is capped at $3.
# Run from the repo root in PowerShell:  .\scripts\run_sonnet_fresh3.ps1
$ErrorActionPreference = "Stop"
if (-not (Test-Path "netwing")) { throw "Run this from the repo root (the folder that contains netwing/)." }
$sec = Read-Host "Paste a NEW Anthropic API key (input is hidden)" -AsSecureString
$env:ANTHROPIC_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
try {
  foreach ($arm in @(@{n="original"; f=@()}, @{n="tier"; f=@("--tier-claims")})) {
    $out = "results/fresh3_sonnet_$($arm.n).jsonl"
    if (Test-Path $out) { throw "$out already exists: delete it or add --resume yourself" }
    python -m netwing.demo --backend sim --suite fresh3 --modes netwing --repeats 8 --cap 3 --model claude-sonnet-5-5 @($arm.f) --out $out
    if ($LASTEXITCODE -ne 0) { throw "Run failed for $($arm.n); do not rerun without --resume" }
  }
} finally {
  Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
  Write-Host "API key cleared from this session."
}
git add -f results/fresh3_sonnet_original.jsonl results/fresh3_sonnet_tier.jsonl
Write-Host "Logs staged. Now run:  git commit -m 'Add run logs: fresh3 on Sonnet 5.5'  then  git push"
