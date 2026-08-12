import os
import json
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Optional
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
            "akdenizgercek.com.tr",
            "akdenizmanset.com.tr",
            "antalyanews.com.tr",
            "gunhaber.com.tr",
            "lidergazete.com",
            "nehir.net",
            "turizmdays.com",
            "turizmgazetesi.com",
            "turizmguncel.com",
            "yenialanya.com"
        ]
    },
    "turkey_tourism": {
        "lang": "tr", "gl": "TR", "ceid": "TR:tr",
        "domains": [
            "turizmguncel.com", "turizmgazetesi.com", "turizmajansi.com", "gmdergi.com",
            "tourexpi.com", "turizmgunlugu.com", "tourismtoday.net", "turizmaktuel.com",
            "turizmnews.com", "turizmekonomi.com", "turizminsesi.com", "turizmdosyasi.com"
        ]
    },
    "turkey_economy": {
        "lang": "tr", "gl": "TR", "ceid": "TR:tr",
        "domains": [
            "bloomberght.com", "ekonomim.com", "news.foreks.com", "paraanaliz.com",
            "tr.investing.com", "sabah.com.tr", "milliyet.com.tr"
        ]
    },
    "germany_tourism": {
        "lang": "de", "gl": "DE", "ceid": "DE:de",
        "domains": [
            "fvw.de", "touristik-aktuell.de", "reisevor9.de", "travelone.de",
            "trvlcounter.de", "travelbook.de", "germany.travel"
        ]
    },
    "germany_economy": {
        "lang": "de", "gl": "DE", "ceid": "DE:de",
        "domains": [
            "handelsblatt.com", "wiwo.de", "boersen-zeitung.de", "finanzen.net", "manager-magazin.de"
        ]
    },
    "russia_tourism": {
        "lang": "ru", "gl": "RU", "ceid": "RU:ru",
        "domains": [
            "atorus.ru", "tourdom.ru", "profi.travel", "ratanews.ru", "trn-news.ru", "interfax-russia.ru"
        ]
    },
    "russia_economy": {
        "lang": "ru", "gl": "RU", "ceid": "RU:ru",
        "domains": [
            "rbc.ru", "kommersant.ru", "vedomosti.ru", "forbes.ru", "finmarket.ru", "interfax.ru"
        ]
    }
}

class UniversalGoogleNewsScraper:
    """
    Google News RSS Query kullanarak Türkiye, Almanya ve Rusya'daki 43 farklı haber sitesinin
    bugün (TSİ gece 00:00'dan itibaren) yayınladığı haberleri ve tam metinlerini çeken evrensel kazıyıcı.
    """
    
    @staticmethod
    def fetch_today_news_for_domain(
        domain: str, 
        period: str = "1d", 
        max_articles: int = 5,
        lang: str = "tr",
        gl: str = "TR",
        ceid: str = "TR:tr",
        only_today: bool = True,
        category: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Verilen alan adı (domain) için Google News sorgusu ile son haberleri getirir.
        only_today=True ise sadece bugün TSİ gece 00:00'dan sonra yayınlanan haberleri filtreler.
        """
        query_str = f"site:{domain} when:{period}"
        encoded_query = urllib.parse.quote(query_str)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}&gl={gl}&ceid={ceid}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        today_start_tsi = get_today_start_tsi()
        print(f"\n🔍 Google News Query: '{domain}' (Sorgu: when:{period}, Dil: {lang})", flush=True)
        if only_today:
            print(f" ⏱️ TSİ Bugün Başlangıcı (00:00): {today_start_tsi.strftime('%Y-%m-%d %H:%M:%S TSİ')}", flush=True)

        try:
            res = requests.get(rss_url, headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"❌ RSS isteği başarısız oldu ({domain}): HTTP {res.status_code}", flush=True)
                return []

            soup = BeautifulSoup(res.text, "xml")
            items = soup.find_all("item")
            print(f"🔗 Google News toplam {len(items)} adet bağlantı buldu.", flush=True)

            articles = []
            for item in items:
                pub_date = item.find("pubDate").text if item.find("pubDate") else ""
                pub_dt_tsi = parse_pub_date_to_tsi(pub_date)

                # Bugün filtresi: TSİ gece 00:00'dan öncesini atla
                if only_today and pub_dt_tsi and pub_dt_tsi < today_start_tsi:
                    continue

                title = item.find("title").text if item.find("title") else "Başlık Yok"
                google_link = item.find("link").text if item.find("link") else ""

                idx = len(articles) + 1
                print(f" [{idx}/{max_articles}] İşleniyor: {title[:50]}...", flush=True)
                if pub_dt_tsi:
                    print(f"   📅 Yayın Tarihi (TSİ): {pub_dt_tsi.strftime('%Y-%m-%d %H:%M:%S TSİ')}", flush=True)

                # Google News yönlendirme linkini gerçek haber URL'ine çözümlüyoruz
                real_url = google_link
                try:
                    decoded_res = new_decoderv1(google_link)
                    if decoded_res and decoded_res.get("status") and decoded_res.get("decoded_url"):
                        real_url = decoded_res["decoded_url"]
                except Exception as e:
                    print(f"   ⚠️ Link çözümlenemedi, orijinal link kullanılacak: {e}", flush=True)

                # Gerçek URL'den tam metin (full body text) çekiyoruz
                full_text = ""
                try:
                    downloaded = trafilatura.fetch_url(real_url)
                    if downloaded:
                        full_text = trafilatura.extract(downloaded, include_comments=False, include_tables=False) or ""
                except Exception as e:
                    print(f"   ⚠️ Metin çekilirken hata: {e}", flush=True)

                articles.append({
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
                })


                if len(articles) >= max_articles:
                    break

                time.sleep(0.3)

            print(f"✅ '{domain}' için TSİ bugün yayınlanan {len(articles)} adet haber alındı.", flush=True)
            return articles

        except Exception as e:
            print(f"❌ '{domain}' taranırken hata oluştu: {e}", flush=True)
            return []

    def fetch_all_categories(self, max_articles_per_domain: int = 5, only_today: bool = True) -> Dict[str, Any]:
        """
        Tüm ülkelerdeki ve kategorilerdeki 43 kaynağın bugün (TSİ 00:00'dan itibaren) yayınlanan haberlerini sırayla çeker.
        """
        all_data = {}
        now_tsi = datetime.now(TSI_TZ)
        today_start_tsi = get_today_start_tsi()
        total_articles_count = 0

        for category_name, config in TARGET_DOMAINS_BY_CATEGORY.items():
            print(f"\n==================================================")
            print(f"🌐 Kategori Taranıyor: {category_name.upper()}")
            print(f"==================================================", flush=True)
            
            category_results = {}
            for dom in config["domains"]:
                news_items = self.fetch_today_news_for_domain(
                    domain=dom,
                    period="1d",
                    max_articles=max_articles_per_domain,
                    lang=config["lang"],
                    gl=config["gl"],
                    ceid=config["ceid"],
                    only_today=only_today,
                    category=category_name
                )


                category_results[dom] = {
                    "count": len(news_items),
                    "articles": news_items
                }
                total_articles_count += len(news_items)
            all_data[category_name] = category_results

        return {
            "fetch_time_tsi": now_tsi.strftime("%Y-%m-%d %H:%M:%S TSİ"),
            "today_start_tsi": today_start_tsi.strftime("%Y-%m-%d %H:%M:%S TSİ"),
            "only_today_filtered": only_today,
            "total_domains": sum(len(c["domains"]) for c in TARGET_DOMAINS_BY_CATEGORY.values()),
            "total_articles_collected": total_articles_count,
            "categories": all_data
        }

    @staticmethod
    def flatten_articles(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Kategorili sonuç yapısını düz bir haber listesine dönüştürür.
        Örnek çıktı: [ {"category": "turkey_economy", "domain": "bloomberght.com", "title": "..."}, ... ]
        """
        flat_list = []
        categories = results.get("categories", {})
        for category_name, domains_data in categories.items():
            for domain, domain_info in domains_data.items():
                articles = domain_info.get("articles", [])
                for article in articles:
                    article_copy = dict(article)
                    article_copy["category"] = category_name
                    flat_list.append(article_copy)
        return flat_list

    @staticmethod
    def save_to_json(data: Any, filepath: str) -> str:
        """
        Veriyi düzgün Türkçe karakterler ve okunaklı girintileme (indentation) ile JSON dosyasına kaydeder.
        """
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return filepath

if __name__ == "__main__":
    scraper = UniversalGoogleNewsScraper()
    
    # 43 alan adının tamamını tarıyoruz (her domain için maks 3 adet bugün yayınlanmış haber):
    results = scraper.fetch_all_categories(max_articles_per_domain=3, only_today=True)
    flat_articles = scraper.flatten_articles(results)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_categorized = os.path.join(script_dir, "google_news_query_results.json")
    output_flat_list = os.path.join(script_dir, "google_news_flat_list.json")
    
    # Hem kategorili detaylı veriyi hem de doğrudan dizi (array) olan düz liste JSON'ı kaydediyoruz:
    scraper.save_to_json(results, output_categorized)
    scraper.save_to_json(flat_articles, output_flat_list)

    print(f"\n🎉 43 Kaynaktan Bugün Yayınlanan {len(flat_articles)} Adet Haber Başarıyla Çekildi!")
    print(f"📁 Kategorili Çıktı: '{output_categorized}'")
    print(f"📁 Düz Liste JSON Çıktısı: '{output_flat_list}'", flush=True)


