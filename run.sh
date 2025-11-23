#!/bin/bash
# Unified entry point for Tavily scraper operations

set -e

CMD="${1:-help}"
shift || true

case "$CMD" in
  # === MAIN PIPELINE ===
  pipeline)
    echo "🚀 Running main pipeline..."
    python run_pipeline.py "$@"
    ;;
  
  # === COLLECT FAILED URLs ===
  collect-failed)
    echo "🔍 Collecting HTTP-failed URLs..."
    python collect_failed_urls.py "$@"
    ;;
  
  # === COMPARE STEALTH ===
  compare)
    COUNT="${1:-1000}"
    echo "⚖️  Comparing stealth vs normal (first $COUNT URLs)..."
    python compare_stealth_runs.py --count "$COUNT"
    ;;
  
  # === COMPARE BROWSER (on failed URLs) ===
  compare-browser)
    URLS="${1:-.sdd/raw/failed_urls.csv}"
    echo "⚖️  Comparing browser stealth on failed URLs..."
    echo "   Without stealth..."
    python run_pipeline.py --urls "$URLS" --browser --stats-suffix "_browser_normal"
    echo "   With stealth..."
    python run_pipeline.py --urls "$URLS" --browser --stealth --stats-suffix "_browser_stealth"
    echo ""
    echo "📊 Results:"
    python - <<'PY'
import json, pathlib
for name in ("stats_browser_normal.jsonl", "stats_browser_stealth.jsonl"):
    path = pathlib.Path("data", name)
    if not path.exists():
        continue
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    total = len(rows)
    success = sum(r["status"] == "success" for r in rows)
    captcha = sum(r["status"] == "captcha_detected" for r in rows)
    http_err = sum(r["status"] == "http_error" for r in rows)
    timeout = sum(r["status"] == "timeout" for r in rows)
    playwright = sum(r["method"] == "playwright" for r in rows)
    print(f"\n{name}:")
    print(f"  Total: {total}")
    print(f"  Success: {success} ({100*success/total:.1f}%)")
    print(f"  CAPTCHA: {captcha} ({100*captcha/total:.1f}%)")
    print(f"  HTTP Error: {http_err} ({100*http_err/total:.1f}%)")
    print(f"  Timeout: {timeout} ({100*timeout/total:.1f}%)")
    print(f"  Playwright: {playwright} ({100*playwright/total:.1f}%)")
PY
    ;;
  
  # === ANALYZE ===
  analyze)
    FILE="${1:-data/stats.jsonl}"
    echo "📊 Analyzing $FILE..."
    python analyze_results.py --file "$FILE"
    ;;
  
  # === FULL WORKFLOW ===
  workflow)
    echo "🔄 Running full workflow..."
    echo ""
    echo "Step 1: Collect failed URLs from HTTP-only pass"
    ./run.sh collect-failed
    echo ""
    echo "Step 2: Compare browser with/without stealth on failed URLs"
    ./run.sh compare-browser
    ;;
  
  # === HELP ===
  help|*)
    cat <<'HELP'
Tavily Scraper - Unified CLI

USAGE:
  ./run.sh <command> [options]

COMMANDS:
  pipeline [opts]           Run main pipeline (pass through to run_pipeline.py)
                            Example: ./run.sh pipeline --count 100 --stealth
  
  collect-failed            Run HTTP-only pass on all URLs, save failed ones
                            Output: .sdd/raw/failed_urls.csv
  
  compare [count]           Compare stealth vs normal on first N URLs
                            Default: 1000
  
  compare-browser [file]    Compare browser stealth on failed URLs
                            Default file: .sdd/raw/failed_urls.csv
  
  analyze [file]            Analyze results from stats file
                            Default: data/stats.jsonl
  
  workflow                  Full workflow: collect-failed → compare-browser
  
  help                      Show this help

EXAMPLES:
  # Quick test with 100 URLs
  ./run.sh pipeline --count 100
  
  # Full workflow to test stealth on failed URLs
  ./run.sh workflow
  
  # Manual workflow
  ./run.sh collect-failed
  ./run.sh compare-browser .sdd/raw/failed_urls.csv
  
  # Analyze specific run
  ./run.sh analyze data/stats_stealth.jsonl

HELP
    ;;
esac
