# EMCIP User Guide
## Emerging Markets Content Intelligence Platform

**Version**: 2.0  
**Last Updated**: December 2025 (Phase 16: Seed Discovery)

---

## Table of Contents

1. [What is EMCIP?](#what-is-emcip)
2. [Getting Started](#getting-started)
3. [The Dashboard](#the-dashboard)
4. [Managing News Sources](#managing-news-sources)
5. [Working with Seeds (URLs)](#working-with-seeds)
6. [Discovering New Seeds](#discovering-new-seeds)
7. [Reviewing Discovered Seeds](#reviewing-discovered-seeds)
8. [Running Crawls](#running-crawls)
9. [Viewing & Managing Articles](#viewing-and-managing-articles)
10. [Finding Content Opportunities](#finding-content-opportunities)
11. [Creating Content Drafts](#creating-content-drafts)
12. [Scheduling Automatic Crawls](#scheduling-automatic-crawls)
13. [Understanding Scores](#understanding-scores)
14. [Common Tasks & Workflows](#common-tasks-and-workflows)
15. [Troubleshooting](#troubleshooting)
16. [Glossary](#glossary)

---

## What is EMCIP?

EMCIP is a content intelligence platform designed to help you:

- **Collect** news and articles from websites focused on emerging markets
- **Analyze** articles for relevance, quality, and importance
- **Discover** content opportunities based on trending topics and coverage gaps
- **Generate** draft content using AI to synthesize multiple sources

Think of it as your research assistant that never sleeps—it continuously monitors news sources, scores articles by importance, and helps you create content based on what it finds.

### Who Should Use This Guide?

This guide is for content managers, editors, and analysts who need to:
- Monitor emerging market news across multiple sources
- Identify important stories and trends
- Create reports, newsletters, or articles based on curated sources

No technical knowledge is required to use EMCIP effectively.

---

## Getting Started

### Logging In

1. Open your web browser and go to your EMCIP URL (provided by your administrator)
2. Enter your username and password
3. Click **Log In**

### First-Time Setup Checklist

Before you can start collecting articles, you need to:

| Step | What to Do | Why It Matters |
|------|------------|----------------|
| 1 | Add at least one **Source** | Sources are the websites EMCIP will monitor |
| 2 | Add **Seed URLs** to your sources | Seeds tell EMCIP which specific pages to check |
| 3 | Run your first **Crawl** | This collects articles from your sources |
| 4 | Review collected **Articles** | See what EMCIP found and how it scored them |

---

## The Dashboard

When you log in, you'll see the Dashboard—your command center for EMCIP.

### Dashboard Sections

#### 📊 Stats Cards (Top Row)
Quick numbers showing:
- **Total Sources**: How many websites you're monitoring
- **Total Articles**: How many articles have been collected
- **Articles Today**: New articles collected in the last 24 hours
- **Avg. Score**: Average quality score across all articles

#### 📈 Recent Activity
Shows the latest actions in the system:
- Recent crawl runs and their status
- Newly collected articles
- Any errors that need attention

#### 💚 System Health
Indicates whether all system components are working properly:
- **Green**: Everything is running normally
- **Yellow**: Some components need attention
- **Red**: Critical issues that need immediate attention

---

## Managing News Sources

Sources are the websites EMCIP monitors for articles. Each source represents one publication or news outlet.

### Viewing Your Sources

1. Click **Sources** in the navigation menu
2. You'll see a list of all your sources with:
   - Name and website URL
   - Status (Active, Paused, or Error)
   - Reputation score
   - Last crawl date
   - Number of articles collected

### Adding a New Source

1. Click the **+ Add Source** button
2. Fill in the required information:

| Field | Description | Example |
|-------|-------------|---------|
| **Name** | A friendly name for the source | "Reuters Africa" |
| **URL** | The main website address | "https://www.reuters.com/world/africa/" |
| **Region** | Primary geographic focus | "Africa" |
| **Source Type** | Type of publication | "News Agency" |

3. Click **Save**

### Source Status Explained

| Status | Meaning | What to Do |
|--------|---------|------------|
| 🟢 **Active** | Working normally | Nothing needed |
| 🟡 **Paused** | Temporarily stopped | Resume when ready |
| 🔴 **Error** | Something went wrong | Check the error message and fix |
| ⚪ **Pending** | Not yet tested | Run a test crawl |

### Testing a Source

Before relying on a source, test it to make sure it works:

1. Find the source in your list
2. Click the **⋮** menu (three dots)
3. Select **Test Connection**
4. Wait for results showing:
   - Whether the site is reachable
   - How many links were found
   - Sample content preview

---

## Working with Seeds

Seeds are specific URLs within a source that EMCIP should check for new articles. Think of them as "starting points" for finding content.

### Why Seeds Matter

A source like "Reuters" has thousands of pages. Seeds tell EMCIP exactly where to look:
- A news category page: `reuters.com/world/africa/`
- An RSS feed: `reuters.com/rss/world-news/`
- A topic page: `reuters.com/business/energy/`

### Viewing Seeds

1. Click **Seeds** in the navigation menu
2. You'll see all seeds organized by source
3. Each seed shows:
   - The URL
   - Status (Active, Inactive, Error)
   - How many articles it has yielded
   - Last time it was checked

### Adding Seeds

#### Add One at a Time

1. Click **+ Add Seed**
2. Enter the URL
3. Select the source it belongs to
4. Choose a category (optional)
5. Click **Save**

#### Bulk Import (Multiple Seeds)

1. Click **Import Seeds**
2. Paste URLs (one per line) into the text box:
   ```
   https://example.com/category/energy/
   https://example.com/category/finance/
   https://example.com/rss/latest.xml
   ```
3. Select the source for all these seeds
4. Click **Import**

#### Import Options

| Option | Description |
|--------|-------------|
| **Skip** (default) | Skip URLs that already exist |
| **Update** | Merge new data into existing seeds |
| **Replace** | Completely overwrite existing seeds |

#### Updating Existing Seeds

When using **Update** mode, you can choose which fields to merge:

| Field | Merge Behavior |
|-------|----------------|
| **Tags** | New tags are added (duplicates removed) |
| **Notes** | New notes are appended with timestamp |
| **Confidence** | Updated to new value |
| **Seed Type** | Updated to new value |
| **Country/Regions** | Updated to new value |
| **Topics** | Updated to new value |

The import results show exactly what changed with before/after values.

### Seed Types

| Type | Best For | Example |
|------|----------|---------|
| **Category Page** | Topic-specific news | `/world/africa/business/` |
| **RSS Feed** | Automatic updates | `/feed/rss.xml` |
| **Homepage** | Breaking news | `/` (front page) |
| **Search Results** | Specific keywords | `/search?q=infrastructure` |

### Discovering New Seeds

EMCIP can help find seeds automatically:

1. Select a source
2. Click **Discover Entry Points**
3. EMCIP will scan the website for:
   - RSS feeds
   - Sitemap files
   - Category pages
   - Archive pages
4. Review the suggestions and add the ones you want

---

## Discovering New Seeds

EMCIP includes an automated discovery system that finds potential seed URLs based on topics and regions you specify. This is more powerful than the simple "Discover Entry Points" feature—it actively searches the web for new sources.

### What is Seed Discovery?

Seed Discovery uses multiple channels to find URLs that might be valuable sources:

| Channel | What It Finds |
|---------|---------------|
| **Web Search** | Websites matching your topic + region |
| **RSS Feeds** | News feeds and content syndication |
| **Directories** | Industry listings and member directories |
| **Sitemaps** | Structured page listings from websites |

### Starting a Discovery Run

1. Go to **Seeds** → **Review Queue**
2. Click **+ New Discovery**
3. Fill in the discovery brief:

| Field | Description | Example |
|-------|-------------|---------||
| **Theme** | Main topic to search for | "logistics companies" |
| **Geography** | Countries or regions | "Vietnam, Thailand" |
| **Entity Types** | Types of organizations | "freight forwarder, 3PL" |
| **Keywords** | Additional search terms | "cargo, shipping, port" |

4. Click **Start Discovery**

### Discovery Run Status

Each discovery creates a "run" that you can track:

| Status | Meaning |
|--------|---------|
| 🔵 **Running** | Discovery is in progress |
| 🟢 **Completed** | Finished successfully |
| 🔴 **Failed** | Something went wrong |

### What Happens During Discovery?

1. **Query Generation**: EMCIP creates search queries from your brief
2. **URL Collection**: Multiple channels are searched for matching URLs
3. **Capture**: Each URL is fetched and saved for review
4. **Classification**: Pages are analyzed for type and relevance
5. **Scoring**: Each candidate receives a quality score
6. **Review Queue**: Candidates appear for your approval

### Discovery Results

After a discovery run completes, you'll see:

- **Queries Generated**: How many search variations were tried
- **URLs Discovered**: Total URLs found
- **Captures Created**: Pages successfully fetched
- **Seeds Created**: New candidates in review queue

---

## Reviewing Discovered Seeds

Discovered seeds go into a review queue where you can approve or reject them before they become active.

### Accessing the Review Queue

1. Click **Seeds** in the navigation
2. Click **Review Queue** tab
3. You'll see pending seeds sorted by score

### Understanding Seed Scores

Each discovered seed has four score dimensions:

| Score | What It Measures |
|-------|------------------|
| **Relevance** (35%) | How well it matches your topic |
| **Utility** (25%) | How useful for scraping |
| **Freshness** (20%) | How active/updated the site is |
| **Authority** (20%) | Reputation and trustworthiness |

The **Overall Score** (0-100) combines these with weights shown above.

### Review Queue Actions

#### For Individual Seeds

| Action | What It Does |
|--------|---------------|
| **Approve** | Accept the seed for crawling |
| **Reject** | Dismiss the seed |
| **Preview** | View the captured page content |
| **Add Notes** | Record why you approved/rejected |

#### Bulk Actions

To review multiple seeds at once:

1. Check the boxes next to seeds
2. Click **Bulk Actions**
3. Choose:
   - **Approve Selected** - Accept all checked
   - **Reject Selected** - Dismiss all checked

### Reviewing Captured Content

Click **Preview** on any seed to see:

- The original page as it was captured
- HTTP status and response headers
- Content type and size
- When the page was fetched

This lets you verify the page is what you expected without visiting the live site.

### Seed Review Workflow

| Status | Meaning | Next Steps |
|--------|---------|------------|
| **Pending** | Awaiting review | Approve or reject |
| **Reviewed** | Looked at, not decided | Make final decision |
| **Approved** | Accepted for use | Will be crawled |
| **Rejected** | Not suitable | No further action |

### Tips for Efficient Review

1. **Sort by Score**: Review highest-scoring seeds first
2. **Filter by Run**: Focus on one discovery run at a time
3. **Use Bulk Actions**: Quickly reject obvious mismatches
4. **Check Preview**: Verify content before approving
5. **Add Notes**: Document your reasoning for future reference

---

## Running Crawls

A "crawl" is when EMCIP visits your sources and collects new articles.

### Starting a Crawl Manually

#### Crawl One Source

1. Go to **Sources**
2. Find the source you want to crawl
3. Click **⋮** → **Crawl Now**
4. The system will start collecting articles

#### Crawl All Sources

1. Go to **Runs**
2. Click **Start Full Crawl**
3. All active sources will be crawled

### Understanding Crawl Runs

Each crawl creates a "Run" record. View runs to see:

| Column | Meaning |
|--------|---------|
| **Started** | When the crawl began |
| **Status** | Running, Completed, or Failed |
| **Source(s)** | Which source(s) were crawled |
| **Articles Found** | New articles collected |
| **Duration** | How long the crawl took |

### Run Status Explained

| Status | Meaning |
|--------|---------|
| 🔵 **Running** | Crawl is in progress |
| 🟢 **Completed** | Finished successfully |
| 🟡 **Partial** | Finished with some errors |
| 🔴 **Failed** | Could not complete |

### What Happens During a Crawl?

1. **Visit Seeds**: EMCIP goes to each seed URL
2. **Find Articles**: Identifies links to individual articles
3. **Extract Content**: Reads and saves article text
4. **Translate**: Converts non-English articles to English
5. **Score**: Rates each article for relevance and quality
6. **Store**: Saves everything for your review

---

## Viewing and Managing Articles

Articles are the individual news stories collected from your sources.

### Browsing Articles

1. Click **Articles** in the navigation
2. You'll see a list of all collected articles
3. Each row shows:
   - Title (click to view full article)
   - Source
   - Score (0-100)
   - Region and Topic
   - Date collected

### Filtering Articles

Use filters to find specific articles:

| Filter | What It Does | Example |
|--------|--------------|---------|
| **Search** | Find keywords in titles | "infrastructure" |
| **Source** | Show one source only | Reuters only |
| **Region** | Geographic focus | Africa, Asia |
| **Topic** | Subject matter | Energy, Finance |
| **Score** | Quality threshold | 70+ only |
| **Date Range** | Time period | Last 7 days |

### Understanding Article Scores

Each article receives a score from 0-100 based on:

| Score Range | Quality Level | Meaning |
|-------------|---------------|---------|
| **80-100** | ⭐ Excellent | High-priority, must-read content |
| **60-79** | 👍 Good | Solid, relevant content |
| **40-59** | 📝 Fair | May be useful for background |
| **0-39** | ⚪ Low | Probably not relevant |

### Article Actions

When viewing an article, you can:

| Action | What It Does |
|--------|--------------|
| **Mark as Used** | Tag articles you've included in content |
| **Mark as Ignored** | Hide articles you don't want to see |
| **Reprocess** | Re-analyze the article (if scoring seems wrong) |
| **View Original** | Open the source website |

### Exporting Articles

EMCIP supports two ways to export articles:

#### Quick Export (Small Sets)

For small exports (under 100 articles):

1. Apply your desired filters
2. Click **Export**
3. Choose format:
   - **CSV**: For spreadsheets (Excel, Google Sheets)
   - **JSON**: For other software systems
4. The file downloads immediately

#### Background Export (Large Sets)

For large exports, EMCIP generates files in the background:

1. Apply your desired filters
2. Click **Export** → **Create Export Job**
3. Choose format:
   - **CSV**: Spreadsheet format
   - **JSON**: Data format
   - **Markdown ZIP**: Individual markdown files in a ZIP archive
4. The export is queued and processed in the background
5. Check **Exports** page to see progress and download when ready

#### Managing Exports

View all your export jobs at **Articles** → **Exports**:

| Status | Meaning |
|--------|----------|
| **Queued** | Waiting to be processed |
| **Running** | Currently generating |
| **Completed** | Ready for download |
| **Failed** | Error occurred (see details) |

Completed exports show file size and row count. Click **Download** to get your file.

---

## Finding Content Opportunities

Content opportunities are suggestions for articles, reports, or stories you could create based on what EMCIP has collected.

### What Are Opportunities?

EMCIP analyzes your articles and suggests content ideas based on:

| Type | Description | Example |
|------|-------------|---------|
| **Trending** | Hot topics with multiple articles | "Renewable energy investment surge in Africa" |
| **Gap** | Underreported topics needing coverage | "Central Asia infrastructure developments" |
| **Deep Dive** | High-scoring articles worth expanding | "Detailed analysis of new port development" |
| **Comparison** | Similar stories across regions | "Energy policy: Africa vs. Southeast Asia" |
| **Follow-Up** | Developing stories with updates | "Update on Chinese investment in Kenya" |
| **Roundup** | Weekly/monthly summaries | "This week in emerging markets finance" |

### Generating Opportunities

1. Click **Content** → **Opportunities**
2. Click **Generate New Opportunities**
3. Optionally set filters:
   - Focus on specific topics
   - Focus on specific regions
   - Set minimum article score
4. Click **Generate**
5. Review the suggestions

### Opportunity Details

Each opportunity includes:

- **Headline**: A suggested title for the content
- **Angle**: The unique perspective or approach
- **Confidence Score**: How confident the system is (0-100%)
- **Source Articles**: The articles supporting this opportunity
- **Expiration**: When this opportunity may become stale

### Working with Opportunities

| Action | What It Does |
|--------|--------------|
| **Approve** | Mark as a content idea you want to pursue |
| **Reject** | Dismiss if not relevant |
| **Start Draft** | Begin writing content based on this opportunity |

### Viewing Trends and Gaps

To see what topics are trending or underreported:

1. Go to **Content** → **Opportunities**
2. Click **Trending Topics** to see:
   - Most-covered topics this week
   - Rising topics gaining coverage
3. Click **Coverage Stats** to see:
   - Topics with little coverage (gaps)
   - Regions with few articles

---

## Creating Content Drafts

EMCIP can generate draft content by synthesizing information from multiple articles.

### What Are Drafts?

Drafts are AI-generated content pieces that combine information from your collected articles. They're meant to be a starting point (about 75-85% complete) that you refine and publish.

### Content Types Available

| Type | Best For | Typical Length |
|------|----------|----------------|
| **Blog Post** | Website articles | 800 words |
| **Newsletter** | Email updates | 500 words |
| **Executive Summary** | Quick briefings | 300 words |
| **Research Brief** | Detailed analysis | 1,200 words |
| **Analysis** | In-depth pieces | 1,000 words |
| **Social Thread** | Twitter/LinkedIn | 280 words |

### Voice Options

Choose the writing style:

| Voice | Best For |
|-------|----------|
| **Professional** | Business audiences |
| **Executive** | C-suite briefings |
| **Journalistic** | News-style reporting |
| **Academic** | Research contexts |
| **Conversational** | Casual audiences |

### Creating a Draft

#### From an Opportunity

1. Find an approved opportunity
2. Click **Start Draft**
3. Choose content type and voice
4. Click **Generate**
5. Review and edit the result

#### From Selected Articles

1. Go to **Articles**
2. Check the boxes next to articles you want to use
3. Click **Create Draft**
4. Choose content type and voice
5. Click **Generate**

### Reviewing Your Draft

Each draft shows:

- **Title & Subtitle**: Suggested headlines
- **Content**: The main text (in Markdown format)
- **Key Points**: Bullet summary
- **Quality Score**: How well-structured the draft is
- **Originality Score**: How much is original vs. copied
- **Source Articles**: What articles were used

### Improving Drafts

#### Regenerate with Feedback

If the draft isn't quite right:

1. Click **Regenerate**
2. Describe what you want changed:
   - "Make the introduction more engaging"
   - "Add more statistics"
   - "Focus on the African perspective"
3. Click **Generate New Version**

#### Refine a Section

To fix just one part:

1. Click **Refine**
2. Specify which section (e.g., "Introduction")
3. Give instructions (e.g., "Make it shorter and punchier")
4. Click **Apply**

### Draft Status Workflow

| Status | Meaning | Next Steps |
|--------|---------|------------|
| 📝 **Draft** | Initial generation | Edit or regenerate |
| 👀 **Review** | Ready for review | Get approval |
| ✅ **Approved** | Approved for use | Publish or export |
| 📤 **Published** | Content has been used | Done! |

---

## Scheduling Automatic Crawls

Instead of running crawls manually, you can set up automatic schedules.

### Why Schedule Crawls?

- **Consistency**: New articles collected at regular intervals
- **Freshness**: Always have up-to-date content
- **Efficiency**: No need to remember to run crawls

### Creating a Schedule

1. Go to **Schedules**
2. Click **+ New Schedule**
3. Configure the schedule:

| Setting | Options | Example |
|---------|---------|---------|
| **Name** | A descriptive name | "Daily Morning Crawl" |
| **Source(s)** | All or specific sources | All sources |
| **Frequency** | How often to run | Every day |
| **Time** | When to run | 6:00 AM |

4. Click **Save**

### Frequency Options

| Type | Best For | Example |
|------|----------|---------|
| **Hourly** | Breaking news sources | Every 2 hours |
| **Daily** | Regular news sites | Once at 6 AM |
| **Weekly** | Weekly publications | Mondays at 8 AM |
| **Custom** | Specific needs | Mon/Wed/Fri at noon |

### Managing Schedules

| Action | How |
|--------|-----|
| **Pause** | Click the toggle to temporarily stop |
| **Edit** | Click the schedule name |
| **Delete** | Click ⋮ → Delete |
| **Run Now** | Click ⋮ → Run Immediately |

---

## Understanding Scores

EMCIP scores articles to help you identify the most important content quickly.

### How Scoring Works

Each article is analyzed for several factors:

| Factor | What It Measures | Weight |
|--------|------------------|--------|
| **Relevance** | How related to emerging markets | 30% |
| **Timeliness** | How recent and newsworthy | 20% |
| **Source Quality** | Reputation of the source | 20% |
| **Content Depth** | Amount of detail and data | 15% |
| **Uniqueness** | Not covered elsewhere | 15% |

### Score Breakdown

When viewing an article, click **Score Details** to see:

- Individual scores for each factor
- Detected topics and regions
- Key statistics or data points found
- Why the score was given

### Using Scores Effectively

| Goal | Filter Setting |
|------|----------------|
| Only top-tier content | Score ≥ 80 |
| Good content for newsletters | Score ≥ 60 |
| Everything potentially useful | Score ≥ 40 |
| See all content (including low quality) | No filter |

---

## Common Tasks & Workflows

### Daily Workflow

```
Morning Routine (15 minutes):
1. Check Dashboard for overnight activity
2. Review high-scoring articles (80+)
3. Star or save important pieces
4. Note any emerging trends

Midday Check (5 minutes):
1. Quick scan of new articles
2. Trigger manual crawl if needed

End of Day (10 minutes):
1. Review saved articles
2. Generate opportunities
3. Start drafts for tomorrow
```

### Creating a Newsletter

1. **Collect**: Filter articles from the past week, score 60+
2. **Select**: Choose 5-8 most important stories
3. **Generate**: Create a newsletter draft from selected articles
4. **Refine**: Edit the draft to match your voice
5. **Approve**: Mark as ready for publication

### Monitoring a Breaking Story

1. **Set up alerts**: Add seeds for the specific topic
2. **Run frequent crawls**: Every few hours
3. **Filter by topic**: Focus on relevant articles
4. **Track developments**: Note how scores change
5. **Create timeline**: Use articles to build story arc

### Weekly Content Planning

1. **Monday**: Review coverage stats and identify gaps
2. **Tuesday**: Generate opportunities for the week
3. **Wednesday**: Approve and prioritize opportunities
4. **Thursday**: Generate drafts for approved opportunities
5. **Friday**: Finalize and schedule content

---

## Troubleshooting

### Common Issues

#### "No articles found after crawl"

**Possible causes:**
- Seeds might be incorrect or outdated
- Website may have changed its structure
- Site may be blocking automated access

**Solutions:**
1. Test the source connection
2. Verify seed URLs are still valid
3. Try discovering new entry points

#### "Source shows Error status"

**Possible causes:**
- Website is down
- URL has changed
- Access is blocked

**Solutions:**
1. Check if you can visit the site in your browser
2. Update the source URL if it changed
3. Contact your administrator if blocked

#### "Articles have low scores"

**Possible causes:**
- Content isn't about emerging markets
- Source isn't a good fit
- Scoring needs adjustment

**Solutions:**
1. Review if the source is appropriate
2. Check the article topics are relevant
3. Consider removing irrelevant sources

#### "Draft quality is poor"

**Possible causes:**
- Source articles lack detail
- Too few articles selected
- Wrong content type chosen

**Solutions:**
1. Select more high-scoring articles (5-8)
2. Choose articles on the same topic
3. Try a different content type or voice

### Getting Help

If you encounter issues not covered here:

1. Check the system health on the Dashboard
2. Note any error messages
3. Contact your system administrator

---

## Glossary

| Term | Definition |
|------|------------|
| **Article** | A single news story or piece of content collected by EMCIP |
| **Capture** | A saved snapshot of a web page fetched during discovery |
| **Crawl** | The process of visiting websites and collecting articles |
| **Discovery** | Automated process of finding new potential seed URLs |
| **Discovery Run** | A single execution of the discovery process |
| **Draft** | AI-generated content based on collected articles |
| **Opportunity** | A suggested content idea based on article analysis |
| **Region** | Geographic area (e.g., Africa, Southeast Asia) |
| **Review Queue** | List of discovered seeds awaiting approval |
| **Run** | A single execution of a crawl job |
| **Score** | A 0-100 rating of article quality and relevance |
| **Seed** | A specific URL that EMCIP checks for new articles |
| **Source** | A publication or website that EMCIP monitors |
| **Topic** | Subject matter category (e.g., Energy, Finance) |

---

## API Reference (Summary)

This section summarizes key API endpoints for operators and integrators. For full technical details, see the separate API Documentation.

### Seeds API

#### Import Seeds
```
POST /api/seeds/import/
```

| Field | Type | Description |
|-------|------|-------------|
| `urls` | array | List of URLs to import |
| `format` | string | `urls`, `text`, or `csv` |
| `on_duplicate` | string | `skip` (default), `update`, or `error` |
| `update_fields` | array | Fields to update on duplicate: `tags`, `notes`, `confidence`, `seed_type`, `country`, `regions`, `topics` |
| `tags` | array | Tags to apply to all imported seeds |

**Response** includes:
- `created`: List of new seeds with IDs
- `updated`: Seeds that were merged (with `merged_fields` diff)
- `duplicates`: Skipped duplicates
- `errors`: Failed URLs with error messages

#### Validate Seed
```
POST /api/seeds/{id}/validate/
```

**Response** includes:
- `is_reachable`: URL responds with 2xx
- `is_crawlable`: robots.txt allows crawling
- `robots_unknown`: True if robots.txt could not be fetched (⚠️ warning)
- `has_articles`: Page contains article patterns
- `final_url`: After redirects
- `content_type`: Detected MIME type
- `detected`: Object with `type_hint`, `feed_urls`, `sitemap_url`
- `warnings`: Array of warning messages
- `is_promotable`: Whether seed can be promoted

#### Discover Entrypoints
```
POST /api/seeds/{id}/discover-entrypoints/
```

**Caps Applied** (configurable):
- Max links per page: 100
- Max total entrypoints: 50
- Max result entrypoints: 20
- Content size limit: 2MB
- Page timeout: 10s

**Response** includes `truncation_warnings` when caps are applied.

#### Test Crawl
```
POST /api/seeds/{id}/test-crawl/
```

**Caps Applied**:
- Max pages: 20
- Max articles: 10
- Same-domain enforcement for entrypoints

### Runs API

#### Start Run
```
POST /api/runs/
```

Alias for `/api/sources/runs/start/`. Returns 201 with:
- `run_id`: The created CrawlJob ID
- `task_id`: Celery task ID (if queued)
- `source_ids`: Sources included

#### Run Detail
```
GET /api/runs/{id}/
```

Includes aggregated `totals`:
- `articles_found`, `articles_new`, `articles_duplicate`
- `pages_crawled`
- `duration_seconds`

### Exports API

#### Create Export
```
POST /api/exports/
```

Returns **202 Accepted** with:
- `export_id`: Poll this for status
- `status`: Initially `queued`

#### Poll Export Status
```
GET /api/exports/{id}/
```

| Status | `download_url` |
|--------|----------------|
| `queued` | null |
| `running` | null |
| `completed` | Available |
| `failed` | null (check `error_message`) |

**TTL Cleanup**: Completed exports deleted after 30 days; failed after 7 days.

---

## Operational Runbooks

For incident response and troubleshooting, runbooks are available in `/docs/runbooks/`:

| Runbook | Use When |
|---------|----------|
| [RUNBOOK_STUCK_RUNS.md](runbooks/RUNBOOK_STUCK_RUNS.md) | Runs stuck in `running` or `pending` |
| [RUNBOOK_EXPORT_FAILURES.md](runbooks/RUNBOOK_EXPORT_FAILURES.md) | Export jobs failing or stuck |
| [RUNBOOK_PROBE_SSRF.md](runbooks/RUNBOOK_PROBE_SSRF.md) | SSRF blocks during validation/discovery |
| [PERMISSION_MATRIX.md](runbooks/PERMISSION_MATRIX.md) | Role permissions reference |

### Permission Matrix (Summary)

| Action | Admin | Operator | Viewer |
|--------|-------|----------|--------|
| View sources/seeds/articles | ✅ | ✅ | ✅ |
| Create/edit sources | ✅ | ✅ | ❌ |
| Delete sources | ✅ | ❌ | ❌ |
| Start/cancel runs | ✅ | ✅ | ❌ |
| Create exports | ✅ | ✅ | ❌ |
| Pause all schedules | ✅ | ❌ | ❌ |
| Promote seeds to sources | ✅ | ✅ | ❌ |
| Delete seeds | ✅ | ❌ | ❌ |

### Throttle Policies

| Endpoint Category | Rate Limit |
|-------------------|------------|
| Probe endpoints (validate, discover, test) | 10/min |
| Import endpoints | 5/min |
| Destructive actions (delete) | 20/min |
| State changes (start, cancel, promote) | 30/min |
| Export creation | 10/min |
| Burst (general) | 60/min |

---

## Quick Reference Card

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + /` | Open search |
| `Ctrl + N` | New item (context-dependent) |
| `Esc` | Close modal/dialog |

### Score Quick Guide

- **80+** = Must read ⭐
- **60-79** = Worth reviewing 👍
- **40-59** = Background info 📝
- **Below 40** = Probably skip ⚪

### Content Types

- **Newsletter** = Quick updates
- **Blog Post** = Standard articles
- **Executive Summary** = Brief overview
- **Analysis** = Deep dive

---

*For technical documentation and API reference, see the separate Technical Documentation.*
