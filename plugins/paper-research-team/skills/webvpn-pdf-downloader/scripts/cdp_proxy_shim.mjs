// Minimal CDP proxy shim for nature-downloader scripts.
// Implements the web-access CDP proxy v2.5.3+ endpoint contract on top of
// Chrome's native DevTools HTTP + WebSocket interface. Zero dependencies
// (Node >= 22 built-in WebSocket).
//
// Env:
//   CHROME_CDP_PORT  Chrome --remote-debugging-port (default 9222)
//   SHIM_PORT        listen port (default 3456)
//
// Endpoints (same shapes as web-access proxy):
//   GET  /targets                      -> [{targetId, url, title, type}]
//   GET  /info?target=<id>             -> {targetId, url, title, ready}
//   POST /new        (body=url)        -> {targetId, url, title}
//   POST /navigate   (body=url, ?target=id) -> {ok, targetId}
//   POST /eval       (body=js,  ?target=id) -> {value}
//   POST /click      (body=sel, ?target=id) -> {ok}
//   GET  /scroll?target=<id>&direction=bottom -> {ok}
//   GET  /close?target=<id>           -> {ok}

import http from "node:http";

const CHROME_PORT = Number(process.env.CHROME_CDP_PORT || 9222);
const PORT = Number(process.env.SHIM_PORT || 3456);
const CHROME = `http://127.0.0.1:${CHROME_PORT}`;

let msgId = 0;

async function chromeJson(pathname, method = "GET") {
  const r = await fetch(CHROME + pathname, { method });
  if (!r.ok) {
    const t = await r.text().catch(() => "");
    throw new Error(`Chrome ${pathname} -> HTTP ${r.status} ${t.slice(0, 120)}`);
  }
  return r.json();
}

function cdpCall(wsUrl, method, params = {}, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const id = ++msgId;
    const timer = setTimeout(() => {
      try { ws.close(); } catch {}
      reject(new Error(`CDP ${method} timed out after ${timeoutMs}ms`));
    }, timeoutMs);
    ws.onerror = () => {
      clearTimeout(timer);
      reject(new Error(`WebSocket error while calling ${method}`));
    };
    ws.onopen = () => ws.send(JSON.stringify({ id, method, params }));
    ws.onmessage = (ev) => {
      let m;
      try { m = JSON.parse(typeof ev.data === "string" ? ev.data : String(ev.data)); }
      catch { return; }
      if (m.id !== id) return;
      clearTimeout(timer);
      try { ws.close(); } catch {}
      if (m.error) reject(new Error(m.error.message || JSON.stringify(m.error)));
      else resolve(m.result);
    };
  });
}

async function getPage(targetId) {
  if (!targetId) throw badRequest("missing ?target=");
  const list = await chromeJson("/json/list");
  const t = list.find((x) => x.id === targetId && x.type === "page");
  if (!t) {
    const e = new Error(`target not found: ${targetId}`);
    e.status = 404;
    throw e;
  }
  return t;
}

function badRequest(msg) {
  const e = new Error(msg);
  e.status = 400;
  return e;
}

async function evalInPage(targetId, js, timeoutMs = 60000) {
  const page = await getPage(targetId);
  const res = await cdpCall(
    page.webSocketDebuggerUrl,
    "Runtime.evaluate",
    { expression: js, returnByValue: true, awaitPromise: true, userGesture: true },
    timeoutMs
  );
  if (res.exceptionDetails) {
    const d = res.exceptionDetails;
    const text =
      d.exception?.description || d.exception?.value || d.text || "page eval failed";
    const e = new Error(String(text).slice(0, 500));
    e.status = 500;
    throw e;
  }
  return res.result ? res.result.value : undefined;
}

async function readyState(targetId) {
  // Best-effort readiness probe; some pages block eval, treat as unknown.
  try {
    const v = await evalInPage(targetId, "document.readyState", 10000);
    return typeof v === "string" ? v : "unknown";
  } catch {
    return "unknown";
  }
}

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, `http://127.0.0.1:${PORT}`);
  const send = (code, obj) => {
    const body = JSON.stringify(obj);
    res.writeHead(code, {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Length": Buffer.byteLength(body),
    });
    res.end(body);
  };

  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", async () => {
    try {
      const target = u.searchParams.get("target");

      switch (u.pathname) {
        case "/targets": {
          const list = await chromeJson("/json/list");
          send(200, list
            .filter((t) => t.type === "page")
            .map((t) => ({ targetId: t.id, url: t.url, title: t.title, type: t.type })));
          return;
        }

        case "/info": {
          const page = await getPage(target);
          const ready = await readyState(target);
          send(200, { targetId: page.id, url: page.url, title: page.title, ready });
          return;
        }

        case "/new": {
          const url = (body || "").trim() || "about:blank";
          if (!/^https?:\/\//i.test(url) && url !== "about:blank") {
            throw badRequest("url must be http(s)");
          }
          // Edge ignores /json/new?url= (creates about:blank); use
          // Target.createTarget over the browser-level WS instead.
          const ver = await chromeJson("/json/version");
          const created = await cdpCall(
            ver.webSocketDebuggerUrl,
            "Target.createTarget",
            { url },
            60000
          );
          const page = await getPage(created.targetId).catch(() => null);
          send(200, {
            targetId: created.targetId,
            url: page ? page.url : url,
            title: page ? page.title : "",
          });
          return;
        }

        case "/navigate": {
          const url = (body || "").trim();
          if (!/^https?:\/\//i.test(url)) throw badRequest("navigate body must be an http(s) URL");
          const page = await getPage(target);
          await cdpCall(page.webSocketDebuggerUrl, "Page.navigate", { url }, 60000);
          send(200, { ok: true, targetId: target });
          return;
        }

        case "/eval": {
          if (!body) throw badRequest("eval body is empty");
          const value = await evalInPage(target, body, 120000);
          send(200, { value });
          return;
        }

        case "/click": {
          const sel = (body || "").trim();
          if (!sel) throw badRequest("click body is a CSS selector");
          await evalInPage(
            target,
            `(()=>{const el=document.querySelector(${JSON.stringify(sel)});if(el){el.click();return true;}return false;})()`,
            30000
          );
          send(200, { ok: true });
          return;
        }

        case "/scroll": {
          const dir = u.searchParams.get("direction") || "bottom";
          const js =
            dir === "top"
              ? "window.scrollTo(0,0);'ok'"
              : "window.scrollTo(0,document.body.scrollHeight);'ok'";
          await evalInPage(target, js, 30000);
          send(200, { ok: true });
          return;
        }

        case "/close": {
          await chromeJson(`/json/close/${encodeURIComponent(target)}`);
          send(200, { ok: true });
          return;
        }

        case "/health":
        case "/ping": {
          const list = await chromeJson("/json/version");
          send(200, { ok: true, browser: list.Browser, shim: "cdp-proxy-shim/1.0" });
          return;
        }

        default:
          send(404, { error: `no such endpoint: ${u.pathname}` });
      }
    } catch (e) {
      send(e.status || 502, { error: String(e.message || e).slice(0, 500) });
    }
  });
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[cdp-proxy-shim] listening on http://127.0.0.1:${PORT} -> Chrome :${CHROME_PORT}`);
});
