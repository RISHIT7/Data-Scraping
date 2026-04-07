import re
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

# Internal imports with safety fallbacks
try:
    from utils.chunking import chunk_text
    from utils.tagging import extract_tags
    from utils.language_detect import detect_language
except ImportError:
    # Minimal fallbacks if running as a standalone script
    def chunk_text(t): return [t]
    def extract_tags(t): return []
    def detect_language(t): return "en"

from scoring.trust_score import compute_trust_score

def get_page_soup(url):
    """Simple wrapper to grab HTML with a browser-like User-Agent."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except RequestException as e:
        print(f"Error fetching PubMed page: {e}")
        return None

def extract_meta_content(soup, meta_name):
    """Helper to pull content from PubMed's meta tags."""
    tag = soup.find("meta", {"name": meta_name})
    return tag["content"].strip() if tag and tag.get("content") else ""

def parse_abstract(soup):
    """Finds and cleans the abstract text."""
    # Try the main div first, then the fallback class
    container = soup.find("div", id="abstract") or soup.find("div", class_="abstract-content")
    if not container:
        return ""

    # PubMed abstracts often have <strong> labels like 'METHODS:' — we strip those for clean text
    for label in container.find_all("strong"):
        label.decompose()
        
    return container.get_text(separator=" ", strip=True)

def scrape_pubmed(url):
    """
    Main function to scrape a PubMed article and return a standardized dict.
    Maps to the same schema as our blog and YouTube scrapers.
    """
    print(f"--- Processing PubMed Article: {url} ---")
    
    soup = get_page_soup(url)
    
    if not soup:
        return {
            "source_url": url, "source_type": "pubmed", "title": "Failed to load",
            "author": "", "published_date": "", "language": "en", "region": "global",
            "topic_tags": [], "trust_score": 0.0, "content_chunks": [], "is_blocked": True
        }

    # 1. Basic Metadata (Meta tags are more reliable than HTML scraping for PubMed)
    title = extract_meta_content(soup, "citation_title")
    authors = [m["content"].strip() for m in soup.find_all("meta", {"name": "citation_author"})]
    author_str = ", ".join(authors)
    pub_date = extract_meta_content(soup, "citation_date")
    journal = extract_meta_content(soup, "citation_journal_title")
    
    # 2. Content & References
    abstract = parse_abstract(soup)
    # Use bibliography count as a proxy for 'citation_count' in the trust score
    ref_count = len(soup.select("ol.references li, li.skip-numbering"))

    # Combine for processing
    full_text = f"{title}. {journal}. {abstract}"
    
    # 3. Utilities for NLP processing
    lang = detect_language(full_text)
    tags = extract_tags(full_text)
    chunks = chunk_text(full_text)

    # 4. Trust Logic
    # Check for medical disclaimers in the abstract
    med_triggers = ["not medical advice", "consult your doctor", "physician"]
    has_disclaimer = any(word in abstract.lower() for word in med_triggers)

    return {
        "source_url": url,
        "source_type": "pubmed",
        "title": title or "Unknown Title",
        "author": author_str,
        "published_date": pub_date,
        "language": lang,
        "region": "global",
        "topic_tags": tags,
        "trust_score": compute_trust_score(
            url=url,
            author=author_str,
            published_date=pub_date,
            citation_count=ref_count,
            has_medical_disclaimer=has_disclaimer,
            source_type="pubmed"
        ),
        "content_chunks": chunks,
        "is_blocked": False
    }