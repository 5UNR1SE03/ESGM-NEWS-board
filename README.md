# 🌿 ESG 全球新闻台

每日自动更新国内外 ESG 领域最新新闻的静态网站。免费托管在 GitHub Pages，由 GitHub Actions 每天定时抓取多家新闻源并自动发布，**无需自己的服务器、无需 API Key、完全免费**。

## 功能

- **国内外分开看**：首页一键切换「全部 / 🇨🇳 国内 / 🌍 国际」
- **多源聚合**：Google News RSS + Bing News RSS + ESG 专业站点（ESG Today、ESG News、ESG Dive、ESG Clarity），单源故障自动跳过
- **自动分类**：政策监管 / 企业动态 / 金融市场 / 气候环境 / 社会议题 / 治理反腐，彩色徽章展示
- **按日期分组**：今日 / 昨日 / 本周 / 更早
- **每日自动更新**：北京时间每天 08:00 和 20:00 各抓取一次，也可随时手动触发

## 目录结构

```
esg-news-site/
├── .github/workflows/daily-update.yml   # 每日定时抓取 + 部署工作流
├── fetcher/fetch_news.py                # 多源抓取脚本（纯 Python 标准库）
└── site/                                # 网站本体（GitHub Pages 部署目录）
    ├── index.html
    ├── css/style.css
    ├── js/app.js
    └── news.json                        # 抓取结果（首次推送后由 Actions 自动生成真实数据）
```

## 部署步骤（只需做一次，约 10 分钟）

### 第 1 步：创建 GitHub 仓库

1. 注册 / 登录 [GitHub](https://github.com)
2. 右上角 `+` → **New repository**，仓库名随意（如 `esg-news`）
3. **必须选 Public（公开）**——GitHub Pages 免费版不支持私有仓库
4. 不要勾选任何初始化文件（保持空仓库），点 **Create repository**

### 第 2 步：上传本项目文件

方式 A（推荐，用 Git 命令行，在你的电脑上本项目的根目录 `esg-news-site` 里执行）：

```bash
git init
git add .
git commit -m "init: ESG news site"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

方式 B（不用命令行）：进入仓库页面 → **uploading an existing file** → 把 `esg-news-site` 里的文件夹和文件原样拖进去上传（注意保留 `.github` 开头的隐藏文件夹和目录层级）。

### 第 3 步：启用 GitHub Pages

进入仓库 **Settings** → 左侧 **Pages**：

- **Build and deployment** → **Source** 选 **GitHub Actions**（不是 Deploy from a branch）

### 第 4 步：确认 Actions 已启用

进入仓库 **Actions** 标签页 → 点击绿色按钮 **I understand my workflows, go ahead and enable them**（首次推送后才会出现此提示）。

### 第 5 步：等待自动部署

- 第 2 步推送代码后，工作流会**自动运行一次**：抓新闻 → 生成 `news.json` → 部署网站
- 仓库 **Actions** 页可查看运行进度，出现绿色 ✓ 即完成

### 第 6 步：打开你的网站 🎉

```
https://<你的用户名>.github.io/<仓库名>/
```

> 如果 404：等 1~2 分钟再试；或检查第 3 步 Source 是否选了 GitHub Actions。

## 每日更新机制

- 工作流里 `cron: "0 0,12 * * *"` 是 UTC 时间，对应**北京时间每天 08:00 和 20:00**
- 抓取脚本运行在 GitHub 的美区服务器上，Google / Bing / 各 ESG 站点均能正常访问
- 也可以随时手动更新：仓库 **Actions** → **ESG 新闻每日更新** → **Run workflow** → 绿色按钮运行

## 本地预览

```bash
cd site
python -m http.server 8080
```

浏览器打开 http://localhost:8080 （不要直接双击 index.html，浏览器会拦截 file:// 下的数据加载）。

## 自定义数据源 / 查询词

编辑 `fetcher/fetch_news.py` 顶部的配置区：

- `GOOGLE_QUERIES` / `BING_QUERIES`：增删搜索词、修改语言和市场
- `DIRECT_FEEDS`：增删专业站点 RSS 地址
- `CATEGORY_RULES`：调整分类关键词
- `KEEP_DAYS`：只保留最近 N 天的新闻

修改后推送到 GitHub 即生效。

## 常见问题

| 问题 | 解决办法 |
| --- | --- |
| 网站打不开 / 404 | 确认仓库是 Public；Pages 的 Source 选了 GitHub Actions；等待工作流跑完 |
| Actions 运行失败 | Actions 页点开失败的那次运行查看日志；多数是某个新闻源临时故障，下次自动重跑即可 |
| 新闻列表是空的 | 全部源都失败时脚本会保留旧数据不清空；可手动触发一次更新 |
| Google News 的跳转链接在国内打不开 | Google 跳转链接需要代理；Bing 及国内媒体来源的链接不受影响 |
| 想改更新频率 | 修改 `daily-update.yml` 里的 cron 表达式（注意是 UTC 时间） |

## 已知限制

- 分类基于标题/摘要关键词自动判定，仅供参考
- Google News 与 Bing News 会去重合并，少量重复或转述新闻可能出现
- 免费方案下 GitHub Pages 仓库必须公开
