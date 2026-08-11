# News Collection & NLP Data Scrapers

Bu proje, Doğal Dil İşleme (NLP) modelleri için Türkiye, Almanya ve Rusya'daki 43 farklı turizm ve ekonomi haber kaynağından güncel haber verilerini ve tam metinlerini (full body text) otomatik olarak toplamak amacıyla geliştirilmiştir.

## 🌐 Desteklenen Kaynaklar (43 Adet Benzersiz Domain)

### 🇹🇷 Türkiye (Antalya Haber, Turizm & Ekonomi)
- **Antalya Haberleri:** `akdenizgercek.com.tr`, `akdenizmanset.com.tr`, `antalyanews.com.tr`, `gunhaber.com.tr`, `lidergazete.com`, `nehir.net`, `turizmdays.com`, `turizmgazetesi.com`, `turizmguncel.com`, `yenialanya.com`
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

- **`news_fetch.py`**: Google News sorgusu (`site:domain.com when:1d`) ile Türkçe, Almanca ve Rusça dillerindeki haber kaynaklarını otomatik tarayan ana kazıyıcı modülü.
- **`main.py`**: Projenin çalıştırma dosyası. Belirlenen haber kaynaklarından güncel haberleri ve tam metinlerini toplayıp `news_output.json` dosyasına kaydeder.

## 🚀 Kurulum

Gerekli bağımlılıkları yüklemek için:

```bash
pip install -r requirements.txt
```

## 🛠️ Kullanım

Haber kaynaklarından güncel haberleri çekmek için:

```bash
python3 news_fetch.py
```

veya `main.py` üzerinden:

```bash
python3 main.py
```
