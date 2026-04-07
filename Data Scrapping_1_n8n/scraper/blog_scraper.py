import re
import json
import time
import requests
from bs4 import BeautifulSoup
from newspaper import Article
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from requests.exceptions import RequestException
from json import JSONDecodeError

# Local utils (with fallback)
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


class BlogScraper:
    def __init__(self):
        self.driver = None

    def _init_driver(self):
        if self.driver is None:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--disable-blink-features=AutomationControlled")

            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _extract_metadata(self, soup):
        metadata = {
            "title": soup.title.get_text(strip=True) if soup.title else "",
            "author": "",
            "date": ""
        }

        # JSON-LD (best source)
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]

                for item in items:
                    if isinstance(item, dict):
                        if "author" in item:
                            auth = item["author"]
                            metadata["author"] = (
                                auth.get("name") if isinstance(auth, dict)
                                else str(auth)
                            )
                        if "datePublished" in item:
                            metadata["date"] = item["datePublished"]

            except (JSONDecodeError, TypeError, AttributeError):
                continue

        # fallback meta
        if not metadata["author"]:
            tag = soup.find("meta", {"name": "author"})
            if tag:
                metadata["author"] = tag.get("content", "")

        if not metadata["date"]:
            time_tag = soup.find("time")
            if time_tag:
                metadata["date"] = (
                    time_tag.get("datetime")
                    or time_tag.get_text(strip=True)
                )

        return metadata

    def _clean_content(self, text):
        if not text:
            return ""

        index = text.rfind("©")
        if index > len(text) * 0.85:
            text = text[:index]

        text = re.sub(r"\s+", " ", text).strip()
        return text

    def scrape(self, url):
        is_blocked = False
        content = ""
        soup = None
        meta = {"title": "", "author": "", "date": ""}

        # -------- PHASE 1: requests --------
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            is_blocked = any(x in html.lower() for x in [
                "cloudflare", "just a moment", "enable javascript"
            ])

            meta = self._extract_metadata(soup)

            paragraphs = soup.find_all("p")
            content = " ".join([p.get_text() for p in paragraphs])

        except RequestException as e:
            print("Request failed:", e)
            is_blocked = True

        # -------- PHASE 2: newspaper --------
        if is_blocked or len(content) < 300:
            try:
                article = Article(url)
                article.download()
                article.parse()

                if len(article.text) > len(content):
                    content = article.text
                    meta["title"] = article.title or meta["title"]
                    meta["author"] = ", ".join(article.authors) or meta["author"]

                    if article.publish_date:
                        meta["date"] = str(article.publish_date)

                    is_blocked = False

            except Exception as e:
                print("Newspaper failed:", e)

        # -------- PHASE 3: selenium --------
        if is_blocked or len(content) < 300:
            print("Using Selenium...")

            try:
                self._init_driver()
                self.driver.get(url)
                time.sleep(5)

                soup = BeautifulSoup(self.driver.page_source, "html.parser")

                new_meta = self._extract_metadata(soup)
                for key in meta:
                    if not meta[key] and new_meta[key]:
                        meta[key] = new_meta[key]

                container = soup.find("article") or soup.find("main") or soup
                paragraphs = container.find_all("p")
                content = " ".join([p.get_text() for p in paragraphs])

                is_blocked = False

            except Exception as e:
                print("Selenium failed:", e)

        # -------- CITATIONS --------
        try:
            if soup:
                links = soup.find_all("a", href=True)
                citation_count = len([
                    a for a in links
                    if a["href"].startswith("http") and url not in a["href"]
                ])
            else:
                citation_count = 0
        except:
            citation_count = 0

        # -------- POST --------
        content = self._clean_content(content)

        language = detect_language(content) if content else "unknown"
        tags = extract_tags(content) if content else []
        chunks = chunk_text(content) if content else []

        return {
            "source_url": url,
            "source_type": "blog",
            "title": meta["title"] or "",
            "author": meta["author"],
            "published_date": meta["date"],
            "language": language,
            "region": "global",
            "topic_tags": tags,
            "trust_score": compute_trust_score(
                url=url,
                author=meta["author"],
                published_date=meta["date"],
                citation_count=citation_count,
                has_medical_disclaimer=("not medical advice" in content.lower())
            ),
            "content_chunks": chunks,
            "is_blocked": is_blocked
        }


# wrapper
def scrape_blog(url):
    scraper = BlogScraper()
    try:
        return scraper.scrape(url)
    finally:
        scraper.close()