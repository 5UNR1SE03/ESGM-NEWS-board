#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESG 每日新闻多源聚合抓取器 v3
================================
数据源（全部免费、无需 API Key）：
  1. Google News RSS（国际英文 + 国内中文）
  2. Bing News RSS（国际英文 + 国内中文）
  3. ESG 专业站点 RSS（ESG Today / ESG News / ESG Dive / ESG Clarity）

功能：
  - 多源抓取、单源失败自动跳过（强容错）
  - 按标题去重
  - 自动分类：政策监管 / 企业动态 / 金融市场 / 气候环境 / 社会议题 / 治理/反腐
  - 自动区分：国内（中国大陆媒体）/ 国际
  - 按发布时间倒序，输出 site/news.json 供前端读取

运行环境：GitHub Actions（ubuntu-latest, Python 3.12），仅用标准库。
"""

import datetime
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

# Windows 控制台默认 GBK，打印 emoji/中文可能崩溃；统一转 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------- 配置区（按需修改） ----------------

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 15
RETRIES = 2
SLEEP_BETWEEN = 0.5          # 每次请求间隔（秒），避免触发限流
MAX_DESC = 160               # 摘要最长字符数
KEEP_DAYS = 14               # 只保留最近 N 天的新闻
MAX_ITEMS = 800              # 最终列表上限

# (查询词, 语言/市场, 默认地区)  —— Google News
GOOGLE_QUERIES = [
    # ---- 国际（英文）----
    ("ESG",                          "en-US", "US", "US:en",       "intl"),
    ("ESG investing",                "en-US", "US", "US:en",       "intl"),
    ("sustainability regulation",    "en-US", "US", "US:en",       "intl"),
    ("climate disclosure",           "en-US", "US", "US:en",       "intl"),
    ("green finance",                "en-US", "US", "US:en",       "intl"),
    # ---- 国内（中文）----
    ("ESG",                          "zh-CN", "CN", "CN:zh-Hans", "dom"),
    ("ESG 评级 绿色金融",            "zh-CN", "CN", "CN:zh-Hans", "dom"),
    ("碳排放 碳市场 碳中和",         "zh-CN", "CN", "CN:zh-Hans", "dom"),
    ("可持续发展报告 披露",          "zh-CN", "CN", "CN:zh-Hans", "dom"),
]

# (查询词, 市场, 默认地区)  —— Bing News
BING_QUERIES = [
    ("ESG",                          "en-US", "intl"),
    ("ESG investing",                "en-US", "intl"),
    ("sustainability regulation",    "en-US", "intl"),
    ("climate disclosure",           "en-US", "intl"),
    ("ESG",                          "zh-CN", "dom"),
    ("ESG 绿色金融 评级",            "zh-CN", "dom"),
    ("碳排放 碳市场",                "zh-CN", "dom"),
    ("可持续发展报告 披露",          "zh-CN", "dom"),
]

# (RSS 地址, 默认地区, 展示来源名)  —— 专业 ESG 站点
DIRECT_FEEDS = [
    ("https://www.esgtoday.com/feed/",       "intl", "ESG Today"),
    ("https://esgnews.com/feed/",            "intl", "ESG News"),
    ("https://www.esgdive.com/feeds/news/",  "intl", "ESG Dive"),
    ("https://esgclarity.com/feed/",         "intl", "ESG Clarity"),
]

# 中国大陆媒体关键词（用于把来源名称判定为“国内”）
CN_SOURCE_KEYWORDS = [
    "新华", "人民", "央视", "中新", "光明", "经济日报", "中国证券报", "证券时报",
    "证券日报", "上海证券", "每日经济", "每经", "财新", "澎湃", "界面", "第一财经",
    "21世纪", "经济观察", "中国经营报", "新京报", "南方都市", "中国环境", "环境报",
    "东方财富", "新浪", "搜狐", "网易", "腾讯", "凤凰", "钛媒体", "36氪", "虎嗅",
    "北京商报", "环球", "观察者", "参考消息", "中国日报", "财联社", "时代周报",
    "华夏时报", "国际金融报", "央广", "工人日报", "科技日报", "大众网", "齐鲁",
    "广州日报", "羊城晚报", "南方日报", "深圳", "湖北日报", "湖南日报", "河南日报",
    "北京日报", "天津日报", "重庆日报", "解放日报", "文汇", "红星新闻", "封面新闻",
    "上游新闻", "极目新闻", "扬子晚报", "钱江晚报", "澎湃新闻", "证券之星", "金融界",
]

# 明显非大陆中文媒体（中文查询里出现的港澳台/海外媒体 → 归“国际”）
NON_MAINLAND_SOURCE_KEYWORDS = [
    "联合早报", "星岛", "明报", "香港01", "大公", "南华早报", "SCMP", "中央社",
    "自由时报", "联合报", "中时", "旺报", "风传媒", "BBC", "VOA", "美国之音",
    "德国之声", "RFI", "日经", "共同社", "朝日", "韩联社", "华尔街日报", "纽约时报",
    "金融时报", "路透", "彭博", "Reuters", "Bloomberg", "Yahoo", "AFP", "AP News",
    "CNBC", "CNN", "Forbes", "Fortune",
    # ESG 专业站点
    "ESG Today", "ESG News", "ESG Dive", "ESG Clarity", "GreenBiz", "Responsible Investor",
]

# 分类规则（按顺序第一个命中生效，顺序=优先级）
CATEGORY_RULES = [
    ("政策监管", [
        "政策", "监管", "新规", "法规", "法案", "草案", "指引", "披露要求", "强制披露",
        "证监会", "交易所", "财政部", "欧盟", "欧盟委员会", "立法", "生效", "修订",
        "征求意见", "CSRD", "CBAM", "ISSB", "IFRS", "TCFD", "TNFD", "GRI", "SASB",
        "SEC", "FCA", "ESMA", "regulation", "regulator", "regulatory", "mandate",
        "directive", "rule", "ruling", "guideline", "disclosure requirement",
        "compliance", "law", "legislation", "bill", "policy",
    ]),
    ("金融市场", [
        "绿色债券", "债券", "基金", "投资者", "投资", "融资", "评级", "绿色金融",
        "碳交易", "碳市场", "碳价", "碳配额", "CCER", "ETF", "股价", "股票", "上市",
        "IPO", "私募", "险资", "银行", "保险", "asset manager", "investors", "fund",
        "green bond", "carbon market", "carbon price", "credit rating", "MSCI",
        "S&P", "Moody's", "Fitch", "stock", "shares", "IPO", "bank", "insurance",
        "capital", "financing", "yield",
    ]),
    ("气候环境", [
        "气候", "碳排放", "碳中和", "碳达峰", "温室气体", "减排", "净零", "能源",
        "可再生能源", "光伏", "风电", "氢能", "生物多样性", "污染", "环保", "生态",
        "climate", "emissions", "carbon", "net zero", "net-zero", "renewable",
        "energy", "biodiversity", "coal", "oil", "solar", "wind", "hydrogen",
        "pollution", "deforestation", "methane", "transition",
    ]),
    ("社会议题", [
        "员工", "劳工", "人权", "性别", "多元", "包容", "社区", "公益", "童工",
        "薪酬", "职场", "劳动", "social", "workers", "labor", "human rights",
        "diversity", "inclusion", "community", "gender", "wage", "strike",
        "union", "supply chain workers", "DEI",
    ]),
    ("治理/反腐", [
        "治理", "反腐", "贿赂", "合规", "董事会", "股东", "投票", "审计", "透明度",
        "内幕", "高管薪酬", "governance", "anti-corruption", "bribery", "board",
        "shareholder", "proxy", "audit", "transparency", "executive pay",
        "whistleblower", "conflict of interest",
    ]),
    ("企业动态", [
        "企业", "公司", "集团", "宣布", "发布", "合作", "战略", "供应链", "高管",
        "CEO", "收购", "合并", "净零目标", "承诺", "工厂", "制造", "品牌",
        "company", "corp", "announces", "launches", "partnership", "merger",
        "acquisition", "supply chain", "CEO", "strategy", "factory", "brand",
    ]),
]

# ---------------- 工具函数 ----------------

SITE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
OUT_JSON = os.path.join(SITE_DIR, "news.json")

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def log(msg):
    print(msg, flush=True)


def fetch_url(url, retries=RETRIES):
    """抓取 URL 内容，返回 bytes；失败返回 None（带重试）"""
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    })
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except Exception as e:
            if attempt == retries:
                log(f"    [跳过] {url} 失败: {e}")
                return None
            time.sleep(2 * attempt)
    return None


def clean_text(s):
    """去 HTML 标签、去多余空白"""
    s = TAG_RE.sub(" ", html.unescape(s or ""))
    return WS_RE.sub(" ", s).strip()


def parse_date(pub_str):
    """解析 RFC822 日期 → UTC datetime（失败返回 None）"""
    try:
        dt = parsedate_to_datetime(pub_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        return None


def domain_of(link):
    try:
        return urllib.parse.urlparse(link).netloc.lower()
    except Exception:
        return ""


def guess_region(source, link, default_region):
    """根据来源名/域名细化地区判定：dom=国内, intl=国际"""
    src = (source or "").strip()
    dom = domain_of(link)

    # 中国大陆域名 → 国内
    if dom.endswith(".cn") or dom.endswith(".com.cn") or dom.endswith(".gov.cn"):
        return "dom"
    # 来源名命中大陆媒体 → 国内
    if any(k in src for k in CN_SOURCE_KEYWORDS):
        return "dom"
    # 来源名命中港澳台/海外媒体 → 国际
    if any(k in src for k in NON_MAINLAND_SOURCE_KEYWORDS):
        return "intl"
    # 其他（如 Google News 跳转链接）按查询语言默认
    return default_region


def classify_news(title, desc):
    """根据标题+摘要判断类别"""
    text = f"{title} {desc}".lower()
    for cat, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.lower() in text:
                return cat
    return "其他"


def parse_rss(xml_bytes, default_region, feed_label="", default_source=""):
    """解析 RSS XML → 新闻条目列表"""
    if not xml_bytes:
        return []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    items = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", ""))
        link = (item.findtext("link", "") or "").strip()
        pub = (item.findtext("pubDate", "") or "").strip()
        source = clean_text(item.findtext("source", "")) or default_source
        desc = clean_text(item.findtext("description", ""))

        # Bing 没有 <source> 标签，标题格式常为 “标题 - 来源名”
        if not source and " - " in title and feed_label.startswith("bing"):
            head, _, tail = title.rpartition(" - ")
            if head.strip() and tail.strip() and len(tail) <= 40:
                source, title = tail.strip(), head.strip()

        # Google News 的 description 开头会重复一遍标题，去掉
        if feed_label.startswith("google") and desc.startswith(title):
            desc = desc[len(title):].strip(" -–— ")

        if not title or not link:
            continue

        pub_dt = parse_date(pub)
        region = guess_region(source, link, default_region)

        items.append({
            "title": title,
            "link": link,
            "source": source or "未知来源",
            "published": pub,
            "pubTs": pub_dt.isoformat() if pub_dt else None,
            "pubDt": pub_dt,          # 仅脚本内部使用，写入 JSON 前删除
            "region": region,          # dom / intl
            "category": classify_news(title, desc),
            "desc": desc[:MAX_DESC],
        })
    return items


def dedupe_and_sort(all_items):
    """按标题去重 → 按时间倒序（无时间的排最后）"""
    seen = set()
    unique = []
    for it in all_items:
        key = re.sub(r"\W+", "", it["title"].lower())
        if key and key not in seen:
            seen.add(key)
            unique.append(it)

    def sort_key(x):
        dt = x["pubDt"] or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        return dt
    unique.sort(key=sort_key, reverse=True)
    return unique


def main():
    log("=" * 56)
    log("📡 ESG 多源新闻聚合抓取器 v3 启动")
    log(f"   时间（UTC）：{datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    log("=" * 56)

    os.makedirs(SITE_DIR, exist_ok=True)
    all_items = []
    fetched_feeds, failed_feeds = 0, 0

    # 1) Google News
    for q, hl, gl, ceid, region in GOOGLE_QUERIES:
        params = urllib.parse.urlencode({"q": q, "hl": hl, "gl": gl, "ceid": ceid})
        url = f"https://news.google.com/rss/search?{params}"
        log(f"  🔍 [Google] {q} ({hl})")
        xml = fetch_url(url)
        if xml is None:
            failed_feeds += 1
        else:
            fetched_feeds += 1
            got = parse_rss(xml, region, "google")
            all_items.extend(got)
            log(f"     ✓ {len(got)} 条")
        time.sleep(SLEEP_BETWEEN)

    # 2) Bing News
    for q, mkt, region in BING_QUERIES:
        params = urllib.parse.urlencode({"q": q, "format": "rss", "mkt": mkt,
                                         "setlang": "en" if mkt.startswith("en") else "zh-cn"})
        url = f"https://www.bing.com/news/search?{params}"
        log(f"  🔍 [Bing] {q} ({mkt})")
        xml = fetch_url(url)
        if xml is None:
            failed_feeds += 1
        else:
            fetched_feeds += 1
            got = parse_rss(xml, region, "bing")
            all_items.extend(got)
            log(f"     ✓ {len(got)} 条")
        time.sleep(SLEEP_BETWEEN)

    # 3) 专业 ESG 站点
    for feed_url, region, site_name in DIRECT_FEEDS:
        log(f"  🔍 [RSS] {site_name}")
        xml = fetch_url(feed_url)
        if xml is None:
            failed_feeds += 1
        else:
            fetched_feeds += 1
            got = parse_rss(xml, region, "direct", default_source=site_name)
            all_items.extend(got)
            log(f"     ✓ {len(got)} 条")
        time.sleep(SLEEP_BETWEEN)

    # ---- 处理：去重、过滤、排序 ----
    final = dedupe_and_sort(all_items)
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=KEEP_DAYS)
    final = [it for it in final if (it["pubDt"] is None or it["pubDt"] >= cutoff)]
    final = final[:MAX_ITEMS]

    dom_count = sum(1 for it in final if it["region"] == "dom")
    intl_count = len(final) - dom_count

    # 统计来源（前 15 名）
    source_stat = {}
    for it in final:
        source_stat[it["source"]] = source_stat.get(it["source"], 0) + 1
    top_sources = sorted(source_stat.items(), key=lambda kv: -kv[1])[:15]

    # 统计类别
    cat_stat = {}
    for it in final:
        cat_stat[it["category"]] = cat_stat.get(it["category"], 0) + 1

    # 输出 JSON（去掉内部字段）
    out_items = [{k: v for k, v in it.items() if k != "pubDt"} for it in final]

    # 一条都没抓到时：不写文件、保留旧数据，避免把网站清空
    if not out_items:
        log("-" * 56)
        log("⚠️ 警告：本次没有抓到任何新闻（全部源失败或过滤后为空）。")
        log("   已保留现有 news.json，网站数据不变。")
        sys.exit(0)

    payload = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "demo": False,
        "feedsOk": fetched_feeds,
        "feedsFailed": failed_feeds,
        "total": len(out_items),
        "domestic": dom_count,
        "international": intl_count,
        "topSources": [[s, c] for s, c in top_sources],
        "categories": cat_stat,
        "items": out_items,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    log("-" * 56)
    log(f"✅ 完成：抓取 {fetched_feeds}/{fetched_feeds + failed_feeds} 路源"
        f"，去重后 {len(out_items)} 条（国内 {dom_count} / 国际 {intl_count}）")
    log(f"   输出：{OUT_JSON}")
    log("=" * 56)


if __name__ == "__main__":
    main()
