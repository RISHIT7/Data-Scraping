"""
scoring/trust_score.py
Trust Score Algorithm — range 0.0 to 1.0
Handles edge cases, multiple authors, abuse prevention
"""

import re
from datetime import datetime
from urllib.parse import urlparse


# ─────────────────────────────────────────────
# Known credible organizations / author signals
# ─────────────────────────────────────────────
CREDIBLE_ORGS = [
    "mit", "stanford", "harvard", "oxford", "nature", "who", "cdc",
    "nih", "pubmed", "ncbi", "ieee", "acm", "deepmind", "openai",
    "anthropic", "google", "microsoft research", "meta ai"
]

CREDIBLE_CREDENTIALS = ["dr", "md", "phd", "professor", "prof"]

# Domains known for SEO spam / low quality
SPAM_DOMAINS = [
    "buzzfeed.com", "listverse.com", "toptenz.net", "scoopwhoop.com",
    "viralnova.com", "distractify.com"
]

# High authority domains
HIGH_AUTHORITY_DOMAINS = [".gov", ".edu", "pubmed", "ncbi", "nature.com",
                           "science.org", "thelancet.com", "nejm.org"]
GOOD_AUTHORITY_DOMAINS = ["youtube.com", "github.com", "arxiv.org",
                           "towardsdatascience.com", "realpython.com"]
MEDIUM_AUTHORITY_DOMAINS = ["medium.com", "substack.com", "hashnode.com",
                             "dev.to", "blogger.com"]


# ─────────────────────────────────────────────
# Individual scoring components
# ─────────────────────────────────────────────

def compute_recency_score(published_date) -> float:
    """
    Recency scoring with strong penalty for outdated content.
    - < 1 year old  → 1.0
    - 1–2 years     → 0.8
    - 2–5 years     → 0.6
    - 5–10 years    → 0.3
    - > 10 years    → 0.1
    - Missing date  → 0.3 (unknown penalty)
    """
    if not published_date:
        return 0.3  # missing date penalty

    try:
        year = int(str(published_date)[:4])
        if year < 1900 or year > datetime.now().year:
            return 0.2  # implausible date
        years_old = datetime.now().year - year
        if years_old < 1:
            return 1.0
        elif years_old <= 2:
            return 0.8
        elif years_old <= 5:
            return 0.6
        elif years_old <= 10:
            return 0.3
        else:
            return 0.1  # strong recency penalty for > 10 years
    except:
        return 0.3


def compute_domain_score(url: str) -> float:
    """
    Domain authority scoring + spam domain penalty.
    Abuse prevention: penalizes known SEO spam domains.
    """
    if not url:
        return 0.2

    try:
        domain = urlparse(url).netloc.lower()
    except:
        domain = url.lower()

    # Abuse prevention: penalize spam domains
    for spam in SPAM_DOMAINS:
        if spam in domain:
            return 0.1

    # High authority
    for d in HIGH_AUTHORITY_DOMAINS:
        if d in domain:
            return 0.9

    # Good authority
    for d in GOOD_AUTHORITY_DOMAINS:
        if d in domain:
            return 0.75

    # Medium authority
    for d in MEDIUM_AUTHORITY_DOMAINS:
        if d in domain:
            return 0.5

    return 0.4  # unknown domain default


def compute_author_score(author) -> float:
    """
    Author credibility scoring.
    Handles:
    - Missing author       → penalty
    - Multiple authors     → average score
    - Credentials (Dr/PhD) → boost
    - Known org match      → boost
    - Fake/generic names   → penalty (abuse prevention)
    """
    if not author:
        return 0.2  # missing author penalty

    # Handle multiple authors — split by comma or semicolon
    authors = [a.strip() for a in re.split(r"[,;]", str(author)) if a.strip()]

    if not authors:
        return 0.2

    def score_single_author(name: str) -> float:
        name_lower = name.lower()

        # Abuse prevention: suspicious generic names
        suspicious = ["admin", "editor", "staff", "anonymous", "unknown",
                       "user", "guest", "webmaster", "info"]
        if any(s == name_lower for s in suspicious):
            return 0.1

        # Abuse prevention: very short names (< 3 chars) likely fake
        if len(name) < 3:
            return 0.1

        score = 0.5  # base score for named author

        # Credential boost
        if any(cred in name_lower for cred in CREDIBLE_CREDENTIALS):
            score += 0.3

        # Known organization boost
        if any(org in name_lower for org in CREDIBLE_ORGS):
            score += 0.2

        return min(score, 1.0)

    # Average across all authors
    scores = [score_single_author(a) for a in authors]
    return round(sum(scores) / len(scores), 3)


def compute_citation_score(citation_count: int) -> float:
    """
    Citation count scoring with diminishing returns.
    - 0 citations   → 0.0
    - 1–10          → 0.3
    - 10–50         → 0.6
    - 50–100        → 0.8
    - 100+          → 1.0
    """
    if not citation_count or citation_count <= 0:
        return 0.0
    elif citation_count <= 10:
        return 0.3
    elif citation_count <= 50:
        return 0.6
    elif citation_count <= 100:
        return 0.8
    else:
        return 1.0


def compute_disclaimer_score(has_medical_disclaimer: bool,
                              url: str,
                              source_type: str) -> float:
    """
    Medical disclaimer scoring.
    Abuse prevention: medical/health content WITHOUT disclaimer is penalized.
    Non-medical content is not penalized for lacking a disclaimer.
    """
    medical_signals = ["pubmed", "ncbi", "health", "medical", "clinical",
                        "drug", "treatment", "disease", "patient"]

    is_medical = (
        source_type == "pubmed" or
        any(s in url.lower() for s in medical_signals)
    )

    if is_medical:
        # Medical content MUST have disclaimer
        return 1.0 if has_medical_disclaimer else 0.1
    else:
        # Non-medical: disclaimer is a bonus, not required
        return 0.8 if has_medical_disclaimer else 0.7


# ─────────────────────────────────────────────
# Abuse prevention: final score manipulation guard
# ─────────────────────────────────────────────

def apply_abuse_penalties(score: float, url: str, author: str,
                           published_date, citation_count: int) -> float:
    """
    Final layer of abuse prevention checks.
    Applies hard penalties for clear manipulation signals.
    """
    penalty = 0.0

    # Penalty: implausibly high citations for very new content
    try:
        year = int(str(published_date)[:4])
        years_old = datetime.now().year - year
        if years_old < 1 and citation_count > 500:
            penalty += 0.2  # suspicious: too many citations too fast
    except:
        pass

    # Penalty: URL has excessive query params (SEO spam signal)
    try:
        query = urlparse(url).query
        if query.count("&") > 5:
            penalty += 0.1
    except:
        pass

    # Penalty: no author + no date = very low trust
    if not author and not published_date:
        penalty += 0.2

    return round(max(0.0, score - penalty), 3)


# ─────────────────────────────────────────────
# Main function
# ─────────────────────────────────────────────

def compute_trust_score(
    url: str,
    author: str,
    published_date,
    citation_count: int = 0,
    has_medical_disclaimer: bool = False,
    source_type: str = ""
) -> float:
    """
    Final trust score in range [0.0, 1.0].

    Weights:
        author_credibility      25%
        citation_count          20%
        domain_authority        20%
        recency                 20%
        medical_disclaimer      15%
    """
    author_score     = compute_author_score(author)
    domain_score     = compute_domain_score(url)
    recency_score    = compute_recency_score(published_date)
    citation_score   = compute_citation_score(citation_count)
    disclaimer_score = compute_disclaimer_score(
                           has_medical_disclaimer, url, source_type)

    raw_score = (
        0.25 * author_score +
        0.20 * citation_score +
        0.20 * domain_score +
        0.20 * recency_score +
        0.15 * disclaimer_score
    )

    # Apply abuse prevention penalties
    final_score = apply_abuse_penalties(
        raw_score, url, author, published_date, citation_count
    )

    return round(min(max(final_score, 0.0), 1.0), 3)