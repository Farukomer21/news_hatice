import os
import json
import time
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
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
            # Antalya Turizm Odaklı Kaynaklar
            "hurriyet.com.tr Antalya turizm",
            "milliyet.com.tr Antalya turizm",
            "tourismjournal.com.tr",
            "turizmajansi.com",
            "turizmdays.com",
            "turizmgazetesi.com",
            "turizmguncel.com",
            # En Popüler 3 Genel Antalya Haber Kaynağı
            "akdenizmanset.com.tr",
            "gunhaber.com.tr",
            "yenialanya.com"
        ]
    },
    "turkey_tourism": {
        "lang": "tr", "gl": "TR", "ceid": "TR:tr",
        "domains": [
            # En Popüler 10 Türkiye Turizm Kaynağı
            "turizmguncel.com",
            "turizmgunlugu.com",
            "turizmgazetesi.com",
            "turizmajansi.com",
            "turizmaktuel.com",
            "tourismtoday.net",
            "tourismjournal.com.tr",
            "aktob.org.tr",
            "turizminsesi.com",
            "turizmhabermerkezi.net"
        ]
    },
    "turkey_economy": {
        "lang": "tr", "gl": "TR", "ceid": "TR:tr",
        "domains": [
            "bloomberght.com", "ekonomim.com", "paraanaliz.com",
            "sabah.com.tr", "milliyet.com.tr"
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

    def fetch_all_categories(
        self, 
        max_articles_per_domain: Optional[int] = None, 
        since_yesterday_noon: bool = True,
        only_today: bool = False,
        auto_save_paths: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Tüm ülkelerdeki ve kategorilerdeki kaynakların dün öğlen 12:00'den itibaren yayınlanan haberlerini sırayla çeker.
        auto_save_paths verilirse her domain bittiğinde dosyaları diske anlık otomatik kaydeder.
        """
        all_data = {}
        now_tsi = datetime.now(TSI_TZ)
        total_articles_count = 0

        if since_yesterday_noon:
            start_time_tsi = get_yesterday_noon_tsi()
            filter_desc = f"Dün Öğlen 12:00'den İtibaren ({start_time_tsi.strftime('%Y-%m-%d %H:%M:%S TSİ')})"
        elif only_today:
            start_time_tsi = get_today_start_tsi()
            filter_desc = f"Bugün 00:00'dan İtibaren ({start_time_tsi.strftime('%Y-%m-%d %H:%M:%S TSİ')})"
        else:
            start_time_tsi = None
            filter_desc = "Tüm Zamanlar"

        try:
            for category_name, config in TARGET_DOMAINS_BY_CATEGORY.items():
                print(f"\n==================================================")
                print(f"🌐 Kategori Taranıyor: {category_name.upper()}")
                print(f"==================================================", flush=True)
                
                category_results = {}
                for dom in config["domains"]:
                    news_items = self.fetch_today_news_for_domain(
                        domain=dom,
                        period="2d",
                        max_articles=max_articles_per_domain,
                        lang=config["lang"],
                        gl=config["gl"],
                        ceid=config["ceid"],
                        since_yesterday_noon=since_yesterday_noon,
                        only_today=only_today,
                        category=category_name
                    )

                    category_results[dom] = {
                        "count": len(news_items),
                        "articles": news_items
                    }
                    total_articles_count += len(news_items)

                    # Anlık Otomatik Kaydetme (Auto-save)
                    all_data[category_name] = category_results
                    if auto_save_paths:
                        current_out = {
                            "fetch_time_tsi": datetime.now(TSI_TZ).strftime("%Y-%m-%d %H:%M:%S TSİ"),
                            "filter_start_tsi": start_time_tsi.strftime("%Y-%m-%d %H:%M:%S TSİ") if start_time_tsi else "",
                            "filter_description": filter_desc,
                            "total_domains": sum(len(c["domains"]) for c in TARGET_DOMAINS_BY_CATEGORY.values()),
                            "total_articles_collected": total_articles_count,
                            "categories": all_data
                        }
                        if "categorized" in auto_save_paths:
                            self.save_to_json(current_out, auto_save_paths["categorized"])
                        if "flat" in auto_save_paths:
                            self.save_to_json(self.flatten_articles(current_out), auto_save_paths["flat"])

                all_data[category_name] = category_results

        except KeyboardInterrupt:
            print("\n⚠️ Tarama kullanıcı tarafından durduruldu! Şimdiye kadar toplanan tüm haberler kaydediliyor...", flush=True)

        health_report = self.generate_health_report(all_data)

        final_result = {
            "fetch_time_tsi": datetime.now(TSI_TZ).strftime("%Y-%m-%d %H:%M:%S TSİ"),
            "filter_start_tsi": start_time_tsi.strftime("%Y-%m-%d %H:%M:%S TSİ") if start_time_tsi else "",
            "filter_description": filter_desc,
            "total_domains": sum(len(c["domains"]) for c in TARGET_DOMAINS_BY_CATEGORY.values()),
            "total_articles_collected": total_articles_count,
            "diagnostics": health_report,
            "categories": all_data
        }

        if auto_save_paths:
            if "categorized" in auto_save_paths:
                self.save_to_json(final_result, auto_save_paths["categorized"])
            if "flat" in auto_save_paths:
                self.save_to_json(self.flatten_articles(final_result), auto_save_paths["flat"])

        return final_result

    @staticmethod
    def generate_health_report(categories: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tarama sonuçlarına göre kaynakların sağlık ve bloklanma raporunu çıkarır.
        """
        healthy = []
        zero_news = []
        blocked_or_empty = []

        for cat_name, domains_data in categories.items():
            for domain, info in domains_data.items():
                count = info.get("count", 0)
                articles = info.get("articles", [])
                
                if count == 0 or len(articles) == 0:
                    zero_news.append({"domain": domain, "category": cat_name, "reason": "0 haber bulundu"})
                    continue
                
                empty_texts = sum(1 for a in articles if not a.get("full_text"))
                if empty_texts == len(articles):
                    blocked_or_empty.append({
                        "domain": domain, 
                        "category": cat_name, 
                        "total": len(articles), 
                        "empty": empty_texts,
                        "reason": "Tüm haber metinleri boş (Bot/Paywall/Sayfa yapısı)"
                    })
                elif empty_texts > 0:
                    blocked_or_empty.append({
                        "domain": domain, 
                        "category": cat_name, 
                        "total": len(articles), 
                        "empty": empty_texts,
                        "reason": f"{len(articles)} haberin {empty_texts} tanesinde metin boş"
                    })
                else:
                    healthy.append({"domain": domain, "category": cat_name, "articles_count": len(articles)})

        suggested_removals = [item["domain"] for item in zero_news] + [item["domain"] for item in blocked_or_empty if item["empty"] == item["total"]]

        return {
            "healthy_domains_count": len(healthy),
            "zero_news_domains": zero_news,
            "blocked_or_empty_domains": blocked_or_empty,
            "suggested_removals": suggested_removals
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


