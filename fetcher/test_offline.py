# -*- coding: utf-8 -*-
"""
离线逻辑自测（不联网）：验证 RSS 解析、来源提取、地区判定、分类、去重、排序。
运行：python fetcher/test_offline.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_news as f

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
<item>
  <title>证监会发布ESG披露新规 - 新浪财经</title>
  <link>https://finance.sina.com.cn/a.html</link>
  <pubDate>Wed, 03 Sep 2026 10:30:00 +0800</pubDate>
  <description>证监会发布新规，强制披露要求明确</description>
</item>
<item>
  <title>EU finalizes CSRD reporting guidance</title>
  <link>https://www.esgtoday.com/x</link>
  <pubDate>Wed, 03 Sep 2026 08:00:00 GMT</pubDate>
  <source>ESG Today</source>
  <description>European Commission publishes guidance</description>
</item>
<item>
  <title>Tesla faces board governance vote</title>
  <link>https://news.google.com/rss/articles/abc</link>
  <pubDate>Tue, 02 Sep 2026 12:00:00 GMT</pubDate>
  <source>Reuters</source>
  <description>Shareholders vote on governance proposal</description>
</item>
<item>
  <title>某公司发布碳中和路线图</title>
  <link>https://news.google.com/rss/articles/zzz</link>
  <pubDate>Mon, 01 Sep 2026 06:00:00 GMT</pubDate>
  <source>界面新闻</source>
  <description>公司宣布2030年实现碳中和</description>
</item>
</channel></rss>"""


def main():
    items = f.parse_rss(SAMPLE_RSS.encode("utf-8"), "dom", "bing")
    assert len(items) == 4, f"解析条数错误: {len(items)}"

    # 1) Bing 风格 “标题 - 来源” 提取
    assert items[0]["title"] == "证监会发布ESG披露新规", items[0]["title"]
    assert items[0]["source"] == "新浪财经", items[0]["source"]

    # 2) 地区判定：新浪(大陆) → 国内；ESG Today / Reuters → 国际；界面新闻 → 国内
    assert items[0]["region"] == "dom"
    assert items[1]["region"] == "intl"
    assert items[2]["region"] == "intl"
    assert items[3]["region"] == "dom"
    assert f.guess_region("星岛日报", "https://news.google.com/rss/articles/x", "dom") == "intl"
    assert f.guess_region("联合早报", "", "dom") == "intl"

    # 3) 分类
    assert f.classify_news(items[0]["title"], items[0]["desc"]) == "政策监管"
    assert f.classify_news(items[1]["title"], items[1]["desc"]) == "政策监管"
    assert f.classify_news(items[2]["title"], items[2]["desc"]) == "治理/反腐"
    assert f.classify_news(items[3]["title"], items[3]["desc"]) == "气候环境"
    assert f.classify_news("完全无关的标题", "没有关键词") == "其他"

    # 4) 日期解析
    assert items[0]["pubTs"] == "2026-09-03T02:30:00+00:00", items[0]["pubTs"]
    assert f.parse_date("不是日期") is None

    # 5) 去重（标题相同只留一条）
    dup = [dict(items[0]), dict(items[0])]
    assert len(f.dedupe_and_sort(dup)) == 1

    # 6) 排序：最新的在最前；无日期的排最后
    # 样例中 EU 条目 (08:00 UTC) 比 证监会条目 (02:30 UTC) 更新，应排第一
    no_date = dict(items[0]); no_date["title"] = "无日期条目"; no_date["pubDt"] = None; no_date["pubTs"] = None
    sorted_items = f.dedupe_and_sort(items + [no_date])
    assert sorted_items[0]["title"].startswith("EU finalizes")
    assert sorted_items[-1]["title"] == "无日期条目"

    print("ALL TESTS PASSED ✔")


def test_all_sources_fail_keeps_old_file():
    """模拟全部源失败：main() 必须以 0 退出，且不得覆盖现有 news.json"""
    news_path = os.path.join(f.SITE_DIR, "news.json")
    with open(news_path, encoding="utf-8") as fp:
        original = fp.read()

    real_fetch, real_sleep = f.fetch_url, f.SLEEP_BETWEEN
    f.fetch_url = lambda url, retries=2: None   # 模拟断网：所有源都失败
    f.SLEEP_BETWEEN = 0
    exit_code = None
    try:
        f.main()
    except SystemExit as e:
        exit_code = e.code
    finally:
        f.fetch_url, f.SLEEP_BETWEEN = real_fetch, real_sleep

    assert exit_code == 0, f"全源失败时应正常退出(0)，实际 {exit_code}"
    with open(news_path, encoding="utf-8") as fp:
        after = fp.read()
    assert after == original, "全部源失败时不应覆盖旧数据"
    print("FAILURE-PATH TEST PASSED ✔")


if __name__ == "__main__":
    main()
    test_all_sources_fail_keeps_old_file()
