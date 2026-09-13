# -*- coding: utf-8 -*-
"""
vpn_download_v3.py — 南昌大学 WebVPN 通道 PDF 补全下载器
基于已验证链路: 专用 Edge (CDP 9222) + cdp_proxy_shim (3456) + WebVPN 域名重写
重写规则(实测): https://host[:port]/path -> https://scheme-host-port.wvpn.ncu.edu.cn/path

用法:
  python vpn_download_v3.py --limit 10          # 默认测试批次
  python vpn_download_v3.py --limit 50 --sleep 4
  python vpn_download_v3.py --only-springer     # 仅 Springer 系(最稳)
"""
import sqlite3, json, base64, os, re, sys, time, argparse
import urllib.request, urllib.error
from urllib.parse import urlparse, quote

SHIM = "http://127.0.0.1:3456"
WVPN = "wvpn.ncu.edu.cn"
DB = r"E:\TRAE\英文文章\ncu2fy_literature\ncu2fy.db"
PDF_DIR = r"E:\TRAE\英文文章\ncu2fy_literature\pdfs"
MANIFEST = r"E:\TRAE\英文文章\ncu2fy_literature\vpn_download_manifest.tsv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0"

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>#?&]+")

# WebVPN 白名单实测(2026-09-13): 仅图书馆启用的站点可访问
ENABLED_SUFFIXES = (
    "link.springer.com",
    ".biomedcentral.com",          # BMC 系期刊实测可下载
    "www.sciencedirect.com",
    "www.tandfonline.com",
    "pubs.acs.org",
    "ieeexplore.ieee.org",
)
# 未启用 → 直接跳过, 免去无谓导航
NOT_ENABLED_HINT = ("wiley", "nature.com", "oup.com", "lww.com", "bmj.com",
                    "frontiersin.org", "mdpi.com", "dovepress.com", "karger.com",
                    "spandidos", "linkinghub.elsevier.com")

def host_enabled(url):
    h = urlparse(url).hostname or ""
    return any(h == s or h.endswith(s) for s in ENABLED_SUFFIXES)

def map_host(url):
    """linkinghub.elsevier.com/retrieve/pii/<PII> -> www.sciencedirect.com/science/article/pii/<PII>"""
    m = re.match(r"https?://linkinghub\.elsevier\.com/retrieve/pii/([A-Z0-9]+)", url)
    if m:
        return f"https://www.sciencedirect.com/science/article/pii/{m.group(1)}"
    return url

# ---------- shim HTTP ----------
def shim_get(endpoint, params=None, timeout=60):
    url = SHIM + endpoint
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def shim_post(endpoint, body, params=None, timeout=120):
    url = SHIM + endpoint
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params)
    req = urllib.request.Request(url, data=body.encode("utf-8"), method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def eval_js(target, js, timeout=120):
    try:
        res = shim_post("/eval", js, {"target": target}, timeout)
        return res.get("value")
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None

# ---------- url helpers ----------
def rewrite_url(url):
    """https://host[:port]/path -> https://scheme-host-port.wvpn.ncu.edu.cn/path"""
    p = urlparse(url)
    if not p.hostname or p.hostname.endswith(WVPN):
        return url
    scheme = p.scheme or "https"
    port = p.port or (443 if scheme == "https" else 80)
    tag = f"{scheme}-{p.hostname.replace('.', '-')}-{port}"
    rest = (p.path or "") + (("?" + p.query) if p.query else "")
    return f"https://{tag}.{WVPN}{rest}"

def normalize_doi(raw):
    """doi 字段可能是 URL / 裸 DOI，统一提取纯 DOI"""
    if not raw:
        return None
    raw = raw.strip()
    if raw.lower().startswith("http"):
        m = DOI_RE.search(raw)
        return m.group(0).rstrip(".,").lower() if m else None
    if DOI_RE.match(raw):
        return raw.lower()
    return None

def resolve_doi(doi, timeout=25):
    """浏览器外直连解析 DOI 最终落地页(仅取跳转地址; 终点 403/406 也算成功)"""
    url = f"https://doi.org/{doi}"
    opener = urllib.request.build_opener(_NoRedirect)
    last = url
    for _ in range(10):
        try:
            with opener.open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
                return r.geturl()
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location")
            if loc and 300 <= e.code < 400:
                last = url
                url = loc if loc.startswith("http") else f"https://{urlparse(url).netloc}{loc}"
                continue
            # 终点拒绝机器人(Cloudflare 等)但地址已确定, 返回当前 URL
            return url
        except Exception:
            return None if url == last else url
    return url

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None

# ---------- page helpers ----------
CHALLENGE_PAT = ("请稍候", "just a moment", "cloudflare", "attention required",
                 "人机验证", "robot check", "access denied", "captcha")

def page_state(target):
    try:
        info = shim_get("/info", {"target": target}, 15)
        return info.get("url", ""), (info.get("title") or ""), (info.get("ready") or "")
    except Exception:
        return "", "", ""

def wait_ready(target, max_s=40):
    t0 = time.time()
    while time.time() - t0 < max_s:
        url, title, ready = page_state(target)
        if ready == "complete":
            time.sleep(2)  # SPA 渲染缓冲
            return url, title
        time.sleep(1.5)
    url, title, _ = page_state(target)
    return url, title

PDF_DISCOVER_JS = """
(()=>{
  const out={metas:[],links:[],title:document.title};
  document.querySelectorAll('meta[name="citation_pdf_url"]').forEach(m=>out.metas.push(m.content));
  document.querySelectorAll('a[href]').forEach(a=>{
    const h=a.getAttribute('href')||'';
    if(/\\.pdf(\\?|$)|\\/pdf(\\?|\\/|$)|pdfft|epdf|pdf\\/direct|pdfDirect/i.test(h)) out.links.push(h);
  });
  return JSON.stringify(out);
})()
"""

FETCH_SETUP_JS = """
(async (u)=>{
  try{
    const r=await fetch(u,{credentials:'include'});
    const ab=await r.arrayBuffer();
    const b=new Uint8Array(ab);
    if(b.length>200*1024*1024) return JSON.stringify({ok:false,err:'too_large'});
    window.__vpnPdf__=b;
    return JSON.stringify({ok:r.ok,status:r.status,size:b.length,
      head:Array.from(b.slice(0,8)),ct:r.headers.get('content-type')||''});
  }catch(e){return JSON.stringify({ok:false,err:String(e).slice(0,200)})}
})
"""

def fetch_pdf_bytes(target, url, size):
    """按 1MB 分块把页面上下文里的 window.__vpnPdf__ 传回本地"""
    chunks = []
    for s in range(0, size, 1 << 20):
        e = min(s + (1 << 20), size)
        b64 = eval_js(target,
            f"(()=>{{const b=window.__vpnPdf__.slice({s},{e});let x='';"
            f"for(let i=0;i<b.length;i+=0x8000)x+=String.fromCharCode.apply(null,b.subarray(i,i+0x8000));"
            f"return btoa(x);}})()", 90)
        if not b64:
            return None
        chunks.append(base64.b64decode(b64))
    eval_js(target, "delete window.__vpnPdf__", 15)
    return b"".join(chunks)

def discover_pdf_url(target):
    raw = eval_js(target, PDF_DISCOVER_JS, 30)
    if not raw:
        return []
    data = json.loads(raw)
    cands = []
    for m in data.get("metas", []):
        cands.append(("meta", m))
    for l in data.get("links", []):
        cands.append(("link", l))
    return cands

def absolutize(base_url, href):
    if href.startswith("http"):
        return href
    p = urlparse(base_url)
    if href.startswith("//"):
        return f"{p.scheme}:{href}"
    if href.startswith("/"):
        return f"{p.scheme}://{p.netloc}{href}"
    return f"{p.scheme}://{p.netloc}" + (p.path or "") + "/" + href

# ---------- main flow ----------
def pick_articles(limit, only_springer, prefixes=None):
    db = sqlite3.connect(DB)
    db.execute("PRAGMA busy_timeout=60000")
    # doi 字段大量为 URL 格式, 在 Python 侧规范化后再过滤
    rows = db.execute("""
        SELECT id, doi, journal_name, publisher, pub_year FROM articles
        WHERE pdf_path='NO_PDF' AND exclude_flag=0
          AND doi IS NOT NULL AND doi != ''
        ORDER BY pub_year DESC, id DESC""").fetchall()
    springer_pfx = ("10.1007", "10.1038", "10.1186")
    spr_kw = ("springer",)
    out, seen = [], set()
    for r in rows:
        doi = normalize_doi(r[1])
        if not doi or doi in seen:
            continue
        if only_springer:
            hit = doi.startswith(springer_pfx) or any(
                k in (r[2] or "").lower() or k in (r[3] or "").lower() for k in spr_kw)
            if not hit:
                continue
        if prefixes and doi.split("/")[0] not in [p.lower() for p in prefixes]:
            continue
        seen.add(doi)
        out.append({"id": r[0], "doi": doi, "journal": r[2], "publisher": r[3]})
    return out[:limit]

def download_one(tab, art):
    doi = art["doi"]
    # 1. 解析出版商落地页
    final = resolve_doi(doi)
    if not final:
        return art, "doi_resolve_failed", None
    final = map_host(final)
    host = urlparse(final).hostname or ""
    # 2. 白名单预检: 未启用站点直接跳过(已在实测中确认)
    if not host_enabled(final):
        if any(h in host for h in NOT_ENABLED_HINT):
            return art, f"host_not_enabled:{host}", final
        # 未知主机也试一次导航, 由 WebVPN 判定
        pass
    # 3. WebVPN 重写并导航
    wurl = rewrite_url(final)
    try:
        shim_post("/navigate", wurl, {"target": tab}, 60)
    except Exception as e:
        return art, f"navigate_error:{str(e)[:60]}", wurl
    url, title = wait_ready(tab)
    low = (title or "").lower()
    if any(p in low for p in CHALLENGE_PAT) or "请稍候" in (title or ""):
        return art, "challenge_wait_user", wurl
    if "无法访问" in (title or "") or (eval_js(tab, "document.body?document.body.innerText.includes('尚未启用')||document.body.innerText.includes('无法访问')", 15) is True):
        return art, f"host_not_enabled:{host}", wurl
    # 4. 发现 PDF 候选
    cands = discover_pdf_url(tab)
    m = DOI_RE.search(wurl)
    if m and "link-springer" in wurl:
        cands.append(("gen", f"/content/pdf/{m.group(0)}"))
    if not cands:
        return art, "no_pdf_link", wurl
    # 5. 逐候选抓取
    for kind, href in cands:
        absu = absolutize(url, href)          # 页面里的相对链接基于当前(已重写)地址
        fu = rewrite_url(absu) if WVPN not in absu else absu
        js = f"({FETCH_SETUP_JS})({json.dumps(fu)})"
        raw = eval_js(tab, js, 150)
        if not raw:
            continue
        try:
            meta = json.loads(raw)
        except Exception:
            continue
        if not meta.get("ok"):
            continue
        head = "".join(chr(c) for c in (meta.get("head") or []))
        if not head.startswith("%PDF"):
            continue
        data = fetch_pdf_bytes(tab, fu, meta["size"])
        if not data or not data[:5].startswith(b"%PDF"):
            continue
        path = os.path.join(PDF_DIR, f"{art['id']}.pdf")
        with open(path, "wb") as f:
            f.write(data)
        return art, "downloaded", path
    return art, "pdf_fetch_failed", wurl

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--sleep", type=int, default=3)
    ap.add_argument("--only-springer", action="store_true")
    ap.add_argument("--prefixes", type=str, default="",
                    help="逗号分隔 DOI 前缀, 如 10.1007,10.1186,10.1080,10.1021")
    args = ap.parse_args()

    os.makedirs(PDF_DIR, exist_ok=True)
    prefixes = [p.strip() for p in args.prefixes.split(",") if p.strip()] or None
    arts = pick_articles(args.limit, args.only_springer, prefixes)
    print(f"[plan] {len(arts)} papers selected", flush=True)

    # 建专用下载标签页
    tab = shim_post("/new", "about:blank")["targetId"]
    print(f"[tab] {tab}", flush=True)

    db = sqlite3.connect(DB)
    db.execute("PRAGMA busy_timeout=60000")
    ok = fail = 0
    try:
        with open(MANIFEST, "a", encoding="utf-8") as mf:
            for i, art in enumerate(arts, 1):
                art, status, info = download_one(tab, art)
                if status == "downloaded":
                    db.execute("UPDATE articles SET pdf_path=? WHERE id=?",
                               (info, art["id"]))
                    db.commit()
                    ok += 1
                else:
                    fail += 1
                mf.write(f"{art['id']}\t{art['doi']}\t{status}\t{info or ''}\n")
                mf.flush()
                print(f"[{i}/{len(arts)}] {art['doi']} -> {status}", flush=True)
                # 挑战页: 立即中止本批次(等用户处理)
                if status == "challenge_wait_user":
                    print("[halt] challenge page detected — batch stopped, user action required", flush=True)
                    break
                time.sleep(args.sleep)
    finally:
        try:
            shim_get("/close", {"target": tab}, 10)
        except Exception:
            pass
    print(f"[done] ok={ok} fail={fail}", flush=True)

if __name__ == "__main__":
    main()
