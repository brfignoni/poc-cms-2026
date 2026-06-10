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

import argparse
import asyncio
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


# ── Config ──────────────────────────────────────────────────────────────────

BASE_URL = "https://www.genexus.com/en/"
OUTPUT_DIR = Path("crawl_output")
SCREENSHOTS_DIR = OUTPUT_DIR / "screenshots"
MAX_PAGES = 50000      # Optimized to map out the entire site hierarchy
CONCURRENCY = 5        # Safe speed balance to prevent rate-limiting/IP blocks
VIEWPORT = {"width": 1440, "height": 900}
SCREENSHOT_CLIP = {"x": 0, "y": 0, "width": 1440, "height": 700}  # First ~700px


# ── Crawler ──────────────────────────────────────────────────────────────────

class SiteCrawler:
    def __init__(self, base_url: str, max_pages: int):
        self.base_url = base_url.rstrip("/")
        self.origin = urlparse(base_url).scheme + "://" + urlparse(base_url).netloc
        self.visited: dict[str, dict] = {}   # url -> {title, depth, parent, children}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(CONCURRENCY)
        self.max_pages = max_pages

    def is_internal(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc == urlparse(self.base_url).netloc

    def is_english_only(self, url: str) -> bool:
        """
        Filters out route structures starting with common regional locales like /es/ or /pt/.
        """
        path = urlparse(url).path.lower()
        non_english_pattern = re.compile(r'^/(es|pt)(-[a-z0-9]+)?(/|$)')
        return not bool(non_english_pattern.search(path))

    def normalize(self, url: str) -> str:
        parsed = urlparse(url)
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
                print(f"⚠️ Warning: Target base URL looks like a non-English regional route!")

            self.visited[start] = {"title": "", "depth": 0, "parent": None, "children": [], "screenshot": ""}
            await self.queue.put((start, None, 0))

            tasks = []
            while not self.queue.empty() or any(not t.done() for t in tasks):
                while not self.queue.empty() and len(self.visited) <= self.max_pages:
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
                await page.wait_for_timeout(800)  # Grace period for JS assets

                title = await page.title()
                if not title:
                    title = urlparse(url).path or "/"

                # Hardcoded ultra-lightweight JPEG output configuration
                safe_name = re.sub(r'[^\w]', '_', urlparse(url).path.strip("/") or "home") + ".jpeg"
                shot_path = SCREENSHOTS_DIR / safe_name
                await page.screenshot(path=str(shot_path), clip=SCREENSHOT_CLIP, type="jpeg", quality=30)

                self.visited[url]["title"] = title
                self.visited[url]["screenshot"] = str(shot_path.relative_to(OUTPUT_DIR))

                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                links = set()
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                        continue
                    full = self.normalize(urljoin(url, href))
                    
                    if self.is_internal(full) and self.is_english_only(full) and full not in self.visited:
                        links.add(full)

                for link in links:
                    if link not in self.visited and len(self.visited) < self.max_pages:
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


# ── Tree Factory ────────────────────────────────────────────────────────────

def build_tree(pages: dict, root: str) -> dict:
    def node(url):
        info = pages.get(url, {})
        return {
            "url": url,
            "title": info.get("title") or url,
            "screenshot": info.get("screenshot", ""),
            "children": [node(c) for c in info.get("children", []) if c in pages],
        }
    return node(root)


# ── HTML Template Generation ────────────────────────────────────────────────

def render_tree_html(node: dict, progress_state: dict | None = None) -> str:
    url = node["url"]
    title = node["title"]
    shot = node["screenshot"]
    shot_html = f'<img src="{shot}" alt="screenshot" class="thumb" onclick="openModal(\'{shot}\')">' if shot else '<div class="no-shot">No screenshot</div>'

    is_migrated = progress_state.get("migrated", {}).get(url, False) if progress_state else False
    is_ignored = progress_state.get("ignored", {}).get(url, False) if progress_state else False
    is_starred = progress_state.get("starred", {}).get(url, False) if progress_state else False
    custom_note = progress_state.get("notes", {}).get(url, "").strip() if progress_state else ""

    checked_attr = "checked" if is_migrated else ""
    ignored_attr = "checked" if is_ignored else ""
    starred_attr = "checked" if is_starred else ""
    
    node_classes = ["page-node"]
    if is_migrated: node_classes.append("done")
    if is_ignored: node_classes.append("ignored-branch")
    if is_starred: node_classes.append("starred-item")

    has_children = len(node["children"]) > 0
    children_html = "".join(render_tree_html(c, progress_state) for c in node["children"])
    children_block = f'<div class="children">{children_html}</div>' if has_children else ""

    toggle = '<button class="toggle" onclick="toggleChildren(this)">▾</button>' if has_children else '<span class="toggle-spacer"></span>'
    subtree_btn = f'<button class="btn-mini" onclick="toggleIgnoreSubtree(\'{url}\')" title="Toggle ignore state on all descendants">Ignore Branch</button>' if has_children else ''

    note_icon = "📌" if custom_note else "✏️"
    note_btn_class = "btn-notes-toggle has-note" if custom_note else "btn-notes-toggle empty-note"
    notes_container_class = "notes-container open" if custom_note else "notes-container"

    return f"""
    <div class="{" ".join(node_classes)}" data-url="{url}">
      <div class="page-row">
        {toggle}
        
        <div class="page-info">
          <label class="check-label">
            <input type="checkbox" class="migrate-check" data-url="{url}" onclick="handleMigrateClick(event, this)" onchange="updateProgress()" {checked_attr}>
            <span class="page-title">{title}</span>
          </label>
          
          <a class="page-url" href="{url}" target="_blank">{url}</a>
          
          <div class="{notes_container_class}" id="notes-container-{url}">
            <textarea class="notes-textarea" placeholder="Add custom row annotations here..." oninput="autoExpandTextarea(this); saveProgress()" onblur="handleNotesBlur('{url}')" data-url="{url}">{custom_note}</textarea>
          </div>
        </div>
        
        <div class="action-wrap">
          {subtree_btn}
          <button class="{note_btn_class}" id="note-icon-{url}" onclick="toggleNotesField('{url}')" title="Edit row annotations">{note_icon}</button>
          <label class="star-label" title="Flag page as high priority">
            <input type="checkbox" class="star-check" data-url="{url}" onchange="updateProgress()" {starred_attr}>
            <span>⭐ High Priority</span>
          </label>
          <label class="ignore-label">
            <input type="checkbox" class="ignore-check" data-url="{url}" onchange="updateProgress()" {ignored_attr}>
            <span>Ignore</span>
          </label>
          <div class="shot-wrap">{shot_html}</div>
        </div>
      </div>
      {children_block}
    </div>"""


def generate_report(tree: dict, base_url: str, total: int, progress_state: dict | None = None):
    tree_html = render_tree_html(tree, progress_state)
    saved_timestamp = progress_state.get("exportDate", "Never") if progress_state else "Never"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Migration Checklist Tree - GeneXus</title>
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
    --warning: #ffb700;
    --text: #e8e8e8;
    --muted: #666;
    --done-bg: #0a1f15;
    --ignore-bg: #141414;
    --star-bg: #241e10;
  }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 14px;
    line-height: 1.5;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
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
    height: 120px;
  }}

  header h1 {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 18px;
    font-weight: 600;
    color: var(--accent);
    letter-spacing: -0.5px;
  }}

  .header-meta {{
    display: flex;
    flex-direction: column;
    gap: 2px;
  }}

  header .site-url, header .export-date {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: var(--muted);
  }}
  
  header .export-date {{
    color: var(--accent2);
    font-size: 11px;
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
    position: sticky;
    top: 120px;
    z-index: 101;
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
    transition: border-color 0.15s, color 0.15s, background-color 0.15s;
  }}
  .btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  
  .btn.active {{
    border-color: var(--accent2);
    color: var(--accent2);
    background: #0f1a24;
  }}

  .btn-danger-hover:hover {{
    border-color: var(--danger) !important;
    color: var(--danger) !important;
    background: #241214 !important;
  }}

  .btn-mini {{
    background: transparent;
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px !important;
    transition: all 0.15s ease;
  }}
  .btn-mini:hover {{
    color: var(--accent2);
    border-color: var(--accent2);
    background: #0f1a24;
  }}

  .separator {{
    height: 20px;
    width: 1px;
    background: var(--border);
    margin: 0 8px;
  }}

  main {{ padding: 24px 32px 60px; flex: 1; }}

  .page-node {{ margin-bottom: 6px; position: relative; }}

  .children {{
    position: relative;
    margin-left: 28px;
    margin-top: 4px;
  }}

  .page-row {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    position: relative;
    z-index: 2;
    transition: border-color 0.15s, background 0.15s;
  }}
  .page-row:hover {{ border-color: #3a3a3a; }}

  .page-node.starred-item > .page-row {{
    background: var(--star-bg);
    border-color: rgba(255, 183, 0, 0.3);
  }}
  .page-node.done > .page-row {{
    background: var(--done-bg) !important;
    border-color: #1a4030 !important;
  }}
  
  .page-node.starred-item > .page-row .page-title::before {{
    content: "⭐ ";
    padding-right: 4px;
  }}

  .page-node.ignored-branch > .page-row {{
    opacity: 0.35;
    background: var(--ignore-bg);
  }}
  .page-node.ignored-branch > .page-row .page-title {{
    text-decoration: line-through;
    color: var(--muted);
  }}

  body.hide-ignored .page-node.ignored-branch > .page-row {{
    display: none !important;
  }}
  body.hide-ignored .page-node.ignored-branch > .children {{
    margin-left: 0px !important;
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
    display: inline-flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    width: max-content;
    max-width: 100%;
  }}

  .migrate-check {{
    margin-top: 0px !important;
    width: 16px;
    height: 16px;
    flex-shrink: 0;
  }}
  .ignore-check, .star-check {{
    width: 16px;
    height: 16px;
    flex-shrink: 0;
    margin-top: 0 !important;
  }}
  
  .ignore-check {{ accent-color: var(--danger); }}
  .star-check {{ accent-color: var(--warning); }}

  .page-info {{
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
    pointer-events: auto;
    min-width: 0;
  }}

  .page-title {{
    font-weight: 500;
    color: var(--text);
    font-size: 14px;
    display: inline-block;
    width: max-content;
    max-width: 100%;
  }}

  .page-url {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px !important;
    color: var(--muted);
    text-decoration: none;
    word-break: break-all;
    display: inline-block;
    width: max-content;
    max-width: 100%;
    margin-left: 26px;
  }}
  .page-url:hover {{ color: var(--accent2); }}

  .notes-container {{
    display: none;
    margin-top: 8px;
    width: 100%;
  }}
  .notes-container.open {{
    display: block;
  }}
  
  .notes-textarea {{
    width: 100%;
    min-height: 48px;
    background: #111;
    border: 1px solid var(--border);
    border-radius: 4px;
    color: #ccc;
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 13px !important;
    line-height: 1.6 !important;
    padding: 8px 12px;
    resize: none;
    outline: none;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.5);
  }}
  .notes-textarea:focus {{
    border-color: var(--accent2);
  }}

  .action-wrap {{
    display: flex;
    align-items: center;
    gap: 16px;
    flex-shrink: 0;
  }}

  .ignore-label {{
    display: inline-flex;
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
  .ignore-label:hover {{ color: var(--danger); border-color: rgba(255, 74, 90, 0.2); }}

  .star-label {{
    display: inline-flex;
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
    opacity: 0;
    transition: opacity 0.15s ease;
  }}
  .star-label:hover {{ color: var(--warning); border-color: rgba(255, 183, 0, 0.2); }}

  .btn-notes-toggle.empty-note {{
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 12px;
    padding: 4px;
    opacity: 0;
    transition: opacity 0.15s ease;
  }}
  
  .btn-notes-toggle.has-note {{
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 12px;
    padding: 4px;
    opacity: 0.65;
    transition: opacity 0.15s ease;
  }}
  
  .page-row:hover .btn-notes-toggle.empty-note {{
    opacity: 0.65;
  }}
  
  .page-row:hover .star-label {{
    opacity: 1.0;
  }}
  
  .btn-notes-toggle:hover {{
    opacity: 1.0 !important;
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
  <div class="header-meta">
    <h1>Migration Checklist Tree - GeneXus</h1>
    <div class="site-url">{base_url}</div>
    <div class="export-date" id="globalExportDate">Exported State: Never</div>
  </div>
  <div class="progress-wrap">
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <div class="progress-label" id="progressLabel">0 / 0</div>
  </div>
</header>

<div class="toolbar">
  <button class="btn" onclick="expandAll()">⊞ Expand All</button>
  <button class="btn" onclick="collapseAll()">⊟ Collapse All</button>
  <div class="separator"></div>
  <button class="btn active" id="filterAllBtn" onclick="setFilter('all')">👁 Show All</button>
  <button class="btn" id="filterActiveBtn" onclick="setFilter('hide-ignored')">🚫 Hide 0 Ignored</button>
  <div class="separator"></div>
  <button class="btn" onclick="exportJSON()">↓ Export Progress</button>
  <button class="btn" onclick="importJSON()">↑ Import Progress</button>
  <div class="separator"></div>
  <button class="btn btn-danger-hover" onclick="resetBrowserData()">⚠️ Clear Browser Data</button>
</div>

<main>
{tree_html}
</main>

<div class="modal" id="modal" onclick="closeModal()">
  <button class="modal-close" onclick="closeModal()">×</button>
  <img id="modalImg" src="" alt="">
</div>

<script>
let currentFilter = 'all';
let globalExportTimestamp = '{saved_timestamp}';

function getFormattedTimestamp() {{
  const options = {{ year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }};
  return new Date().toLocaleDateString('en-US', options);
}}

function autoExpandTextarea(el) {{
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}}

function toggleNotesField(url) {{
  const container = document.getElementById(`notes-container-${{url}}`);
  if (!container) return;
  const opening = container.classList.toggle('open');
  if (opening) {{
    const ta = container.querySelector('.notes-textarea');
    ta.focus();
    autoExpandTextarea(ta);
  }}
}}

function handleNotesBlur(url) {{
  setTimeout(() => {{
    const container = document.getElementById(`notes-container-${{url}}`);
    if (!container) return;
    container.classList.remove('open');
    updateProgress();
  }}, 150);
}}

function handleMigrateClick(event, checkbox) {{
  if (event.shiftKey) {{
    const parentNode = checkbox.closest('.page-node');
    if (!parentNode) return;
    
    const childrenContainer = parentNode.querySelector('.children');
    if (!childrenContainer) return;

    const directChildren = childrenContainer.querySelectorAll(':scope > .page-node > .page-row .migrate-check');
    directChildren.forEach(childCheck => {{
      childCheck.checked = checkbox.checked;
    }});
  }}
}}

function updateProgress() {{
  const allNodes = document.querySelectorAll('.page-node');
  let countIgnored = 0;
  
  allNodes.forEach(node => {{
    const url = node.dataset.url;
    const isMigrated = node.querySelector(`.migrate-check[data-url="${{CSS.escape(url)}}"]`).checked;
    const isIgnored = node.querySelector(`.ignore-check[data-url="${{CSS.escape(url)}}"]`).checked;
    const isStarred = node.querySelector(`.star-check[data-url="${{CSS.escape(url)}}"]`).checked;
    
    node.classList.toggle('done', isMigrated);
    node.classList.toggle('ignored-branch', isIgnored);
    node.classList.toggle('starred-item', isStarred);
    
    if (isIgnored) countIgnored++;

    const ta = node.querySelector('.notes-textarea');
    const noteBtn = document.getElementById(`note-icon-${{url}}`);
    if (ta && noteBtn) {{
      if (ta.value.trim().length > 0) {{
        noteBtn.textContent = '📌';
        noteBtn.className = 'btn-notes-toggle has-note';
      }} else {{
        noteBtn.textContent = '✏️';
        noteBtn.className = 'btn-notes-toggle empty-note';
      }}
    }}
  }});

  document.getElementById('filterActiveBtn').textContent = `🚫 Hide ${{countIgnored}} Ignored`;
  document.getElementById('globalExportDate').textContent = `Exported State: ${{globalExportTimestamp}}`;

  let countTotal = 0;
  let countDone = 0;

  allNodes.forEach(node => {{
    const isIgnored = node.querySelector('.ignore-check').checked;
    if (currentFilter === 'hide-ignored') {{
      if (!isIgnored) {{
        countTotal++;
        if (node.querySelector('.migrate-check').checked) countDone++;
      }}
    }} else {{
      countTotal++;
      if (node.querySelector('.migrate-check').checked) countDone++;
    }}
  }});
  
  document.getElementById('progressFill').style.width = (countTotal ? (countDone / countTotal * 100) : 0) + '%';
  document.getElementById('progressLabel').textContent = countDone + ' / ' + countTotal;
  
  saveProgress();
}}

function toggleIgnoreSubtree(url) {{
  const parentNode = document.querySelector(`.page-node[data-url="${{CSS.escape(url)}}"]`);
  if (!parentNode) return;
  
  const targetCheck = parentNode.querySelector('.ignore-check');
  const nextState = !targetCheck.checked;
  
  parentNode.querySelectorAll('.ignore-check').forEach(chk => {{
    chk.checked = nextState;
  }});
  
  updateProgress();
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
  updateProgress();
}}

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
  const state = {{ migrated: {{}}, ignored: {{}}, starred: {{}}, notes: {{}}, exportDate: globalExportTimestamp }};
  document.querySelectorAll('.migrate-check').forEach(c => {{ state.migrated[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.ignore-check').forEach(c => {{ state.ignored[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.star-check').forEach(c => {{ state.starred[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.notes-textarea').forEach(t => {{ state.notes[t.dataset.url] = t.value; }});
  localStorage.setItem('migration_progress_v4', JSON.stringify(state));
}}

function loadProgress() {{
  const savedFilter = localStorage.getItem('migration_filter_mode');
  if (savedFilter) currentFilter = savedFilter;

  const raw = localStorage.getItem('migration_progress_v4');
  if (!raw) {{
    updateProgress();
    setFilter(currentFilter);
    return;
  }}
  try {{
    const state = JSON.parse(raw);
    if (state.exportDate) globalExportTimestamp = state.exportDate;
    
    document.querySelectorAll('.migrate-check').forEach(c => {{
      if (state.migrated && c.dataset.url in state.migrated) c.checked = state.migrated[c.dataset.url];
    }});
    document.querySelectorAll('.ignore-check').forEach(c => {{
      if (state.ignored && c.dataset.url in state.ignored) c.checked = state.ignored[c.dataset.url];
    }});
    document.querySelectorAll('.star-check').forEach(c => {{
      if (state.starred && c.dataset.url in state.starred) c.checked = state.starred[c.dataset.url];
    }});
    document.querySelectorAll('.notes-textarea').forEach(t => {{
      if (state.notes && t.dataset.url in state.notes && state.notes[t.dataset.url]) {{
        t.value = state.notes[t.dataset.url];
        autoExpandTextarea(t);
      }}
    }});
  }} catch(e) {{
    console.error("Error context indexing browser state.", e);
  }}
  
  setFilter(currentFilter);
}}

function exportJSON() {{
  globalExportTimestamp = getFormattedTimestamp();
  document.getElementById('globalExportDate').textContent = `Exported State: ${{globalExportTimestamp}}`;

  const state = {{ migrated: {{}}, ignored: {{}}, starred: {{}}, notes: {{}}, exportDate: globalExportTimestamp }};
  document.querySelectorAll('.migrate-check').forEach(c => {{ state.migrated[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.ignore-check').forEach(c => {{ state.ignored[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.star-check').forEach(c => {{ state.starred[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.notes-textarea').forEach(t => {{ state.notes[t.dataset.url] = t.value; }});
  
  const blob = new Blob([JSON.stringify(state, null, 2)], {{ type: 'application/json' }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'migration_progress.json';
  
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  saveProgress();
}}

function importJSON() {{
  const input = document.createElement('input'); 
  input.type = 'file'; 
  input.accept = '.json';
  input.onchange = e => {{
    const file = e.target.files[0];
    const reader = new FileReader();
    reader.onload = ev => {{
      try {{
        const state = JSON.parse(ev.target.result);
        globalExportTimestamp = state.exportDate || 'Never';

        document.querySelectorAll('.migrate-check').forEach(c => {{
          if (state.migrated && c.dataset.url in state.migrated) c.checked = state.migrated[c.dataset.url];
        }});
        document.querySelectorAll('.ignore-check').forEach(c => {{
          if (state.ignored && c.dataset.url in state.ignored) c.checked = state.ignored[c.dataset.url];
        }});
        document.querySelectorAll('.star-check').forEach(c => {{
          if (state.starred && c.dataset.url in state.starred) c.checked = state.starred[c.dataset.url];
        }});
        
        document.querySelectorAll('.notes-textarea').forEach(t => {{
          if (state.notes && t.dataset.url in state.notes) {{
            t.value = state.notes[t.dataset.url];
            autoExpandTextarea(t);
          }} else {{
            t.value = '';
          }}
        }});
        
        updateProgress();
      }} catch (err) {{
        alert("Failed to parse matching JSON architecture schema.");
      }}
    }};
    reader.readAsText(file);
  }};
  input.click();
}}

function resetBrowserData() {{
  const confirmed = confirm(
    "⚠️ ATENCIÓN: El estado de las casillas, estrellas de prioridad y anotaciones personalizadas se guardan localmente en el almacenamiento de tu navegador (localStorage).\\n\\n" +
    "Al borrar estos datos, perderás todo el progreso guardado en esta sesión de navegación de manera irreversible.\\n\\n" +
    "Para evitar descuidos, se descargará automáticamente un archivo de copia de seguridad ('migration_progress_backup.json') antes de proceder.\\n\\n" +
    "¿Estás seguro de que deseas vaciar el almacenamiento local y reiniciar la lista?"
  );
  
  if (!confirmed) return;

  globalExportTimestamp = getFormattedTimestamp();
  const state = {{ migrated: {{}}, ignored: {{}}, starred: {{}}, notes: {{}}, exportDate: globalExportTimestamp }};
  document.querySelectorAll('.migrate-check').forEach(c => {{ state.migrated[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.ignore-check').forEach(c => {{ state.ignored[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.star-check').forEach(c => {{ state.starred[c.dataset.url] = c.checked; }});
  document.querySelectorAll('.notes-textarea').forEach(t => {{ state.notes[t.dataset.url] = t.value; }});
  
  const blob = new Blob([JSON.stringify(state, null, 2)], {{ type: 'application/json' }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'migration_progress_backup.json';
  
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  localStorage.removeItem('migration_progress_v4');
  localStorage.removeItem('migration_filter_mode');
  
  window.location.reload();
}}

document.addEventListener("DOMContentLoaded", () => {{
  loadProgress();
}});
</script>
</body>
</html>"""
    return html


# ── Main Execution ──────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Run the interactive checklist tree generator crawler.")
    parser.add_argument('--test', action='store_true', help='Cap execution runtime to max 20 pages.')
    args = parser.parse_args()

    runtime_limit = 20 if args.test else MAX_PAGES

    print(f"\n🔍 Crawling (English Only): {BASE_URL}")
    print(f"⚙️ Execution Mode: {'TEST RUN (Cap: 20 pages)' if args.test else f'PRODUCTION RUN (Cap: {MAX_PAGES} pages)'}")
    print(f"📁 Output:   {OUTPUT_DIR.resolve()}\n")

    crawler = SiteCrawler(BASE_URL, max_pages=runtime_limit)
    await crawler.crawl()

    root_url = crawler.normalize(BASE_URL)
    tree = build_tree(crawler.visited, root_url)
    total = len(crawler.visited)

    with open(OUTPUT_DIR / "pages.json", "w") as f:
        json.dump(crawler.visited, f, indent=2)

    progress_file = Path("migration_progress.json")
    progress_state = None
    if progress_file.exists():
        try:
            progress_state = json.loads(progress_file.read_text(encoding="utf-8"))
            print(f"📦 Found baseline tracking states in '{progress_file.name}'. Merging into build template...")
        except Exception as e:
            print(f"⚠️ Failed to parse {progress_file.name}: {e}")

    report_html = generate_report(tree, BASE_URL, total, progress_state)
    report_path = OUTPUT_DIR / "checklist.html"
    report_path.write_text(report_html, encoding="utf-8")

    print(f"\n✅ Complete! Managed {total} discovered pages.")
    print(f"📋 Interactive Checklist: {report_path.resolve()}")
    print(f"🖼️  Viewport Screenshots:  {SCREENSHOTS_DIR.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())