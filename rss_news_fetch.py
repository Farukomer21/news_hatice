"""
Yayıncı RSS beslemelerini birincil kaynak olarak kullanan haber toplayıcı.

news_fetch.py'deki Google News yolundan farkı:
  - Google News decoder'ına (ve onun IP bazlı 429 rate limit'ine) bağımlı değil
  - Kiril/aksanlı başlıklarda çalışır (Google yolundaki [a-z0-9] token sorunu yok)
  - RSS doğrudan gerçek makale URL'ini verdiği için bölüm/listeleme sayfası
    metninin haber gövdesi diye kaydedilmesi mümkün değil

RSS'i olmayan kaynaklar için news_fetch.py'deki Google News yolu yedek olarak kullanılır.
Çıktı şeması news_fetch.py ile aynıdır; ek olarak teşhis alanları taşır.
"""

import os
import re
import sys
import json
import time
import hashlib
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

import requests
import trafilatura
from bs4 import BeautifulSoup

# Mevcut modülü değiştirmeden yeniden kullanıyoruz
from news_fetch import (
    TSI_TZ,
    get_today_start_tsi,
    get_yesterday_noon_tsi,
    parse_pub_date_to_tsi,
    TARGET_DOMAINS_BY_CATEGORY,
    UniversalGoogleNewsScraper,
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Canlı olarak doğrulanmış RSS adresleri (2026-08-14 taraması).
# Bir domain için birden fazla besleme verilebilir; hepsi birleştirilir.
RSS_FEEDS: Dict[str, List[str]] = {
    # --- Antalya / Türkiye turizm ---
    "akdenizmanset.com.tr": ["https://www.akdenizmanset.com.tr/rss"],
    "haberantalya.com": ["https://www.haberantalya.com/rss"],
    "turizmajansi.com": ["https://www.turizmajansi.com/rss"],
    "turizmaktuel.com": ["https://www.turizmaktuel.com/rss"],
    "turizmdays.com": ["https://www.turizmdays.com/rss.xml"],
    "turizmgazetesi.com": ["https://www.turizmgazetesi.com/rss"],
    "turizmguncel.com": ["https://www.turizmguncel.com/rss.xml"],
    "turizmgunlugu.com": ["https://www.turizmgunlugu.com/feed/"],
    "turizmgundemi.com": ["https://turizmgundemi.com/feed/"],
    "turizmhabermerkezi.net": ["https://www.turizmhabermerkezi.net/rss"],
    "turizmnews.com": ["https://www.turizmnews.com/rss.xml"],
    "turizminsesi.com": ["https://www.turizminsesi.com/rss/"],
    "tourismtoday.net": ["https://www.tourismtoday.net/rss.xml"],
    "yenialanya.com": ["https://www.yenialanya.com/rss"],

    # --- Türkiye genel / ekonomi ---
    "hurriyet.com.tr": [
        "https://www.hurriyet.com.tr/rss/gundem",
        "https://www.hurriyet.com.tr/rss/seyahat",
        "https://www.hurriyet.com.tr/rss/ekonomi",
    ],
    "milliyet.com.tr": [
        "https://www.milliyet.com.tr/rss/rssnew/gundemrss.xml",
        "https://www.milliyet.com.tr/rss/rssnew/ekonomirss.xml",
    ],
    "sabah.com.tr": [
        "https://www.sabah.com.tr/rss/turizm.xml",
        "https://www.sabah.com.tr/rss/ekonomi.xml",
    ],
    "bloomberght.com": ["https://www.bloomberght.com/rss"],
    "ekonomim.com": ["https://www.ekonomim.com/export/rss"],
    "paraanaliz.com": ["https://paraanaliz.com/rss.xml"],

    # --- Almanya ---
    "fvw.de": ["https://www.fvw.de/news/feed/"],
    "touristik-aktuell.de": ["https://www.touristik-aktuell.de/feed/"],
    "reisevor9.de": ["https://www.reisevor9.de/view/rss/59"],
    "handelsblatt.com": ["https://www.handelsblatt.com/contentexport/feed/schlagzeilen"],
    "wiwo.de": ["https://www.wiwo.de/contentexport/feed/rss/schlagzeilen"],

    # --- Rusya ---
    "tourdom.ru": ["https://www.tourdom.ru/rss"],
    "ratanews.ru": ["https://ratanews.ru/rss.xml"],
    "trn-news.ru": ["https://www.trn-news.ru/feed"],
    "kommersant.ru": ["https://www.kommersant.ru/RSS/news.xml"],
    "vedomosti.ru": ["https://vedomosti.ru/rss/articles"],
    "forbes.ru": ["https://www.forbes.ru/newrss.xml"],
    "finmarket.ru": ["https://www.finmarket.ru/rss/mainnews.asp"],
    "interfax.ru": ["https://www.interfax.ru/rss"],
}

# RSS bulunamayan (ya da beslemesi boş dönen) kaynaklar; bunlar Google News yoluna düşer.
NO_RSS_DOMAINS = {
    "atorus.ru", "boersen-zeitung.de", "gunhaber.com.tr", "profi.travel",
    "tourismjournal.com.tr",   # /rss 200 dönüyor ama içi boş; Google yolu %100 tam metin veriyor
}

# Taramadan tamamen çıkarılan kaynaklar (2026-08-14 canlı doğrulama).
# news_fetch.py'deki TARGET_DOMAINS_BY_CATEGORY'ye dokunmadan burada eleniyor,
# böylece eski Google News yolu istenirse aynı listeyle çalışmaya devam eder.
EXCLUDED_DOMAINS = {
    "aktob.org.tr",     # feed sağlam ama zaman penceresinde hiç haber üretmiyor
    "rbc.ru",           # bot koruması: makale sayfaları HTTP 401, sadece RSS özeti alınabiliyor
    "travelbook.de",    # bot koruması: site ve feed HTTP 403 "Access Denied"
    "trvlcounter.de",   # www. alt alanında SSL sertifika uyuşmazlığı, RSS'i de yok
}

# Kaynak bazlı özel haber sayısı kısıtları (aşırı haber üreten dev portallar için)
DOMAIN_ARTICLE_LIMITS = {
    "turizmdays.com": 50,
    "bloomberght.com": 20,
    "ekonomim.com": 20,
    "handelsblatt.com": 20,
    "wiwo.de": 20,
    "kommersant.ru": 15,
    "vedomosti.ru": 15,
    "interfax.ru": 15,
}

# Gövde metni bu uzunluğun altındaysa çerez/JS uyarısı sayılır, kabul edilmez.
MIN_TEXT_LENGTH = 250

# Makale URL'i olamayacak son path parçaları (bölüm / listeleme sayfaları)
NON_ARTICLE_SLUGS = {
    "rss", "feed", "haberler", "haber", "gundem", "turizm", "ekonomi",
    "sondakika", "son-dakika", "news", "index", "anasayfa", "arama",
    "search", "havadurumu", "galeri", "video", "yazarlar", "kategori",
}


def split_domain_and_keywords(entry: str) -> Tuple[str, List[str]]:
    """
    'hurriyet.com.tr Antalya turizm' -> ('hurriyet.com.tr', ['Antalya', 'turizm'])
    'turizmajansi.com'               -> ('turizmajansi.com', [])
    """
    parts = entry.split()
    return parts[0].strip(), parts[1:]


def normalize_for_match(text: str) -> str:
    """Türkçe karakterleri sadeleştirip küçük harfe indirger (anahtar kelime eşleşmesi için)."""
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosucgiosuaiu")
    return text.translate(tr_map).casefold()


def matches_keywords(title: str, summary: str, keywords: List[str]) -> bool:
    """
    Anahtar kelimelerden EN AZ BİRİ başlık veya özette geçiyorsa kabul eder.
    Anahtar kelime yoksa her haber kabul edilir.
    """
    if not keywords:
        return True
    haystack = normalize_for_match(f"{title} {summary}")
    return any(normalize_for_match(k) in haystack for k in keywords)


def looks_like_article_url(url: str) -> bool:
    """
    URL'in bir haber sayfasına mı yoksa bölüm/listeleme sayfasına mı işaret ettiğini kestirir.
    news_fetch.py'deki 'bölüm sayfası metnini haber sanma' hatasına karşı koruma.
    """
    if not url or not url.startswith("http"):
        return False
    try:
        path = urllib.parse.urlparse(url).path.strip("/")
    except Exception:
        return False
    if not path:
        return False
    last = path.split("/")[-1].lower()
    last = re.sub(r"\.(html?|php|aspx?)$", "", last)
    if not last or last in NON_ARTICLE_SLUGS:
        return False
    # Haber URL'leri ya slug taşır ya da sayısal/uzun bir kimlik içerir
    return ("-" in last) or last.isdigit() or len(last) >= 15


def fetch_article_text(url: str, lang_hint: str = "tr") -> str:
    """
    Makale tam metnini çeker. Önce kendi User-Agent'ımızla requests, olmazsa trafilatura.
    Bot koruması olan siteler (ör. rbc.ru HTTP 401) boş string döndürür.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": f"{lang_hint},en;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200 and r.text:
            txt = trafilatura.extract(r.text, include_comments=False, include_tables=False)
            if txt and len(txt) >= MIN_TEXT_LENGTH:
                return txt
    except Exception:
        pass
    try:
        dl = trafilatura.fetch_url(url)
        if dl:
            txt = trafilatura.extract(dl, include_comments=False, include_tables=False)
            if txt and len(txt) >= MIN_TEXT_LENGTH:
                return txt
    except Exception:
        pass
    return ""


def parse_feed(feed_url: str) -> List[Dict[str, str]]:
    """Bir RSS/Atom beslemesini ayrıştırıp ham kayıt listesi döndürür."""
    try:
        r = requests.get(feed_url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "xml")
    except Exception:
        return []

    entries = soup.find_all("item") or soup.find_all("entry")
    out = []
    for e in entries:
        title_el = e.find("title")
        link_el = e.find("link")
        link = ""
        if link_el is not None:
            link = (link_el.text or "").strip() or (link_el.get("href") or "").strip()
        date_el = e.find("pubDate") or e.find("published") or e.find("updated")
        desc_el = e.find("description") or e.find("summary")
        summary = ""
        if desc_el is not None and desc_el.text:
            summary = BeautifulSoup(desc_el.text, "html.parser").get_text(" ", strip=True)
        out.append({
            "title": (title_el.text or "").strip() if title_el else "Başlık Yok",
            "link": link,
            "pub_date": (date_el.text or "").strip() if date_el else "",
            "summary": summary,
        })
    return out


def fetch_domain_via_rss(
    entry: str,
    category: str,
    start_filter_tsi: Optional[datetime],
    max_articles: Optional[int] = None,
    lang: str = "tr",
    max_workers: int = 5,
) -> Optional[List[Dict[str, Any]]]:
    """
    Bir kaynağı RSS üzerinden toplar.
    RSS tanımlı değilse None döndürür (çağıran taraf Google yoluna düşer).
    """
    domain, keywords = split_domain_and_keywords(entry)
    feeds = RSS_FEEDS.get(domain)
    if not feeds:
        return None

    print(f"\n📡 RSS: '{entry}' ({len(feeds)} besleme)", flush=True)

    raw_items, seen_links = [], set()
    for f in feeds:
        for it in parse_feed(f):
            if it["link"] and it["link"] not in seen_links:
                seen_links.add(it["link"])
                raw_items.append(it)
    print(f"   🔗 Beslemelerde toplam {len(raw_items)} kayıt bulundu.", flush=True)

    selected = []
    for it in raw_items:
        pub_dt = parse_pub_date_to_tsi(it["pub_date"])
        if start_filter_tsi and pub_dt and pub_dt < start_filter_tsi:
            continue
        if not matches_keywords(it["title"], it["summary"], keywords):
            continue
        if not looks_like_article_url(it["link"]):
            continue
        selected.append((it, pub_dt))
        # Yeterli dolu haber bulabilmek için aday havuzunu geniş tutuyoruz
        if max_articles and len(selected) >= (max_articles * 3):
            break

    kw_note = f", anahtar kelime: {keywords}" if keywords else ""
    print(f"   🎯 Filtreye uyan {len(selected)} aday haber taranıyor{kw_note}...", flush=True)

    def build(pair):
        it, pub_dt = pair
        text = fetch_article_text(it["link"], lang_hint=lang)
        source = "article"
        if not text and it["summary"] and len(it["summary"]) >= 80:
            text, source = it["summary"], "rss_summary"
        elif not text:
            source = ""
        return {
            "category": category,
            "domain": entry,
            "title": it["title"],
            "google_link": "",
            "url": it["link"],
            "pub_date_raw": it["pub_date"],
            "pub_date_tsi": pub_dt.strftime("%Y-%m-%d %H:%M:%S TSİ") if pub_dt else it["pub_date"],
            "pub_timestamp_iso": pub_dt.isoformat() if pub_dt else "",
            "full_text_length": len(text),
            "full_text": text,
            "fetch_method": "rss",
            "text_source": source,
        }

    articles: List[Dict[str, Any]] = []
    if selected:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            articles = list(ex.map(build, selected))

    # Tekrar eden gövdeleri temizle
    articles = drop_duplicate_bodies(articles)

    # YALNIZCA TAM METNİ DOLU OLAN HABERLERİ AL
    full_articles = [
        a for a in articles 
        if a.get("full_text") and len(a["full_text"].strip()) >= 150
    ]

    if max_articles:
        full_articles = full_articles[:max_articles]

    print(f"✅ '{entry}': {len(full_articles)} adet %100 DOLU haber alındı.", flush=True)
    return full_articles


def sanitize_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Google News yolundan gelen kayıtlara da aynı kalite korumalarını uygular:
    makale olmayan URL'lerin (bölüm/listeleme/hava durumu sayfası) metnini boşaltır,
    ardından tekrar eden gövdeleri temizler.
    """
    for a in articles:
        if a.get("full_text") and not looks_like_article_url(a.get("url", "")):
            a["full_text"] = ""
            a["full_text_length"] = 0
            a["text_source"] = ""
            a["rejected_reason"] = "makale olmayan URL (bölüm/listeleme sayfası)"
    return drop_duplicate_bodies(articles)


def drop_duplicate_bodies(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aynı gövde metni birden fazla haberde görünüyorsa ilki dışındakilerin metnini boşaltır.
    Tekrar eden gövde, yanlış sayfanın (bölüm/listeleme) çekildiğinin işaretidir.
    """
    seen = {}
    for a in articles:
        t = a.get("full_text", "")
        if not t:
            continue
        h = hashlib.sha1(t.encode("utf-8")).hexdigest()
        if h in seen:
            a["full_text"] = ""
            a["full_text_length"] = 0
            a["text_source"] = ""
            a["duplicate_of"] = seen[h]
        else:
            seen[h] = a.get("url", "")
    return articles


class RssFirstNewsScraper:
    """RSS'i birincil, Google News'i yedek kaynak olarak kullanan toplayıcı."""

    def fetch_all_categories(
        self,
        max_articles_per_domain: Optional[int] = None,
        since_yesterday_noon: bool = True,
        only_today: bool = False,
        auto_save_paths: Optional[Dict[str, str]] = None,
        use_google_fallback: bool = True,
    ) -> Dict[str, Any]:
        all_data: Dict[str, Any] = {}
        total = 0

        if since_yesterday_noon:
            start_tsi = get_yesterday_noon_tsi()
            desc = f"Dün Öğlen 12:00'den İtibaren ({start_tsi.strftime('%Y-%m-%d %H:%M:%S TSİ')})"
        elif only_today:
            start_tsi = get_today_start_tsi()
            desc = f"Bugün 00:00'dan İtibaren ({start_tsi.strftime('%Y-%m-%d %H:%M:%S TSİ')})"
        else:
            start_tsi, desc = None, "Tüm Zamanlar"

        try:
            for category_name, config in TARGET_DOMAINS_BY_CATEGORY.items():
                print(f"\n{'='*50}\n🌐 Kategori: {category_name.upper()}\n{'='*50}", flush=True)
                category_results: Dict[str, Any] = {}

                for entry in config["domains"]:
                    dom_clean = split_domain_and_keywords(entry)[0]
                    if dom_clean in EXCLUDED_DOMAINS:
                        print(f"\n⏭️  Atlandı (dışlama listesinde): '{entry}'", flush=True)
                        continue

                    dom_limit = DOMAIN_ARTICLE_LIMITS.get(dom_clean, max_articles_per_domain)

                    items = fetch_domain_via_rss(
                        entry=entry,
                        category=category_name,
                        start_filter_tsi=start_tsi,
                        max_articles=dom_limit,
                        lang=config["lang"],
                    )

                    # RSS tanımlı değilse ya da besleme bayat olduğu için hiç sonuç
                    # vermediyse Google News yoluna düşeriz.
                    if not items and use_google_fallback:
                        why = "RSS yok" if items is None else "RSS 0 sonuç verdi (bayat besleme?)"
                        print(f"\n↩️  {why}, Google News yoluna düşülüyor: '{entry}'", flush=True)
                        items = UniversalGoogleNewsScraper.fetch_today_news_for_domain(
                            domain=entry,
                            period="2d",
                            max_articles=dom_limit,
                            lang=config["lang"],
                            gl=config["gl"],
                            ceid=config["ceid"],
                            since_yesterday_noon=since_yesterday_noon,
                            only_today=only_today,
                            category=category_name,
                        )
                        for a in items:
                            a.setdefault("fetch_method", "google")
                            a.setdefault("text_source", "article" if a.get("full_text") else "")
                        items = sanitize_articles(items)
                    elif items is None:
                        items = []

                    category_results[entry] = {"count": len(items), "articles": items}
                    total += len(items)

                    all_data[category_name] = category_results
                    if auto_save_paths:
                        self._save_snapshot(auto_save_paths, all_data, start_tsi, desc, total)

                all_data[category_name] = category_results

        except KeyboardInterrupt:
            print("\n⚠️ Kullanıcı durdurdu; toplanan haberler kaydediliyor...", flush=True)

        final = {
            "fetch_time_tsi": datetime.now(TSI_TZ).strftime("%Y-%m-%d %H:%M:%S TSİ"),
            "filter_start_tsi": start_tsi.strftime("%Y-%m-%d %H:%M:%S TSİ") if start_tsi else "",
            "filter_description": desc,
            "total_domains": sum(
                1
                for c in TARGET_DOMAINS_BY_CATEGORY.values()
                for d in c["domains"]
                if split_domain_and_keywords(d)[0] not in EXCLUDED_DOMAINS
            ),
            "excluded_domains": sorted(EXCLUDED_DOMAINS),
            "total_articles_collected": total,
            "diagnostics": self.generate_health_report(all_data),
            "categories": all_data,
        }
        if auto_save_paths:
            if "categorized" in auto_save_paths:
                self.save_to_json(final, auto_save_paths["categorized"])
            if "flat" in auto_save_paths:
                self.save_to_json(self.flatten_articles(final), auto_save_paths["flat"])
        return final

    def _save_snapshot(self, paths, all_data, start_tsi, desc, total):
        snap = {
            "fetch_time_tsi": datetime.now(TSI_TZ).strftime("%Y-%m-%d %H:%M:%S TSİ"),
            "filter_start_tsi": start_tsi.strftime("%Y-%m-%d %H:%M:%S TSİ") if start_tsi else "",
            "filter_description": desc,
            "total_articles_collected": total,
            "categories": all_data,
        }
        if "categorized" in paths:
            self.save_to_json(snap, paths["categorized"])
        if "flat" in paths:
            self.save_to_json(self.flatten_articles(snap), paths["flat"])

    @staticmethod
    def generate_health_report(categories: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kaynak sağlığı. news_fetch.py'den farkı: tekrar eden gövdeleri ve
        sadece RSS özeti alınabilen kaynakları da ayrı ayrı raporlar.
        """
        healthy, zero_news, partial, summary_only, duplicates = [], [], [], [], []

        for cat, domains in categories.items():
            for domain, info in domains.items():
                arts = info.get("articles", [])
                if not arts:
                    zero_news.append({"domain": domain, "category": cat, "reason": "0 haber"})
                    continue
                empty = sum(1 for a in arts if not a.get("full_text"))
                dup = sum(1 for a in arts if a.get("duplicate_of"))
                summ = sum(1 for a in arts if a.get("text_source") == "rss_summary")

                if dup:
                    duplicates.append({"domain": domain, "category": cat,
                                       "total": len(arts), "duplicate": dup})
                if summ:
                    summary_only.append({"domain": domain, "category": cat,
                                         "total": len(arts), "rss_summary": summ})
                if empty == len(arts):
                    partial.append({"domain": domain, "category": cat, "total": len(arts),
                                    "empty": empty, "reason": "Tüm metinler boş (bot/paywall)"})
                elif empty:
                    partial.append({"domain": domain, "category": cat, "total": len(arts),
                                    "empty": empty, "reason": f"{len(arts)} haberin {empty} tanesi boş"})
                else:
                    healthy.append({"domain": domain, "category": cat, "articles_count": len(arts)})

        return {
            "healthy_domains_count": len(healthy),
            "healthy_domains": healthy,
            "zero_news_domains": zero_news,
            "partial_or_blocked_domains": partial,
            "rss_summary_only_domains": summary_only,
            "duplicate_body_domains": duplicates,
        }

    @staticmethod
    def flatten_articles(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        flat = []
        for category_name, domains in results.get("categories", {}).items():
            for _domain, info in domains.items():
                for a in info.get("articles", []):
                    c = dict(a)
                    c["category"] = category_name
                    flat.append(c)
        return flat

    @staticmethod
    def save_to_json(data: Any, filepath: str) -> str:
        tmp = f"{filepath}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(tmp, filepath)  # atomik yazım: yarım dosya bırakmaz
        return filepath


def acquire_lock(lock_path: str) -> bool:
    """
    Aynı anda ikinci bir çalışmanın çıktı dosyalarını ezmesini engeller
    (news_fetch.py çalıştırılırken yaşanan sorun).
    """
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            with open(lock_path) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)          # süreç yaşıyor mu
            print(f"⛔ Zaten çalışan bir tarama var (PID {pid}). Çıkılıyor.", flush=True)
            print(f"   Yanlışsa şu dosyayı silin: {lock_path}", flush=True)
            return False
        except (ValueError, ProcessLookupError, FileNotFoundError):
            os.unlink(lock_path)      # bayat kilit
            return acquire_lock(lock_path)
        except PermissionError:
            print(f"⛔ Kilit dosyası başka bir sürece ait: {lock_path}", flush=True)
            return False


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lock_path = os.path.join(script_dir, ".rss_fetch.lock")
    if not acquire_lock(lock_path):
        sys.exit(1)

    try:
        print("🚀 RSS öncelikli haber toplama başlatılıyor...\n", flush=True)
        started = time.time()

        paths = {
            "categorized": os.path.join(script_dir, "rss_news_output.json"),
            "flat": os.path.join(script_dir, "rss_news_list.json"),
        }
        scraper = RssFirstNewsScraper()
        results = scraper.fetch_all_categories(
            max_articles_per_domain=None,
            since_yesterday_noon=True,
            auto_save_paths=paths,
        )
        flat = scraper.flatten_articles(results)
        with_text = sum(1 for a in flat if a["full_text"])
        via_rss = sum(1 for a in flat if a.get("fetch_method") == "rss")

        print(f"\n🎉 Tamamlandı ({time.time()-started:.0f} sn)")
        print(f"   Toplam haber      : {len(flat)}")
        print(f"   Metni alınan      : {with_text}"
              + (f" (%{100*with_text/len(flat):.0f})" if flat else ""))
        print(f"   RSS ile gelen     : {via_rss} | Google yedeği: {len(flat)-via_rss}")
        print(f"📁 {paths['categorized']}")
        print(f"📁 {paths['flat']}", flush=True)
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
