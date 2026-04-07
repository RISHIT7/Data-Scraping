"""
main.py  —  entry point for the full scraping pipeline
Runs: blog scraper + youtube scraper (+ pubmed when ready)
"""

import json
import os

from scraper.blog_scraper import scrape_blog
from scraper.youtube_scraper import scrape_youtube_videos
from scraper.pubmed_scraper import scrape_pubmed

# ── Output directory ─────────────────────────────────────────────────────────
os.makedirs("output", exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# BLOGS  (existing, untouched)
# ═══════════════════════════════════════════════════════════════════════════
BLOG_URLS = [
    "https://realpython.com/python-web-scraping-practical-introduction/",
    "https://news.mit.edu/2025/new-ai-system-could-accelerate-clinical-research-0925",
    "https://news.mit.edu/2026/mit-scientists-investigate-memorization-risk-clinical-ai-0105",
]

print("=" * 60)
print("SCRAPING BLOGS")
print("=" * 60)

blog_results = []
for url in BLOG_URLS:
    print(f"\n→ {url}")
    data = scrape_blog(url)
    blog_results.append(data)

with open("output/blogs.json", "w", encoding="utf-8") as f:
    json.dump(blog_results, f, indent=2, ensure_ascii=False)
print(f"\n✅ Blogs saved → output/blogs.json ({len(blog_results)} entries)")


# ═══════════════════════════════════════════════════════════════════════════
# YOUTUBE  (new)
# ═══════════════════════════════════════════════════════════════════════════
YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=aircAruvnKk",   # 3Blue1Brown: Neural Networks
    "https://www.youtube.com/watch?v=kCc8FmEb1nY",   # Andrej Karpathy: GPT from scratch
    "https://www.youtube.com/watch?v=R9OHn5ZF4Uo",   # StatQuest: Machine Learning
]

print("\n" + "=" * 60)
print("SCRAPING YOUTUBE")
print("=" * 60)

youtube_results = scrape_youtube_videos(YOUTUBE_URLS)

with open("output/youtube.json", "w", encoding="utf-8") as f:
    json.dump(youtube_results, f, indent=2, ensure_ascii=False)
print(f"\n✅ YouTube saved → output/youtube.json ({len(youtube_results)} entries)")



# ═══════════════════════════════════════════════════════════════════════════
# PUBMED
# ═══════════════════════════════════════════════════════════════════════════
PUBMED_URLS = [
    "https://pubmed.ncbi.nlm.nih.gov/38478847/",
]

print("\n" + "=" * 60)
print("SCRAPING PUBMED")
print("=" * 60)

pubmed_results = []
for url in PUBMED_URLS:
    print(f"\n→ {url}")
    data = scrape_pubmed(url)
    pubmed_results.append(data)

with open("output/pubmed.json", "w", encoding="utf-8") as f:
    json.dump(pubmed_results, f, indent=2, ensure_ascii=False)
print(f"\n✅ PubMed saved → output/pubmed.json ({len(pubmed_results)} entries)")


print("\n🎉 Pipeline complete.")