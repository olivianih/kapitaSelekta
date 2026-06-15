from transformers import pipeline
from collections import Counter
import pandas as pd
import torch
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import matplotlib
matplotlib.use('Agg')   # simpan ke file, tidak pop-up window
import matplotlib.pyplot as plt
import time
import os
import re

USERNAME        = ''      # username Instagram kamu
PASSWORD        = ''      # password Instagram kamu
POST_URL        = 'https://www.instagram.com/reel/DZJ7Ua0zpmI/'
OUTPUT_CSV      = 'instagram_komentar_sentiment.csv'
CHART_SENTIMENT = 'chart_sentimen.png'
CHART_KEYWORD   = 'chart_keyword.png'
MAX_SCROLL      = 30      # maksimal iterasi scroll komentar
SCROLL_PAUSE    = 2.5     # detik jeda antar scroll

KEYWORDS = [
    "demo", "dollar", "dolar", "MBG", "dulu",
    "19 jt lapangan kerja", "presiden", "pertamax",
    "wowo", "prabowo", "desa", "turunkan", "lengserkan",
    "manusia", "banyak omong", "pendukung", "negara",
    "Indonesia", "rupiah", "kurs", "inflasi", "ekonomi",
]

def init_driver():
    options = Options()

    # Sembunyikan tanda-tanda Selenium/bot
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Tampilan & stabilitas
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # User-Agent seperti browser manusia biasa
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['id-ID', 'id', 'en-US', 'en']
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """
        }
    )
    return driver

def human_type(element, text, delay=0.09):
    """Ketik karakter per karakter agar terlihat seperti manusia."""
    for char in text:
        element.send_keys(char)
        time.sleep(delay + (0.04 * (ord(char) % 3)))


def tutup_popup(driver):
    """Tutup berbagai pop-up yang muncul setelah login."""
    popup_texts = [
        "Not Now", "Tidak Sekarang", "Nanti Saja",
        "Skip", "Lewati", "Dismiss", "Tutup"
    ]
    for teks in popup_texts:
        try:
            btn = driver.find_element(
                By.XPATH,
                f"//button[contains(text(),'{teks}')] | "
                f"//div[contains(text(),'{teks}')]"
            )
            btn.click()
            time.sleep(1)
        except Exception:
            pass


def login(driver, username, password):
    print("[...] Membuka halaman login Instagram...")
    driver.get('https://www.instagram.com/accounts/login/')
    time.sleep(5)   # tunggu sampai halaman benar-benar selesai load

    wait = WebDriverWait(driver, 30)

    user_selectors = [
        (By.NAME,         'username'),
        (By.NAME,         'email'),
        (By.XPATH,        "//input[@name='username']"),
        (By.XPATH,        "//input[@name='email']"),
        (By.XPATH,        "//input[contains(@placeholder,'username')]"),
        (By.XPATH,        "//input[contains(@placeholder,'Mobile number')]"),
        (By.XPATH,        "//input[contains(@placeholder,'number, username')]"),
        (By.XPATH,        "//input[contains(@placeholder,'Nomor')]"),
        (By.XPATH,        "//input[@type='text'][1]"),
        (By.CSS_SELECTOR, "input[name='username']"),
        (By.CSS_SELECTOR, "input[name='email']"),
        (By.CSS_SELECTOR, "input[type='text']"),
    ]

    user_field = None
    for by, selector in user_selectors:
        try:
            user_field = wait.until(EC.element_to_be_clickable((by, selector)))
            print(f"[✓] Field username ditemukan: {selector}")
            break
        except Exception:
            continue

    if user_field is None:
        all_inputs = driver.find_elements(By.TAG_NAME, 'input')
        print("[!] SEMUA SELECTOR GAGAL. Input yang ada di halaman:")
        for inp in all_inputs:
            print(
                f"    type={inp.get_attribute('type')!r:12} | "
                f"name={inp.get_attribute('name')!r:15} | "
                f"placeholder={inp.get_attribute('placeholder')!r}"
            )
        driver.save_screenshot("debug_login_gagal.png")
        raise Exception(
            "\n[✗] Field username tidak ditemukan!\n"
            "    → Screenshot disimpan: debug_login_gagal.png\n"
            "    → Kirim log di atas ke pembuat kode untuk analisis lebih lanjut."
        )

    # Isi field username
    user_field.click()
    time.sleep(0.6)
    user_field.clear()
    human_type(user_field, username)
    time.sleep(0.9)

    pass_selectors = [
        (By.NAME,         'password'),
        (By.XPATH,        "//input[@name='password']"),
        (By.XPATH,        "//input[@type='password']"),
        (By.CSS_SELECTOR, "input[name='password']"),
        (By.CSS_SELECTOR, "input[type='password']"),
    ]
    pass_field = None
    for by, selector in pass_selectors:
        try:
            pass_field = driver.find_element(by, selector)
            print(f"[✓] Field password ditemukan: {selector}")
            break
        except Exception:
            continue

    if pass_field is None:
        driver.save_screenshot("debug_password_gagal.png")
        raise Exception("[✗] Field password tidak ditemukan! Cek debug_password_gagal.png")

    pass_field.click()
    time.sleep(0.6)
    human_type(pass_field, password)
    time.sleep(0.6)

    submitted = False
    for btn_selector in [
        "//button[@type='submit']",
        "//button[contains(text(),'Log in')]",
        "//button[contains(text(),'Masuk')]",
        "//button[contains(text(),'Login')]",
    ]:
        try:
            btn = driver.find_element(By.XPATH, btn_selector)
            btn.click()
            print(f"[✓] Tombol login diklik: {btn_selector}")
            submitted = True
            break
        except Exception:
            continue

    if not submitted:
        pass_field.send_keys(Keys.RETURN)
        print("[✓] ENTER dikirim sebagai fallback login")

    print("[...] Menunggu proses login (10 detik)...")
    time.sleep(10)

    current_url = driver.current_url
    print(f"[i] URL setelah login: {current_url}")

    if 'challenge' in current_url or 'verify' in current_url:
        driver.save_screenshot("debug_challenge.png")
        print("[!] Instagram meminta verifikasi tambahan!")
        print("    Screenshot: debug_challenge.png")
        print("    Selesaikan verifikasi secara manual di browser, lalu tekan Enter di sini...")
        input("    [Tekan Enter setelah verifikasi selesai] >>> ")

    tutup_popup(driver)
    print("[✓] Login selesai\n")

def open_post_and_scroll(driver, url):
    print(f"[...] Membuka post: {url}")
    driver.get(url)
    time.sleep(5)

    # Klik "Load more comments" jika ada
    for _ in range(8):
        try:
            btn = driver.find_element(
                By.XPATH,
                "//span[contains(text(),'Load more comments')] | "
                "//span[contains(text(),'View more comments')] | "
                "//span[contains(text(),'Muat lebih banyak')]"
            )
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
        except Exception:
            break

    # Temukan container komentar untuk di-scroll
    scroll_target = None
    for selector in [
        "//div[@role='dialog']",
        "//ul[contains(@class,'_a9ym')]",
        "//div[contains(@class,'_aano')]",
        "//section//article",
        "//article",
    ]:
        try:
            scroll_target = driver.find_element(By.XPATH, selector)
            print(f"[✓] Scroll target ditemukan: {selector}")
            break
        except Exception:
            continue

    if scroll_target is None:
        print("[!] Scroll target tidak ditemukan, fallback ke scroll halaman")

    last_height = 0
    for i in range(MAX_SCROLL):
        try:
            if scroll_target:
                driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight",
                    scroll_target
                )
                new_height = driver.execute_script(
                    "return arguments[0].scrollHeight", scroll_target
                )
            else:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                new_height = driver.execute_script("return document.body.scrollHeight")
        except Exception:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            new_height = driver.execute_script("return document.body.scrollHeight")

        time.sleep(SCROLL_PAUSE)

        if new_height == last_height:
            print(f"[✓] Scroll selesai pada iterasi ke-{i + 1}")
            break
        last_height = new_height
        if (i + 1) % 5 == 0:
            print(f"    ... scroll iterasi {i + 1}/{MAX_SCROLL}")

    print("[✓] Selesai scroll\n")

# Kata-kata UI Instagram yang bukan komentar nyata
UI_NOISE = {
    "like", "reply", "balas", "suka", "follow", "following",
    "share", "save", "more", "lainnya", "load more", "view",
    "lihat", "semua", "komentar", "comment", "send", "kirim",
    "emoji", "sponsored", "bersponsor", "suggested", "disarankan",
    "ago", "hours", "minutes", "days", "weeks", "seconds",
    "jam", "menit", "hari", "minggu", "detik", "tahun", "year",
    "verified", "terverifikasi",
}

# Pola regex yang pasti bukan komentar
NOISE_PATTERNS = [
    re.compile(r'^\d+$'),                          # angka murni
    re.compile(r'^[\s\W]+$'),                      # simbol/spasi murni
    re.compile(                                    # pola waktu relatif
        r'^\d+\s*(hour|minute|day|week|second|year|'
        r'jam|menit|hari|minggu|detik|tahun)s?\s*(ago|lalu)?$',
        re.IGNORECASE
    ),
    re.compile(r'^https?://', re.IGNORECASE),      # URL
]


def is_valid_comment(text: str) -> bool:
    text = text.strip()
    if len(text) < 5 or len(text) > 500:
        return False
    if text.lower() in UI_NOISE:
        return False
    for pattern in NOISE_PATTERNS:
        if pattern.search(text):
            return False
    return True


def extract_comments(driver) -> list:
    """
    Ekstrak teks komentar dari halaman Instagram.
    Tiga strategi bertingkat untuk ketahanan terhadap perubahan HTML Instagram.
    """
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    raw_texts = set()

    for ul in soup.find_all('ul'):
        for span in ul.find_all('span', recursive=True):
            t = span.get_text(separator=' ', strip=True)
            if t:
                raw_texts.add(t)

    for span in soup.find_all('span', attrs={'dir': 'auto'}):
        t = span.get_text(separator=' ', strip=True)
        if t:
            raw_texts.add(t)

    # Strategi 3: fallback semua <span> jika hasil masih sedikit
    if len(raw_texts) < 10:
        print("[!] Fallback: mengambil semua <span> di halaman")
        for span in soup.find_all('span'):
            t = span.get_text(separator=' ', strip=True)
            if t:
                raw_texts.add(t)

    valid = [t for t in raw_texts if is_valid_comment(t)]
    print(f"[✓] Total span ditemukan : {len(raw_texts)}")
    print(f"[✓] Komentar valid       : {len(valid)}\n")
    return valid

def count_keywords(comment_texts: list, keywords: list) -> dict:
    word_count = {kw: 0 for kw in keywords}
    for comment in comment_texts:
        c_lower = comment.lower()
        for kw in keywords:
            word_count[kw] += c_lower.count(kw.lower())
    filtered = {kw: cnt for kw, cnt in word_count.items() if cnt > 0}
    return dict(sorted(filtered.items(), key=lambda x: x[1], reverse=True))

LABEL_MAP = {
    "LABEL_0": "negative",
    "LABEL_1": "positive",
    "LABEL_2": "neutral",
}


def run_sentiment(comment_texts: list) -> list:
    device = 0 if torch.cuda.is_available() else -1
    print(f"[✓] Device sentimen: {'GPU' if device == 0 else 'CPU'}")
    print("[...] Memuat model IndoBERT (bisa beberapa menit pertama kali)...")

    model = pipeline(
        "text-classification",
        model="crypter70/IndoBERT-Sentiment-Analysis",
        device=device,
        truncation=True,
        max_length=512,
    )

    results = []
    for i, comment in enumerate(comment_texts):
        comment = comment.strip()
        if not is_valid_comment(comment):
            continue
        try:
            out = model(comment[:512])[0]
            sentiment = LABEL_MAP.get(out["label"], out["label"])
            results.append({
                "comment":   comment,
                "sentiment": sentiment,
                "score":     round(float(out["score"]), 4),
            })
        except Exception as e:
            print(f"[!] Error komentar ke-{i}: {e}")

        if (i + 1) % 50 == 0:
            print(f"    ... {i + 1}/{len(comment_texts)} komentar diproses")

    print(f"[✓] Analisis sentimen selesai: {len(results)} komentar\n")
    return results
def save_csv(results: list, filepath: str) -> pd.DataFrame:
    df = pd.DataFrame(results)
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    abs_path = os.path.abspath(filepath)
    print(f"[✓] CSV disimpan  : {abs_path}")
    print(f"    Jumlah baris  : {len(df)}")
    print(f"    Kolom         : {list(df.columns)}\n")
    return df

def plot_sentiment(sentiment_count: Counter, filepath: str):
    COLOR_MAP = {
        'positive': '#4CAF50',
        'negative': '#F44336',
        'neutral':  '#2196F3',
    }
    labels = list(sentiment_count.keys())
    values = list(sentiment_count.values())
    colors = [COLOR_MAP.get(l, '#9E9E9E') for l in labels]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor='white', linewidth=1.2)

    # Label angka di atas bar
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            str(val),
            ha='center', va='bottom', fontweight='bold', fontsize=12
        )

    total = sum(values)
    ax.set_xlabel('Sentimen', fontsize=12)
    ax.set_ylabel('Jumlah Komentar', fontsize=12)
    ax.set_title(
        f'Distribusi Sentimen Komentar Instagram\n'
        f'Topik: Dolar Rp18.000 | Total: {total} komentar',
        fontsize=13, fontweight='bold'
    )
    ax.set_ylim(0, max(values) * 1.2)
    ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[✓] Grafik sentimen: {os.path.abspath(filepath)}")


def plot_keywords(word_count: dict, filepath: str, top_n: int = 15):
    if not word_count:
        print("[!] Tidak ada keyword yang ditemukan, grafik dilewati")
        return

    items = list(word_count.items())[:top_n]
    kws, cnts = zip(*items)

    fig, ax = plt.subplots(figsize=(11, 5))
    bars = ax.bar(kws, cnts, color='#42A5F5', edgecolor='white', linewidth=1.2)

    for bar, val in zip(bars, cnts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.2,
            str(val),
            ha='center', va='bottom', fontweight='bold', fontsize=10
        )

    ax.set_xlabel('Kata Kunci', fontsize=12)
    ax.set_ylabel('Jumlah Kemunculan', fontsize=12)
    ax.set_title('Frekuensi Kata Kunci dalam Komentar Instagram', fontsize=13, fontweight='bold')
    ax.spines[['top', 'right']].set_visible(False)
    plt.xticks(rotation=40, ha='right', fontsize=10)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[✓] Grafik keyword : {os.path.abspath(filepath)}")

def main():
    print("=" * 55)
    print("  Instagram Scraper + IndoBERT Sentiment Analysis")
    print("=" * 55 + "\n")
    driver = init_driver()
    comment_texts = []
    try:
        login(driver, USERNAME, PASSWORD)
        open_post_and_scroll(driver, POST_URL)
        comment_texts = extract_comments(driver)
    except Exception as e:
        print(f"\n[✗] ERROR saat scraping: {e}")
    finally:
        driver.quit()
        print("[✓] Browser ditutup\n")

    if not comment_texts:
        print("[✗] Tidak ada komentar yang berhasil diekstrak.")
        print("    Kemungkinan: login gagal, post dihapus, atau akun terkunci.")
        print("    Cek file debug_*.png jika ada.")
        return
    print(f"Sampel 5 komentar pertama:")
    for c in comment_texts[:5]:
        print(f"  • {c[:90]}")
    print()
    print("─" * 45)
    word_count = count_keywords(comment_texts, KEYWORDS)
    print("=== FREKUENSI KATA KUNCI ===")
    if word_count:
        for kw, cnt in word_count.items():
            bar = '█' * cnt
            print(f"  {kw:<25} {cnt:>4}  {bar}")
    else:
        print("  (tidak ada keyword yang ditemukan)")
    print()
    print("─" * 45)
    results = run_sentiment(comment_texts)

    sentiment_count = Counter(r["sentiment"] for r in results)
    print("=== DISTRIBUSI SENTIMEN ===")
    total = sum(sentiment_count.values())
    for s, n in sentiment_count.items():
        pct = n / total * 100 if total else 0
        print(f"  {s:<12} : {n:>4} komentar ({pct:.1f}%)")
    print()
    print("─" * 45)
    save_csv(results, OUTPUT_CSV)
    plot_sentiment(sentiment_count, CHART_SENTIMENT)
    plot_keywords(word_count, CHART_KEYWORD)

    print("\n" + "=" * 55)
    print(f"   📄  {os.path.abspath(OUTPUT_CSV)}")
    print(f"   📊  {os.path.abspath(CHART_SENTIMENT)}")
    print(f"   📊  {os.path.abspath(CHART_KEYWORD)}")
    print("=" * 55)


if __name__ == "__main__":
    main()