import re
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
from json import JSONDecodeError

# Local utils (with fallback) — same as blog_scraper.py
try:
    from utils.chunking import chunk_text
except:
    def chunk_text(t): return [t]

try:
    from utils.tagging import extract_tags
except:
    def extract_tags(t): return []

try:
    from utils.language_detect import detect_language
except:
    def detect_language(t): return "en"

# 🚨 IMPORTANT: DO NOT FALLBACK THIS
from scoring.trust_score import compute_trust_score


class PubMedScraper:
    """
    Scrapes a single PubMed article page and returns a structured dict
    that matches the same schema used by BlogScraper and YouTubeScraper.

    Supported URL formats:
        https://pubmed.ncbi.nlm.nih.gov/XXXXXXXX/
        https://pubmed.ncbi.nlm.nih.gov/XXXXXXXX
    """

    BASE_URL = "https://pubmed.ncbi.nlm.nih.gov"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_pmid(self, url: str) -> str:
        """Extract the numeric PubMed ID from the URL."""
        match = re.search(r"/(\d+)/?$", url)
        return match.group(1) if match else ""

    def _fetch_html(self, url: str) -> BeautifulSoup | None:
        """Download the PubMed article page and return a BeautifulSoup object."""
        headers = {
            # Mimic a real browser so NCBI doesn't return a bot-check page
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except RequestException as e:
            print(f"[PubMedScraper] Request failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Metadata extraction
    # ------------------------------------------------------------------

    def _extract_title(self, soup: BeautifulSoup) -> str:
        tag = soup.find("h1", class_="heading-title")
        if tag:
            return tag.get_text(strip=True)
        # fallback: <meta name="citation_title">
        meta = soup.find("meta", {"name": "citation_title"})
        return meta["content"].strip() if meta else ""

    def _extract_authors(self, soup: BeautifulSoup) -> str:
        """
        Returns a comma-separated string of author full names.
        PubMed renders authors inside <span class="authors-list-item">.
        """
        # Primary: <meta name="citation_author"> tags (one per author)
        metas = soup.find_all("meta", {"name": "citation_author"})
        if metas:
            return ", ".join(m["content"].strip() for m in metas)

        # Fallback: visible author list
        author_tags = soup.select(".authors-list .authors-list-item a.full-name")
        if author_tags:
            return ", ".join(a.get_text(strip=True) for a in author_tags)

        return ""

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """
        Returns the publication date as a string (e.g. '2024 Mar 15').
        Checks <meta name="citation_date"> first, then the visible date span.
        """
        meta = soup.find("meta", {"name": "citation_date"})
        if meta:
            return meta["content"].strip()

        # Fallback: span.cit inside the citation section
        cit = soup.find("span", class_="cit")
        if cit:
            # Typical text: "2024 Mar 15;14(3):e012345. doi:…"
            return cit.get_text(strip=True).split(";")[0].strip()

        return ""

    def _extract_abstract(self, soup: BeautifulSoup) -> str:
        """
        Returns the full abstract text, stripping section labels
        (BACKGROUND, METHODS, RESULTS, CONCLUSIONS, etc.).
        """
        # PubMed wraps the abstract in <div id="abstract">
        abstract_div = soup.find("div", id="abstract")
        if not abstract_div:
            # Older layout fallback
            abstract_div = soup.find("div", class_="abstract-content")

        if not abstract_div:
            return ""

        # Each labelled section is a <p> — grab all of them
        paragraphs = abstract_div.find_all("p")
        if paragraphs:
            parts = []
            for p in paragraphs:
                # Remove the <strong> section label if present
                for strong in p.find_all("strong", class_="sub-title"):
                    strong.decompose()
                text = p.get_text(separator=" ", strip=True)
                if text:
                    parts.append(text)
            return " ".join(parts)

        return abstract_div.get_text(separator=" ", strip=True)

    def _extract_journal(self, soup: BeautifulSoup) -> str:
        meta = soup.find("meta", {"name": "citation_journal_title"})
        if meta:
            return meta["content"].strip()
        tag = soup.find("button", class_="journal-actions-trigger")
        return tag.get_text(strip=True) if tag else ""

    def _extract_doi(self, soup: BeautifulSoup) -> str:
        meta = soup.find("meta", {"name": "citation_doi"})
        if meta:
            return meta["content"].strip()
        # Fallback: look for the doi link in the identifiers section
        doi_link = soup.find("a", class_="id-link", href=re.compile(r"doi\.org"))
        return doi_link.get_text(strip=True) if doi_link else ""

    def _extract_citation_count(self, soup: BeautifulSoup) -> int:
        """
        PubMed doesn't expose citation counts directly on the article page,
        but we can count the number of references (bibliography) as a proxy.
        """
        refs = soup.find_all("li", class_="skip-numbering")
        if refs:
            return len(refs)
        # Alternative: ol.references li
        ref_list = soup.select("ol.references li")
        return len(ref_list)

    def _has_medical_disclaimer(self, text: str) -> bool:
        disclaimers = [
            "not medical advice",
            "consult a physician",
            "consult your doctor",
            "this information is not intended",
        ]
        lower = text.lower()
        return any(d in lower for d in disclaimers)

    # ------------------------------------------------------------------
    # Public scrape method
    # ------------------------------------------------------------------

    def scrape(self, url: str) -> dict:
        print(f"[PubMedScraper] Scraping: {url}")

        soup = self._fetch_html(url)

        if soup is None:
            # Return a minimal failed record — same shape as a success record
            return {
                "source_url": url,
                "source_type": "pubmed",
                "title": "",
                "author": "",
                "published_date": "",
                "language": "en",
                "region": "global",
                "topic_tags": [],
                "trust_score": 0.0,
                "content_chunks": [],
                "is_blocked": True,
            }

        title       = self._extract_title(soup)
        author      = self._extract_authors(soup)
        date        = self._extract_date(soup)
        abstract    = self._extract_abstract(soup)
        doi         = self._extract_doi(soup)
        journal     = self._extract_journal(soup)
        cite_count  = self._extract_citation_count(soup)

        # Build the full content string that the shared utils will process
        # Include journal and DOI so taggers / chunkers see them
        full_content = " ".join(filter(None, [title, journal, abstract]))

        language = detect_language(full_content) if full_content else "en"
        tags     = extract_tags(full_content) if full_content else []
        chunks   = chunk_text(full_content) if full_content else []

        return {
            "source_url":       url,
            "source_type":      "pubmed",
            "title":            title,
            "author":           author,
            "published_date":   date,
            "language":         language,
            "region":           "global",
            "topic_tags":       tags,
            "trust_score": compute_trust_score(
                url=url,
                author=author,
                published_date=date,
                citation_count=cite_count,
                has_medical_disclaimer=self._has_medical_disclaimer(abstract),
            ),
            "content_chunks":   chunks,
            "is_blocked":       False,
        }


# ------------------------------------------------------------------
# Module-level wrapper — mirrors scrape_blog(url) pattern exactly
# ------------------------------------------------------------------

def scrape_pubmed(url: str) -> dict:
    scraper = PubMedScraper()
    return scraper.scrape(url)