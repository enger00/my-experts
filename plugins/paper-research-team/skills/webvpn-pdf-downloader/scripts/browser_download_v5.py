# -*- coding: utf-8 -*-
"""
browser_download_v5.py — 真实浏览器通道 PDF 下载器（专攻 Cloudflare 站点）
目标: 10.18632 Aging/Oncotarget | 10.21037 AME | 10.1155 Hindawi(Wiley 托管)
解析: Crossref API 优先(机器人友好), doi.org 兜底
抓取: 专用 Edge 页面上下文内 fetch(CDP 垫片), 真实浏览器可过 Cloudflare JS
挑战页: 等待自动放行 25s; 连续 5 次挑战则停批等用户点击
用法:
  python browser_download_v5.py --limit 500 --sleep 3
"""
import sqlite3, json, os, re, time, argparse, base64
import urllib.request, urllib.error
from urllib.parse import urlencode
import requests as rq

S = rq.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0"})

SHIM = "http://127.0.0.1:3456"
DB = r"E:\TRAE\英文文章\ncu2fy_literature\ncu2fy.db"
PDF_DIR = r"E:\TRAE\英文文章\ncu2fy_literature\pdfs"
MANIFEST = r"E:\TRAE\英文文章\ncu2fy_literature\browser_manifest.tsv"
PREFIXES = ["10.18632", "10.21037", "10.1155"]
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>#?&]+")

# ---------- shim ----------
def shim_post(endpoint, body, params=None, timeout=120):
    url = SHIM + endpoint + ("?" + urlencode(params) if params else "")
    req = urllib.request.Request(url, data=body.encode("utf-8"), method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def shim_get(endpoint, params=None, timeout=30):
    url = SHIM + endpoint + ("?" + urlencode(params) if params else "")
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def eval_js(target, js, timeout=120):
    try:
        res = shim_post("/eval", js, {"target": target}, timeout)
        return res.get("value")
    except Exception:
        return None

def wait_ready(target, max_s=45):
    t0 = time.time()
    url, title = "", ""
    while time.time() - t0 < max_s:
        try:
            info = shim_get("/info", {"target": target}, 12)
            url, title = info.get("url", ""), (info.get("title") or "")
            if info.get("ready") == "complete":
                time.sleep(2)
                return url, title
        except Exception:
            pass
        time.sleep(1.5)
    return url, title

def is_challenge(title, body=""):
    low = (title or "").lower() + (body or "")[:500].lower()
    return ("请稍候" in (title or "") or "just a moment" in low
            or "attention required" in low or "captcha" in low or "人机验证" in (title or ""))

def wait_challenge_pass(target, max_s=25):
    """Cloudflare 托管挑战在真实浏览器常自动放行; 轮询等待"""
    t0 = time.time()
    while time.time() - t0 < max_s:
        time.sleep(4)
        try:
            info = shim_get("/info", {"target": target}, 12)
            title = info.get("title") or ""
            if not is_challenge(title):
                return True
        except Exception:
            pass
    return False

# ---------- resolve ----------
def resolve_crossref(doi):
    try:
        req = urllib.request.Request(
            f"https://api.crossref.org/works/{doi}",
            headers={"User-Agent": "lit-dl/1.0 (mailto:biobank@nc2h-bio.cn)"})
        with urllib.request.urlopen(req, timeout=25) as r:
            m = json.loads(r.read().decode())["message"]
            prim = (m.get("resource") or {}).get("primary", {}).get("URL")
            pdf_links = [l.get("URL") for l in m.get("link", [])
                         if "pdf" in (l.get("content-type") or "")]
            return prim, pdf_links
    except Exception:
        return None, []

# ---------- page PDF discovery ----------
PDF_DISCOVER_JS = """
(()=>{
  const out={metas:[],links:[]};
  document.querySelectorAll('meta[name="citation_pdf_url"]').forEach(m=>out.metas.push(m.content));
  document.querySelectorAll('a[href]').forEach(a=>{
    const h=a.getAttribute('href')||'';
    if(/\\.pdf(\\?|$)|\\/pdf(\\?|\\/|$)|\\/doi\\/pdf\\/|pdfft|getfile/i.test(h)) out.links.push(h);
  });
  return JSON.stringify(out);
})()
"""

FETCH_JS = """
(async (u)=>{
  try{
    const r=await fetch(u,{credentials:'include'});
    const ab=await r.arrayBuffer();
    const b=new Uint8Array(ab);
    if(b.length>200*1024*1024) return JSON.stringify({ok:false,err:'too_large'});
    window.__pdf5__=b;
    return JSON.stringify({ok:r.ok,status:r.status,size:b.length,head:Array.from(b.slice(0,8))});
  }catch(e){return JSON.stringify({ok:false,err:String(e).slice(0,150)})}
})
"""

def fetch_pdf_bytes(target, url, size):
    chunks = []
    for s in range(0, size, 1 << 20):
        e = min(s + (1 << 20), size)
        b64 = eval_js(target,
            f"(()=>{{const b=window.__pdf5__.slice({s},{e});let x='';"
            f"for(let i=0;i<b.length;i+=0x8000)x+=String.fromCharCode.apply(null,b.subarray(i,i+0x8000));"
            f"return btoa(x);}})()", 90)
        if not b64:
            return None
        chunks.append(base64.b64decode(b64))
    eval_js(target, "delete window.__pdf5__", 15)
    return b"".join(chunks)

def absolutize(base, href):
    from urllib.parse import urljoin
    return urljoin(base, href)

# ---------- main ----------
def pick(limit):
    db = sqlite3.connect(DB)
    db.execute("PRAGMA busy_timeout=60000")
    rows = db.execute("""SELECT id, doi FROM articles
        WHERE pdf_path='NO_PDF' AND exclude_flag=0 AND doi IS NOT NULL AND doi!=''""").fetchall()
    pset = set(PREFIXES)
    out, seen = [], set()
    for aid, raw in rows:
        raw = raw.strip()
        if raw.lower().startswith("http"):
            m = DOI_RE.search(raw)
            doi = m.group(0).rstrip(".,").lower() if m else None
        elif DOI_RE.match(raw):
            doi = raw.lower()
        else:
            doi = None
        if doi and doi not in seen and doi.split("/")[0] in pset:
            seen.add(doi)
            out.append({"id": aid, "doi": doi})
    return out[:limit]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--sleep", type=int, default=3)
    args = ap.parse_args()
    arts = pick(args.limit)
    print(f"[plan] {len(arts)} papers (browser channel)", flush=True)
    tab = shim_post("/new", "about:blank")["targetId"]
    print(f"[tab] {tab}", flush=True)
    db = sqlite3.connect(DB)
    db.execute("PRAGMA busy_timeout=60000")
    ok = fail = consec_challenge = 0
    try:
        with open(MANIFEST, "a", encoding="utf-8") as mf:
            for i, art in enumerate(arts, 1):
                doi = art["doi"]
                prim, xr_pdf = resolve_crossref(doi)
                if not prim:
                    status = "crossref_miss"
                else:
                    cands_extra = list(xr_pdf[:2])
                    shim_post("/navigate", prim, {"target": tab}, 60)
                    url, title = wait_ready(tab)
                    if is_challenge(title):
                        passed = wait_challenge_pass(tab)
                        if not passed:
                            status = "challenge_wait_user"
                            consec_challenge += 1
                            mf.write(f"{art['id']}\t{doi}\t{status}\t{prim}\n")
                            print(f"[{i}/{len(arts)}] {doi} -> {status}", flush=True)
                            if consec_challenge >= 5:
                                print("[halt] 5 consecutive challenges — user action required", flush=True)
                                break
                            time.sleep(args.sleep)
                            continue
                    consec_challenge = 0
                    url, title = wait_ready(tab, 20)
                    raw = eval_js(tab, PDF_DISCOVER_JS, 30)
                    cands = list(cands_extra)
                    if raw:
                        d = json.loads(raw)
                        cands += [absolutize(url, m) for m in d.get("metas", [])]
                        cands += [absolutize(url, l) for l in d.get("links", [])]
                    # 站点规则
                    if "/article/view/" in url and url.rstrip("/").endswith(("/html", "/full")):
                        cands.append(url.rstrip("/")[:-5] + "/pdf" if url.rstrip("/").endswith("/html") else url.rstrip("/") + "/pdf")
                    # Wiley: /doi/pdfdirect/ 返回真 PDF(页内 fetch 可用)
                    mdoi = DOI_RE.search(doi)
                    if "onlinelibrary.wiley.com" in url:
                        cands.insert(0, f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}")
                    status = "no_pdf_link"
                    got = False
                    seen_u = set()
                    for u in cands:
                        if u in seen_u:
                            continue
                        seen_u.add(u)
                        data = None
                        # 1) 直连 requests(适用无 CF 的 CDN, 如 cdn.aging-us.com)
                        try:
                            r = S.get(u, timeout=90, allow_redirects=True)
                            if r.status_code == 200 and r.content[:5] == b"%PDF-":
                                data = r.content
                        except Exception:
                            pass
                        # 2) 页内 fetch(带浏览器 cookie, 适用 Wiley pdfdirect 等)
                        if not data:
                            js = f"({FETCH_JS})({json.dumps(u)})"
                            r = eval_js(tab, js, 150)
                            if r:
                                try:
                                    meta = json.loads(r)
                                except Exception:
                                    meta = {}
                                if meta.get("ok"):
                                    head = "".join(chr(c) for c in (meta.get("head") or []))
                                    if head.startswith("%PDF"):
                                        data = fetch_pdf_bytes(tab, u, meta["size"])
                        if data and data[:5] == b"%PDF-":
                            path = os.path.join(PDF_DIR, f"{art['id']}.pdf")
                            with open(path, "wb") as f:
                                f.write(data)
                            db.execute("UPDATE articles SET pdf_path=? WHERE id=?", (path, art["id"]))
                            db.commit()
                            status, got = "downloaded", True
                            ok += 1
                            break
                    if not got:
                        fail += 1
                        status = status if status != "no_pdf_link" else "no_pdf_fetchable"
                mf.write(f"{art['id']}\t{doi}\t{status}\t{prim or ''}\n")
                mf.flush()
                print(f"[{i}/{len(arts)}] {doi} -> {status}", flush=True)
                time.sleep(args.sleep)
    finally:
        try:
            shim_get("/close", {"target": tab}, 10)
        except Exception:
            pass
    print(f"[done] ok={ok} fail={fail}", flush=True)

if __name__ == "__main__":
    main()
