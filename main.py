import os
import json
import sys
from datetime import datetime

# Import scraper from news_fetch module
from news_fetch import UniversalGoogleNewsScraper, TARGET_DOMAINS_BY_CATEGORY

def main():
    print("🚀 Belirlenen Kaynaklardan Genel Güncel Haber Toplama Başlatılıyor...\n", flush=True)
    scraper = UniversalGoogleNewsScraper()
    
    # 43 hedef haber sitesinden haber çekme (varsayılan: domain başı 3 haber)
    results = scraper.fetch_all_categories(max_articles_per_domain=3)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "news_output.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"\n🎉 Haber Çekme İşlemi Tamamlandı!")
    print(f"📁 Çıktı '{output_file}' dosyasına kaydedildi.", flush=True)

if __name__ == "__main__":
    main()
