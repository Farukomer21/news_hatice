"""
Toplanan haberlerin kaynak bazlı sayı tablosunu üretir.

Kullanım:
    python3 rapor_tablo.py                     # rss_news_list.json okur
    python3 rapor_tablo.py news_list.json      # başka bir düz liste dosyası
    python3 rapor_tablo.py --csv tablo.csv     # ayrıca CSV olarak kaydeder

Sütunlar:
    TOPLAM    : o kaynaktan toplanan haber sayısı
    TAM METİN : haberin tam gövdesi alınanlar
    ÖZET      : tam metin alınamayıp RSS özetiyle kalanlar (text_source=rss_summary)
    BOŞ       : hiç metin alınamayanlar
    ORAN      : (TAM METİN + ÖZET) / TOPLAM
    YÖNTEM    : rss / google / karma
"""

import sys
import csv
import json
import collections

W = (18, 34, 7, 10, 6, 6, 7, 8)
HDR = ("KATEGORİ", "KAYNAK", "TOPLAM", "TAM METİN", "ÖZET", "BOŞ", "ORAN", "YÖNTEM")


def build_rows(articles):
    rows = {}
    for a in articles:
        key = (a.get("category", "?"), a.get("domain", "?"))
        r = rows.setdefault(key, {"n": 0, "art": 0, "sum": 0, "empty": 0,
                                  "m": collections.Counter()})
        r["n"] += 1
        r["m"][a.get("fetch_method", "?")] += 1
        ts = a.get("text_source")
        if ts == "article":
            r["art"] += 1
        elif ts == "rss_summary":
            r["sum"] += 1
        elif a.get("full_text"):
            # fetch_method/text_source taşımayan eski çıktılarla da çalışsın
            r["art"] += 1
        else:
            r["empty"] += 1
    return rows


def method_label(counter):
    has_rss, has_goo = counter.get("rss"), counter.get("google")
    if has_rss and not has_goo:
        return "rss"
    if has_goo and not has_rss:
        return "google"
    if has_rss and has_goo:
        return "karma"
    return "-"


def main():
    args = [a for a in sys.argv[1:]]
    csv_path = None
    if "--csv" in args:
        i = args.index("--csv")
        csv_path = args[i + 1] if i + 1 < len(args) else "tablo.csv"
        del args[i:i + 2]
    path = args[0] if args else "rss_news_list.json"

    try:
        articles = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        print(f"❌ Dosya bulunamadı: {path}")
        sys.exit(1)
    if not isinstance(articles, list):
        print(f"❌ {path} düz haber listesi değil (kategorili dosya verilmiş olabilir).")
        sys.exit(1)

    rows = build_rows(articles)
    line = "─" * (sum(W) + len(W) - 1)
    print(line)
    print(" ".join(h.ljust(w) if i < 2 else h.rjust(w)
                   for i, (h, w) in enumerate(zip(HDR, W))))
    print(line)

    cat_tot = collections.defaultdict(lambda: [0, 0])
    csv_rows = []
    last = None
    for (cat, dom), r in sorted(rows.items(), key=lambda x: (x[0][0], -x[1]["n"])):
        if last and cat != last:
            print()
        last = cat
        got = r["art"] + r["sum"]
        pct = f"%{100*got/r['n']:.0f}" if r["n"] else "-"
        meth = method_label(r["m"])
        cat_tot[cat][0] += r["n"]
        cat_tot[cat][1] += got
        print(f"{cat.ljust(W[0])} {dom[:W[1]].ljust(W[1])} {str(r['n']).rjust(W[2])} "
              f"{str(r['art']).rjust(W[3])} {str(r['sum']).rjust(W[4])} "
              f"{str(r['empty']).rjust(W[5])} {pct.rjust(W[6])} {meth.rjust(W[7])}")
        csv_rows.append([cat, dom, r["n"], r["art"], r["sum"], r["empty"], pct, meth])

    print(line)
    print("KATEGORİ TOPLAMLARI")
    print(line)
    for cat, (n, t) in cat_tot.items():
        print(f"{cat.ljust(W[0])} {''.ljust(W[1])} {str(n).rjust(W[2])} {str(t).rjust(W[3])} "
              f"{''.rjust(W[4])} {str(n-t).rjust(W[5])} {f'%{100*t/n:.0f}'.rjust(W[6])}")

    N = sum(v[0] for v in cat_tot.values())
    T = sum(v[1] for v in cat_tot.values())
    print(line)
    print(f"{'GENEL TOPLAM'.ljust(W[0])} {''.ljust(W[1])} {str(N).rjust(W[2])} "
          f"{str(T).rjust(W[3])} {''.rjust(W[4])} {str(N-T).rjust(W[5])} "
          f"{(f'%{100*T/N:.0f}' if N else '-').rjust(W[6])}")
    print(line)

    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(HDR)
            w.writerows(csv_rows)
        print(f"\n📁 CSV kaydedildi: {csv_path}")


if __name__ == "__main__":
    main()
