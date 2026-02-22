# Music Industry Job Aggregation MVP (Beginner Friendly)

This project is **free to develop** and **free to use** under the **MIT License**.

It collects internship / assistant / coordinator style music-industry jobs from a YAML config, then writes:

- `output/jobs_latest.csv` (all currently known jobs after filtering)
- `output/jobs_new.csv` (only jobs newly discovered in this run)

It also saves dedupe state in `data/state.json`.

---

## What this MVP does

- Reads sources from `config/sources.yaml` (no code editing needed for normal source changes)
- Fetches pages with retries + timeout + User-Agent
- Parses with simple parser types:
  - `generic`
  - `bamboohr`
  - `workday` (best-effort)
  - `mbw`
  - `musicweek`
  - `page_only` (fallback when parsing is hard)
- Filters by broad keywords (role-level or domain-level)
- De-duplicates by URL first, then title+company fingerprint fallback
- Never crashes the full run because one source fails

---

## CSV format (fixed Chinese headers)

The exact header order is:

`Base国家, 公司, 岗位名称, Base城市, 发布时间, 职业渠道, 职位分类, 职位类型, 职位开始时间, 职位结束时间, 具体职责, 要求硬技能, 要求软技能, 链接, 联系方式`

---

## Step 1: Create a GitHub repository and upload files

1. Go to GitHub and click **New repository**.
2. Name it (for example: `music-job-scraper`).
3. Upload all files from this project (drag-and-drop in the GitHub web UI is okay).
4. Commit changes.

---

## Step 2: Edit sources (no code needed)

Open `config/sources.yaml`.

Each source block looks like this:

```yaml
- id: example_source
  name: Example Company
  channel: Company Website
  url: https://example.com/jobs
  parser_type: generic
  default_country: UK
  notes: optional
```

Supported `parser_type` values:

- `generic`
- `bamboohr`
- `workday`
- `mbw`
- `musicweek`
- `page_only`

To disable a source temporarily, comment it out with `#`.

### Advanced source filtering (v1.1)

In `config/sources.yaml`, each source can also define:

```yaml
include_patterns:
  - internship
  - assistant
exclude_patterns:
  - privacy
  - policy
fetch_detail: true
```

How it works:
- `exclude_patterns`: if any pattern appears in title or URL, the candidate is dropped.
- `include_patterns`: if present, at least one pattern must appear in title or URL.
- Matching is case-insensitive substring matching.
- There is also a built-in global exclude list for non-job pages (privacy/cookie/terms/legal/news/blog/article/etc).
- `fetch_detail: false` disables detail-page enrichment for that source.



---

## Step 3: Enable and use GitHub Actions

1. Open your GitHub repo.
2. Click **Actions** tab.
3. Enable workflows if prompted.
4. Open workflow **job-scraper**.
5. Click **Run workflow** for a manual run.
6. Scheduled runs happen at **Monday + Thursday, 09:00 UTC**.
7. After a run finishes, scroll to **Artifacts** and download `job-csv-output`.
8. Open CSV files with Excel / Google Sheets.

Screenshot guidance (no images included in this README):
- In Actions, take a screenshot of the successful workflow run page.
- Take a screenshot of the Artifacts panel showing `job-csv-output`.
- Optionally, take a screenshot of `config/sources.yaml` edits for your own notes.

---

## Step 4: Run locally (optional)

### Requirements
- Python 3.11+

### Commands

```bash
pip install -r requirements.txt
python src/main.py
```

Then check:
- `output/jobs_latest.csv`
- `output/jobs_new.csv`
- `data/state.json`

---

## Step 5: Troubleshooting

### 1) 403 forbidden
Possible reason:
- Website blocks bots.

What to do:
- Keep default User-Agent (already set).
- Reduce frequency.
- Switch that source to `page_only` so run stays stable.

### 2) Timeout / temporary network error
Possible reason:
- Site is down or slow.

What to do:
- Re-run later.
- Keep source enabled; retries are automatic.
- If detail fetches are too slow for one source, set `fetch_detail: false`.

### 3) HTML changed and parser stops finding jobs
Possible reason:
- Website redesigned.

What to do:
- Temporarily set `parser_type: page_only`.
- Add `exclude_patterns` to drop bad links (privacy/policy/etc).
- Narrow with `include_patterns` (for example `jobs`, `careers`, `intern`).
- Later improve parser in `src/parsers/`.

### 4) No rows in `jobs_new.csv`
Possible reason:
- No new jobs since last run.
- All URLs already seen in `data/state.json`.

What to do:
- This is normal.
- If you want a fresh start, backup then clear `data/state.json`.

---

## How to add a new website

1. Add a new entry in `config/sources.yaml`.
2. Choose parser type:
   - **Simple list of links** → `generic`
   - **ATS page** → try `bamboohr` or `workday`
   - **Hard / JS-heavy / blocked** → `page_only`
3. Commit the YAML change.
4. Run workflow manually and verify artifact CSV output.

---

## Notes about platform rules

- This MVP does **not** require login.
- It does **not** scrape LinkedIn groups or login-protected areas.
- If a source is unparseable, the run continues with warnings.

