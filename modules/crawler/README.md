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
python crawl_site.py https://yoursite.com
```

---

## Output

All files are saved in a `crawl_output/` folder created next to the script:

| File             | Description                                       |
| ---------------- | ------------------------------------------------- |
| `checklist.html` | Interactive migration checklist (open in browser) |
| `screenshots/`   | PNG screenshot of the top of every page           |
| `pages.json`     | Raw crawl data                                    |

---

## Using the Checklist

Open `crawl_output/checklist.html` in any browser.

- **Check off** pages as you migrate them — progress saves automatically in the browser
- **Click a thumbnail** to zoom into the screenshot
- **Expand / collapse** branches to focus on sections
- **Export progress** as JSON to back it up or share with teammates
- **Import progress** to restore a previously saved state

---

## Notes

- The crawler stays within the same domain — it won't follow external links
- Capped at **500 pages** by default (edit `MAX_PAGES` in the script to change)
- Runs **3 pages in parallel** by default (edit `CONCURRENCY` to change)
