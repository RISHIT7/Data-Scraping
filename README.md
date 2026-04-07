# Data-Scraping
# 🧠 Multi-Source Scraper with Trust Scoring

This project implements a **data scraping pipeline** that extracts structured content from:

- 📰 Blogs  
- 🎥 YouTube Videos  
- 🧬 PubMed Research Articles  

and computes a **Trust Score (0.0 – 1.0)** based on credibility signals.

---

## 🚀 Tools and Libraries Used

### Core Libraries
- `requests` – HTTP requests
- `BeautifulSoup` – HTML parsing
- `newspaper3k` – article extraction
- `selenium` – dynamic content scraping
- `yt-dlp` – YouTube metadata + transcript
- `youtube-transcript-api` – transcript fallback

### NLP & Processing
- `KeyBERT` – topic extraction
- `langdetect` – language detection

### Utilities
- Custom chunking module  
- Trust score algorithm (custom-built)

---

## 🔍 Scraping Approach

### 1. Blog Scraping (Multi-layer Strategy)
1. Requests + BeautifulSoup  
2. Newspaper3k fallback  
3. Selenium fallback (JS-heavy sites)  

✔ Ensures high success rate even for protected websites  

---

### 2. YouTube Scraping (No API Key)
- Uses `yt-dlp` for:
  - Metadata
  - Auto subtitles (VTT)
- Fallback:
  - `youtube-transcript-api`

✔ Avoids API limits and restrictions  
✔ Extracts full transcripts for NLP  

---

### 3. PubMed Scraping
- Extracts:
  - Title
  - Authors
  - Abstract
  - DOI
  - Journal  

- Citation proxy:
  - Number of references  

---

## 🧠 Topic Tagging Method

### 1. KeyBERT
- Extracts semantic keywords from content  
- Based on transformer embeddings  

### 2. Hybrid Tagging (YouTube)
- Combines:
  - YouTube tags  
  - KeyBERT-generated tags  

✔ Example output: deep learning, neural networks, backpropagation, gradient descent


---

## 📊 Trust Score Design

Final score ∈ **[0.0, 1.0]**

### Weighted Components:

| Factor                | Weight |
|---------------------|--------|
| Author credibility   | 25%   |
| Citation count       | 20%   |
| Domain authority     | 20%   |
| Recency              | 20%   |
| Medical disclaimer   | 15%   |

---

### Key Features
- 📉 Recency penalty for outdated content  
- 🚫 Spam domain detection  
- 🧑‍⚕️ Medical disclaimer validation  
- ⚠️ Abuse prevention layer  

---

### YouTube Special Handling

Since YouTube has no citation count: citation_proxy = (views / 10000) + (likes / 1000)


---

## ⚠️ Edge Case Handling

### Blog Scraper
- Cloudflare blocking → Selenium fallback  
- Missing metadata → meta tag extraction  
- Short content → alternate extraction  

---

### YouTube Scraper
- No transcript → fallback to description  
- Duplicate subtitle lines → removed  
- Missing tags → KeyBERT fallback  

---

### PubMed Scraper
- Missing fields → meta fallback  
- No references → citation count = 0  

---

## 📉 Limitations

- Selenium is slower (used only when needed)  
- Some YouTube videos have no transcripts  
- KeyBERT requires sufficient content  
- Trust score is heuristic (not absolute truth)  

---

## ▶️ How to Run the Project

# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the full pipeline
python main.py

### 🏗 Pipeline Architecture
```text 
       [ Input URLs ]
    (Blog / YT / PubMed)
             │
             ▼
┌───────────────────────────┐
│      Scraper Factory      │ (Routing & Fallback Logic)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│     NLP & Enrichment      │ (KeyBERT, LangDetect, Chunking)
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│   Trust Scoring Engine    │ (Weighted Heuristics & Abuse Guard)
└─────────────┬─────────────┘
              │
              ▼
      [ JSON Outputs ]
 (blogs.json, youtube.json...)
 
