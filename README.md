# Soul Badman

> In legal trouble? Better call Soul.
>
> 一个专为打工人设计的劳动维权 AI Skill。不做法条词典，做你的赛博维权军师。

## 这是什么

Soul Badman 是一套**可独立使用也可挂载到 AI Agent 的劳动维权知识系统**。它包含三大组件：

| 组件 | 内容 | 独立可用？ |
|------|------|-----------|
| 🧠 **SKILL.md** | AI Agent 的 Persona + 反击五步法（挂载后自动生效） | Hermes/Claude 等 Agent 加载即用 |
| ⚖️ **法条库** (laws.json) | 159 条劳动法律条款，结构化（原文 + 大白话 + 场景标签 + 权重） | ✅ `python scripts/laws_lookup.py --scene 违法解除` |
| 💰 **赔偿计算器** | N / N+1 / 2N + 年假 + 加班费 + 双倍工资 | ✅ `python scripts/calculate_severance.py --years 3.67 --salary 18000 --type 2N` |
| 📋 **证据指南** | P0/P1/P2 分级操作指南（傻瓜式："打开钉钉→点这里→截图"） | ✅ 照着操作就行 |
| 🕵️ **HR话术解码** | 10 种 HR 话术 → 法律含义 → 反击剧本 | ✅ 对号入座 |
| ⚡ **判例 RAG** | ChromaDB 向量索引，9 个判例（5 胜 + 4 败，含避雷点） | ✅ `python cases/build_index.py --query "35岁被优化"` |

## 快速开始

### 用法一：作为 AI Agent Skill（推荐）

将 `SKILL.md` 注册到你的 AI Agent（Hermes / Claude / Dify 等），让 Agent 自动变身 Soul Badman。

对话示例：
```
用户: 我被公司裁员了，HR 让我签协议
Agent: 伙计，稳住。先说最重要的——你签字了吗？没签？干得漂亮。
      现在听我的：第一，不准在任何文件上签名……
```

## Installation

```bash
git clone https://github.com/White-Wolf-233/SoulBadman.git
cd SoulBadman
pip install -r requirements.txt
```

核心工具（laws_lookup / calculate_severance / media_miner / store）均为纯 Python 标准库，无需额外依赖。仅判例 RAG 需要 chromadb。

## 项目结构

```
SoulBadman/
├── SKILL.md                      # AI Agent 挂载入口
├── README.md                     # 本文件
├── references/
│   ├── laws.json                 # 结构化法条库（核心）
│   ├── compensation-guide.md     # 赔偿全项计算指南
│   ├── evidence-checklist.md     # 证据收集傻瓜式指引
│   └── hr-trap-decoder.md        # HR 话术解码表
├── scripts/
│   ├── laws_lookup.py            # 法条检索工具
│   ├── calculate_severance.py    # 赔偿金计算器
│   ├── media_miner.py            # 公开媒体判例搜索
│   └── wenshu_miner.py           # 裁判文书采集（备用）
├── cases/
│   ├── build_index.py            # ChromaDB 判例索引构建
│   ├── curated/                  # 精校判例（人工核验后）
│   │   ├── 01_最高法指导案例18号_末位淘汰.md
│   │   ├── 02_杭州AI替岗案_35岁被优化.md
│   │   ├── ...                   # 9个判例（5胜+4败）
│   │   └── _TEMPLATE.md          # 判例模板
│   └── raw_media/                # 媒体采集判例（待核验，不入索引）
│   └── chromadb_index/           # 向量索引（运行时生成）
└── data/
    └── store.py                  # SQLite 咨询记录持久化存储
```

## 法条覆盖

| 法律 | 条款数 | 覆盖场景 |
|------|--------|---------|
| 劳动法 | 100 条（全文） | 工时、休息、工资、女职工、未成年工、社保、劳动争议、法律责任 |
| 劳动合同法 | 44 条 | 签订、试用期、竞业、违约金、解除、终止、赔偿、双倍工资、劳务派遣、非全日制、法律责任 |
| 劳动合同法实施条例 | 5 条 | 工作年限合并、代通知金计算、退休终止、2N 年限、工资基数 |
| 工伤保险条例 | 3 条 | 工伤认定、视同工伤、申请时效 |
| 劳动争议调解仲裁法 | 2 条 | 仲裁时效、审理期限 |
| 职工带薪年休假条例 | 2 条 | 年假天数、未休折算 |
| 女职工劳动保护特别规定 | 2 条 | 不得辞退、产假 |
| 最高法司法解释 | 1 条 | 举证责任倒置 |
| **总计** | **159 条** | |

## 设计原则

1. **默认用户是法律小白**：不说"依据第48条"，说"公司违法开除你，要赔双倍的钱"
2. **最大化赔偿收益**：不只算 N+1，逐项核查年假/加班费/双倍工资/年终奖/社保
3. **操作级指引**：不说"收集证据"，说"打开钉钉→考勤打卡→截图"
4. **胜败皆收录**：判例覆盖胜诉和败诉，标注避雷点
5. **法条精准**：每一条都有人工校对来源，禁止编造

## 免责声明

⚠️ Soul Badman 提供的建议仅供参考，不构成正式法律意见。
涉及劳动仲裁或诉讼，建议咨询专业劳动法律师。
全国免费法律援助热线：**12348**。

## 灵感来源

- 捏他《风骚律师》索尔·古德曼 (Saul Goodman)
- 致敬 996.ICU 打工人维权精神
- "给自己增援未来"——针对互联网行业 35 岁危机

## License

MIT
