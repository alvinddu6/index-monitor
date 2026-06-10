/**
 * Cloudflare Pages 全能 Worker
 * 静态文件直接返回，/api/proxy 转发请求绕过 CORS
 */

const ALLOWED = [
  "hq.sinajs.cn", "money.finance.sina.com.cn",
  "stock.finance.sina.com.cn", "push2his.eastmoney.com",
  "push2.eastmoney.com", "www.sge.com.cn",
];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/api/proxy") {
      const targetUrl = url.searchParams.get("url");
      const referer = url.searchParams.get("ref") || "https://finance.sina.com.cn";

      if (!targetUrl) {
        return new Response('{"error":"missing url"}', {
          status: 400,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
        });
      }

      try {
        const host = new URL(targetUrl).hostname;
        if (!ALLOWED.some(a => host.endsWith(a))) {
          return new Response(JSON.stringify({ error: "domain not allowed: " + host }), {
            status: 403,
            headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
          });
        }
      } catch {
        return new Response('{"error":"invalid url"}', {
          status: 400,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
        });
      }

      try {
        const fetchOpts = {
          method: request.method,
          headers: {
            "Referer": referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36",
          },
        };

        if (request.method === "POST") {
          fetchOpts.headers["Content-Type"] = request.headers.get("content-type") || "application/x-www-form-urlencoded";
          fetchOpts.body = await request.text();
        }

        const resp = await fetch(targetUrl, fetchOpts);
        const body = await resp.text();

        return new Response(body, {
          status: resp.status,
          headers: {
            "Content-Type": resp.headers.get("content-type") || "text/plain; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=60",
          },
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), {
          status: 502,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
        });
      }
    }

    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    return env.ASSETS.fetch(request);
  },
};
