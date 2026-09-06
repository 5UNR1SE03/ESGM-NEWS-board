/* ESG 全球新闻台 前端逻辑 */
(function () {
  "use strict";

  var CATEGORY_COLORS = {
    "政策监管": "#c0392b",
    "企业动态": "#2471a3",
    "金融市场": "#b9770e",
    "气候环境": "#1e8449",
    "社会议题": "#7d3c98",
    "治理/反腐": "#b03a5b",
    "其他": "#7f8c8d"
  };

  var GROUP_ORDER = ["今日", "昨日", "本周", "更早"];
  var GROUP_TITLES = {
    "今日": "📅 今日",
    "昨日": "📅 昨日",
    "本周": "🗓 本周",
    "更早": "📚 更早"
  };
  var BEIJING_OFFSET = 8 * 60 * 60 * 1000; // 北京时间 = UTC + 8h

  var DATA = null;
  var currentRegion = "all";

  /* ---------- 工具 ---------- */
  function $(id) { return document.getElementById(id); }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function beijingDate(d) {
    return new Date(d.getTime() + BEIJING_OFFSET);
  }

  function dayKey(ts) {
    // ts: ISO 字符串（UTC）→ 北京时间日期 YYYY-MM-DD
    var d = new Date(ts);
    if (isNaN(d.getTime())) return null;
    return beijingDate(d).toISOString().slice(0, 10);
  }

  function fmtTime(ts) {
    var d = new Date(ts);
    if (isNaN(d.getTime())) return "--";
    var b = beijingDate(d);
    var mm = String(b.getUTCMonth() + 1).padStart(2, "0");
    var dd = String(b.getUTCDate()).padStart(2, "0");
    var hh = String(b.getUTCHours()).padStart(2, "0");
    var mi = String(b.getUTCMinutes()).padStart(2, "0");
    return mm + "-" + dd + " " + hh + ":" + mi;
  }

  function fmtFullTime(iso) {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "未知";
    var b = beijingDate(d);
    return b.getUTCFullYear() + "年" + String(b.getUTCMonth() + 1).padStart(2, "0") + "月" +
      String(b.getUTCDate()).padStart(2, "0") + "日 " +
      String(b.getUTCHours()).padStart(2, "0") + ":" +
      String(b.getUTCMinutes()).padStart(2, "0");
  }

  /* ---------- 分组 ---------- */
  function groupItems(items) {
    var today = beijingDate(new Date()).toISOString().slice(0, 10);
    var groups = { "今日": [], "昨日": [], "本周": [], "更早": [] };

    items.forEach(function (it) {
      var key = it.pubTs ? dayKey(it.pubTs) : null;
      if (!key) { groups["更早"].push(it); return; }
      if (key === today) groups["今日"].push(it);
      else {
        var d = new Date(key + "T00:00:00Z");
        var t = new Date(today + "T00:00:00Z");
        var diffDays = Math.round((t - d) / 86400000);
        if (diffDays === 1) groups["昨日"].push(it);
        else if (diffDays >= 2 && diffDays <= 7) groups["本周"].push(it);
        else groups["更早"].push(it);
      }
    });
    return groups;
  }

  /* ---------- 渲染 ---------- */
  function cardHtml(it, showRegion) {
    var badge = '<span class="badge" style="background:' +
      (CATEGORY_COLORS[it.category] || CATEGORY_COLORS["其他"]) + '">' +
      escapeHtml(it.category) + "</span>";
    var regionTag = showRegion
      ? (it.region === "dom"
          ? '<span class="region-tag dom">国内</span>'
          : '<span class="region-tag intl">国际</span>')
      : "";
    return (
      '<article class="card">' +
        '<div class="card-top">' + badge + regionTag +
          '<span class="card-time">' + escapeHtml(fmtTime(it.pubTs)) + "</span>" +
        "</div>" +
        '<a class="card-title" href="' + escapeHtml(it.link) +
          '" target="_blank" rel="noopener noreferrer">' + escapeHtml(it.title) + "</a>" +
        (it.desc ? '<p class="card-desc">' + escapeHtml(it.desc) + "</p>" : "") +
        '<div class="card-meta">来源：' + escapeHtml(it.source) + "</div>" +
      "</article>"
    );
  }

  function render() {
    var list = $("newsList");
    var empty = $("emptyState");
    var stats = $("stats");
    var items = DATA.items || [];

    var filtered = items;
    if (currentRegion !== "all") {
      filtered = items.filter(function (it) { return it.region === currentRegion; });
    }

    if (!filtered.length) {
      list.innerHTML = "";
      empty.classList.remove("hidden");
      stats.innerHTML = "";
      return;
    }
    empty.classList.add("hidden");

    var groups = groupItems(filtered);
    var domCount = filtered.filter(function (it) { return it.region === "dom"; }).length;
    var intlCount = filtered.length - domCount;
    var todayCount = groups["今日"].length;

    stats.innerHTML =
      '<span class="stat-chip">今日 <b>' + todayCount + "</b></span>" +
      '<span class="stat-chip">国内 <b>' + domCount + "</b></span>" +
      '<span class="stat-chip">国际 <b>' + intlCount + "</b></span>" +
      '<span class="stat-chip">共 <b>' + filtered.length + "</b> 条</span>";

    var html = "";
    GROUP_ORDER.forEach(function (g) {
      if (!groups[g].length) return;
      html +=
        '<section class="date-group">' +
          '<div class="group-head">' +
            "<h2>" + GROUP_TITLES[g] + "</h2>" +
            '<span class="group-count">' + groups[g].length + " 条</span>" +
          "</div>" +
          '<div class="cards">' +
            groups[g].map(function (it) { return cardHtml(it, currentRegion === "all"); }).join("") +
          "</div>" +
        "</section>";
    });
    list.innerHTML = html;
  }

  function renderMeta() {
    var t = DATA.generatedAt ? fmtFullTime(DATA.generatedAt) : "未知";
    $("updatedAt").textContent = t;
    if (DATA.demo) $("demoBanner").classList.remove("hidden");
  }

  /* ---------- 事件 ---------- */
  function bindTabs() {
    $("regionTabs").addEventListener("click", function (e) {
      var btn = e.target.closest(".seg-btn");
      if (!btn) return;
      currentRegion = btn.getAttribute("data-region");
      document.querySelectorAll(".seg-btn").forEach(function (b) {
        b.classList.toggle("active", b === btn);
      });
      render();
    });
  }

  /* ---------- 启动 ---------- */
  function showLoadError(msg) {
    $("updatedAt").textContent = "加载失败";
    var list = $("newsList");
    list.innerHTML =
      '<div class="empty"><div class="empty-icon">⚠️</div>' +
      "<p>新闻数据加载失败</p>" +
      '<p class="empty-hint">' + escapeHtml(msg || "请刷新重试。") + "</p></div>";
  }

  function init() {
    bindTabs();
    fetch("news.json", { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        DATA = data || { items: [] };
        DATA.items.sort(function (a, b) {
          var ta = a.pubTs ? Date.parse(a.pubTs) : 0;
          var tb = b.pubTs ? Date.parse(b.pubTs) : 0;
          return (isNaN(tb) ? 0 : tb) - (isNaN(ta) ? 0 : ta);
        });
        renderMeta();
        render();
      })
      .catch(function (err) {
        showLoadError("可能是直接用 file:// 打开了页面，请改用本地服务器（见 README）。(" + err.message + ")");
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
