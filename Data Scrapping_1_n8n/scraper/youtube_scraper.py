"""
youtube_scraper.py
------------------
Scrapes 3 YouTube videos and outputs structured JSON
matching the same schema as blog_scraper.py.

Libraries used:
  - yt-dlp          : metadata + transcript (no API key needed)
  - youtube-transcript-api : fallback transcript fetcher
  - langdetect      : language detection (already in project)
  - keybert         : topic tagging (already in project)

Install once:
  pip install yt-dlp youtube-transcript-api
(langdetect and keybert already in requirements.txt)
"""

import json
import re
import yt_dlp
from datetime import datetime

# ── Local utils (same pattern as blog_scraper.py) ──────────────────────────
try:
    from utils.chunking import chunk_text
except ImportError:
    def chunk_text(t): return [t]

try:
    from utils.tagging import extract_tags
except ImportError:
    def extract_tags(t): return []

try:
    from utils.language_detect import detect_language
except ImportError:
    def detect_language(t): return "en"

# 🚨 DO NOT remove — same rule as blog_scraper.py
from scoring.trust_score import compute_trust_score


# ── Transcript helpers ──────────────────────────────────────────────────────

def _fetch_transcript_ytdlp(video_id: str) -> str:
    """
    Uses yt-dlp to download auto-generated or manual subtitles
    and returns them as a plain-text string.
    Returns "" if no subtitles found.
    """
    import tempfile, os, glob

    ydl_opts = {
        "skip_download": True,
        "writeautomaticsub": True,
        "writesubtitles": True,
        "subtitleslangs": ["en"],
        "subtitlesformat": "vtt",
        "outtmpl": tempfile.gettempdir() + "/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        # Find the downloaded .vtt file
        pattern = os.path.join(tempfile.gettempdir(), f"{video_id}*.vtt")
        files = glob.glob(pattern)
        if not files:
            return ""

        with open(files[0], "r", encoding="utf-8") as f:
            raw = f.read()

        # Clean VTT formatting — remove timestamps and tags
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("WEBVTT") or "-->" in line:
                continue
            if re.match(r"^\d+$", line):
                continue
            # Strip inline tags like <00:00:01.000><c>word</c>
            clean = re.sub(r"<[^>]+>", "", line).strip()
            if clean:
                lines.append(clean)

        # Deduplicate consecutive duplicate lines (common in auto-subs)
        deduped = []
        for line in lines:
            if not deduped or line != deduped[-1]:
                deduped.append(line)

        # Cleanup temp files
        for f in files:
            try:
                os.remove(f)
            except OSError:
                pass

        return " ".join(deduped)

    except Exception as e:
        print(f"  [yt-dlp transcript] failed for {video_id}: {e}")
        return ""


def _fetch_transcript_api(video_id: str) -> str:
    """
    Fallback: uses youtube-transcript-api (no cookies needed).
    Returns "" on failure.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        entries = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(e["text"] for e in entries)
    except Exception as e:
        print(f"  [youtube-transcript-api] failed for {video_id}: {e}")
        return ""


def _get_transcript(video_id: str) -> str:
    """Try yt-dlp first, then youtube-transcript-api as fallback."""
    transcript = _fetch_transcript_ytdlp(video_id)
    if not transcript:
        print("  Trying youtube-transcript-api as fallback...")
        transcript = _fetch_transcript_api(video_id)
    return transcript


# ── Metadata helper ─────────────────────────────────────────────────────────

def _extract_video_id(url: str) -> str:
    """Extracts the 11-char video ID from any YouTube URL format."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url}")


def _fetch_metadata(url: str) -> dict:
    """
    Uses yt-dlp to extract video metadata without downloading the video.
    Returns a dict with keys: title, channel, upload_date, description,
    view_count, like_count, tags, duration.
    """
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # Normalise upload_date: "20230415" → "2023-04-15"
    raw_date = info.get("upload_date", "")
    if raw_date and len(raw_date) == 8:
        published_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
    else:
        published_date = raw_date

    return {
        "title":          info.get("title", ""),
        "channel":        info.get("channel") or info.get("uploader", ""),
        "published_date": published_date,
        "description":    info.get("description", "") or "",
        "view_count":     info.get("view_count", 0),
        "like_count":     info.get("like_count", 0),
        "tags":           info.get("tags", []),          # YouTube's own tags
        "duration":       info.get("duration", 0),       # seconds
        "webpage_url":    info.get("webpage_url", url),
    }


# ── Citation proxy for YouTube ──────────────────────────────────────────────

def _youtube_citation_proxy(view_count: int, like_count: int) -> int:
    """
    YouTube has no citation count like academic papers.
    We approximate it from engagement so trust_score stays meaningful:
      - Every 10 000 views  → 1 proxy citation
      - Every 1 000 likes   → 1 proxy citation
    Capped at 100 (same ceiling used in trust_score.py).
    """
    proxy = (view_count // 10_000) + (like_count // 1_000)
    return min(proxy, 100)


# ── Main scraper class ──────────────────────────────────────────────────────

class YouTubeScraper:
    """Scrapes a single YouTube video and returns a structured dict."""

    def scrape(self, url: str) -> dict:
        print(f"\n[YouTubeScraper] Scraping: {url}")

        # ── Step 1: video ID ──
        video_id = _extract_video_id(url)

        # ── Step 2: metadata ──
        print("  Fetching metadata...")
        meta = _fetch_metadata(url)

        # ── Step 3: transcript ──
        print("  Fetching transcript...")
        transcript = _get_transcript(video_id)

        if not transcript:
            print("  ⚠ No transcript available — using description as content.")

        # ── Step 4: build full content for downstream NLP ──
        # Combine description + transcript so tagging & chunking are useful
        # even when transcript is empty.
        full_content = " ".join(filter(None, [
            meta["description"],
            transcript,
        ])).strip()

        # ── Step 5: language detection ──
        language = detect_language(full_content) if full_content else "unknown"

        # ── Step 6: topic tagging ──
        # Merge YouTube's own tags with KeyBERT tags for richer coverage
        youtube_tags = [t.lower() for t in meta["tags"][:5]]
        keybert_tags = extract_tags(full_content) if full_content else []
        # Deduplicate while keeping order
        seen = set()
        topic_tags = []
        for tag in youtube_tags + keybert_tags:
            if tag not in seen:
                seen.add(tag)
                topic_tags.append(tag)
        topic_tags = topic_tags[:10]   # cap at 10

        # ── Step 7: chunking ──
        # Prefer transcript for chunking; fall back to description
        chunk_source = transcript if transcript else meta["description"]
        chunks = chunk_text(chunk_source) if chunk_source else []

        # ── Step 8: trust score ──
        citation_proxy = _youtube_citation_proxy(
            meta["view_count"], meta["like_count"]
        )
        medical_disclaimer = (
            "not medical advice" in full_content.lower()
            or "consult a doctor" in full_content.lower()
            or "consult your physician" in full_content.lower()
        )

        trust = compute_trust_score(
            url=meta["webpage_url"],
            author=meta["channel"],
            published_date=meta["published_date"],
            citation_count=citation_proxy,
            has_medical_disclaimer=medical_disclaimer,
        )

        # ── Step 9: assemble output (same schema as blog_scraper.py) ──
        return {
            "source_url":     meta["webpage_url"],
            "source_type":    "youtube",
            "title":          meta["title"],
            "author":         meta["channel"],       # channel = author for YT
            "published_date": meta["published_date"],
            "language":       language,
            "region":         "global",              # YT doesn't expose region
            "topic_tags":     topic_tags,
            "trust_score":    trust,
            "content_chunks": chunks,
            # Extra YouTube-specific fields (bonus data)
            "duration_seconds": meta["duration"],
            "view_count":       meta["view_count"],
            "transcript_available": bool(transcript),
        }


# ── Convenience wrapper (mirrors scrape_blog) ───────────────────────────────

def scrape_youtube(url: str) -> dict:
    scraper = YouTubeScraper()
    return scraper.scrape(url)


# ── Batch scraper ────────────────────────────────────────────────────────────

def scrape_youtube_videos(urls: list) -> list:
    """Scrape multiple YouTube URLs and return a list of result dicts."""
    results = []
    for url in urls:
        try:
            result = scrape_youtube(url)
            results.append(result)
        except Exception as e:
            print(f"[ERROR] Failed to scrape {url}: {e}")
            results.append({
                "source_url":   url,
                "source_type":  "youtube",
                "error":        str(e),
            })
    return results


# ── CLI / standalone run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # ✅ 3 YouTube videos as required by the assignment
    YOUTUBE_URLS = [
        "https://www.youtube.com/watch?v=aircAruvnKk",   # 3Blue1Brown: Neural Networks
        "https://www.youtube.com/watch?v=kCc8FmEb1nY",   # Andrej Karpathy: GPT from scratch
        "https://www.youtube.com/watch?v=R9OHn5ZF4Uo",   # StatQuest: Machine Learning
    ]

    results = scrape_youtube_videos(YOUTUBE_URLS)

    # Save to output/youtube.json (same pattern as blog_scraper.py)
    import os
    os.makedirs("output", exist_ok=True)
    output_path = os.path.join("output", "youtube.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(results)} videos to {output_path}")
    print(json.dumps(results, indent=2, ensure_ascii=False))