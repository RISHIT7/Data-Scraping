import os
import re
import json
import yt_dlp
import tempfile
import glob
from datetime import datetime

# Import local processing tools with safety fallbacks
try:
    from utils.chunking import chunk_text
    from utils.tagging import extract_tags
    from utils.language_detect import detect_language
except ImportError:
    def chunk_text(t): return [t]
    def extract_tags(t): return []
    def detect_language(t): return "en"

from scoring.trust_score import compute_trust_score

def clean_vtt_content(vtt_text):
    """
    Cleans raw VTT subtitle data into readable sentences.
    Removes timestamps, WEBVTT headers, and duplicate 'scrolling' lines.
    """
    lines = []
    for line in vtt_text.splitlines():
        line = line.strip()
        # Skip VTT junk and timestamps
        if not line or line.startswith("WEBVTT") or "-->" in line or line.isdigit():
            continue
        
        # Strip inline style/time tags like <00:00:01.000>
        clean_line = re.sub(r"<[^>]+>", "", line).strip()
        if clean_line:
            lines.append(clean_line)

    # Filter out consecutive identical lines (common in auto-generated subs)
    final_lines = []
    for l in lines:
        if not final_lines or l != final_lines[-1]:
            final_lines.append(l)
            
    return " ".join(final_lines)

def get_transcript(video_id):
    """
    Attempts to pull transcripts using yt-dlp first (more reliable), 
    then falls back to the youtube-transcript-api.
    """
    tmp_dir = tempfile.gettempdir()
    ydl_opts = {
        "skip_download": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "outtmpl": f"{tmp_dir}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        # Check for the downloaded .vtt file
        vtt_files = glob.glob(os.path.join(tmp_dir, f"{video_id}*.vtt"))
        if vtt_files:
            with open(vtt_files[0], "r", encoding="utf-8") as f:
                content = clean_vtt_content(f.read())
            # Cleanup temp file
            for f in vtt_files: os.remove(f)
            return content
    except Exception as e:
        print(f"yt-dlp failed for {video_id}, trying API fallback...")

    # Fallback to the dedicated API
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        data = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([item["text"] for item in data])
    except:
        return ""

def scrape_youtube(url):
    """
    Main scraper: extracts metadata and transcript, then computes trust score.
    Maps results to the standardized project schema.
    """
    print(f"Scraping YouTube: {url}")
    
    # 1. Extract ID and Metadata
    id_match = re.search(r"(?:v=|be/|embed/|shorts/)([A-Za-z0-9_-]{11})", url)
    if not id_match:
        return {"url": url, "error": "Invalid ID"}
    
    video_id = id_match.group(1)

    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)

    # Date normalization (YYYYMMDD to YYYY-MM-DD)
    raw_date = info.get("upload_date", "")
    pub_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date

    # 2. Get Content (Transcript + Description)
    transcript = get_transcript(video_id)
    description = info.get("description") or ""
    full_text = f"{description} {transcript}".strip()

    # 3. Processing (NLP)
    lang = detect_language(full_text) if full_text else "en"
    
    # Merge YT tags with our own NLP tags
    yt_tags = [t.lower() for t in info.get("tags", [])[:5]]
    nlp_tags = extract_tags(full_text) if full_text else []
    merged_tags = list(dict.fromkeys(yt_tags + nlp_tags))[:10] # Deduplicate

    # 4. Trust Evaluation
    # Since YT lacks academic citations, we use a proxy: (views / 10k) + (likes / 1k)
    views = info.get("view_count", 0)
    likes = info.get("like_count", 0)
    cite_proxy = min((views // 10000) + (likes // 1000), 100)

    # Check for medical disclaimers
    med_terms = ["not medical advice", "consult a doctor", "professional advice"]
    has_disclaimer = any(term in full_text.lower() for term in med_terms)

    return {
        "source_url": info.get("webpage_url", url),
        "source_type": "youtube",
        "title": info.get("title"),
        "author": info.get("uploader") or info.get("channel"),
        "published_date": pub_date,
        "language": lang,
        "region": "global",
        "topic_tags": merged_tags,
        "trust_score": compute_trust_score(
            url=url,
            author=info.get("uploader"),
            published_date=pub_date,
            citation_count=cite_proxy,
            has_medical_disclaimer=has_disclaimer
        ),
        "content_chunks": chunk_text(transcript if transcript else description),
        "metadata": {
            "views": views,
            "likes": likes,
            "duration_min": round(info.get("duration", 0) / 60, 2)
        }
    }

if __name__ == "__main__":
    urls = [
        "https://www.youtube.com/watch?v=aircAruvnKk",
        "https://www.youtube.com/watch?v=kCc8FmEb1nY"
    ]
    
    all_data = [scrape_youtube(u) for u in urls]
    
    os.makedirs("output", exist_ok=True)
    with open("output/youtube.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)
    
    print(f"Finished. Saved {len(all_data)} videos to output/youtube.json")