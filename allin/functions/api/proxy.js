/**
 * CORS 代理 — 支持 GET/POST，转发到新浪/东方财富/上金所
 * Cloudflare Pages Function: 自动识别 functions/ 目录
 */

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const targetUrl = url.searchParams.get("url");
  const referer = url.searchParams.get("ref") || "https://finance.sina.com.cn";

  if (!targetUrl) {
    return new Response('{"error":"missing url param"}', {
      status: 400,
      headers: corsHeaders(),
    });
  }

  // 域名白名单
  const allowed = [
    "hq.sinajs.cn", "money.finance.sina.com.cn",
    "stock.finance.sina.com.cn", "push2his.eastmoney.com",
    "push2.eastmoney.com", "www.sge.com.cn",
  ];
  try {
    const host = new URL(targetUrl).hostname;
    if (!allowed.some((a) => host.endsWith(a))) {
      return new Response(`{"error":"domain not allowed: ${host}"}`, {
        status: 403,
        headers: corsHeaders(),
      });
    }
  } catch {
    return new Response('{"error":"invalid url"}', {
      status: 400,
      headers: corsHeaders(),
    });
  }

  const method = request.method.toUpperCase();

  try {
    const fetchOptions = {
      method: method,
      headers: {
        Referer: referer,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36",
      },
      cf: { cacheTtl: 60 },
    };

    // POST 请求：转发 body
    if (method === "POST") {
      const contentType = request.headers.get("content-type") || "";
      fetchOptions.headers["Content-Type"] = contentType;
      if (url.searchParams.has("origin")) {
        fetchOptions.headers["Origin"] = url.searchParams.get("origin");
      }
      if (url.searchParams.has("xrw")) {
        fetchOptions.headers["X-Requested-With"] = url.searchParams.get("xrw");
      }
      const body = await request.text();
      if (body) fetchOptions.body = body;
    }

    const resp = await fetch(targetUrl, fetchOptions);
    const body = await resp.text();

    const headers = corsHeaders();
    if (resp.headers.get("content-type")) {
      headers["Content-Type"] = resp.headers.get("content-type");
    }

    return new Response(body, { status: resp.status, headers });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 502,
      headers: corsHeaders(),
    });
  }
}

function corsHeaders() {
  return {
    "Content-Type": "text/plain; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Max-Age": "86400",
    "Cache-Control": "public, max-age=60",
  };
}
