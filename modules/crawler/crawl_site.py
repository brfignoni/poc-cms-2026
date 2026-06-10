#!/usr/bin/env python3
"""
Website Crawler & Migration Checklist Generator
================================================
Crawls a website, builds a page hierarchy tree, takes a screenshot
of the first viewport of every page, and outputs an HTML checklist.
Filters out non-English paths (e.g., /es/, /pt/).

Requirements:
    pip install playwright beautifulsoup4 requests
    playwright install chromium
"""

import asyncio
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


# ── Config ──────────────────────────────────────────────────────────────────

BASE_URL = ""          # Set via CLI arg or edit here: e.g. "https://example.com"
OUTPUT_DIR = Path("crawl_output")
SCREENSHOTS_DIR = OUTPUT_DIR / "screenshots"
MAX_PAGES = 500        # Safety cap
CONCURRENCY = 3        # Parallel browser tabs
VIEWPORT = {"width": 1440, "height": 900}
SCREENSHOT_CLIP = {"x": 0, "y": 0, "width": 1440, "height": 700}  # First ~700px


# ── Crawler ──────────────────────────────────────────────────────────────────

class SiteCrawler:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.origin = urlparse(base_url).scheme + "://" + urlparse(base_url).netloc
        self.visited: dict[str, dict] = {}   # url -> {title, depth, parent, children}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(CONCURRENCY)

    def is_internal(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc == urlparse(self.base_url).netloc

    def is_english_only(self, url: str) -> bool:
        """
        Filters out path structures starting with common Spanish (es) 
        and Portuguese (pt) locales.
        """
        path = urlparse(url).path.lower()
        # Matches patterns like /es/, /pt/, /es-419/, /pt-br/ at the beginning of paths
        non_english_pattern = re.compile(r'^/(es|pt)(-[a-z0-9]+)?(/|$)')
        return not bool(non_english_pattern.search(path))

    def normalize(self, url: str) -> str:
        parsed = urlparse(url)
        # Remove fragments and trailing slashes (except root)
        clean = parsed._replace(fragment="").geturl()
        if clean != self.origin + "/" and clean.endswith("/"):
            clean = clean.rstrip("/")
        return clean

    def path_depth(self, url: str) -> int:
        path = urlparse(url).path.strip("/")
        return len(path.split("/")) if path else 0

    async def crawl(self):
        OUTPUT_DIR.mkdir(exist_ok=True)
        SCREENSHOTS_DIR.mkdir(exist_ok=True)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            start = self.normalize(self.base_url)
            
            if not self.is_english_only(start):
                print(f"⚠️ Warning: Base URL looks like a non-English locale path!")

            self.visited[start] = {"title": "", "depth": 0, "parent": None, "children": [], "screenshot": ""}
            await self.queue.put((start, None, 0))

            tasks = []
            while not self.queue.empty() or any(not t.done() for t in tasks):
                while not self.queue.empty() and len(self.visited) <= MAX_PAGES:
                    url, parent, depth = await self.queue.get()
                    task = asyncio.create_task(self.process_page(browser, url, parent, depth))
                    tasks.append(task)

                tasks = [t for t in tasks if not t.done()]
                if tasks:
                    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                else:
                    break

            await browser.close()

    async def process_page(self, browser, url: str, parent: str | None, depth: int):
        async with self.semaphore:
            try:
                page = await browser.new_page(viewport=VIEWPORT)
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(800)  # let JS settle

                # Title
                title = await page.title()
                if not title:
                    title = urlparse(url).path or "/"

                # Screenshot
                safe_name = re.sub(r'[^\w]', '_', urlparse(url).path.strip("/") or "home") + ".png"
                shot_path = SCREENSHOTS_DIR / safe_name
                await page.screenshot(path=str(shot_path), clip=SCREENSHOT_CLIP)

                # Update node
                self.visited[url]["title"] = title
                self.visited[url]["screenshot"] = str(shot_path.relative_to(OUTPUT_DIR))

                # Extract links
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                links = set()
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                        continue
                    full = self.normalize(urljoin(url, href))
                    
                    # Verify internal link structure and English locale exclusivity
                    if self.is_internal(full) and self.is_english_only(full) and full not in self.visited:
                        links.add(full)

                # Enqueue new pages
                for link in links:
                    if link not in self.visited and len(self.visited) < MAX_PAGES:
                        new_depth = self.path_depth(link)
                        self.visited[link] = {
                            "title": "",
                            "depth": new_depth,
                            "parent": url,
                            "children": [],
                            "screenshot": "",
                        }
                        if url in self.visited:
                            self.visited[url]["children"].append(link)
                        await self.queue.put((link, url, new_depth))

                await page.close()
                print(f"  ✓ [{len(self.visited):>3}] {url}")

            except Exception as e:
                print(f"  ✗ {url}  ({e})")
                if url in self.visited:
                    self.visited[url]["title"] = self.visited[url]["title"] or "(error)"
                    self.visited[url]["screenshot"] = ""


# ── Tree Builder ──────────────────────────────────────────────────────────────

def build_tree(pages: dict, root: str) -> dict:
    """Build a nested tree from flat page dict."""
    def node(url):
        info = pages.get(url, {})
        return {
            "url": url,
            "title": info.get("title") or url,
            "screenshot": info.get("screenshot", ""),
            "children": [node(c) for c in info.get("children", []) if c in pages],
        }
    return node(root)


# ── HTML Report ───────────────────────────────────────────────────────────────

def render_tree_html(node: dict, depth=0) -> str:
    indent = depth * 20
    url = node["url"]
    title = node["title"]
    shot = node["screenshot"]
    shot_html = f'<img src="{shot}" alt="screenshot" class="thumb" onclick="openModal(\'{shot}\')">' if shot else '<div class="no-shot">No screenshot</div>'

    children_html = "".join(render_tree_html(c, depth + 1) for c in node["children"])
    children_block = f'<div class="children">{children_html}</div>' if children_html else ""

    toggle = '<button class="toggle" onclick="toggleChildren(this)">▾</button>' if children_html else '<span class="toggle-spacer"></span>'

    return f"""
    <div class="page-node" style="margin-left:{indent}px" data-url="{url}">
      <div class="page-row">
        {toggle}
        <label class="check-label">
          <input type="checkbox" class="migrate-check" data-url="{url}" onchange="updateProgress()">
          <span class="page-info">
            <span class="page-title">{title}</span>
            <a class="page-url" href="{url}" target="_blank">{url}</a>
          </span>
        </label>
        <div class="action-wrap">
          <label class="ignore-label">
            <input type="checkbox" class="ignore-check" data-url="{url}" onchange="updateProgress()">
            <span>Ignore</span>
          </label>
          <div class="shot-wrap">{shot_html}</div>
        </div>
      </div>
      {children_block}
    </div>"""


def generate_report(tree: dict, base_url: str, total: int):
    tree_html = render_tree_html(tree)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Migration Checklist — {base_url}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg: #0f0f0f;
    --surface: #1a1a1a;
    --border: #2a2a2a;
    --accent: #00e5a0;
    --accent2: #0099ff;
    --danger: #ff4a5a;
    --text: #e8e8e8;
    --muted: #666;
    --done-bg: #0a1f15;
    --ignore-bg: #141414;
  }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 14px;
    line-height: 1.5;
    min-height: 100vh;
  }}

  header {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 24px 32px;
    position: sticky;
    top: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 32px;
    flex-wrap: wrap;
  }}

  header h1 {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 18px;
    font-weight: 600;
    color: var(--accent);
    letter-spacing: -0.5px;
  }}

  header .site-url {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: var(--muted);
  }}

  .progress-wrap {{
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 16px;
  }}

  .progress-bar {{
    width: 200px;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
  }}

  .progress-fill {{
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    border-radius: 3px;
    transition: width 0.3s ease;
    width: 0%;
  }}

  .progress-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    color: var(--accent);
    min-width: 80px;
    text-align: right;
  }}

  .toolbar {{
    padding: 12px 32px;
    display: flex;
    gap: 12px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    align-items: center;
    flex-wrap: wrap;
  }}

  .btn {{
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 6px 14px;
    border-radius: 4px;
    cursor: pointer;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    transition: border-color 0.15s, color 0.15s;
  }}
  .btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  
  .btn.active {{
    border-color: var(--accent2);
    color: var(--accent2);
    background: #0f1a24;
  }}

  .separator {{
    height: 20px;
    width: 1px;
    background: var(--border);
    margin: 0 8px;
  }}

  main {{ padding: 24px 32px 80px; }}

  .page-node {{ margin-bottom: 4px; transition: opacity 0.2s ease, max-height 0.3s ease; }}

  .page-row {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    transition: border-color 0.15s, background 0.15s;
  }}
  .page-row:hover {{ border-color: #3a3a3a; }}

  /* Migration Done State */
  .page-node.done > .page-row {{
    background: var(--done-bg);
    border-color: #1a4030;
  }}
  
  /* Ignored Pools Low Opacity State */
  .page-node.ignored-branch > .page-row {{
    opacity: 0.4;
    background: var(--ignore-bg);
    border-color: var(--border);
  }}
  .page-node.ignored-branch > .page-row .page-title {{
    text-decoration: line-through;
    color: var(--muted);
  }}

  /* Hide Ignored filter mechanism */
  body.hide-ignored .page-node.ignored-branch {{
    display: none !important;
  }}

  .toggle, .toggle-spacer {{
    width: 20px;
    flex-shrink: 0;
    background: none;
    border: none;
    color: var(--muted);
    cursor: pointer;
    font-size: 14px;
    padding: 0;
    margin-top: 2px;
    transition: transform 0.2s;
  }}
  .toggle.collapsed {{ transform: rotate(-90deg); }}

  .check-label {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    cursor: pointer;
    flex: 1;
  }}

  .migrate-check, .ignore-check {{
    width: 16px;
    height: 16px;
    margin-top: 3px;
    flex-shrink: 0;
    accent-color: var(--accent);
  }}
  
  .ignore-check {{
    accent-color: var(--danger);
  }}

  .page-info {{ display: flex; flex-direction: column; gap: 2px; }}

  .page-title {{
    font-weight: 500;
    color: var(--text);
    font-size: 14px;
  }}

  .page-url {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--muted);
    text-decoration: none;
    word-break: break-all;
  }}
  .page-url:hover {{ color: var(--accent2); }}

  .action-wrap {{
    display: flex;
    align-items: center;
    gap: 20px;
    flex-shrink: 0;
  }}

  .ignore-label {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--muted);
    cursor: pointer;
    user-select: none;
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid transparent;
  }}
  .ignore-label:hover {{
    color: var(--danger);
    border-color: rgba(255, 74, 90, 0.2);
  }}

  .shot-wrap {{
    flex-shrink: 0;
    width: 180px;
  }}

  .thumb {{
    width: 180px;
    height: auto;
    border-radius: 4px;
    border: 1px solid var(--border);
    cursor: zoom-in;
    display: block;
    transition: border-color 0.15s;
  }}
  .thumb:hover {{ border-color: var(--accent); }}

  .no-shot {{
    width: 180px;
    height: 60px;
    border: 1px dashed var(--border);
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--muted);
    font-size: 11px;
  }}

  .children {{ margin-top: 4px; }}

  /* Modal */
  .modal {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.88);
    z-index: 1000;
    align-items: center;
    justify-content: center;
  }}
  .modal.open {{ display: flex; }}
  .modal img {{
    max-width: 90vw;
    max-height: 90vh;
    border-radius: 8px;
    box-shadow: 0 0 60px rgba(0,229,160,0.15);
  }}
  .modal-close {{
    position: fixed;
    top: 20px; right: 24px;
    background: none;
    border: none;
    color: #fff;
    font-size: 32px;
    cursor: pointer;
    line-height: 1;
  }}
</style>
</head>
<body>

<header>
  <div>
    <h1>Migration Checklist</h1>
    <div class="site-url">{base_url}</div>
  </div>
  <div class="progress-wrap">
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <div class="progress-label" id="progressLabel">0 / {total}</div>
  </div>
</header>

<div class="toolbar">
  <button class="btn" onclick="checkAll()">✓ Check all</button>
  <button class="btn" onclick="uncheckAll()">✗ Uncheck all</button>
  <button class="btn" onclick="expandAll()">⊞ Expand all</button>
  <button class="btn" onclick="collapseAll()">⊟ Collapse all</button>
  <div class="separator"></div>
  <button class="btn active" id="filterAllBtn" onclick="setFilter('all')">👁 Show All</button>
  <button class="btn" id="filterActiveBtn" onclick="setFilter('hide-ignored')">🚫 Hide Ignored</button>
  <div class="separator"></div>
  <button class="btn" onclick="exportJSON()">↓ Export progress</button>
  <button class="btn" onclick="importJSON()">↑ Import progress</button>
</div>

<main>
{tree_html}
</main>

<div class="modal" id="modal" onclick="closeModal()">
  <button class="modal-close" onclick="closeModal()">×</button>
  <img id="modalImg" src="" alt="">
</div>

<script>
const TOTAL = {total};
let currentFilter = 'all';

function updateProgress() {{
  const allChecks = document.querySelectorAll('.migrate-check');
  const allNodes = document.querySelectorAll('.page-node');
  
  // First run: apply explicit classes to rows
  allNodes.forEach(node => {{
    const url = node.dataset.url;
    const isMigrated = node.querySelector(`.migrate-check[data-url="${{CSS.escape(url)}}"]`).checked;
    const isIgnored = node.querySelector(`.ignore-check[data-url="${{CSS.escape(url)}}"]`).checked;
    
    node.classList.toggle('done', isMigrated);
    node.classList.toggle('ignored-branch', isIgnored);
  }});

  // Re-calculate counts
  const liveMigrateChecks = [...document.querySelectorAll('.migrate-check')];
  const totalCount = liveMigrateChecks.length;
  const doneCount = liveMigrateChecks.filter(c => c.checked).length;
  
  document.getElementById('progressFill').style.width = (totalCount ? (doneCount / totalCount * 100) : 0) + '%';
  document.getElementById('progressLabel').textContent = doneCount + ' / ' + totalCount;
  
  saveProgress();
}}

function setFilter(mode) {{
  currentFilter = mode;
  if (mode === 'hide-ignored') {{
    document.body.classList.add('hide-ignored');
    document.getElementById('filterActiveBtn').classList.add('active');
    document.getElementById('filterAllBtn').classList.remove('active');
  }} else {{
    document.body.classList.remove('hide-ignored');
    document.getElementById('filterAllBtn').classList.add('active');
    document.getElementById('filterActiveBtn').classList.remove('active');
  }}
  localStorage.setItem('migration_filter_mode', mode);
}}

function checkAll() {{ document.querySelectorAll('.migrate-check').forEach(c => {{ c.checked = true; }}); updateProgress(); }}
function uncheckAll() {{ document.querySelectorAll('.migrate-check').forEach(c => {{ c.checked = false; }}); updateProgress(); }}

function toggleChildren(btn) {{
  const node = btn.closest('.page-node');
  const children = node.querySelector('.children');
  if (!children) return;
  const collapsed = btn.classList.toggle('collapsed');
  children.style.display = collapsed ? 'none' : '';
}}

function expandAll() {{
  document.querySelectorAll('.toggle').forEach(b => {{
    b.classList.remove('collapsed');
    const c = b.closest('.page-node').querySelector('.children');
    if (c) c.style.display = '';
  }});
}}

function collapseAll() {{
  document.querySelectorAll('.toggle').forEach(b => {{
    b.classList.add('collapsed');
    const c = b.closest('.page-node').querySelector('.children');
    if (c) c.style.display = 'none';
  }});
}}

function openModal(src) {{ document.getElementById('modalImg').src = src; document.getElementById('modal').classList.add('open'); }}
function closeModal() {{ document.getElementById('modal').classList.remove('open'); }}

function saveProgress() {{
  const state = {{ migrated: {{}}, ignored: {{}} }};
  document.querySelectorAll('.migrate-check').forEach(c => {{ state.migrated[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.ignore-check').forEach(c => {{ state.ignored[c.dataset.url] = c.checked; }});
  localStorage.setItem('migration_progress_v2', JSON.stringify(state));
}}

function loadProgress() {{
  // Load Filters
  const savedFilter = localStorage.getItem('migration_filter_mode');
  if (savedFilter) setFilter(savedFilter);

  // Load States
  const raw = localStorage.getItem('migration_progress_v2');
  if (!raw) return;
  try {{
    const state = JSON.parse(raw);
    document.querySelectorAll('.migrate-check').forEach(c => {{
      if (state.migrated && c.dataset.url in state.migrated) c.checked = state.migrated[c.dataset.url];
    }});
    document.querySelectorAll('.ignore-check').forEach(c => {{
      if (state.ignored && c.dataset.url in state.ignored) c.checked = state.ignored[c.dataset.url];
    }});
  }} catch(e) {{
    console.error("Error parsing local state data, upgrading old scheme.", e);
  }}
  updateProgress();
}}

function exportJSON() {{
  const state = {{ migrated: {{}}, ignored: {{}} }};
  document.querySelectorAll('.migrate-check').forEach(c => {{ state.migrated[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.ignore-check').forEach(c => {{ state.ignored[c.dataset.url] = c.checked; }});
  const blob = new Blob([JSON.stringify(state, null, 2)], {{type:'application/json'}});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'migration_progress.json'; a.click();
}}

function importJSON() {{
  const input = document.createElement('input'); input.type = 'file'; input.accept = '.json';
  input.onchange = e => {{
    const file = e.target.files[0];
    const reader = new FileReader();
    reader.onload = ev => {{
      try {{
        const state = JSON.parse(ev.target.result);
        document.querySelectorAll('.migrate-check').forEach(c => {{
          if (state.migrated && c.dataset.url in state.migrated) c.checked = state.migrated[c.dataset.url];
        }});
        document.querySelectorAll('.ignore-check').forEach(c => {{
          if (state.ignored && c.dataset.url in state.ignored) c.checked = state.ignored[c.dataset.url];
        }});
        updateProgress();
      }} catch (err) {{
        alert("Failed to parse JSON schema profile!");
      }}
    }};
    reader.readAsText(file);
  }};
  input.click();
}}

loadProgress();
updateProgress();
</script>
</body>
</html>"""
    return html


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    global BASE_URL
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1].rstrip("/")
    if not BASE_URL:
        print("Usage: python crawl_site.py https://example.com")
        sys.exit(1)

    if not BASE_URL.startswith("http"):
        BASE_URL = "https://" + BASE_URL

    print(f"\n🔍 Crawling (English Only): {BASE_URL}")
    print(f"📁 Output:   {OUTPUT_DIR.resolve()}\n")

    crawler = SiteCrawler(BASE_URL)
    await crawler.crawl()

    root_url = crawler.normalize(BASE_URL)
    tree = build_tree(crawler.visited, root_url)
    total = len(crawler.visited)

    # Save raw data
    with open(OUTPUT_DIR / "pages.json", "w") as f:
        json.dump(crawler.visited, f, indent=2)

    # Generate HTML report
    report_html = generate_report(tree, BASE_URL, total)
    report_path = OUTPUT_DIR / "checklist.html"
    report_path.write_text(report_html, encoding="utf-8")

    print(f"\n✅ Done! {total} pages crawled.")
    print(f"📋 Checklist: {report_path.resolve()}")
    print(f"🖼️  Screenshots: {SCREENSHOTS_DIR.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())