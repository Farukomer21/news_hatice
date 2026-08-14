"""
RSS öncelikli toplayıcının (rss_news_fetch.py) kullandığı ortak parçalar:
  - TSİ zaman yardımcıları
  - Kaynak listesi (TARGET_DOMAINS_BY_CATEGORY)
  - Google News yedek yolu (UniversalGoogleNewsScraper)

Bu modül tek başına çalıştırılmaz; giriş noktası rss_news_fetch.py'dir.
Google yolu yalnızca RSS'i olmayan kaynaklar için yedek olarak çağrılır.
"""

import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup
from googlenewsdecoder import new_decoderv1
import trafilatura

# Türkiye Standard Time (TSİ / UTC+3)
TSI_TZ = timezone(timedelta(hours=3))

def get_today_start_tsi() -> datetime:
    """TSİ (UTC+3) saat dilimine göre bugünün gece 00:00:00 zamanını döndürür."""
    now_tsi = datetime.now(TSI_TZ)
    return now_tsi.replace(hour=0, minute=0, second=0, microsecond=0)

def get_yesterday_noon_tsi() -> datetime:
    """TSİ (UTC+3) saat dilimine göre dünün öğlen 12:00:00 zamanını döndürür."""
    now_tsi = datetime.now(TSI_TZ)
    yesterday_tsi = now_tsi - timedelta(days=1)
    return yesterday_tsi.replace(hour=12, minute=0, second=0, microsecond=0)

def parse_pub_date_to_tsi(pub_date_str: str) -> Optional[datetime]:
    """
    RSS pubDate metin ifadesini TSİ (UTC+3) datetime objesine dönüştürür.
    """
    if not pub_date_str:
        return None
    try:
        dt = parsedate_to_datetime(pub_date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TSI_TZ)
    except Exception:
        return None

# Türkiye, Almanya ve Rusya için haber kaynakları kategorize edilmiştir.
TARGET_DOMAINS_BY_CATEGORY = {
    "antalya_news": {
        "lang": "tr", "gl": "TR", "ceid": "TR:tr",
        "domains": [
            "turizmdays.com",
            "turizmgazetesi.com",
            "turizmguncel.com",
            "turizmajansi.com"
        ]
    },
    "turkey_tourism": {
        "lang": "tr", "gl": "TR", "ceid": "TR:tr",
        "domains": [
            # En Popüler 5 Türkiye Turizm Kaynağı
            "turizmguncel.com",
            "turizmgazetesi.com",
            "tourismtoday.net",
            "turizmajansi.com",
            "turizmaktuel.com"
        ]
    },
    "turkey_economy": {
        "lang": "tr", "gl": "TR", "ceid": "TR:tr",
        "domains": [
            "bloomberght.com", "ekonomim.com", "paraanaliz.com"
        ]
    },
    "germany_tourism": {
        "lang": "de", "gl": "DE", "ceid": "DE:de",
        "domains": [
            "fvw.de", "touristik-aktuell.de", "reisevor9.de",
            "trvlcounter.de", "travelbook.de"
        ]
    },
    "germany_economy": {
        "lang": "de", "gl": "DE", "ceid": "DE:de",
        "domains": [
            "handelsblatt.com", "wiwo.de", "boersen-zeitung.de"
        ]
    },
    "russia_tourism": {
        "lang": "ru", "gl": "RU", "ceid": "RU:ru",
        "domains": [
            "atorus.ru", "tourdom.ru", "profi.travel", "ratanews.ru", "trn-news.ru"
        ]
    },
    "russia_economy": {
        "lang": "ru", "gl": "RU", "ceid": "RU:ru",
        "domains": [
            "kommersant.ru", "vedomosti.ru", "interfax.ru"
        ]
    }
}

class UniversalGoogleNewsScraper:
    """
    Google News RSS sorgusuyla tek bir kaynağın haberlerini çeken yedek kazıyıcı.
    rss_news_fetch.py, RSS beslemesi olmayan ya da 0 sonuç veren kaynaklar için
    yalnızca fetch_today_news_for_domain() metodunu çağırır.
    """

    @staticmethod
    def fetch_today_news_for_domain(
        domain: str, 
        period: str = "2d", 
        max_articles: Optional[int] = None,
        lang: str = "tr",
        gl: str = "TR",
        ceid: str = "TR:tr",
        since_yesterday_noon: bool = True,
        only_today: bool = False,
        category: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Verilen alan adı (domain) için Google News sorgusu ile haberleri getirir.
        max_articles=None ise kısıtlama olmaksızın tüm uygun haberleri çeker.
        since_yesterday_noon=True ise dünün öğlen 12:00'sinden itibaren yayınlanan haberleri filtreler.
        only_today=True ise sadece bugün TSİ gece 00:00'dan sonra yayınlanan haberleri filtreler.
        """
        query_str = f"site:{domain} when:{period}"
        encoded_query = urllib.parse.quote(query_str)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}&gl={gl}&ceid={ceid}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        if since_yesterday_noon:
            start_filter_tsi = get_yesterday_noon_tsi()
            filter_label = f"TSİ Dün Öğlen 12:00 Başlangıcı: {start_filter_tsi.strftime('%Y-%m-%d %H:%M:%S TSİ')}"
        elif only_today:
            start_filter_tsi = get_today_start_tsi()
            filter_label = f"TSİ Bugün Başlangıcı (00:00): {start_filter_tsi.strftime('%Y-%m-%d %H:%M:%S TSİ')}"
        else:
            start_filter_tsi = None
            filter_label = None

        print(f"\n🔍 Google News Query: '{domain}' (Sorgu: when:{period}, Dil: {lang})", flush=True)
        if filter_label:
            print(f" ⏱️ {filter_label}", flush=True)

        try:
            res = requests.get(rss_url, headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"❌ RSS isteği başarısız oldu ({domain}): HTTP {res.status_code}", flush=True)
                return []

            soup = BeautifulSoup(res.text, "xml")
            items = soup.find_all("item")
            print(f"🔗 Google News toplam {len(items)} adet bağlantı buldu.", flush=True)

            filtered_items = []
            for item in items:
                pub_date = item.find("pubDate").text if item.find("pubDate") else ""
                pub_dt_tsi = parse_pub_date_to_tsi(pub_date)

                # Zaman filtresi: Başlangıç tarihinden öncesini atla
                if start_filter_tsi and pub_dt_tsi and pub_dt_tsi < start_filter_tsi:
                    continue

                title = item.find("title").text if item.find("title") else "Başlık Yok"
                google_link = item.find("link").text if item.find("link") else ""

                filtered_items.append((title, google_link, pub_date, pub_dt_tsi))
                if max_articles and len(filtered_items) >= max_articles:
                    break

            print(f"   🎯 Zaman filtresine uyan {len(filtered_items)} haber paralel olarak indiriliyor...", flush=True)

            def slugify_words(text: str) -> set:
                tr_map = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')
                clean = text.translate(tr_map).lower()
                return set(re.findall(r'[a-z0-9]{3,}', clean))

            def resolve_news_url_and_text(dom_str: str, art_title: str, g_link: str):
                # 1. Google Decoder denemesi
                try:
                    dec = new_decoderv1(g_link)
                    if dec and dec.get("status") and dec.get("decoded_url"):
                        real = dec["decoded_url"]
                        dl = trafilatura.fetch_url(real)
                        txt = trafilatura.extract(dl) if dl else ""
                        if txt and len(txt) > 100:
                            return real, txt
                except Exception:
                    pass

                clean_dom = dom_str.split()[0].strip()

                # 2. Siteden doğrudan başlık eşleştirme
                test_urls = [
                    f"https://www.{clean_dom}/",
                    f"https://{clean_dom}/",
                    f"https://www.{clean_dom}/haberler",
                    f"https://www.{clean_dom}/turizm"
                ]

                title_words = slugify_words(art_title)
                title_words.discard("hurriyet")
                title_words.discard("milliyet")

                for site_url in test_urls:
                    try:
                        r = requests.get(
                            site_url, 
                            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}, 
                            timeout=5
                        )
                        if r.status_code != 200:
                            continue

                        soup = BeautifulSoup(r.text, "html.parser")
                        best_link = None
                        best_score = 0

                        for a in soup.find_all("a"):
                            href = a.get("href", "")
                            text = a.text.strip()
                            if not href or href == "#" or href.startswith("javascript:"):
                                continue

                            link_words = slugify_words(href + " " + text)
                            common = title_words.intersection(link_words)
                            score = len(common)

                            if score > best_score and score >= 2:
                                best_score = score
                                if href.startswith("http"):
                                    best_link = href
                                elif href.startswith("/"):
                                    best_link = site_url.rstrip("/") + href

                        if best_link and best_score >= 2:
                            dl = trafilatura.fetch_url(best_link)
                            txt = trafilatura.extract(dl) if dl else ""
                            if txt and len(txt) > 100:
                                return best_link, txt
                    except Exception:
                        pass

                # 3. Site içi arama
                try:
                    clean_search = " ".join(list(title_words)[:5])
                    search_urls = [
                        f"https://www.{clean_dom}/?s={urllib.parse.quote(clean_search)}",
                        f"https://www.{clean_dom}/arama?q={urllib.parse.quote(clean_search)}"
                    ]
                    for su in search_urls:
                        r = requests.get(su, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                        if r.status_code != 200:
                            continue
                        soup = BeautifulSoup(r.text, "html.parser")
                        for a in soup.find_all("a"):
                            href = a.get("href", "")
                            if clean_dom in href and len(href) > len(clean_dom) + 15:
                                dl = trafilatura.fetch_url(href)
                                txt = trafilatura.extract(dl) if dl else ""
                                if txt and len(txt) > 100:
                                    return href, txt
                except Exception:
                    pass

                return g_link, ""

            def fetch_single_article(item_tuple):
                title, google_link, pub_date, pub_dt_tsi = item_tuple
                real_url, full_text = resolve_news_url_and_text(domain, title, google_link)

                return {
                    "category": category,
                    "domain": domain,
                    "title": title,
                    "google_link": google_link,
                    "url": real_url,
                    "pub_date_raw": pub_date,
                    "pub_date_tsi": pub_dt_tsi.strftime("%Y-%m-%d %H:%M:%S TSİ") if pub_dt_tsi else pub_date,
                    "pub_timestamp_iso": pub_dt_tsi.isoformat() if pub_dt_tsi else "",
                    "full_text_length": len(full_text),
                    "full_text": full_text
                }

            articles = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(fetch_single_article, filtered_items))
                articles.extend(results)

            print(f"✅ '{domain}' için {len(articles)} adet haber eksiksiz alındı.", flush=True)
            return articles

        except Exception as e:
            print(f"❌ '{domain}' taranırken hata oluştu: {e}", flush=True)
            return []
