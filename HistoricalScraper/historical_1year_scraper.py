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

# Türkiye, Almanya ve Rusya için 43 adet kategorize edilmiş haber kaynağı
TARGET_DOMAINS_BY_CATEGORY = {
    "turkey_tourism": {
        "country": "Turkey", "category_type": "Tourism", "lang": "tr", "gl": "TR", "ceid": "TR:tr",
        "domains": [
            "turizmguncel.com", "turizmgazetesi.com", "turizmajansi.com", "gmdergi.com",
            "tourexpi.com", "turizmgunlugu.com", "tourismtoday.net", "turizmaktuel.com",
            "turizmnews.com", "turizmekonomi.com", "turizminsesi.com", "turizmdosyasi.com"
        ]
    },
    "turkey_economy": {
        "country": "Turkey", "category_type": "Economy", "lang": "tr", "gl": "TR", "ceid": "TR:tr",
        "domains": [
            "bloomberght.com", "ekonomim.com", "news.foreks.com", "paraanaliz.com",
            "tr.investing.com", "sabah.com.tr", "milliyet.com.tr"
        ]
    },
    "germany_tourism": {
        "country": "Germany", "category_type": "Tourism", "lang": "de", "gl": "DE", "ceid": "DE:de",
        "domains": [
            "fvw.de", "touristik-aktuell.de", "reisevor9.de", "travelone.de",
            "trvlcounter.de", "travelbook.de", "germany.travel"
        ]
    },
    "germany_economy": {
        "country": "Germany", "category_type": "Economy", "lang": "de", "gl": "DE", "ceid": "DE:de",
        "domains": [
            "handelsblatt.com", "wiwo.de", "boersen-zeitung.de", "finanzen.net", "manager-magazin.de"
        ]
    },
    "russia_tourism": {
        "country": "Russia", "category_type": "Tourism", "lang": "ru", "gl": "RU", "ceid": "RU:ru",
        "domains": [
            "atorus.ru", "tourdom.ru", "profi.travel", "ratanews.ru", "trn-news.ru", "interfax-russia.ru"
        ]
    },
    "russia_economy": {
        "country": "Russia", "category_type": "Economy", "lang": "ru", "gl": "RU", "ceid": "RU:ru",
        "domains": [
            "rbc.ru", "kommersant.ru", "vedomosti.ru", "forbes.ru", "finmarket.ru", "interfax.ru"
        ]
    }
}

class HistoricalNewsScraper:
    """
    43 haber kaynağından son 1 yıla ait haberleri ay ay tarayarak toplayan 
    ve etiketleme (labeling) için veriyi 2 eşit parçaya bölen kazıyıcı.
    """
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    @staticmethod
    def get_monthly_ranges(num_months: int = 12) -> List[tuple]:
        """
        Son 12 ay için başlangıç ve bitiş tarihlerini (YYYY-MM-DD) döndürür.
        """
        now = datetime.now()
        year, month = now.year, now.month
        ranges = []
        for i in range(num_months - 1, -1, -1):
            m = month - i
            y = year
            while m <= 0:
                m += 12
                y -= 1
            start_str = f"{y:04d}-{m:02d}-01"
            next_m = m + 1
            next_y = y
            if next_m > 12:
                next_m = 1
                next_y += 1
            end_str = f"{next_y:04d}-{next_m:02d}-01"
            if i == 0:
                end_str = now.strftime("%Y-%m-%d")
            ranges.append((start_str, end_str))
        return ranges

    def fetch_articles_for_range(
        self,
        domain: str,
        start_date: str,
        end_date: str,
        lang: str,
        gl: str,
        ceid: str,
        max_articles: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Belirli bir tarih aralığı için Google News sorgusu atar.
        """
        query_str = f"site:{domain} after:{start_date} before:{end_date}"
        encoded_query = urllib.parse.quote(query_str)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}&gl={gl}&ceid={ceid}"

        articles = []
        try:
            res = requests.get(rss_url, headers=self.HEADERS, timeout=15)
            if res.status_code != 200:
                return []

            soup = BeautifulSoup(res.text, "xml")
            items = soup.find_all("item")

            for item in items[:max_articles]:
                title = item.find("title").text if item.find("title") else "Başlık Yok"
                pub_date = item.find("pubDate").text if item.find("pubDate") else ""
                google_link = item.find("link").text if item.find("link") else ""

                # Real URL decoding
                real_url = google_link
                try:
                    decoded_res = new_decoderv1(google_link)
                    if decoded_res and decoded_res.get("status") and decoded_res.get("decoded_url"):
                        real_url = decoded_res["decoded_url"]
                except Exception:
                    pass

                # Full text extraction
                full_text = ""
                try:
                    downloaded = trafilatura.fetch_url(real_url)
                    if downloaded:
                        full_text = trafilatura.extract(downloaded, include_comments=False, include_tables=False) or ""
                except Exception:
                    pass

                if full_text and len(full_text) > 100:  # Boş veya çok kısa metinleri süzüyoruz
                    articles.append({
                        "domain": domain,
                        "title": title,
                        "google_link": google_link,
                        "url": real_url,
                        "pub_date": pub_date,
                        "full_text_length": len(full_text),
                        "full_text": full_text
                    })

                time.sleep(0.2)

        except Exception as e:
            print(f"Hata ({domain} [{start_date} - {end_date}]): {e}", flush=True)

        return articles

    def collect_1year_dataset(self, max_per_month_per_domain: int = 5) -> List[Dict[str, Any]]:
        """
        43 domain ve 12 ay için tüm haberleri toplar ve tekrarlanan haberleri eler.
        """
        monthly_ranges = self.get_monthly_ranges(num_months=12)
        print(f"📅 Son 1 Yıl 12 Aylık Dilimlere Bölündü ({monthly_ranges[0][0]} - {monthly_ranges[-1][1]})", flush=True)

        seen_urls = set()
        all_articles = []

        total_domains = sum(len(c["domains"]) for c in TARGET_DOMAINS_BY_CATEGORY.values())
        current_dom_count = 0

        for cat_name, config in TARGET_DOMAINS_BY_CATEGORY.items():
            print(f"\n==========================================", flush=True)
            print(f"🌐 Kategori: {cat_name.upper()} ({len(config['domains'])} Domain)", flush=True)
            print(f"==========================================", flush=True)

            for dom in config["domains"]:
                current_dom_count += 1
                print(f"\n[{current_dom_count}/{total_domains}] Domain Taranıyor: {dom}", flush=True)
                dom_article_count = 0

                for start_d, end_d in monthly_ranges:
                    items = self.fetch_articles_for_range(
                        domain=dom,
                        start_date=start_d,
                        end_date=end_d,
                        lang=config["lang"],
                        gl=config["gl"],
                        ceid=config["ceid"],
                        max_articles=max_per_month_per_domain
                    )

                    for item in items:
                        if item["url"] not in seen_urls:
                            seen_urls.add(item["url"])
                            item["country"] = config["country"]
                            item["category_group"] = config["category_type"]
                            all_articles.append(item)
                            dom_article_count += 1

                print(f"  --> {dom} için toplam {dom_article_count} benzersiz haber toplandı.", flush=True)

        return all_articles

if __name__ == "__main__":
    scraper = HistoricalNewsScraper()

    print("🚀 Son 1 Yıllık Haber Toplama İşlemi Başlatılıyor...", flush=True)
    # Her domain için her ay maks 4 haber çekiyoruz (43 domain x 12 ay x 4 = ~2.000+ kaliteli haber)
    dataset = scraper.collect_1year_dataset(max_per_month_per_domain=4)

    total_count = len(dataset)
    print(f"\n🎉 Toplam {total_count} adet benzersiz haber başarıyla toplandı ve metinleri çıkarıldı!", flush=True)

    # Veriyi Tam Eşit 2 Parçaya Bölüyoruz
    half_size = total_count // 2
    part1 = dataset[:half_size]
    part2 = dataset[half_size:]

    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_part1 = os.path.join(script_dir, "dataset_part1.json")
    file_part2 = os.path.join(script_dir, "dataset_part2.json")

    with open(file_part1, "w", encoding="utf-8") as f:
        json.dump({
            "part": 1,
            "total_part_count": len(part1),
            "articles": part1
        }, f, ensure_ascii=False, indent=4)

    with open(file_part2, "w", encoding="utf-8") as f:
        json.dump({
            "part": 2,
            "total_part_count": len(part2),
            "articles": part2
        }, f, ensure_ascii=False, indent=4)

    print(f"\n✅ Veri Seti Eşit Şekilde 2 Dosyaya Bölündü:")
    print(f" 📂 Part 1 ({len(part1)} Haber): '{file_part1}'")
    print(f" 📂 Part 2 ({len(part2)} Haber): '{file_part2}'", flush=True)
