#!/usr/bin/env python3
"""Soul Badman 法条全文收录 — 从劳动法 JSON 提取全部条款，补全劳动合同法。

用法：python build_full_laws.py
"""

import json
import re
from pathlib import Path

LAWS_JSON = Path(__file__).parent.parent / "references" / "laws.json"
LABOR_RAW = Path("/tmp/labor_law_raw.json")


def parse_labor_law_articles(raw: dict) -> list[dict]:
    """从劳动法 JSON 解析全部条款。"""
    articles = []
    content = raw.get("laodongfa", {}).get("content", [])
    for chapter in content:
        ch_name = chapter.get("chapter", "")
        body = chapter.get("body", [])
        for item in body:
            # Parse "第X条\ncontent" format
            m = re.match(r"第([一二三四五六七八九十百]+)条\s*\n(.+)", item, re.DOTALL)
            if not m:
                continue

            num_cn = m.group(1)
            text = m.group(2).strip()

            # Convert Chinese numeral to digits for ID
            cn_num_map = {
                "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
                "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
                "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
                "二十一": 21, "二十二": 22, "二十三": 23, "二十四": 24, "二十五": 25,
                "二十六": 26, "二十七": 27, "二十八": 28, "二十九": 29, "三十": 30,
                "三十一": 31, "三十二": 32, "三十三": 33, "三十四": 34, "三十五": 35,
                "三十六": 36, "三十七": 37, "三十八": 38, "三十九": 39, "四十": 40,
                "四十一": 41, "四十二": 42, "四十三": 43, "四十四": 44, "四十五": 45,
                "四十六": 46, "四十七": 47, "四十八": 48, "四十九": 49, "五十": 50,
                "五十一": 51, "一百": 100,
            }
            # Handle compound numbers like "一百零七"
            article_num = num_cn
            if article_num in cn_num_map:
                aid = f"labor-{cn_num_map[article_num]:02d}"
            else:
                # Try parsing complex numbers
                aid = f"labor-{article_num}"

            # Auto-generate plain based on chapter context
            plain, scenes, priority = auto_plain_labor(article_num, text, ch_name)

            articles.append({
                "id": aid,
                "law": "劳动法",
                "article": f"第{num_cn}条",
                "text": text,
                "plain": plain,
                "scenes": scenes,
                "priority": priority,
            })

    return articles


def auto_plain_labor(num_cn: str, text: str, chapter: str) -> tuple[str, list[str], int]:
    """为劳动法条款自动生成大白话摘要。"""
    # Extract first sentence for summary
    first_sent = text.split("。")[0][:80] + "。" if "。" in text else text[:80]

    # Map by chapter
    chapter_scenes = {
        "总则": (["基本原则"], 1),
        "促进就业": (["就业", "招聘", "歧视"], 2),
        "劳动合同和集体合同": (["劳动合同", "集体合同", "解除"], 5),
        "工作时间和休息休假": (["工时", "加班", "休假"], 5),
        "工资": (["工资", "最低工资", "支付"], 5),
        "劳动安全卫生": (["劳动安全", "劳动保护"], 2),
        "女职工和未成年工特殊保护": (["女职工", "未成年工", "特殊保护"], 3),
        "职业培训": (["职业培训"], 1),
        "社会保险和福利": (["社会保险", "福利"], 3),
        "劳动争议": (["劳动争议", "仲裁"], 5),
        "监督检查": (["监督检查", "劳动监察"], 2),
        "法律责任": (["法律责任", "处罚"], 3),
        "附则": (["附则"], 1),
    }

    for ch_key, (scenes, priority) in chapter_scenes.items():
        if ch_key in chapter:
            return first_sent, scenes, priority

    return first_sent, ["其他"], 1


def build_contract_law_remaining() -> list[dict]:
    """补充劳动合同法后半部分（第63-98条，劳务派遣、非全日制、法律责任等）。"""
    return [
        # 劳务派遣 (Section 2: Labor Dispatch)
        {"id":"labor-contract-58","law":"劳动合同法","article":"第五十八条",
         "text":"劳务派遣单位是本法所称用人单位，应当履行用人单位对劳动者的义务。劳务派遣单位应当与被派遣劳动者订立二年以上的固定期限劳动合同，按月支付劳动报酬。",
         "plain":"劳务派遣公司才是你的用人单位，必须签2年以上合同，每月支付工资。如果只跟你签短期合同=违法。",
         "scenes":["劳务派遣","合同期限"],"priority":3},
        {"id":"labor-contract-60","law":"劳动合同法","article":"第六十条",
         "text":"劳务派遣单位不得克扣用工单位按照劳务派遣协议支付给被派遣劳动者的劳动报酬。",
         "plain":"派遣公司不能克扣你的工资。用工单位给了多少钱，派遣公司必须全发给你。",
         "scenes":["劳务派遣","工资"],"priority":3},
        {"id":"labor-contract-62","law":"劳动合同法","article":"第六十二条",
         "text":"用工单位应当履行下列义务：（一）执行国家劳动标准，提供相应的劳动条件和劳动保护；（二）告知被派遣劳动者的工作要求和劳动报酬；（三）支付加班费、绩效奖金，提供与工作岗位相关的福利待遇；（四）对在岗被派遣劳动者进行工作岗位所必需的培训；（五）连续用工的，实行正常的工资调整机制。",
         "plain":"你被派遣到的用工单位也有义务——必须提供劳动保护、支付加班费和奖金、提供福利待遇。用工单位不能因为是「派遣工」就区别对待。",
         "scenes":["劳务派遣","同工同酬"],"priority":4},
        {"id":"labor-contract-63","law":"劳动合同法","article":"第六十三条",
         "text":"被派遣劳动者享有与用工单位的劳动者同工同酬的权利。用工单位应当按照同工同酬原则，对被派遣劳动者与本单位同类岗位的劳动者实行相同的劳动报酬分配办法。",
         "plain":"派遣工和正式工必须同工同酬！做同样的活拿不一样的钱=违法。",
         "scenes":["劳务派遣","同工同酬"],"priority":5},
        {"id":"labor-contract-66","law":"劳动合同法","article":"第六十六条",
         "text":"劳动合同用工是我国的企业基本用工形式。劳务派遣用工是补充形式，只能在临时性、辅助性或者替代性的工作岗位上实施。",
         "plain":"劳务派遣只能用于临时、辅助、替代性岗位。公司把你长期放在核心岗位当派遣工用=违法。",
         "scenes":["劳务派遣","岗位性质"],"priority":3},
        # 非全日制用工 (Section 3: Part-time)
        {"id":"labor-contract-68","law":"劳动合同法","article":"第六十八条",
         "text":"非全日制用工，是指以小时计酬为主，劳动者在同一用人单位一般平均每日工作时间不超过四小时，每周工作时间累计不超过二十四小时的用工形式。",
         "plain":"非全日制=每天不超过4小时、每周不超过24小时。超过这个时间就不能叫非全日制了。",
         "scenes":["非全日制"],"priority":2},
        {"id":"labor-contract-69","law":"劳动合同法","article":"第六十九条",
         "text":"非全日制用工双方当事人可以订立口头协议。从事非全日制用工的劳动者可以与一个或者一个以上用人单位订立劳动合同；但是，后订立的劳动合同不得影响先订立的劳动合同的履行。",
         "plain":"非全日制可以不签书面合同（口头协议就行），可以同时给多家公司打工。",
         "scenes":["非全日制"],"priority":2},
        {"id":"labor-contract-72","law":"劳动合同法","article":"第七十二条",
         "text":"非全日制用工劳动报酬结算支付周期最长不得超过十五日。",
         "plain":"非全日制工资支付周期不超过15天。超过15天不发→违法。",
         "scenes":["非全日制","工资支付"],"priority":2},
        # 监督检查
        {"id":"labor-contract-74","law":"劳动合同法","article":"第七十四条",
         "text":"县级以上地方人民政府劳动行政部门依法对下列实施劳动合同制度的情况进行监督检查：（一）用人单位制定直接涉及劳动者切身利益的规章制度及其执行的情况；（二）用人单位与劳动者订立和解除劳动合同的情况；（三）劳务派遣单位和用工单位遵守劳务派遣有关规定的情况；（四）用人单位遵守国家关于劳动者工作时间和休息休假规定的情况；（五）用人单位支付劳动合同约定的劳动报酬和执行最低工资标准的情况；（六）用人单位参加各项社会保险和缴纳社会保险费的情况。",
         "plain":"劳动监察大队管什么：规章制度是否合法、签合同/解除合同是否合法、劳务派遣是否合规、工时休假、工资是否按时发、社保是否缴纳。这六件事都可以向劳动监察大队投诉。",
         "scenes":["劳动监察","投诉"],"priority":4,
         "tactical":"遇到拖欠工资、不缴社保、违法加班——不用走仲裁，直接去劳动监察大队投诉，更快。电话：12333。"},
        # 法律责任 (关键：公司违法的后果)
        {"id":"labor-contract-80","law":"劳动合同法","article":"第八十条",
         "text":"用人单位直接涉及劳动者切身利益的规章制度违反法律、法规规定的，由劳动行政部门责令改正，给予警告；给劳动者造成损害的，应当承担赔偿责任。",
         "plain":"公司制度违法→劳动部门责令改正+警告+赔偿。比如违法的「末位淘汰制」就是典型。",
         "scenes":["违法制度","劳动监察"],"priority":3},
        {"id":"labor-contract-83","law":"劳动合同法","article":"第八十三条",
         "text":"用人单位违反本法规定与劳动者约定试用期的，由劳动行政部门责令改正；违法约定的试用期已经履行的，由用人单位以劳动者试用期满月工资为标准，按已经履行的超过法定试用期的期间向劳动者支付赔偿金。",
         "plain":"试用期超过法定上限的，超出部分按转正工资赔给你。比如法定试用期2个月，公司约定了6个月→多收的4个月试用期，每个月赔你转正工资差额+赔偿。",
         "formula":"超出天数 × 日工资",
         "scenes":["试用期","违法试用期"],"priority":4},
        {"id":"labor-contract-84","law":"劳动合同法","article":"第八十四条",
         "text":"用人单位违反本法规定，扣押劳动者居民身份证等证件的，由劳动行政部门责令限期退还劳动者本人，并依照有关法律规定给予处罚。用人单位违反本法规定，以担保或者其他名义向劳动者收取财物的，由劳动行政部门责令限期退还劳动者本人，并以每人五百元以上二千元以下的标准处以罚款；给劳动者造成损害的，应当承担赔偿责任。",
         "plain":"公司扣你身份证或收押金→劳动监察罚款500-2000元/人，还要赔偿你的损失。",
         "scenes":["押金","扣押证件"],"priority":3},
        {"id":"labor-contract-88","law":"劳动合同法","article":"第八十八条",
         "text":"用人单位有下列情形之一的，依法给予行政处罚；构成犯罪的，依法追究刑事责任；给劳动者造成损害的，应当承担赔偿责任：（一）以暴力、威胁或者非法限制人身自由的手段强迫劳动的；（二）违章指挥或者强令冒险作业危及劳动者人身安全的；（三）侮辱、体罚、殴打、非法搜查或者拘禁劳动者的；（四）劳动条件恶劣、环境污染严重，给劳动者身心健康造成严重损害的。",
         "plain":"公司有暴力、强迫劳动、侮辱殴打、环境恶劣致人损害=行政处罚+刑事追责+民事赔偿。",
         "scenes":["暴力强迫劳动","劳动安全"],"priority":2},
    ]


def main():
    # Load existing
    with open(LAWS_JSON) as f:
        data = json.load(f)

    existing_ids = {a["id"] for a in data["articles"]}

    # Parse labor law full text
    if LABOR_RAW.exists():
        with open(LABOR_RAW) as f:
            labor_raw = json.load(f)
        labor_articles = parse_labor_law_articles(labor_raw)
        for a in labor_articles:
            if a["id"] not in existing_ids:
                data["articles"].append(a)
                existing_ids.add(a["id"])
        print(f"劳动法: 新增 {sum(1 for a in labor_articles if a['id'] not in existing_ids)} / 总计 {len(labor_articles)} 条")
    else:
        print("劳动法 JSON 未找到，跳过")

    # Add remaining contract law articles
    contract_articles = build_contract_law_remaining()
    added = 0
    for a in contract_articles:
        if a["id"] not in existing_ids:
            data["articles"].append(a)
            existing_ids.add(a["id"])
            added += 1
    print(f"劳动合同法: 新增 {added} 条（劳务派遣/非全日制/法律责任）")

    # Update meta
    data["meta"]["total_articles"] = len(data["articles"])
    # Re-sort by id
    data["articles"].sort(key=lambda a: a["id"])

    with open(LAWS_JSON, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n法条总数: {len(data['articles'])}")
    by_law = {}
    for a in data["articles"]:
        by_law[a["law"]] = by_law.get(a["law"], 0) + 1
    for law, count in sorted(by_law.items(), key=lambda x: x[1], reverse=True):
        print(f"  {law}: {count} 条")


if __name__ == "__main__":
    main()
