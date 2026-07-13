"""
Research Agent — web research and structured report writing.

Specializes in:
  - Fetching data from URLs and APIs
  - Synthesizing information into reports
  - Writing findings to persistent files
  - Multi-source research with citations

This is the "fully private AI assistant" use case —
no data leaves your infrastructure, all sources are your choice.
"""

from typing import Any, Dict
from runtime.agent import BaseAgent
from runtime.logger import get_logger


class ResearchAgent(BaseAgent):
    name = "research_agent"
    description = "Agent that researches topics via HTTP and writes structured reports."

    def __init__(self, output_file: str = "research_report.md"):
        self.output_file = output_file
        self.logger = get_logger(self.name)

    def get_system_prompt(self) -> str:
        return f"""You are a research agent. You gather information and write structured reports.

## How to work

1. **Understand the research question.** What specifically needs to be answered?
2. **Identify sources.** What APIs, URLs, or endpoints have the data?
3. **Fetch systematically.** Use the http tool to retrieve data.
4. **Synthesize.** Process what you've gathered into clear findings.
5. **Write the report.** Use the file tool to write a structured Markdown report.
   - Save to: {self.output_file}
   - Include: summary, findings, sources, date

## Report format

```
# Research Report: [Topic]
Date: [today]

## Summary
[2-3 sentence overview]

## Findings
[Detailed findings with source citations]

## Sources
[List of URLs/APIs consulted]
```

## Important

- Cite your sources. Every claim should reference where it came from.
- If a request fails (HTTP error, timeout), note it and try an alternative.
- Prefer structured data (JSON APIs) over scraping HTML when possible.
- Write the report file before giving your final response.
"""

    def on_start(self, task: str, state: Dict) -> Dict:
        self.logger.info("research_started", topic=task[:100])
        return state

    def on_complete(self, result: str, state: Dict):
        self.logger.info(
            "research_complete",
            steps=state.get("step", 0),
            output_file=self.output_file,
        )
