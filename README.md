# News Collection & NLP Data Scrapers

Bu proje, Doğal Dil İşleme (NLP) modelleri için Türkiye, Almanya ve Rusya'daki 43 farklı turizm ve ekonomi haber kaynağından güncel haber verilerini ve tam metinlerini (full body text) otomatik olarak toplamak amacıyla geliştirilmiştir.

## 🌐 Desteklenen Kaynaklar (43 Adet Benzersiz Domain)

### 🇹🇷 Türkiye (Turizm & Ekonomi)
- **Turizm Odaklı:** `turizmguncel.com`, `turizmgazetesi.com`, `turizmajansi.com`, `gmdergi.com`, `tourexpi.com`, `turizmgunlugu.com`, `tourismtoday.net`, `turizmaktuel.com`, `turizmnews.com`, `turizmekonomi.com`, `turizminsesi.com`, `turizmdosyasi.com`
- **Ekonomi Odaklı:** `bloomberght.com`, `ekonomim.com`, `news.foreks.com`, `paraanaliz.com`, `tr.investing.com`, `sabah.com.tr`, `milliyet.com.tr`

### 🇩🇪 Almanya (Turizm & Ekonomi)
- **Turizm Odaklı:** `fvw.de`, `touristik-aktuell.de`, `reisevor9.de`, `travelone.de`, `trvlcounter.de`, `travelbook.de`, `germany.travel`
- **Ekonomi Odaklı:** `handelsblatt.com`, `wiwo.de`, `boersen-zeitung.de`, `finanzen.net`, `manager-magazin.de`

### 🇷🇺 Rusya (Turizm & Ekonomi)
- **Turizm Odaklı:** `atorus.ru`, `tourdom.ru`, `profi.travel`, `ratanews.ru`, `trn-news.ru`, `interfax-russia.ru`
- **Ekonomi Odaklı:** `rbc.ru`, `kommersant.ru`, `vedomosti.ru`, `forbes.ru`, `finmarket.ru`, `interfax.ru`

---

## 📁 Proje Yapısı

- **`GoogleNewsQuery/`**: Google News `site:domain.com when:1d` sorgusunu kullanan, Türkçe, Almanca ve Rusça dillerindeki 43 haber kaynağının son 24 saatlik haberlerinin tam metinlerini jenerik olarak çeken evrensel kazıyıcı.
- **`Currents API/`**: Currents API entegrasyonu.
- **`TurizmGüncel/`**: TurizmGüncel (turizmguncel.com) özel kazıyıcı.
- **`Turizm Ajansı/`**: Turizm Ajansı (turizmajansi.com) özel kazıyıcı.

## 🚀 Kurulum

Gerekli bağımlılıkları yüklemek için:

```bash
pip install -r requirements.txt
```

## 🛠️ Kullanım

### 43 Kaynaktan Evrensel Haber Çekici:
```bash
python3 GoogleNewsQuery/universal_google_news_scraper.py
```
