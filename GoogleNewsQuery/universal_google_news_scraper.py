import os
import json
import time
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
from googlenewsdecoder import new_decoderv1
import trafilatura

class UniversalGoogleNewsScraper:
    """
    Google News RSS Query kullanarak HERHANGİ bir haber sitesinin
    son 24 saatte (veya belirtilen sürede) yayınladığı haberleri ve tam metinlerini çeken evrensel kazıyıcı.
    """
    
    @staticmethod
    def fetch_today_news_for_domain(domain: str, period: str = "1d", max_articles: int = 10) -> List[Dict[str, Any]]:
        """
        Verilen alan adı (domain) için Google News sorgusu ile son 24 saatlik haberleri getirir.
        Örn domain: "turizmguncel.com", "turizmajansi.com", "sabah.com.tr"
        """
        query_str = f"site:{domain} when:{period}"
        encoded_query = urllib.parse.quote(query_str)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=tr&gl=TR&ceid=TR:tr"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        print(f"\n🔍 Google News Query İle Aranıyor: '{domain}' (Sorgu: when:{period})", flush=True)
        try:
            res = requests.get(rss_url, headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"❌ RSS isteği başarısız oldu ({domain}): HTTP {res.status_code}", flush=True)
                return []

            soup = BeautifulSoup(res.text, "xml")
            items = soup.find_all("item")
            print(f"🔗 Google News toplam {len(items)} adet güncel haber bağlantısı buldu. ({max_articles} tanesi işlenecek)", flush=True)

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

if __name__ == "__main__":
    # Test etmek istediğiniz alan adları:
    target_domains = [
        "turizmguncel.com",
        "turizmajansi.com",
        "sabah.com.tr",
        "milliyet.com.tr"
    ]

    scraper = UniversalGoogleNewsScraper()
    all_results = {}
    today_str = datetime.now().strftime("%Y-%m-%d")

    for dom in target_domains:
        news_items = scraper.fetch_today_news_for_domain(dom, period="1d")
        all_results[dom] = {
            "count": len(news_items),
            "articles": news_items
        }

    # Çıktıyı JSON olarak kaydedelim
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "google_news_query_results.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "date": today_str,
            "query_period": "when:1d",
            "results": all_results
        }, f, ensure_ascii=False, indent=4)

    print(f"\n✅ Tüm sonuçlar '{output_file}' dosyasına başarıyla kaydedildi!")
