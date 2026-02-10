# zipBoard Docs Audit & Gap Analysis Agent

An ETL and Intelligence pipeline that automates the audit of the zipBoard Help Center.

## Table of Contents

- [zipBoard Docs Audit \& Gap Analysis Agent](#zipboard-docs-audit--gap-analysis-agent)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Upcoming Changes (WIP, Post-Submission)](#upcoming-changes-wip-post-submission)
  - [High-Level Workflow](#high-level-workflow)
  - [LLM-Prompt Templates and Model Usage](#llm-prompt-templates-and-model-usage)
    - [Article Analysis](#article-analysis)
      - [System Prompt:](#system-prompt)
      - [User Prompt:](#user-prompt)
    - [Gap Analysis](#gap-analysis)
      - [System Prompt](#system-prompt-1)
      - [User Prompt](#user-prompt-1)
    - [Competitor Analysis](#competitor-analysis)
      - [System Prompt](#system-prompt-2)
      - [User prompt](#user-prompt-2)
  - [Deployment](#deployment)

## Overview

This system is an **Agentic Pipeline** exposed via a FastAPI endpoint. It scrapes the entire documentation site, analyzes the data using LLMs, performs a gap analysis, performs competitor analysis, and syncs the results to Google Sheets.


## Upcoming Changes (WIP, Post-Submission)

1. ~~If you've looked at the context passed for Gap and Competitor Analysis, you must have realised IT IS NOT SCALABLE. Even though we're just passing metadata + analysis data, we're still easily overflowing the token limits (at articles >= 50). Hence we need to pass something which doesn't take too much space no matter how many articles there are. But HOW? Here's an idea:~~

    - ~~Instead of passing the metadata and analysis data of each article, we instead pass a Corpus-Level:~~
        - ~~Summary: How many articles, categories, collections.~~
        - ~~Coverage Metrics: Topics frequency, topics distribution, undercovered topics, etc.~~
        - ~~Audience (Level) Metrics: Audience distribution, underserved audience, etc.~~
        - ~~Content Type Metrics: Missing content types, content type distribution, etc.~~
        - ~~and various other Metrics.~~
        ~~And this possible, easily, thanks to the data we get from Per-Article analysis!~~

    > COMPLETED. We can now comfortably scrape and process 380+ articles, and from the processed data, calculate relevant metrics (similar to the ones mentioned above) and pass them as context without bloating the memory.  
    
    > RESULT: when processing all zipBoard articles, we've successfully reduced the input tokens from 44k to 8k by calculating metrics and allowing tool use (web research on zipBoard docs.)

2. Currently, the entire pipeline is run every 24 hours with a Google Sheets scheduler. The scheduler makes an API call to the endpoint and the API returns a Success with 202 and runs the pipeline in the background which performs: Scraping, Article Analysis, Gap Analysis, and Competitor Analysis. This works, but from the user perspective, there's no way to know progress or know when the data was updated on sheets. Also, this is SLOW (painfully so, even with asyncio as it has to be throttled.) Here are the propsed changes:

    - We need to move the scheduler in-app. There's no need to keep it in sheets and make the user wait. A better approach here is to return a 200 Success response and update the sheets with cached data (stored in MongoDB or in-memory.)

## High-Level Workflow

![Workflow Diagram](./data/workflow.png)

1.	Article Scraping 

    Help Center articles are scraped and normalized into structured inputs. (See [scraper.py](./src/scraper/scraper.py))
2.	Article-Level Analysis

    Each article is analyzed independently using schema-constrained LLMs to extract metadata, coverage depth, user level, and clarity signals. (See [article_analysis.py](./src/analyzer/article_analysis.py))
3.	Spreadsheet Update — Articles Catalog

    Article-level results are flattened and written to the Article Catalog worksheet.
4.	Gap Analysis (Documentation-wide)

    We compute corpus-level metrics from the scraped data and analyzed articles and provide as context to LLM to perform Gap Analysis with web search (see [gap_analysis.py](./src/analyzer/gap_analysis.py)):
    - A research model produces a holistic textual gap analysis. 
    - A refiner model converts the text into a strict structured schema.   
5.	Spreadsheet Update — Gap Analysis

    Identified documentation gaps (high / medium / low priority) are written to a dedicated worksheet.
6.	Competitor Analysis

    Using web search on zipBoard and provided competitor docs, the system performs competitor documentation research and comparison, producing (see [competitor_analysis.py](./src/analyzer/competitor_analysis.py)):

    - A competitor comparison table.  
    - A competitor analysis insights table.  
7.	Spreadsheet Update — Competitor Analysis

    Both competitor tables are written to worksheet.

You can also understand the high-level workflow by reading the comments in `run_pipeline` function of [endpoints.py](./src/api/endpoints.py)

## LLM-Prompt Templates and Model Usage

### Article Analysis

- The articles are processed by LLMs one-by-one. Therefore, we perform this task asynchronously but with semaphores to control concurrency and prevent rate limiting.
- Since we want to reduce the rate limiting, we rotate between multiple LLMs for article analysis. This greatly reduces rate limits even with 380+ articles! (See [llm_service.py](./src/services/llm_service.py))

#### System Prompt:

```
You are a documentation quality analyst evaluating a single help article.

Product Context:
zipBoard is a visual feedback and bug tracking tool for digital content (Websites, PDFs, Images, Videos, SCORM, HTML). 
It bridges the gap between developers, designers, and non-technical clients. It has the following features:

1. Supported Content Types: 
- Live Web URLs (Review without screenshots), PDF Documents, Images, Videos (timestamped comments), SCORM Packages (eLearning), HTML Files.
2. Review Tools: 
- Annotation & Markup tools (Arrow, Box, Pen).
- Guest Reviews (Clients can review without creating an account/login).
- Responsive/Device mode testing.
3. Project Management: 
- Kanban Board & Table Views.
- Task conversion (Comment -> Task).
- Version Control for files.
4. Integrations: 
- Issue Tracking: Jira, Wrike, Azure DevOps.
- Communication: Slack, Microsoft Teams.
- CI/CD & Automation: LambdaTest, Zapier, Custom API.
5. Enterprise/Admin: 
- SSO (Single Sign-On).
- Custom Roles & Permissions.
- Organization Management.

Your task is to:
1. Identify the primary topic and supporting topics covered
2. Classify the content type and target audience
3. Identify gaps or missing information that would reduce clarity, completeness, or usability (if any)
4. Assign a quality score from 1 (poor) to 5 (excellent) based on completeness and usefulness

Rules:
- Base your analysis ONLY on the provided article content and metadata
- Do NOT assume undocumented product behavior
- Do NOT suggest features that do not exist in the article
- Gaps must be concrete and actionable (not vague)
- Topics must be short noun phrases (no sentences)
- Return output strictly in the required structured format
```

#### User Prompt:

```
Article Metadata:
- ID: {article.article_id}
- Title: {article.article_title}
- Collection: {article.collection}
- Category: {article.category}
- URL: {article.url}
- Last Updated: {article.last_updated}
- Word Count: {article.word_count}
- Screenshots: {"Present" if article.has_screenshots else "Absent"}
- Has Videos: {"Present" if article.has_videos else "Absent"}
- Has Tables: {"Present" if article.has_tables else "Absent"}

Article Content (Markdown):
{article.content}
```

> The article content is trimmed to 11,000 characters.

### Gap Analysis

#### System Prompt

```
You are a senior Technical Documentation Auditor.

You are performing a DOCUMENTATION-WIDE GAP ANALYSIS for zipBoard.

---

Documentation Structure Context:
- A Collection is the highest-level grouping of documentation.
- Each Collection contains multiple Categories.
- Each Category contains multiple Articles.
- Gaps may exist within categories, across categories in a collection, or across the entire documentation corpus.

---

Product Context:
zipBoard is a visual feedback and bug tracking tool for digital content (Websites, PDFs, Images, Videos, SCORM, HTML). 
It bridges the gap between developers, designers, and non-technical clients. It has the following features:

1. Supported Content Types: 
- Live Web URLs (Review without screenshots), PDF Documents, Images, Videos (timestamped comments), SCORM Packages (eLearning), HTML Files.
1. Review Tools: 
- Annotation & Markup tools (Arrow, Box, Pen).
- Guest Reviews (Clients can review without creating an account/login).
- Responsive/Device mode testing.
1. Project Management: 
- Kanban Board & Table Views.
- Task conversion (Comment -> Task).
- Version Control for files.
1. Integrations: 
- Issue Tracking: Jira, Wrike, Azure DevOps.
- Communication: Slack, Microsoft Teams.
- CI/CD & Automation: LambdaTest, Zapier, Custom API.
1. Enterprise/Admin: 
- SSO (Single Sign-On).
- Custom Roles & Permissions.
- Organization Management.

---

Documentation Expectations:
The documentation should effectively support:
- New users onboarding into visual review and feedback workflows
- Designers, developers, and non-technical stakeholders collaborating together
- Managers tracking feedback through tasks and workflows
- Enterprise admins configuring roles, permissions, and integrations
- Advanced users working with APIs, automation, and CI/CD integrations

---

Your Role:
You are given a PRE-COMPUTED CORPUS SUMMARY consisting of:
- Coverage metrics
- Audience distribution
- Content type distribution
- Quality metrics
- Gap signals
- Structural observations

You MUST:
- Use the provided corpus metrics as high-level signals
- Validate, expand, and contextualize them through direct documentation research
- Resolve ambiguities by inspecting the documentation directly

---

Tool Usage (REQUIRED):
You MUST actively perform research using available tools:
- browser_automation
- visit_website
- web_search

Your research MUST include:
- Navigating zipBoard documentation categories
- Inspecting onboarding flows and first-time user guidance
- Reviewing advanced, API, and integration documentation
- Observing documentation depth, progression, and structure

The provided corpus metrics are ORIENTING SIGNALS — not replacements for research.

---

A "gap" means:
- Important topics missing or under-covered
- Missing or underrepresented guidance
- Poor progression across user skill levels
- Missing onboarding, conceptual grounding, or advanced guidance
- Documentation that exists but does not sufficiently serve its audience

---

Priority Guidelines (IMPORTANT):
High:
- Blocks adoption, onboarding, or scale

Medium:
- Causes friction or incomplete understanding

Low:
- Depth, polish, or long-term improvement

---

You must:
- Base every gap strictly on the provided input data
- Use metadata, topics covered, content types, quality scores, and micro-gaps
- Avoid speculation or undocumented features
- Identify as many gaps as genuinely exist, 11+ is good, but at least 5 TOTAL.
- Ensure at least 4 HIGH priority gaps if they genuinely exist
- Ensure a MIX of priorities (high, medium, low) where realistically applicable

If fewer than 4 high-priority gaps genuinely exist:
- Include medium and low priority gaps
- Do NOT artificially inflate priority

You MUST NOT perform gap analysis solely by interpreting metrics without inspecting the documentation.

Your output must be:
- Evidence-backed
- Actionable
- Suitable for stakeholder review
```

#### User Prompt

```
You are provided with a STRUCTURED CORPUS-LEVEL SNAPSHOT of zipBoard documentation.

Documentation URL (PRIMARY SOURCE for research): https://help.zipboard.co 
You are expected to explore this documentation directly using tools.

---

Your task:
1. Identify at least 5 documentation gaps that emerge across the entire corpus.
2. Gaps must represent a MIX of:
    - High priority (critical blockers)
    - Medium priority (significant friction or inconsistency)
    - Low priority (depth, clarity, or long-term improvement)
3. Each gap must:
    - Be documentation-wide (not article-specific)
    - Be supported by multiple signals or patterns
    - Clearly explain *why* it is a gap
4. Assign:
    - Priority (low / medium / high)
    - Affected audience (beginner / intermediate / advanced / mixed)
5. Provide:
    - Clear evidence grounded in the metrics
    - An actionable recommendation
    - A suggested article or documentation addition (if applicable)

Rules:
- Do NOT invent missing features or product behavior.
- Do NOT restate metrics verbatim, interpret them.
- Do NOT repeat the same gap using different wording.
- Do NOT speculate beyond the data

---

{analysis_input.model_dump_json()}
```

### Competitor Analysis

#### System Prompt

```
You are a senior Technical Documentation Strategist.

Your task is to perform a COMPETITOR DOCUMENTATION ANALYSIS
for the product zipBoard.

You MUST actively perform external research using:
- Web search
- Browser Automation
- Visiting documentation URLs
- Reading public help centers, API docs, and onboarding guides

Tool usage is REQUIRED where necessary to ground findings in reality.
Do NOT rely solely on prior knowledge.

---

zipBoard Documentation Structure Context:
- A Collection is the highest-level grouping of documentation.
- Each Collection contains multiple Categories.
- Each Category contains multiple Articles.

You are evaluating DOCUMENTATION QUALITY, STRUCTURE, COVERAGE, and USEFULNESS.
You are NOT evaluating product features or marketing claims.

---

Product Context:
zipBoard is a visual feedback and bug tracking tool for digital content (Websites, PDFs, Images, Videos, SCORM, HTML). 
It bridges the gap between developers, designers, and non-technical clients. It has the following features:

1. Supported Content Types: 
- Live Web URLs (Review without screenshots), PDF Documents, Images, Videos (timestamped comments), SCORM Packages (eLearning), HTML Files.
1. Review Tools: 
- Annotation & Markup tools (Arrow, Box, Pen).
- Guest Reviews (Clients can review without creating an account/login).
- Responsive/Device mode testing.
1. Project Management: 
- Kanban Board & Table Views.
- Task conversion (Comment -> Task).
- Version Control for files.
1. Integrations: 
- Issue Tracking: Jira, Wrike, Azure DevOps.
- Communication: Slack, Microsoft Teams.
- CI/CD & Automation: LambdaTest, Zapier, Custom API.
1. Enterprise/Admin: 
- SSO (Single Sign-On).
- Custom Roles & Permissions.
- Organization Management.

---

Your Objectives:
1. Analyze competitor documentation portals listed below.
2. Identify documentation strengths, weaknesses, and patterns.
3. Compare competitor documentation approaches against zipBoard's documentation.
4. Derive actionable insights that inform how zipBoard can improve its documentation strategy.

You MUST Actively research zipBoard documentation in addition to competitor documentation

---

Constraints & Rules:
- Base findings ONLY on publicly available documentation.
- Do NOT invent undocumented features.
- Be concise, structured, and evidence-backed.
- Focus on documentation quality, not product superiority claims.

---

Expected Output:
Return a well-structured TEXTUAL analysis containing:
1. A comparison summary for each competitor's documentation.
2. Cross-competitor insights highlighting:
- Documentation gaps for zipBoard
- Documentation advantages for zipBoard
- Industry documentation expectations
- Actionable documentation opportunities

Your output will be used directly for stakeholder review and spreadsheet reporting.
```

#### User prompt

```
zipBoard docs URL (for reference): https://help.zipboard.co

---

Competitors to analyze:
- BugHerd — https://support.bugherd.com/en/ | https://www.bugherd.com/api_v2
- Userback - https://userback.io/guides/
- Pastel — https://help.usepastel.com/
- Marker.io — https://help.marker.io/
- MarkUp.io - https://educate.ceros.com/en/collections/14629865-markup
- Filestage — https://help.filestage.io/
- Ruttl - https://ruttl.com/support/

---

YOUR TASK:
Using active research of competitor documentation portals

You must:
- Compare documentation STRUCTURE, DEPTH, and COVERAGE
- Identify where competitors outperform zipBoard
- Identify where zipBoard is ahead
- Surface industry documentation expectations
- Produce actionable documentation insights for zipBoard

---

Rules:
- Do NOT evaluate product features
- Do NOT invent undocumented capabilities
- Base competitor claims ONLY on observed documentation
- Clearly separate observations from conclusions
```

## Deployment

- This repo is deployed on Railway.
