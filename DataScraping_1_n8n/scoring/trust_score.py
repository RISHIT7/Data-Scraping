from datetime import datetime
from urllib.parse import urlparse
import re


# these are orgs/credentials i'm treating as more trustworthy
TRUSTED_ORGS = [
    "mit", "stanford", "harvard", "oxford", "nature", "who", "cdc",
    "nih", "pubmed", "ncbi", "ieee", "acm", "deepmind", "openai",
    "anthropic", "google", "microsoft research", "meta ai"
]

GOOD_CREDENTIALS = ["dr", "md", "phd", "professor", "prof"]

# sites i've flagged as clickbait/spam
SPAM_SITES = [
    "buzzfeed.com", "listverse.com", "toptenz.net",
    "scoopwhoop.com", "viralnova.com", "distractify.com"
]

# rough tiers of domain quality
TOP_DOMAINS    = [".gov", ".edu", "pubmed", "ncbi", "nature.com",
                  "science.org", "thelancet.com", "nejm.org"]
GOOD_DOMAINS   = ["youtube.com", "github.com", "arxiv.org",
                  "towardsdatascience.com", "realpython.com"]
OK_DOMAINS     = ["medium.com", "substack.com", "hashnode.com",
                  "dev.to", "blogger.com"]


# --- how old is this content? ---

def recency_score(date_published) -> float:
    if not date_published:
        return 0.3

    try:
        year = int(str(date_published)[:4])
        if year < 1900 or year > datetime.now().year:
            return 0.2

        age = datetime.now().year - year
        if age < 1:   return 1.0
        if age <= 2:  return 0.8
        if age <= 5:  return 0.6
        if age <= 10: return 0.3
        return 0.1

    except:
        return 0.3


# --- how trustworthy is the domain? ---

def domain_score(url: str) -> float:
    if not url:
        return 0.2

    try:
        domain = urlparse(url).netloc.lower()
    except:
        domain = url.lower()

    if any(s in domain for s in SPAM_SITES):
        return 0.1

    if any(d in domain for d in TOP_DOMAINS):
        return 0.9

    if any(d in domain for d in GOOD_DOMAINS):
        return 0.75

    if any(d in domain for d in OK_DOMAINS):
        return 0.5

    return 0.4


# --- how credible is the author? ---

def author_score(author) -> float:
    if not author:
        return 0.2

    # split if there are multiple authors listed
    names = [n.strip() for n in re.split(r"[,;]", str(author)) if n.strip()]
    if not names:
        return 0.2

    def score_one(name: str) -> float:
        n = name.lower()

        # generic/fake-sounding names get penalized
        fake_names = ["admin", "editor", "staff", "anonymous",
                      "unknown", "user", "guest", "webmaster", "info"]
        if n in fake_names or len(name) < 3:
            return 0.1

        score = 0.5  # baseline for any real-looking name

        if any(c in n for c in GOOD_CREDENTIALS):
            score += 0.3

        if any(org in n for org in TRUSTED_ORGS):
            score += 0.2

        return min(score, 1.0)

    all_scores = [score_one(n) for n in names]
    return round(sum(all_scores) / len(all_scores), 3)


# --- citation count (or engagement proxy for youtube) ---

def citation_score(count: int) -> float:
    if not count or count <= 0: return 0.0
    if count <= 10:  return 0.3
    if count <= 50:  return 0.6
    if count <= 100: return 0.8
    return 1.0


# --- does it have a medical disclaimer where needed? ---

def disclaimer_score(has_disclaimer: bool, url: str, source_type: str) -> float:
    medical_keywords = ["pubmed", "ncbi", "health", "medical", "clinical",
                        "drug", "treatment", "disease", "patient"]

    looks_medical = (
        source_type == "pubmed" or
        any(k in url.lower() for k in medical_keywords)
    )

    if looks_medical:
        return 1.0 if has_disclaimer else 0.1
    else:
        return 0.8 if has_disclaimer else 0.7


# --- catch obvious manipulation attempts ---

def abuse_check(score: float, url: str, author: str,
                date_published, citation_count: int) -> float:
    penalty = 0.0

    # brand new content with suspiciously high citations
    try:
        age = datetime.now().year - int(str(date_published)[:4])
        if age < 1 and citation_count > 500:
            penalty += 0.2
    except:
        pass

    # too many query params = SEO spam signal
    try:
        if urlparse(url).query.count("&") > 5:
            penalty += 0.1
    except:
        pass

    # no author AND no date = very low trust
    if not author and not date_published:
        penalty += 0.2

    return round(max(0.0, score - penalty), 3)


# --- the main function everything else calls ---

def compute_trust_score(
    url: str,
    author: str,
    published_date,
    citation_count: int = 0,
    has_medical_disclaimer: bool = False,
    source_type: str = ""
) -> float:

    a = author_score(author)
    d = domain_score(url)
    r = recency_score(published_date)
    c = citation_score(citation_count)
    disc = disclaimer_score(has_medical_disclaimer, url, source_type)

    # weighted combination — author and citations matter most
    raw = (
        0.25 * a +
        0.20 * c +
        0.20 * d +
        0.20 * r +
        0.15 * disc
    )

    final = abuse_check(raw, url, author, published_date, citation_count)
    return round(min(max(final, 0.0), 1.0), 3)