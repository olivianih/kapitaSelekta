import os
import re
import requests
import pandas as pd
import torch

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from transformers import pipeline
from collections import Counter

# ==========================
# CONFIG
# ==========================

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

ARTICLE_URL = "https://money.kompas.com/read/2026/06/05/072633626/rupiah-tembus-rp-18000-per-dollar-as-efek-berantai-hingga-ke-meja-makan"

OUTPUT_FILE = "news_sentiment_result.csv"

MIN_WORDS = 5

TOP_N_KEYWORDS = 20

STOPWORDS_ID = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan",
    "untuk", "pada", "adalah", "dalam", "juga", "akan",
    "sebagai", "oleh", "karena", "telah", "sudah", "bisa", "ada",
    "atau", "saat", "agar", "jika", "maka",
    "tapi", "namun", "sedangkan", "bahwa", "para", "mereka",
    "kita", "kami", "saya", "ia", "dia", "mereka", "kamu",
    "nya", "pun", "hal", "harus", "bagi", "menjadi", "dapat",
    "secara", "masih", "hingga", "antara",
    "ketika", "sehingga", "per",
}

LABEL_MAP = {
    "LABEL_0": "negative",
    "LABEL_1": "positive"
}

# ==========================
# MODEL
# ==========================

def load_sentiment_model():
    device = 0 if torch.cuda.is_available() else -1
    print("CUDA Available:", torch.cuda.is_available())

    model = pipeline(
        "text-classification",
        model="crypter70/IndoBERT-Sentiment-Analysis",
        token=HF_TOKEN,
        device=device
    )
    return model


# ==========================
# ARTICLE SCRAPER
# ==========================

def scrape_article(url: str) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title_tag = (
        soup.find("h1", class_="read__title")
        or soup.find("h1")
    )
    title = title_tag.get_text(strip=True) if title_tag else "Judul tidak ditemukan"

    content_div = (
        soup.find("div", class_="read__content")
        or soup.find("div", class_="article__content")
        or soup.find("article")
    )

    paragraphs = []
    if content_div:
        for p in content_div.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                paragraphs.append(text)
    else:
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if len(text.split()) >= MIN_WORDS:
                paragraphs.append(text)

    return {"title": title, "paragraphs": paragraphs}


# ==========================
# SENTENCE SPLITTER
# ==========================

def split_into_sentences(paragraphs: list[str]) -> list[str]:
    sentences = []
    for para in paragraphs:
        raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', para)
        for sent in raw_sentences:
            sent = sent.strip()
            if len(sent.split()) >= MIN_WORDS:
                sentences.append(sent)
    return sentences

# ==========================
# CSV KALIMAT
# ==========================

def save_sentences_to_csv(sentences: list[str], output_path: str):
    df = pd.DataFrame(sentences, columns=["sentence"])
    df.index += 1
    df.index.name = "sentence_id"
    df.to_csv(output_path)
    print(f"Kalimat tersimpan di: {output_path}")

# ==========================
# CLEANING
# ==========================

def clean_sentence(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text.split()) < MIN_WORDS:
        return None
    return text


# ==========================
# SENTIMENT
# ==========================

def analyze_sentiment(text: str, model) -> tuple[str, float]:
    result = model(text, truncation=True, max_length=512)[0]
    label = LABEL_MAP.get(result["label"], result["label"])
    score = round(result["score"], 4)
    return label, score


# ==========================
# KEYWORD EXTRACTION
# ==========================

def extract_keywords(sentences: list[str], top_n: int = TOP_N_KEYWORDS) -> list[tuple]:
    all_words = []
    for sent in sentences:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', sent.lower())
        filtered = [w for w in words if w not in STOPWORDS_ID]
        all_words.extend(filtered)

    counter = Counter(all_words)
    return counter.most_common(top_n)

# ==========================
# MAIN
# ==========================

def main():
    print("Loading IndoBERT sentiment model...")
    sentiment_model = load_sentiment_model()

    print(f"\nScraping artikel dari:\n{ARTICLE_URL}\n")
    article = scrape_article(ARTICLE_URL)
    print(f"Judul    : {article['title']}")

    sentences = split_into_sentences(article["paragraphs"])
    save_sentences_to_csv(sentences, "news_sentences.csv")
    print(f"Kalimat  : {len(sentences)} kalimat setelah split")

    results = []
    for i, raw_sent in enumerate(sentences, start=1):
        cleaned = clean_sentence(raw_sent)
        if not cleaned:
            continue

        sentiment, score = analyze_sentiment(cleaned, sentiment_model)

        results.append({
            "sentence_id": i,
            "sentence": cleaned,
            "sentiment": sentiment,
            "score": score,
            "article_url": ARTICLE_URL,
            "article_title": article["title"],
        })

        print(f"  [{i}/{len(sentences)}] {sentiment} ({score}) — {cleaned[:60]}...")

    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\nHasil tersimpan di: {OUTPUT_FILE}")

    keywords = extract_keywords([r["sentence"] for r in results])

    # print_summary(df, article["title"], keywords)


if __name__ == "__main__":
    main()