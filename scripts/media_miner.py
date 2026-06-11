#!/usr/bin/env python3
"""Soul Badman 公开媒体判例采集

从法律自媒体、新闻报道搜索劳动争议判例，比裁判文书网更友好：
- 已有人工撰写的摘要和点评
- 时效性强（含最新判决）
- 反爬不严格

数据源：
    知乎、微信公众号文章、新浪财经法律频道、36氪、虎嗅等

用法：
    python media_miner.py --search "35岁被裁 违法解除 2N"
    python media_miner.py --search "末位淘汰 判例 2024"
    python media_miner.py --search "互联网 加班费 劳动争议"

输出：标准 markdown 格式的待核验线索文件，默认保存到 cases/raw_media/。
      人工核验案号、法院、来源后，再移入 cases/curated/。

纯 Python，零依赖。
"""

import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

CASES_DIR = Path(__file__).parent.parent / "cases" / "curated"
RAW_DIR = Path(__file__).parent.parent / "cases" / "raw_media"

# ─── 搜索源配置 ────────────────────────────────────────

SOURCES = {
    "bing": {
        "name": "Bing 搜索",
        "search_url": "https://www.bing.com/search?q={query}+劳动争议+判例",
        "note": "通用搜索引擎，覆盖面广",
    },
    "sina_finance": {
        "name": "新浪财经",
        "search_url": "https://search.sina.com.cn/?q={query}+劳动争议&c=news",
        "note": "财经类劳动争议报道",
    },
}


# ─── 核心逻辑 ───────────────────────────────────────────


def search_web(query: str, max_results: int = 10) -> list[dict]:
    """通用搜索引擎抓取——使用 DuckDuckGo HTML 接口（无需 API key）。"""
    import urllib.request
    import urllib.error

    encoded = quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  搜索失败: {e}")
        return []

    # 解析搜索结果
    results = []
    # DuckDuckGo HTML 结果格式
    links = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )
    snippets = re.findall(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )

    for i, (url, title) in enumerate(links[:max_results]):
        title = re.sub(r'<[^>]+>', '', title).strip()
        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()

        # 过滤：只保留中文内容、看起来像法律案件的内容
        if not any(kw in title + snippet for kw in
                   ["劳动", "裁员", "辞退", "赔偿", "仲裁", "法院", "判决",
                    "解除", "年假", "加班", "工伤", "社保", "竞业"]):
            continue

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "source": f"web_search:{datetime.now().strftime('%Y-%m-%d')}",
        })

    return results


def extract_case_info(article: dict) -> dict:
    """从文章摘要中提取判例关键信息。"""
    text = f"{article.get('title','')} {article.get('snippet','')}"

    case = {
        "title": article.get("title", ""),
        "url": article.get("url", ""),
        "source": article.get("source", ""),
        "case_number": "",
        "location": "",
        "court": "",
        "verdict": "",
        "summary": article.get("snippet", ""),
        "keywords": [],
    }

    # 提取案号
    m = re.search(r'[（(](\d{4})[)）].+?[民刑行].+?\d+号', text)
    if m:
        case["case_number"] = m.group(0)

    # 提取地点
    for loc in ["北京", "上海", "深圳", "杭州", "广州", "成都", "南京", "武汉"]:
        if loc in text:
            case["location"] = loc
            break

    # 提取关键词
    keyword_bank = [
        "违法解除", "2N", "N+1", "经济补偿", "赔偿金", "经济性裁员",
        "试用期", "孕期", "三期", "工伤", "未签合同", "双倍工资",
        "加班费", "大小周", "996", "末位淘汰", "不胜任", "架构调整",
        "竞业限制", "调岗降薪", "拖欠工资", "年假", "35岁",
        "互联网", "裁员", "辞退", "败诉", "胜诉",
    ]
    case["keywords"] = [kw for kw in keyword_bank if kw in text]

    # 判断胜负
    if any(w in text for w in ["驳回", "败诉", "不予支持", "未获支持"]):
        case["verdict"] = "疑似劳动者败诉"
    elif any(w in text for w in ["支持", "判赔", "赔偿", "胜诉", "认定违法"]):
        case["verdict"] = "疑似劳动者胜诉"

    return case


def save_case_markdown(case: dict, output_dir: Path = None) -> Path:
    """保存为标准判例 markdown。"""
    if output_dir is None:
        output_dir = RAW_DIR  # 媒体来源判例存入 raw_media，人工核验后移入 curated
    output_dir.mkdir(parents=True, exist_ok=True)

    title = case.get("title", "untitled")
    safe_name = re.sub(r'[\\/:*?"<>|]', '-', title)[:50]
    uid = hashlib.md5(case.get("url", "").encode()).hexdigest()[:8]

    md = f"""# 案号：{case.get('case_number', '待确认')}

## 基本信息
- 地点：{case.get('location', '待确认')}
- 判决结果：{case.get('verdict', '待确认')}
- 来源：{case.get('source', '')}

## 案情摘要
{case.get('summary', '')}

> 原文链接: {case.get('url', '')}

## 法院认定
（详见原文——本摘要来自媒体报道，非裁判文书原文。建议点击原文链接核实。）

## 关键词
{', '.join(case['keywords']) if case.get('keywords') else '待标注'}

## 来源
{case.get('source', '')}
自动采集于 {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""

    filepath = output_dir / f"media_{uid}_{safe_name}.md"
    filepath.write_text(md, encoding="utf-8")
    return filepath


def mine_from_media(query: str, max_results: int = 10, save: bool = True):
    """从公开媒体搜索并提取判例。"""
    print(f"\n{'='*60}")
    print(f"Soul Badman 公开媒体判例搜索")
    print(f"查询: {query}")
    print(f"{'='*60}\n")

    articles = search_web(f"{query} 劳动争议 判例 法院", max_results)

    if not articles:
        print("未找到相关结果。")
        print("提示：尝试更具体的关键词，如 '35岁被裁 判赔2N' 或 '互联网公司 加班费 判决'")
        return []

    cases = []
    for i, article in enumerate(articles):
        print(f"[{i+1}/{len(articles)}] {article['title'][:80]}")
        case = extract_case_info(article)

        # 过滤：只保留有价值的结果（有判例特征）
        if case["keywords"] or case["case_number"] or case["verdict"]:
            cases.append(case)
            if save:
                filepath = save_case_markdown(case)
                print(f"  ✓ {filepath.name}")
        else:
            print(f"  - 跳过（无判例特征）")

        time.sleep(1.5)  # 礼貌间隔

    print(f"\n找到 {len(cases)} 个有效判例（存入 cases/raw_media/）")
    if cases:
        print(f"保存目录: {RAW_DIR}")
        print(f"⚠ 这些判例来自公开媒体报道，未经人工核验案号和法院来源。")
        print(f"   核验后请移入 cases/curated/ 并运行:")
        print(f"  python cases/build_index.py --reset")

    return cases


def interactive():
    """交互模式。"""
    print("Soul Badman 公开媒体判例搜索\n")
    print("搜索建议:")
    print("  '35岁被裁 违法解除 互联网'")
    print("  '末位淘汰 最高法指导案例'")
    print("  '加班费 大小周 判决 2024'")
    print("  '孕期辞退 2N 判例'\n")

    query = input("搜索关键词: ").strip()
    if not query:
        print("未输入关键词。")
        return

    try:
        count = int(input("最大结果数 (默认 10): ").strip() or "10")
    except ValueError:
        count = 10

    mine_from_media(query, max_results=count)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Soul Badman 公开媒体判例搜索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python media_miner.py --search "35岁被裁 违法解除 2N 判例"
  python media_miner.py --search "互联网 加班费 大小周 判决 2024"
  python media_miner.py --interactive

数据源: DuckDuckGo 搜索 → 过滤法律类结果 → 提取判例信息 → 生成标准格式
        """
    )
    parser.add_argument("--search", "-s", type=str, help="搜索关键词")
    parser.add_argument("--count", "-n", type=int, default=10, help="最大结果数")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    parser.add_argument("--no-save", action="store_true", help="仅搜索不保存")
    args = parser.parse_args()

    if args.interactive:
        interactive()
    elif args.search:
        mine_from_media(args.search, max_results=args.count, save=not args.no_save)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
