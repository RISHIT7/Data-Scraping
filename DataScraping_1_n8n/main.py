import json
import os
from scraper.blog_scraper import scrape_blog
from scraper.youtube_scraper import scrape_youtube
from scraper.pubmed_scraper import scrape_pubmed

# Define our targets based on the assignment requirements
SOURCES = {
    "blogs": {
        "urls": [
            "https://realpython.com/python-web-scraping-practical-introduction/",
            "https://news.mit.edu/2025/new-ai-system-could-accelerate-clinical-research-0925",
            "https://news.mit.edu/2026/mit-scientists-investigate-memorization-risk-clinical-ai-0105",
        ],
        "func": scrape_blog
    },
    "youtube": {
        "urls": [
            "https://www.youtube.com/watch?v=aircAruvnKk", 
            "https://www.youtube.com/watch?v=kCc8FmEb1nY", 
            "https://www.youtube.com/watch?v=R9OHn5ZF4Uo",
        ],
        "func": scrape_youtube
    },
    "pubmed": {
        "urls": ["https://pubmed.ncbi.nlm.nih.gov/38478847/"],
        "func": scrape_pubmed
    }
}

def run_pipeline():
    """Executes the full scraping suite and saves individual JSON files."""
    os.makedirs("output", exist_ok=True)
    all_results = []

    for source_name, config in SOURCES.items():
        print(f"\n--- Starting {source_name.upper()} Scraping ---")
        current_batch = []
        
        for url in config["urls"]:
            try:
                # Call the specific scraper function for this source
                data = config["func"](url)
                current_batch.append(data)
                all_results.append(data)
                print(f"Success: {url}")
            except Exception as e:
                print(f"Error on {url}: {e}")

        # Save individual files as we go (good for debugging)
        out_file = f"output/{source_name}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(current_batch, f, indent=4, ensure_ascii=False)
        
        print(f"Done. Saved {len(current_batch)} items to {out_file}")

    # Finally, save one master file containing everything
    with open("output/full_dataset.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=4, ensure_ascii=False)
    
    print("\nTotal Pipeline Complete. Master file: output/full_dataset.json")

if __name__ == "__main__":
    run_pipeline()