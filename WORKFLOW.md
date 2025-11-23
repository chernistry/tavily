# Stealth Testing Workflow

## Problem
When testing stealth on the full dataset, ~92% of URLs succeed via HTTP-only path, so stealth techniques (which only run in Playwright) don't affect the aggregate success rate.

## Solution
Test stealth specifically on URLs that **fail** the HTTP-only path, where browser fallback is actually used.

---

## Quick Start

### Full Automated Workflow
```bash
./run.sh workflow
```

This will:
1. Run all 10k URLs through HTTP-only (no browser)
2. Collect failed URLs → `.sdd/raw/failed_urls.csv`
3. Run failed URLs with browser (normal)
4. Run failed URLs with browser + stealth
5. Print comparison

---

## Manual Workflow

### Step 1: Collect Failed URLs
```bash
./run.sh collect-failed
```

Output: `.sdd/raw/failed_urls.csv` (URLs that failed HTTP-only)

### Step 2: Test Browser with/without Stealth
```bash
./run.sh compare-browser
```

This runs:
- `data/stats_browser_normal.jsonl` - browser without stealth
- `data/stats_browser_stealth.jsonl` - browser with stealth

### Step 3: Analyze Results
```bash
./run.sh analyze data/stats_browser_stealth.jsonl
```

---

## Individual Commands

### Run Pipeline
```bash
# Basic
./run.sh pipeline --count 100

# With stealth
./run.sh pipeline --count 100 --stealth

# Custom URLs file
./run.sh pipeline --urls .sdd/raw/failed_urls.csv --stealth

# Custom stats suffix
./run.sh pipeline --count 100 --stats-suffix _test
```

### Compare Stealth (on first N URLs)
```bash
./run.sh compare 1000
```

### Analyze Any Stats File
```bash
./run.sh analyze data/stats_httpx_only.jsonl
./run.sh analyze data/stats_browser_stealth.jsonl
```

---

## Expected Results

On **failed URLs** (where browser is actually used), you should see:

**Without Stealth:**
- Higher CAPTCHA rate
- More HTTP errors (403, 429)
- Lower success rate

**With Stealth:**
- Lower CAPTCHA rate (stealth evasion works)
- Fewer blocks
- Higher success rate

---

## Files Generated

| File | Description |
|------|-------------|
| `data/stats.jsonl` | Default run stats |
| `data/stats_stealth.jsonl` | Run with `--stealth` |
| `data/stats_httpx_only.jsonl` | HTTP-only pass (no browser) |
| `data/stats_browser_normal.jsonl` | Browser without stealth |
| `data/stats_browser_stealth.jsonl` | Browser with stealth |
| `.sdd/raw/failed_urls.csv` | URLs that failed HTTP-only |

---

## Tips

1. **Quick test**: `./run.sh pipeline --count 10 --stealth`
2. **Full workflow**: `./run.sh workflow` (takes ~30-60 min for 10k URLs)
3. **Incremental**: Run `collect-failed` once, then iterate on `compare-browser`
4. **Custom dataset**: Create your own CSV and use `--urls`

---

## Troubleshooting

**"No failed URLs found"**
- Check if HTTP-only pass actually ran: `ls -lh data/stats_httpx_only.jsonl`
- Verify URLs file exists: `head .sdd/raw/urls.csv`

**"Stats file not found"**
- Make sure you ran the pipeline first
- Check `data/` directory: `ls -lh data/`

**"Stealth not working"**
- Verify stealth is enabled: look for "Stealth mode: enabled" in logs
- Check Playwright share: should be >0% in results
- Analyze stealth-specific stats: `./run.sh analyze data/stats_browser_stealth.jsonl`
