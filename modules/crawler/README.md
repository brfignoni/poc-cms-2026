# Website Crawler & Migration Checklist

## Requirements

- Python 3.8+
- That's it. No Node.js, no npm.

---

## Setup

```bash
pip install playwright beautifulsoup4
playwright install chromium
```

---

## Usage

```bash
python crawl_site.py
```

- Production Run: Maps out the site hierarchy matching the configured page limits.
- Test Run: Execute `python crawl_site.py --test` to cap the crawler at a maximum of 20 discovered pages for fast validation.
- Target: The crawler scans `https://www.genexus.com/en/` by default and filters out non-English paths (e.g., paths starting with `/es/` or `/pt/`).

---

## Output

All files are saved in a `crawl_output/` folder created next to the script:

| File             | Description                                       |
| ---------------- | ------------------------------------------------- |
| `checklist.html` | Interactive migration checklist (open in browser) |
| `screenshots/`   | PNG screenshot of the top viewport of every page  |
| `pages.json`     | Raw hierarchical crawl data                       |

---

## Using the Checklist

Open `crawl_output/checklist.html` in any browser.

- **Automatic Persistent Progress:** Progress is immediately synchronized to your browser's local storage (`localStorage`). Checking boxes, toggling priority stars, or writing custom row annotations will not be lost if you refresh the page.
- **Shift + Click Cascading:** Holding Shift while clicking a parent node's migration checkbox will automatically check or uncheck all of its direct children simultaneously, without bleeding into deeper nested branches.
- **Branch Filtering:** Use the toolbar controls to isolate active workloads or clean up your tree views by entirely hiding nodes marked as "Ignore".
- **Subtree Ignore:** Use the "Ignore Branch" shortcut to flag an entire nested tree layout at once.
- **Click a Thumbnail:** Click any image preview to launch a high-resolution lightbox overlay of the viewport screenshot.
- **Export Progress:** Saves your current tracking states along with an explicit snapshot timestamp into a transportable `migration_progress.json` payload.
- **Import Progress:** Ingests external progress state JSON structures to instantly overlay team validation work onto your checklist view.

---

## Notes

- **Domain-Restricted Crawling:** The crawler stays within the same target domain and will not follow external links.
- **Large Crawl Capacity:** Capped at 50,000 pages by default to allow deep sitewide architecture mapping. Edit `MAX_PAGES` in the script to change this limit.
- **Parallel Processing:** Runs 5 pages in parallel by default (`CONCURRENCY = 5`) to improve execution speed without unnecessarily triggering target infrastructure firewall rate limits.
- **Data Clearance Protection:** Clicking **"Clear Browser Data"** automatically downloads a backup `.json` file before wiping local browser data keys, helping prevent accidental progress loss.
