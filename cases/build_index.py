#!/usr/bin/env python3
"""Soul Badman 判例 RAG 索引构建

从 cases/curated/ 目录读取精选判例 markdown 文件，
构建 ChromaDB 向量索引，供 Soul Badman 语义检索。

用法：
    python build_index.py                  # 构建索引
    python build_index.py --query "35岁被裁 违法解除"   # 测试检索
    python build_index.py --reset          # 重建索引

依赖：
    pip install chromadb
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

CASES_DIR = Path(__file__).parent.parent / "cases"
CURATED_DIR = CASES_DIR / "curated"
INDEX_DIR = CASES_DIR / "chromadb_index"


def parse_case_markdown(filepath: Path) -> Optional[dict]:
    """解析判例 markdown 文件，提取结构化字段。"""
    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception:
        return None

    case = {
        "file": str(filepath.name),
        "id": hashlib.md5(str(filepath).encode()).hexdigest()[:12],
        "case_number": "",
        "location": "",
        "court": "",
        "judgment_date": "",
        "verdict": "",
        "summary": "",
        "reasoning": "",
        "compensation": "",
        "keywords": [],
        "full_text": text,
    }

    # 案号
    m = re.search(r"案号[：:]\s*(.+?)($|\n)", text)
    if m:
        case["case_number"] = m.group(1).strip()

    # 地点
    m = re.search(r"地\s*点[：:]\s*(.+?)($|\n)", text)
    if m:
        case["location"] = m.group(1).strip()

    # 法院
    m = re.search(r"审理法院[：:]\s*(.+?)($|\n)", text)
    if m:
        case["court"] = m.group(1).strip()

    # 判决时间
    m = re.search(r"判决时间[：:]\s*(.+?)($|\n)", text)
    if m:
        case["judgment_date"] = m.group(1).strip()

    # 判决结果
    m = re.search(r"判决结果[：:]\s*(.+?)($|\n)", text)
    if m:
        case["verdict"] = m.group(1).strip()

    # 案情摘要
    m = re.search(r"##\s*案情摘要\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if m:
        case["summary"] = m.group(1).strip()

    # 法院认定
    m = re.search(r"##\s*法院认定\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if m:
        case["reasoning"] = m.group(1).strip()

    # 赔偿计算
    m = re.search(r"##\s*赔偿(计算)?\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if m:
        case["compensation"] = m.group(2).strip()

    # 关键词（支持两种格式：关键词：a,b,c  或  ## 关键词\n  a, b, c）
    m = re.search(r"关键词[：:]\s*(.+?)($|\n)", text)
    if not m:
        # 尝试 ## 关键词 格式（下一行才是关键词列表）
        m = re.search(r"##\s*关键词\s*\n\s*(.+?)(?:\n\n|\n##|\Z)", text, re.DOTALL)
    if m:
        case["keywords"] = [k.strip() for k in m.group(1).split(",") if k.strip()]

    # 搜索文本：关键词 + 摘要 + 法院认定
    case["search_text"] = (
        " ".join(case["keywords"])
        + " "
        + case["summary"]
        + " "
        + case["reasoning"]
    )

    return case


def build_index(reset: bool = False):
    """构建 ChromaDB 索引。"""
    try:
        import chromadb
    except ImportError:
        print("请先安装 chromadb: pip install chromadb", file=sys.stderr)
        sys.exit(1)

    if not CURATED_DIR.exists():
        print(f"判例目录不存在: {CURATED_DIR}", file=sys.stderr)
        print("请将精选判例 markdown 文件放入该目录后重试。")
        sys.exit(1)

    case_files = [f for f in sorted(CURATED_DIR.glob("*.md")) if not f.name.startswith("_")]
    if not case_files:
        print(f"{CURATED_DIR} 中没有判例文件。", file=sys.stderr)
        print("判例文件格式示例见 cases/curated/_TEMPLATE.md")
        sys.exit(1)

    # 解析所有判例
    cases = []
    for fp in case_files:
        case = parse_case_markdown(fp)
        if case:
            cases.append(case)
        else:
            print(f"警告: 无法解析 {fp.name}")

    if not cases:
        print("没有成功解析的判例。", file=sys.stderr)
        sys.exit(1)

    print(f"解析了 {len(cases)} 个判例")

    # 初始化 ChromaDB（本地持久化）
    if reset and INDEX_DIR.exists():
        import shutil
        shutil.rmtree(INDEX_DIR)
        print("已清除旧索引")

    client = chromadb.PersistentClient(path=str(INDEX_DIR))

    collection_name = "labor_cases"
    try:
        collection = client.get_collection(collection_name)
        if reset:
            client.delete_collection(collection_name)
            collection = client.create_collection(collection_name)
            print("已重建索引")
        else:
            print(f"索引已存在 ({collection.count()} 条记录)，将追加新判例")
    except Exception:
        collection = client.create_collection(collection_name)
        print("创建新索引")

    # 检查已存在的 IDs，跳过重复
    existing_ids = set()
    try:
        existing = collection.get()
        existing_ids = set(existing["ids"])
    except Exception:
        pass

    # 添加判例
    new_count = 0
    for case in cases:
        if case["id"] in existing_ids:
            continue
        collection.add(
            ids=[case["id"]],
            documents=[case["search_text"]],
            metadatas=[{
                "case_number": case["case_number"],
                "location": case["location"],
                "court": case["court"],
                "verdict": case["verdict"],
                "keywords": ", ".join(case["keywords"]),
                "file": case["file"],
            }],
        )
        new_count += 1

    print(f"索引完成: 新增 {new_count} 条，总计 {collection.count()} 条")


def query_index(query_text: str, n_results: int = 3):
    """测试检索。"""
    try:
        import chromadb
    except ImportError:
        print("请先安装 chromadb: pip install chromadb", file=sys.stderr)
        sys.exit(1)

    if not INDEX_DIR.exists():
        print("索引不存在，请先运行 python build_index.py", file=sys.stderr)
        sys.exit(1)

    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    try:
        collection = client.get_collection("labor_cases")
    except Exception:
        print("索引集合不存在", file=sys.stderr)
        sys.exit(1)

    results = collection.query(query_texts=[query_text], n_results=n_results)

    print(f"查询: {query_text}\n")
    for i, (doc_id, metadata, distance) in enumerate(zip(
        results["ids"][0],
        results["metadatas"][0],
        results["distances"][0],
    )):
        print(f"#{i+1} (相似度: {1-distance:.2f})")
        print(f"  案号: {metadata.get('case_number', 'N/A')}")
        print(f"  法院: {metadata.get('court', 'N/A')}")
        print(f"  结果: {metadata.get('verdict', 'N/A')}")
        print(f"  关键词: {metadata.get('keywords', '')}")
        print(f"  文件: {metadata.get('file', '')}")
        print()


def create_template():
    """创建判例模板文件。"""
    template = """# 案号：(YYYY)XX0XXX民初XXXX号

## 基本信息
- 地点：XX省XX市
- 判决时间：YYYY-MM-DD
- 审理法院：XX人民法院
- 判决结果：（如：认定违法解除，判赔2N）

## 案情摘要
（300-500字：简述当事人情况、入职时间、岗位、
公司以什么理由辞退、劳动者主张什么）

## 法院认定
（简述法院的核心判断：为什么认定违法/合法，
引用了哪些法律条款）

## 赔偿计算
- 工作年限：X 年
- 月均工资：XX 元
- 判决赔偿：XX 元
- 计算方式：2N = 2 × X × XX = XX 元

## 关键词
违法解除, 2N, 末位淘汰, 互联网, 35岁

## 来源
（裁判文书网链接或其他来源）
"""
    template_path = CURATED_DIR / "_TEMPLATE.md"
    if not template_path.exists():
        CURATED_DIR.mkdir(parents=True, exist_ok=True)
        template_path.write_text(template, encoding="utf-8")
        print(f"已创建判例模板: {template_path}")
    else:
        print(f"模板已存在: {template_path}")


def main():
    parser = argparse.ArgumentParser(description="Soul Badman 判例索引构建")
    parser.add_argument("--reset", action="store_true", help="重建索引")
    parser.add_argument("--query", type=str, default=None, help="测试检索查询词")
    parser.add_argument("--template", action="store_true", help="创建判例模板文件")
    args = parser.parse_args()

    if args.template:
        create_template()
    elif args.query:
        query_index(args.query)
    else:
        build_index(reset=args.reset)


if __name__ == "__main__":
    main()
