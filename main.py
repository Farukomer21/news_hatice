import os
import json
import sys
from datetime import datetime

# news_fetch modülünden kazıyıcıyı içe aktar
from news_fetch import UniversalGoogleNewsScraper, TARGET_DOMAINS_BY_CATEGORY

def main():
    print("🚀 Belirlenen Kaynaklardan Dün Öğlen 12:00'den İtibaren Yayınlanan Haberleri Toplama Başlatılıyor...\n", flush=True)
    scraper = UniversalGoogleNewsScraper()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_categorized = os.path.join(script_dir, "news_output.json")
    output_flat_list = os.path.join(script_dir, "news_list.json")
    
    auto_save_paths = {
        "categorized": output_categorized,
        "flat": output_flat_list
    }

    # 62 hedef haber sitesinden paralel haber çekme (LİMİTSİZ: dün öğlen 12:00'den itibaren + anlık auto-save)
    results = scraper.fetch_all_categories(
        max_articles_per_domain=None, 
        since_yesterday_noon=True,
        auto_save_paths=auto_save_paths
    )
    flat_articles = scraper.flatten_articles(results)

    print(f"\n🎉 Haber Çekme İşlemi Tamamlandı! Toplam {len(flat_articles)} adet haber kaydedildi.")
    print(f"📁 Kategorili Çıktı Dosyası: '{output_categorized}'")
    print(f"📁 Düz Liste JSON Dosyası (Doğrudan Python/JS okumaları için): '{output_flat_list}'", flush=True)

if __name__ == "__main__":
    main()



