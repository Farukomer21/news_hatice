import os
import re
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
import trafilatura

class TurizmGuncelScraper:
    """
    https://www.turizmguncel.com/ haber sitesinden 
    belirtilen tarihe ait tüm haberleri ve tam metinlerini (full body) çeken kazıyıcı.
    """
    BASE_URL = "https://www.turizmguncel.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    CATEGORIES = [
        "",
        "/gundem",
        "/konaklama",
        "/havacilik",
        "/turlar",
        "/kruvaziyer",
        "/gastronomi",
        "/teknoloji"
    ]

    def get_article_links(self) -> List[str]:
        """
        Sitenin ana sayfasından ve kategorilerinden haber bağlantılarını toplayarak döndürür.
        """
        article_links = set()
        print("🔍 TurizmGüncel sitesindeki haber bağlantıları taranıyor...")

        for cat in self.CATEGORIES:
            url = f"{self.BASE_URL}{cat}"
            try:
                res = requests.get(url, headers=self.HEADERS, timeout=10)
                if res.status_code == 200:
                    found = re.findall(r'href=[\"\'](/haber/[^\"\'\s]+)', res.text)
                    article_links.update(found)
            except Exception as e:
                print(f"Kategori taranırken hata: {cat} -> {e}")

        links_list = [f"{self.BASE_URL}{link}" for link in article_links]
        print(f"🔗 Toplam {len(links_list)} adet benzersiz haber bağlantısı bulundu.")
        return links_list

    def extract_article_details(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Verilen haber URL'sinden başlık, yayınlanma tarihi ve tam metni ayıklar.
        """
        try:
            res = requests.get(url, headers=self.HEADERS, timeout=10)
            if res.status_code != 200:
                return None

            soup = BeautifulSoup(res.text, "html.parser")

            # Başlık
            title_tag = soup.find("h1")
            title = title_tag.text.strip() if title_tag else "Başlık Bulunamadı"

            # Yayınlanma Tarihi
            meta_date = soup.find("meta", {"property": "article:published_time"})
            time_tag = soup.find("time")
            
            published_iso = ""
            if meta_date and meta_date.get("content"):
                published_iso = meta_date["content"]
            elif time_tag and time_tag.text:
                published_iso = time_tag.text.strip()

            # Tam Metin (Full Body) Çıkarma
            full_text = trafilatura.extract(res.text, include_comments=False, include_tables=False)

            return {
                "url": url,
                "title": title,
                "published_date": published_iso,
                "full_text": full_text or ""
            }

        except Exception as e:
            print(f"Haber çekilirken hata ({url}): {e}")
            return None

    def fetch_today_news(self, target_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Belirtilen tarihe (varsayılan: Bugün "YYYY-MM-DD") ait haberleri süzüp getirir.
        """
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")

        print(f"📅 Hedef Tarih Filtresi: {target_date}")
        all_links = self.get_article_links()
        matching_news = []

        for idx, url in enumerate(all_links, 1):
            print(f"[{idx}/{len(all_links)}] İnceleniyor: {url}")
            article = self.extract_article_details(url)
            
            if article and article["published_date"]:
                # Tarih eşleştirmesi (Örn: '2026-08-03' tarihin başında yer alıyor mu?)
                if target_date in article["published_date"]:
                    matching_news.append(article)
                    print(f"   ✅ Bugünün Haberi Bulundu: {article['title']}")
                else:
                    print(f"   ⏭️ Farklı Tarih ({article['published_date'][:10]}), Atlandı.")
            
            # Sunucuyu yormamak için kısa bekleme süresi
            time.sleep(0.3)

        print(f"\n🎉 {target_date} tarihine ait toplam {len(matching_news)} haber başarıyla çekildi.")
        return matching_news

if __name__ == "__main__":
    scraper = TurizmGuncelScraper()
    
    # Bugünün tarihi (Örn: "2026-08-03")
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    news_list = scraper.fetch_today_news(target_date=today_date)

    # Sonuçları JSON dosyasına kaydedelim
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "turizmguncel_today_news.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "site": "https://www.turizmguncel.com",
            "date": today_date,
            "total_count": len(news_list),
            "articles": news_list
        }, f, ensure_ascii=False, indent=4)

    print(f"\n✅ Çıktı '{output_file}' dosyasına kaydedildi.\n")

    # Çekilen haberlerin özetini ekrana basalım
    for i, item in enumerate(news_list, 1):
        print(f"[{i}] {item['title']}")
        print(f"    Tarih: {item['published_date']}")
        print(f"    URL: {item['url']}")
        print(f"    Metin Uzunluğu: {len(item['full_text'])} karakter")
        print(f"    Metin Başlangıcı: {item['full_text'][:200]}...\n")
        print("-" * 60)
