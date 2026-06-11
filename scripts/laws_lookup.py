#!/usr/bin/env python3
"""Soul Badman 法条检索工具 — 按场景/关键词/编号快速查找法条。

用法：
    python laws_lookup.py --scene 违法解除          # 场景检索
    python laws_lookup.py --id labor-contract-87    # 按编号查
    python laws_lookup.py --query "被裁了能拿多少钱"  # 全文模糊搜索
    python laws_lookup.py --list                    # 列出全部法条摘要
    python laws_lookup.py --priority 5              # 按权重筛选

纯 Python，零依赖。
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

LAWS_PATH = Path(__file__).parent.parent / "references" / "laws.json"

# 中文场景词 → 法律关键词映射（解决中文无空格分词问题）
QUERY_ALIASES = {
    "被裁": ["违法解除", "经济补偿", "赔偿金", "N+1", "2N", "解除", "裁员"],
    "开除": ["违法解除", "过失性解除", "赔偿金", "2N"],
    "裁员": ["经济性裁员", "经济补偿", "N", "解除"],
    "优化": ["违法解除", "经济补偿", "赔偿金", "客观情况变化"],
    "毕业": ["违法解除", "赔偿金", "协商解除"],
    "拿多少钱": ["经济补偿", "赔偿金", "工资计算", "N", "2N", "N+1"],
    "能要多少钱": ["经济补偿", "赔偿金", "N", "2N", "N+1"],
    "不给加班费": ["加班费", "劳动报酬", "加班工资"],
    "大小周": ["加班费", "休息日", "加班"],
    "996": ["加班费", "加班上限", "工时"],
    "不签合同": ["未签合同", "双倍工资"],
    "没签合同": ["未签合同", "双倍工资"],
    "末位淘汰": ["末位淘汰", "违法解除", "2N"],
    "绩效不行": ["不胜任", "不能胜任", "解除"],
    "不胜任": ["不胜任", "不能胜任", "解除", "N+1"],
    "架构调整": ["客观情况变化", "协商变更", "解除", "N+1"],
    "调岗": ["调岗降薪", "合同变更", "协商一致"],
    "降薪": ["调岗降薪", "合同变更", "工资"],
    "欠薪": ["拖欠工资", "被迫解除", "劳动报酬"],
    "拖欠工资": ["拖欠工资", "劳动报酬", "被迫解除"],
    "怀孕": ["孕期辞退", "三期保护", "违法解除"],
    "工伤": ["工伤认定", "工伤保险"],
    "试用期": ["试用期", "试用期解除", "录用条件"],
    "竞业": ["竞业限制", "竞业限制补偿"],
    "年假": ["年假", "年休假", "未休年假"],
    "社保": ["社会保险", "未缴社保", "补缴"],
    "离职证明": ["离职证明", "解除手续"],
    "辞职": ["主动辞职", "劳动者解除"],
    "不打官司": ["仲裁", "仲裁时效", "仲裁流程"],
    "打官司": ["仲裁", "仲裁时效", "诉讼"],
}


def _expand_query(q: str) -> list[str]:
    """中文查询词扩展：匹配别名映射，扩展为法律关键词。"""
    tokens = [q]
    for alias, expansions in QUERY_ALIASES.items():
        if alias in q:
            tokens.extend(expansions)
    return tokens


def load_laws() -> dict:
    if not LAWS_PATH.exists():
        print(f"错误: 法条文件不存在: {LAWS_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(LAWS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_article(a: dict, verbose: bool = False) -> str:
    """格式化单条法条输出。"""
    law_name = a.get("law", "")
    article = a.get("article", "")
    plain = a.get("plain", "")
    formula = a.get("formula", "")
    scenes = a.get("scenes", [])
    priority = a.get("priority", 0)
    warning = a.get("warning", "")
    tactical = a.get("tactical", "")

    stars = "⭐" * min(priority, 5)
    header = f"[{a['id']}] {law_name} {article} {stars}"
    if scenes:
        header += f"\n  场景: {', '.join(scenes)}"
    header += f"\n  {plain}"
    if formula:
        header += f"\n  公式: {formula}"
    if warning:
        header += f"\n  ⚠ 注意: {warning}"
    if tactical:
        header += f"\n  💡 战术: {tactical}"

    if verbose:
        text = a.get("text", "")
        header += f"\n  📜 原文: {text}"

    return header


def cmd_list(data: dict, priority_min: int = 0):
    """列出所有法条摘要。"""
    articles = data.get("articles", [])
    if priority_min > 0:
        articles = [a for a in articles if a.get("priority", 0) >= priority_min]

    # 按 law 分组
    grouped = {}
    for a in articles:
        law = a.get("law", "其他")
        grouped.setdefault(law, []).append(a)

    print(f"共 {len(articles)} 条法条")
    print(f"覆盖法律: {', '.join(grouped.keys())}")
    print()

    for law, items in grouped.items():
        print(f"═══ {law} ═══")
        for a in items:
            print(f"  [{a['id']}] {a['article']} (P{a.get('priority','?')}) {a.get('plain','')[:60]}...")
        print()


def cmd_scene(data: dict, scene: str):
    """按场景检索。"""
    articles = data.get("articles", [])
    matches = []
    for a in articles:
        scenes = [s.lower() for s in a.get("scenes", [])]
        if any(scene.lower() in s for s in scenes):
            matches.append(a)
        elif scene.lower() in a.get("plain", "").lower():
            matches.append(a)

    if not matches:
        print(f"未找到匹配场景 '{scene}' 的法条。尝试用 --query 全文搜索。")
        return

    print(f"场景 '{scene}' 匹配 {len(matches)} 条:\n")
    for a in sorted(matches, key=lambda x: x.get("priority", 0), reverse=True):
        print(fmt_article(a))
        print()


def cmd_id(data: dict, aid: str):
    """按编号检索。"""
    for a in data.get("articles", []):
        if a["id"] == aid:
            print(fmt_article(a, verbose=True))
            return
    # 模糊匹配
    for a in data.get("articles", []):
        if aid.lower() in a["id"].lower():
            print(fmt_article(a, verbose=True))
            return
    print(f"未找到法条: {aid}")


def cmd_query(data: dict, query: str):
    """全文模糊搜索（中文自动分词+别名扩展）。"""
    articles = data.get("articles", [])
    tokens = _expand_query(query.lower())
    results = []
    for a in articles:
        text = (
            a.get("plain", "")
            + " " + " ".join(a.get("scenes", []))
            + " " + a.get("article", "")
            + " " + a.get("text", "")
        )
        text_lower = text.lower()

        hit_score = 0
        for word in tokens:
            if word.lower() in text_lower:
                hit_score += 1
            if word.lower() in a.get("article", "").lower():
                hit_score += 2

        if hit_score > 0:
            sort_score = hit_score + a.get("priority", 0) * 0.5
            results.append((sort_score, a))

    results.sort(key=lambda x: x[0], reverse=True)
    if not results:
        print(f"未找到与 '{query}' 相关的法条。")
        return

    print(f"搜索 '{query}' 找到 {len(results)} 条:\n")
    for score, a in results[:10]:
        print(fmt_article(a))
        print(f"  (相关度: {score:.1f})\n")


def cmd_stats(data: dict):
    """统计。"""
    articles = data.get("articles", [])
    meta = data.get("meta", {})
    by_law = {}
    by_priority = {}
    for a in articles:
        law = a.get("law", "其他")
        by_law[law] = by_law.get(law, 0) + 1
        p = a.get("priority", 0)
        by_priority[p] = by_priority.get(p, 0) + 1

    print(f"法条总数: {len(articles)}")
    print(f"覆盖法律: {meta.get('total_articles', 'N/A')} 条声明")
    print(f"\n按法律分布:")
    for law, count in sorted(by_law.items(), key=lambda x: x[1], reverse=True):
        print(f"  {law}: {count} 条")
    print(f"\n按权重分布:")
    for p in sorted(by_priority.keys(), reverse=True):
        print(f"  P{p}: {by_priority[p]} 条")


def main():
    parser = argparse.ArgumentParser(description="Soul Badman 法条检索工具")
    parser.add_argument("--scene", type=str, help="按场景检索（如: 违法解除, 加班费, 孕期辞退）")
    parser.add_argument("--id", type=str, help="按编号检索（如: labor-contract-87）")
    parser.add_argument("--query", type=str, help="全文模糊搜索")
    parser.add_argument("--list", action="store_true", help="列出全部法条摘要")
    parser.add_argument("--priority", type=int, default=0, help="按最低权重筛选（5=核心，1=边缘）")
    parser.add_argument("--stats", action="store_true", help="统计信息")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示法条原文")

    args = parser.parse_args()
    data = load_laws()

    if args.stats:
        cmd_stats(data)
    elif args.scene:
        cmd_scene(data, args.scene)
    elif args.id:
        cmd_id(data, args.id)
    elif args.query:
        cmd_query(data, args.query)
    elif args.list:
        cmd_list(data, args.priority)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
