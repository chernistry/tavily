# Tavily Web Scraping Assignment

## Context
Job application for **Web Research Engineer** position at Tavily - building search engine for AI agents.

## Assignment Overview
Create a scraping automation and analysis system for ~10,000 URLs (mix of static and JS-heavy sites) with focus on the three core trade-offs: **latency, accuracy, and cost**.

## Key Requirements

### Technical Deliverables
1. **Python/Colab Notebook**
   - Implement at least 2 scraping approaches:
     - Lightweight fetch (for static content)
     - JS-enabled browser automation (for dynamic sites)
   - Benchmark and visualize: latency, failures, content length
   - Include flowchart showing code flow
   - Link to GitHub repository

2. **One-pager PDF**
   - Approach and trade-offs
   - Key findings and insights
   - Limitations and challenges

### Constraints
- Respect robots.txt and site terms
- **Do NOT bypass CAPTCHAs** - detect and record them
- Support multilingual pages
- Clear documentation (comments, headings, plots)

### Evaluation Criteria
1. **Reliability**: scrape success rates, error handling
2. **Engineering Choices**: code structure, clarity, scalability
3. **Insights**: quality of analysis, plots, commentary
4. **Feasibility**: realistic production trade-offs (speed vs. cost)

## Provided Resources
- `urls.csv` - ~10,000 URLs (static + dynamic sites: Google, Bing, realtor sites, etc.)
- `proxy.json` - proxy credentials for scraping
  - Provider: network.joinmassive.com
  - Supports: HTTP, HTTPS, SOCKS5

## Timeline
**7 days** from assignment receipt

## Success Metrics
- High scrape success rate across diverse site types
- Clear performance benchmarks (latency distribution)
- Robust error handling and failure categorization
- Production-ready code structure
- Insightful analysis with actionable recommendations

## Technical Challenges to Address
1. Dynamic JS-heavy sites (Google, Bing, etc.)
2. CAPTCHA detection (not bypass)
3. Anti-bot detection mechanisms
4. Multilingual content handling
5. Balancing speed vs. accuracy vs. cost
6. Proxy integration and rotation
7. Concurrent/distributed scraping at scale
