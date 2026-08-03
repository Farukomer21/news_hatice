import os
import json
import time
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from googlenewsdecoder import new_decoderv1
import trafilatura

# Türkiye, Almanya ve Rusya için haber kaynakları kategorize edilmiştir.
TARGET_DOMAINS_BY_CATEGORY = {
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
    son 24 saatte yayınladığı haberleri ve tam metinlerini çeken evrensel kazıyıcı.
    """
    
    @staticmethod
    def fetch_today_news_for_domain(
        domain: str, 
        period: str = "1d", 
        max_articles: int = 5,
        lang: str = "tr",
        gl: str = "TR",
        ceid: str = "TR:tr"
    ) -> List[Dict[str, Any]]:
        """
        Verilen alan adı (domain) için Google News sorgusu ile son 24 saatlik haberleri getirir.
        """
        query_str = f"site:{domain} when:{period}"
        encoded_query = urllib.parse.quote(query_str)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}&gl={gl}&ceid={ceid}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        print(f"\n🔍 Google News Query: '{domain}' (Sorgu: when:{period}, Dil: {lang})", flush=True)
        try:
            res = requests.get(rss_url, headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"❌ RSS isteği başarısız oldu ({domain}): HTTP {res.status_code}", flush=True)
                return []

            soup = BeautifulSoup(res.text, "xml")
            items = soup.find_all("item")
            print(f"🔗 Google News toplam {len(items)} adet güncel haber bağlantısı buldu. (Maks {max_articles} tanesi işlenecek)", flush=True)

            articles = []
            for idx, item in enumerate(items[:max_articles], 1):
                title = item.find("title").text if item.find("title") else "Başlık Yok"
                pub_date = item.find("pubDate").text if item.find("pubDate") else ""
                google_link = item.find("link").text if item.find("link") else ""

                print(f" [{idx}/{min(len(items), max_articles)}] Çözümleniyor: {title[:50]}...", flush=True)
                
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
                    "domain": domain,
                    "title": title,
                    "google_link": google_link,
                    "url": real_url,
                    "pub_date": pub_date,
                    "full_text_length": len(full_text),
                    "full_text": full_text
                })

                time.sleep(0.3)

            return articles

        except Exception as e:
            print(f"❌ '{domain}' taranırken hata oluştu: {e}", flush=True)
            return []

    def fetch_all_categories(self, max_articles_per_domain: int = 5) -> Dict[str, Any]:
        """
        Tüm ülkelerdeki ve kategorilerdeki 43 kaynağın haberlerini sırayla çeker.
        """
        all_data = {}
        today_str = datetime.now().strftime("%Y-%m-%d")

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
                    ceid=config["ceid"]
                )
                category_results[dom] = {
                    "count": len(news_items),
                    "articles": news_items
                }
            all_data[category_name] = category_results

        return {
            "date": today_str,
            "query_period": "when:1d",
            "total_domains": sum(len(c["domains"]) for c in TARGET_DOMAINS_BY_CATEGORY.values()),
            "categories": all_data
        }

if __name__ == "__main__":
    scraper = UniversalGoogleNewsScraper()
    
    # 43 alan adının tamamını tarıyoruz (her domain için maks 3 taze haber):
    results = scraper.fetch_all_categories(max_articles_per_domain=3)

    # Çıktıyı JSON olarak kaydedelim
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "google_news_query_results.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"\n🎉 43 Kaynaktan Güncel Haberler Başarıyla Çekildi!")
    print(f"✅ Çıktı '{output_file}' dosyasına kaydedildi!", flush=True)
