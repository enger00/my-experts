# -*- coding: utf-8 -*-
"""
oa_download_v4.py — OA 期刊直连 PDF 下载器（无需 VPN）
覆盖前缀: 10.3389 Frontiers | 10.1155 Hindawi | 10.21037 AME |
          10.18632 Aging | 10.2147 Dove Press
策略: doi.org 解析落地页 → 抓 HTML 提取 citation_pdf_url / .pdf 链接 →
      出版商特有规则补候选 → 直连下载 → %PDF 校验 → 落库
用法:
  python oa_download_v4.py --limit 300 --sleep 2
"""
import sqlite3, json, os, re, time, argparse
import requests

DB = r"E:\TRAE\英文文章\ncu2fy_literature\ncu2fy.db"
PDF_DIR = r"E:\TRAE\英文文章\ncu2fy_literature\pdfs"
MANIFEST = r"E:\TRAE\英文文章\ncu2fy_literature\oa_download_manifest.tsv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0"
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>#?&]+")

PREFIXES = ["10.3389", "10.1155", "10.21037", "10.18632", "10.2147"]
BLOCK_MARKS = ("captcha", "cloudflare", "请稍候", "just a moment", "attention required")

S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})

META_PDF = re.compile(r'<meta[^>]+(?:name|property)=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)', re.I)
META_PDF2 = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>+(?:name|property)=["\']citation_pdf_url["\']', re.I)
A_PDF = re.compile(r'href=["\']([^"\']*(?:\.pdf(?:\?[^"\']*)?|/pdf(?:/|\?|$)|/pdfft[^"\']*)[^"\']*)["\']', re.I)

def normalize_doi(raw):
    if not raw:
        return None
    raw = raw.strip()
    if raw.lower().startswith("http"):
        m = DOI_RE.search(raw)
        return m.group(0).rstrip(".,").lower() if m else None
    return raw.lower() if DOI_RE.match(raw) else None

def resolve_doi(doi, timeout=25):
    try:
        r = S.get(f"https://doi.org/{doi}", timeout=timeout, allow_redirects=True)
        return r.url if r.status_code < 400 else None
    except Exception:
        return None

def absolutize(base, href):
    from urllib.parse import urljoin
    return urljoin(base, href)

def pdf_candidates(landing, html):
    cands = []
    for pat in (META_PDF, META_PDF2):
        m = pat.search(html)
        if m:
            cands.append(absolutize(landing, m.group(1).strip()))
    for m in A_PDF.finditer(html):
        cands.append(absolutize(landing, m.group(1)))
    # 出版商规则: Frontiers /full -> /pdf ; AME /html -> /pdf
    if "/full" in landing:
        cands.append(landing.rsplit("/full", 1)[0] + "/pdf")
    if landing.rstrip("/").endswith("/html"):
        cands.append(landing.rstrip("/")[:-5] + "/pdf")
    # 去重保序
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:6]

def try_download(cands, out_path):
    for u in cands:
        try:
            r = S.get(u, timeout=90, stream=True, allow_redirects=True)
            if r.status_code != 200:
                continue
            head = b""
            data = b""
            for chunk in r.iter_content(1 << 16):
                data += chunk
                if len(data) > 8 or len(data) > 200 * 1024 * 1024:
                    break
            head = data[:8]
            if not head.startswith(b"%PDF"):
                continue
            rest = r.iter_content(1 << 16)
            for chunk in rest:
                data += chunk
                if len(data) > 200 * 1024 * 1024:
                    break
            with open(out_path, "wb") as f:
                f.write(data)
            return len(data)
        except Exception:
            continue
    return None

def pick(limit):
    db = sqlite3.connect(DB)
    db.execute("PRAGMA busy_timeout=60000")
    # doi 字段大量为 URL 格式, 必须在 Python 侧规范化后再筛前缀
    rows = db.execute("""
        SELECT id, doi FROM articles
        WHERE pdf_path='NO_PDF' AND exclude_flag=0 AND doi IS NOT NULL AND doi!=''""").fetchall()
    pset = set(p.lower() for p in PREFIXES)
    out, seen = [], set()
    for aid, raw in rows:
        doi = normalize_doi(raw)
        if doi and doi not in seen and doi.split("/")[0] in pset:
            seen.add(doi)
            out.append({"id": aid, "doi": doi})
    return out[:limit]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--sleep", type=int, default=2)
    args = ap.parse_args()
    arts = pick(args.limit)
    print(f"[plan] {len(arts)} OA papers", flush=True)
    db = sqlite3.connect(DB)
    db.execute("PRAGMA busy_timeout=60000")
    ok = fail = 0
    with open(MANIFEST, "a", encoding="utf-8") as mf:
        for i, art in enumerate(arts, 1):
            doi = art["doi"]
            path = os.path.join(PDF_DIR, f"{art['id']}.pdf")
            try:
                landing = resolve_doi(doi)
                if not landing:
                    status = "doi_resolve_failed"
                else:
                    r = S.get(landing, timeout=60)
                    if r.status_code != 200:
                        status = f"landing_http_{r.status_code}"
                    else:
                        low = r.text[:3000].lower()
                        if any(m in low for m in BLOCK_MARKS):
                            status = "blocked_landing"
                        else:
                            cands = pdf_candidates(r.url, r.text)
                            size = try_download(cands, path) if cands else None
                            if size:
                                db.execute("UPDATE articles SET pdf_path=? WHERE id=?", (path, art["id"]))
                                db.commit()
                                status = f"downloaded"
                                ok += 1
                            else:
                                status = "no_pdf_fetchable"
                                fail += 1
            except Exception as e:
                status = f"error:{str(e)[:50]}"
                fail += 1
            if status != "downloaded":
                fail += 0
            mf.write(f"{art['id']}\t{doi}\t{status}\t{landing if status!='doi_resolve_failed' else ''}\n")
            mf.flush()
            print(f"[{i}/{len(arts)}] {doi} -> {status}", flush=True)
            time.sleep(args.sleep)
    print(f"[done] ok={ok} fail={fail}", flush=True)

if __name__ == "__main__":
    main()
