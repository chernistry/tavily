Scraping Assignment
Purpose
Tavily’s purpose is to provide agents with the most relevant information from the web at speed. Our
system always balances among three trade-offs — latency, accuracy, and cost. In this assignment,
you’ll explore different ways of scraping and analyzing 'hard' dynamic URLs (Google, Bing, realtor
sites, etc.) while keeping these trade-offs in mind.
Your Task
You will create a scraping automation and analysis notebook that:
1. Scrapes ~1,000 provided URLs (mix of static and JS-heavy sites).
2. Handles dynamic rendering and CAPTCHAs where possible.
3. Produces clear statistics on performance, failures, and content size.
Deliverables
1. Python/Colab Notebook
a. Implement scraping with at least two approaches (lightweight fetch + JS-enabled browser).
b. Benchmark and visualize results (latency, failures, content length).
c. link to github repository - use flow chart to show your code flow.
2. One-pager PDF
a. Outline your approach, trade-offs, and findings.
b. Highlight limitations or challenges you faced.
Requirements
1. Respect robots.txt and site terms.
2. Do not attempt to bypass CAPTCHAs — instead, detect and record them.
3. Notebook must be easy to follow (comments, headings, plots).
4. Support multilingual pages without breaking.
Evaluation Criteria
You will be evaluated on:
1. Reliability: scrape success rates, error handling.
2. Engineering Choices: code structure, clarity, scalability.
3. Insights: quality of analysis, plots, and commentary.
4. Feasibility: realistic trade-offs for production (speed vs. cost).
What you receive
urls.txt — one URL per line.
assignment.pdf — requirements & deliverables.
proxy.json - proxy credentials for you to use.
Don’t forget to record your findings, and save statistics along the way, so you can present them in your
notebook.
Due date
1 week