Read .sdd/CODING_RULES.md first

# P1_10 – Colab notebook and visualizations

## Objective

Create a Colab-ready notebook (`tavily_scraper/notebooks/tavily_assignment.ipynb`) that installs dependencies, loads URLs and proxies, runs the sharded batch runner, and visualizes metrics and flow, as required by the assignment.

## Dependencies

- Depends on:
  - `P0_09_shard_and_batch_runners.md`
  - `P0_08_storage_checkpoints_and_metrics.md`

## Scope

- A single notebook with:

  - Setup and installation.
  - Configuration and environment wiring.
  - Run orchestration (calling `run_all`).
  - Visualization of stats and summary metrics.
  - Flowchart of the architecture.

## Implementation Steps

1. **Create notebook skeleton**

   - Add `tavily_scraper/notebooks/tavily_assignment.ipynb`.
   - Structure cells in a logical order:

     1. **Introduction & context (Markdown)** – explain the assignment, high-level architecture (HTTP + Playwright), and what the notebook will show.
     2. **Environment setup (Code)** – install dependencies and Playwright browsers.
     3. **Configuration (Code)** – configure env vars and paths.
     4. **Run scraper (Code)** – call into `run_all`.
     5. **Load and inspect outputs (Code + Markdown)** – read `stats.jsonl` and `run_summary.json`.
     6. **Visualizations (Code)** – plots and domain-level analytics.
     7. **Flowchart (Markdown/Code)** – Mermaid or ASCII diagram of pipeline.
     8. **Findings & next steps (Markdown)** – commentary.

2. **Environment setup cell**

   Example cell:

   ```python
   !pip install -r requirements.txt
   !python -m playwright install --with-deps chromium
   ```

   - Consider pinning the repo (cloning from GitHub) if notebook is meant to be run directly from Colab.

3. **Configuration cell**

   - Show how to mount or upload `urls.csv` and `proxy.json` in Colab:

     ```python
     from google.colab import files

     uploaded = files.upload()  # for urls.csv and proxy.json
     ```

   - Set env vars in notebook:

     ```python
     import os

     os.environ["TAVILY_ENV"] = "colab"
     os.environ["TAVILY_DATA_DIR"] = "/content/data"
     os.environ["HTTPX_TIMEOUT_SECONDS"] = "10"
     os.environ["HTTPX_MAX_CONCURRENCY"] = "32"
     os.environ["PLAYWRIGHT_HEADLESS"] = "true"
     os.environ["PLAYWRIGHT_MAX_CONCURRENCY"] = "2"
     os.environ["SHARD_SIZE"] = "500"
     os.environ["PROXY_CONFIG_PATH"] = "/content/proxy.json"  # if uploaded
     ```

4. **Run orchestration cell**

   - Example:

     ```python
     import asyncio

     from tavily_scraper.config.env import load_run_config
     from tavily_scraper.pipelines.batch_runner import run_all


     config = load_run_config()
     run_summary = asyncio.run(run_all(config))
     run_summary
     ```

   - For long runs, consider logging progress or printing periodic summaries.

5. **Data loading cells**

   - Read `data/stats.jsonl` into a pandas DataFrame:

     ```python
     import json
     from pathlib import Path

     import pandas as pd


     stats_path = Path("/content/data/stats.jsonl")
     rows = [json.loads(line) for line in stats_path.read_text(encoding="utf-8").splitlines()]
     df = pd.DataFrame(rows)
     df.head()
     ```

   - Load `data/run_summary.json`:

     ```python
     run_summary_path = Path("/content/data/run_summary.json")
     run_summary = json.loads(run_summary_path.read_text(encoding="utf-8"))
     run_summary
     ```

6. **Visualization cells**

   - Latency histograms by method:

     ```python
     import matplotlib.pyplot as plt


     fig, ax = plt.subplots(1, 2, figsize=(12, 4))

     df_httpx = df[df["method"] == "httpx"]
     df_playwright = df[df["method"] == "playwright"]

     ax[0].hist(df_httpx["latency_ms"].dropna(), bins=50)
     ax[0].set_title("HTTPX latency (ms)")
     ax[0].set_xlabel("Latency (ms)")

     ax[1].hist(df_playwright["latency_ms"].dropna(), bins=50)
     ax[1].set_title("Playwright latency (ms)")
     ax[1].set_xlabel("Latency (ms)")
     plt.show()
     ```

   - Status distribution:

     ```python
     df["status"].value_counts().plot(kind="bar", title="Status distribution")
     ```

   - Per-domain success vs CAPTCHA vs robots:

     ```python
     domain_status = df.groupby(["domain", "status"]).size().unstack(fill_value=0)
     domain_status.sort_values("success", ascending=False).head(20)
     ```

7. **Flowchart**

   - Include a Mermaid diagram in a Markdown cell:

     ```markdown
     ```mermaid
     flowchart TD
       A[urls.csv] --> B[make_url_jobs]
       B --> C[make_shards]
       C --> D[run_shard]
       D --> E[router.route_and_fetch]
       E -->|HTTP success| F[UrlStats (httpx)]
       E -->|needs browser| G[BrowserFetcher]
       G --> H[UrlStats (playwright)]
       F & H --> I[stats.jsonl]
       I --> J[compute_run_summary]
       J --> K[run_summary.json]
     ```
     ```

8. **Findings & SLO evaluation**

   - Add Markdown that:

     - Summarizes key metrics (success rate, HTTP vs Playwright share, P95 latencies).
     - States whether SLOs (e.g., success rate ≥ 90%, P95 latencies within bounds) are met.
     - Discusses observed anti-bot patterns or high-CAPTCHA domains.

## Acceptance Criteria

- `tavily_scraper/notebooks/tavily_assignment.ipynb`:

  - Can be opened in Colab and run top-to-bottom.
  - Installs dependencies and Playwright browsers successfully.
  - Loads URLs and proxies from user-uploaded files or configured paths.
  - Calls `run_all` and displays the `RunSummary`.
  - Loads `stats.jsonl` into pandas and displays at least one latency histogram, status distribution chart, and per-domain summary.
  - Includes a flowchart describing the pipeline in a reviewer-friendly way.

- Notebook does not contain core scraping logic (HTTP requests, Playwright calls, router decisions); it calls into the `tavily_scraper` package exclusively.
- Markdown commentary explains how to interpret plots and relates metrics back to architecture decisions and SLOs.

