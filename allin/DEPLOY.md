# 部署到 Cloudflare Pages

## 前置条件

1. GitHub 账号
2. Cloudflare 账号（免费）

## 步骤

### 一、推送到 GitHub

```bash
git init
git add .
git commit -m "index monitor v1"
git branch -M main

# 在 GitHub 创建仓库后：
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

### 二、Cloudflare Pages 部署

1. 打开 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 左侧菜单 → **Workers & Pages** → **Create application** → **Pages**
3. 连接 GitHub，选择你的仓库
4. 构建设置：
   - **Build command**: 留空
   - **Build output directory**: `.`（根目录）
   - **Root directory**: `/`
5. 点击 **Save and Deploy**

部署后 Cloudflare 会给一个域名如 `xxx.pages.dev`。

### ⚠️ CORS 代理

项目里 `functions/api/proxy.js` 就是 CORS 代理。Cloudflare Pages 会自动识别 `functions/` 目录，无需额外配置。

前端通过 `/api/proxy?url=...` 调用，转发到新浪/东方财富接口。

### 三、测试

打开 `https://你的域名.pages.dev/index.html`，应该能看到报告页面。

点击「刷新数据」实时拉取最新行情。

## 工作原理

```
浏览器                        Cloudflare Pages
  │                                │
  ├─ GET /index.html ────────────→ 返回 HTML
  │                                │
  ├─ GET /api/proxy?url=... ─────→ 转发到 sina/eastmoney
  │                                │  (加 Referer 头)
  │  ← JSON数据 ─────────────────  │
  │                                │
  └─ 前端计算回撤 → 渲染报告
```

## 成本

- Cloudflare Pages: 免费（无限流量）
- Cloudflare Functions: 免费（10万次/天，足够用）
- GitHub: 免费
- 总费用: **¥0**
