import os
import json
import sys
from datetime import datetime

# news_fetch modülünden kazıyıcıyı içe aktar
from news_fetch import UniversalGoogleNewsScraper, TARGET_DOMAINS_BY_CATEGORY

def main():
    print("🚀 Belirlenen Kaynaklardan Bugünkü (TSİ 00:00'dan İtibaren) Haberleri Toplama Başlatılıyor...\n", flush=True)
    scraper = UniversalGoogleNewsScraper()
    
    # 43 hedef haber sitesinden haber çekme (varsayılan: domain başı 3 haber, sadece bugün TSİ 00:00 sonrası)
    results = scraper.fetch_all_categories(max_articles_per_domain=3, only_today=True)
    flat_articles = scraper.flatten_articles(results)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_categorized = os.path.join(script_dir, "news_output.json")
    output_flat_list = os.path.join(script_dir, "news_list.json")
    
    # 1) Hiyerarşik/Kategorize edilmiş JSON çıktısı
    scraper.save_to_json(results, output_categorized)
    
    # 2) Doğrudan dizi/liste olarak kolayca okunabilir JSON çıktısı
    scraper.save_to_json(flat_articles, output_flat_list)

    print(f"\n🎉 Haber Çekme İşlemi Tamamlandı! Toplam {len(flat_articles)} adet haber kaydedildi.")
    print(f"📁 Kategorili Çıktı Dosyası: '{output_categorized}'")
    print(f"📁 Düz Liste JSON Dosyası (Doğrudan Python/JS okumaları için): '{output_flat_list}'", flush=True)

if __name__ == "__main__":
    main()


