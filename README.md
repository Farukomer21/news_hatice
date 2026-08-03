# News Collection & NLP Data Scrapers

Bu proje, Doğal Dil İşleme (NLP) modelleri için farklı haber kaynaklarından güncel haber verilerini ve tam metinlerini (full body text) otomatik olarak toplamak amacıyla geliştirilmiştir.

## 📁 Proje Yapısı

- **`Currents API/`**: Currents API entegrasyonu. Haber başlıkları, özetler ve ham JSON verisi.
- **`TurizmGüncel/`**: TurizmGüncel (turizmguncel.com) için özel haber ve tam metin kazıyıcı.
- **`Turizm Ajansı/`**: Turizm Ajansı (turizmajansi.com) için özel haber ve tam metin kazıyıcı.
- **`GoogleNewsQuery/`**: Google News `site:domain.com when:1d` sorgusunu kullanan ve HER HANGİ bir haber sitesinin son 24 saatlik haberlerinin tam metinlerini jenerik olarak çeken evrensel kazıyıcı.

## 🚀 Kurulum

Gerekli bağımlılıkları yüklemek için:

```bash
pip install -r requirements.txt
```

## 🛠️ Kullanım

### Google News Evrensel Kazıyıcı:
```bash
python3 GoogleNewsQuery/universal_google_news_scraper.py
```

### Currents API Entegrasyonu:
```bash
python3 "Currents API/currents_api.py"
```

### Özel Site Kazıyıcılar:
```bash
python3 "TurizmGüncel/turizm_guncel_scraper.py"
python3 "Turizm Ajansı/turizm_ajansi_scraper.py"
```
