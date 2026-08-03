import os
import json
import requests
from typing import Optional, Dict, Any
import trafilatura

class CurrentsAPI:
    """
    Currents API (https://currentsapi.services) entegrasyon sınıfı.
    NLP uygulamaları için haber verilerini çekmek amacıyla kullanılır.
    """
    BASE_URL = "https://api.currentsapi.services/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CURRENTS_API_KEY")

    @staticmethod
    def fetch_article_full_text(url: str) -> Optional[str]:
        """
        Haber URL'inden sayfanın tam metnini (Full Body Text) ayıklar.
        """
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
                return text
        except Exception as e:
            print(f"Metin çekilirken hata oluştu ({url}): {e}")
        return None

    def fetch_latest_news(self, language: str = "tr", category: Optional[str] = None) -> Dict[str, Any]:
        """
        En son eklenen haberleri getirir.
        """
        if not self.api_key:
            raise ValueError("API Anahtarı eksik! Lütfen geçerli bir Currents API anahtarı sağlayın.")

        url = f"{self.BASE_URL}/latest-news"
        params = {
            "apiKey": self.api_key,
            "language": language
        }
        if category:
            params["category"] = category

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def search_news(self, keywords: str, language: str = "tr", start_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Arama terimine (keywords) göre haberleri arar.
        """
        if not self.api_key:
            raise ValueError("API Anahtarı eksik! Lütfen geçerli bir Currents API anahtarı sağlayın.")

        url = f"{self.BASE_URL}/search"
        params = {
            "apiKey": self.api_key,
            "keywords": keywords,
            "language": language
        }
        if start_date:
            params["start_date"] = start_date

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

def display_news(data: Dict[str, Any], limit: int = 5):
    """
    Haber verilerini konsolda düzenli şekilde gösterir.
    """
    news_list = data.get("news", [])
    if not news_list:
        print("Haber bulunamadı.")
        return

    print(f"\n--- Son {min(limit, len(news_list))} Haber ---\n")
    for i, article in enumerate(news_list[:limit], 1):
        title = article.get("title", "Başlık Yok")
        author = article.get("author", "Bilinmiyor")
        categories = ", ".join(article.get("category", []))
        published = article.get("published", "")
        url = article.get("url", "")
        description = article.get("description", "")

        print(f"[{i}] {title}")
        print(f"    Yazar: {author}")
        print(f"    Kategori: {categories}")
        print(f"    Yayınlanma Tarihi: {published}")
        print(f"    URL: {url}")
        print(f"    Özet: {description}\n")
        print("-" * 60)

if __name__ == "__main__":
    API_KEY = "fy8nuCvGr7J_2za5N2_7e74ZudqsyqeHOUS1Uq6ly8VW-POV"

    api = CurrentsAPI(api_key=API_KEY)
    try:
        print("🚀 Currents API'ye 1 adet istek atılıyor...")
        news_data = api.fetch_latest_news(language="tr")
        
        # Ham JSON çıktısını dosyaya yazalım
        script_dir = os.path.dirname(os.path.abspath(__file__))
        raw_output_file = os.path.join(script_dir, "currents_news_raw.json")
        with open(raw_output_file, "w", encoding="utf-8") as f:
            json.dump(news_data, f, ensure_ascii=False, indent=4)
        print(f"✅ Tüm ham veriler (JSON formatında) '{raw_output_file}' dosyasına kaydedildi.")

        # Ekran çıktısını ve özetini gösterelim
        display_news(news_data, limit=10)

    except Exception as e:
        print(f"❌ Hata oluştu: {e}")

