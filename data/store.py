#!/usr/bin/env python3
"""Soul Badman 咨询服务数据持久化存储

SQLite 数据库，记录每次咨询的完整上下文：
- 用户描述、收集的变量、赔偿计算结果、给出的建议
- 支持查询、统计、导出

用法:
    from data.store import Store
    store = Store()
    store.save_consultation(user_input, variables, result, advice)
    history = store.get_history(limit=10)

纯 Python，零依赖（sqlite3 内置）。
"""

import json
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "consultations.db"


@dataclass
class Consultation:
    """一条咨询记录"""
    id: Optional[int] = None
    timestamp: str = ""
    user_input: str = ""           # 用户原始描述
    hire_date: str = ""            # 入职日期
    avg_salary: float = 0.0        # 月均工资
    hr_reason: str = ""            # HR 给出的理由
    has_signed: bool = False       # 是否已签字
    contract_type: str = ""        # 合同类型
    case_type: str = ""            # 定性结果（违法解除/协商解除/经济性裁员...）
    compensation_formula: str = "" # 赔偿公式（N/N+1/2N）
    compensation_amount: float = 0.0  # 计算出的总金额
    breakdown: str = ""            # 各项赔偿明细（JSON）
    advice_summary: str = ""       # 建议摘要
    status: str = "active"         # active/resolved/expired
    tags: str = ""                 # 逗号分隔的标签
    evidence_checked: str = ""     # 已收集的证据清单（JSON）
    notes: str = ""                # 备注


class Store:
    """咨询服务持久化存储"""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self):
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS consultations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_input TEXT,
                    hire_date TEXT,
                    avg_salary REAL DEFAULT 0,
                    hr_reason TEXT,
                    has_signed INTEGER DEFAULT 0,
                    contract_type TEXT,
                    case_type TEXT,
                    compensation_formula TEXT,
                    compensation_amount REAL DEFAULT 0,
                    breakdown TEXT,
                    advice_summary TEXT,
                    status TEXT DEFAULT 'active',
                    tags TEXT,
                    evidence_checked TEXT,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS case_stats (
                    case_type TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    avg_amount REAL DEFAULT 0,
                    last_seen TEXT
                )
            """)
            conn.commit()

    # ── CRUD ─────────────────────────────────────────

    def save(self, c: Consultation) -> int:
        """保存一条咨询记录，返回 ID。"""
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO consultations
                (timestamp, user_input, hire_date, avg_salary, hr_reason,
                 has_signed, contract_type, case_type, compensation_formula,
                 compensation_amount, breakdown, advice_summary,
                 status, tags, evidence_checked, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                c.timestamp or datetime.now().isoformat(),
                c.user_input,
                c.hire_date,
                c.avg_salary,
                c.hr_reason,
                1 if c.has_signed else 0,
                c.contract_type,
                c.case_type,
                c.compensation_formula,
                c.compensation_amount,
                c.breakdown,
                c.advice_summary,
                c.status or "active",
                c.tags,
                c.evidence_checked,
                c.notes,
            ))
            conn.commit()
            return cur.lastrowid

    def update(self, case_id: int, **kwargs):
        """更新咨询记录。"""
        allowed = {
            "status", "advice_summary", "compensation_amount",
            "breakdown", "evidence_checked", "notes", "tags",
            "case_type", "compensation_formula"
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [case_id]

        with self._conn() as conn:
            conn.execute(
                f"UPDATE consultations SET {set_clause} WHERE id=?",
                values
            )
            conn.commit()

    def get(self, case_id: int) -> Optional[Consultation]:
        """获取单条记录。"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM consultations WHERE id=?", (case_id,)
            ).fetchone()
        return self._row_to_consultation(row) if row else None

    def get_history(self, limit: int = 20, status: str = None) -> list[Consultation]:
        """获取最近记录。"""
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM consultations WHERE status=? ORDER BY id DESC LIMIT ?",
                    (status, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM consultations ORDER BY id DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        return [self._row_to_consultation(r) for r in rows]

    def search(self, keyword: str, limit: int = 20) -> list[Consultation]:
        """全文搜索。"""
        with self._conn() as conn:
            q = f"%{keyword}%"
            rows = conn.execute("""
                SELECT * FROM consultations
                WHERE user_input LIKE ? OR hr_reason LIKE ? OR advice_summary LIKE ? OR tags LIKE ?
                ORDER BY id DESC LIMIT ?
            """, (q, q, q, q, limit)).fetchall()
        return [self._row_to_consultation(r) for r in rows]

    # ── 统计 ─────────────────────────────────────────

    def stats(self) -> dict:
        """统计概览。"""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM consultations").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM consultations WHERE status='active'"
            ).fetchone()[0]

            by_type = conn.execute("""
                SELECT case_type, COUNT(*), AVG(compensation_amount)
                FROM consultations WHERE case_type != ''
                GROUP BY case_type ORDER BY COUNT(*) DESC
            """).fetchall()

            total_amount = conn.execute(
                "SELECT SUM(compensation_amount) FROM consultations"
            ).fetchone()[0] or 0

        return {
            "total_consultations": total,
            "active_cases": active,
            "total_claimed": total_amount,
            "by_type": [
                {"type": t, "count": c, "avg_amount": round(a or 0, 2)}
                for t, c, a in by_type
            ],
        }

    def stats_summary(self) -> str:
        """人类可读的统计摘要。"""
        s = self.stats()
        lines = [
            f"总咨询: {s['total_consultations']} 次",
            f"进行中: {s['active_cases']} 件",
            f"累计主张金额: {s['total_claimed']:,.0f} 元",
            "",
            "按类型分布:",
        ]
        for item in s["by_type"]:
            lines.append(
                f"  {item['type']}: {item['count']}件 "
                f"(平均 {item['avg_amount']:,.0f}元)"
            )
        return "\n".join(lines)

    # ── 导出 ─────────────────────────────────────────

    def export_json(self, output_path: Path = None) -> Path:
        """导出全部记录为 JSON。"""
        output_path = output_path or (self.db_path.parent / "export.json")
        records = self.get_history(limit=9999)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                [asdict(r) for r in records],
                f, ensure_ascii=False, indent=2, default=str
            )
        return output_path

    # ── 内部 ─────────────────────────────────────────

    def _row_to_consultation(self, row: tuple) -> Consultation:
        cols = [
            "id", "timestamp", "user_input", "hire_date", "avg_salary",
            "hr_reason", "has_signed", "contract_type", "case_type",
            "compensation_formula", "compensation_amount", "breakdown",
            "advice_summary", "status", "tags", "evidence_checked", "notes"
        ]
        d = dict(zip(cols, row))
        if d.get("has_signed"):
            d["has_signed"] = bool(d["has_signed"])
        return Consultation(**d)


# ─── CLI ──────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Soul Badman 咨询存储")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("stats", help="统计概览")
    sub.add_parser("export", help="导出全部记录为 JSON")

    list_p = sub.add_parser("list", help="列出最近记录")
    list_p.add_argument("--limit", "-n", type=int, default=10)
    list_p.add_argument("--status", type=str, default=None)

    search_p = sub.add_parser("search", help="搜索记录")
    search_p.add_argument("keyword", type=str)
    search_p.add_argument("--limit", "-n", type=int, default=10)

    get_p = sub.add_parser("get", help="查看单条记录")
    get_p.add_argument("id", type=int)

    args = parser.parse_args()
    store = Store()

    if args.cmd == "stats":
        print(store.stats_summary())
    elif args.cmd == "list":
        for c in store.get_history(limit=args.limit, status=args.status):
            print(f"[{c.id}] {c.timestamp[:10]} | {c.case_type or '未定性'} | "
                  f"{c.compensation_amount:,.0f}元 | {c.status}")
    elif args.cmd == "search":
        for c in store.search(args.keyword, limit=args.limit):
            print(f"[{c.id}] {c.timestamp[:10]} | {c.case_type} | "
                  f"{c.compensation_amount:,.0f}元")
            print(f"  {c.user_input[:100]}")
    elif args.cmd == "get":
        c = store.get(args.id)
        if c:
            print(f"ID: {c.id} | {c.timestamp}")
            print(f"状态: {c.status}")
            print(f"用户描述: {c.user_input}")
            print(f"工资: {c.avg_salary} | 入职: {c.hire_date}")
            print(f"HR理由: {c.hr_reason}")
            print(f"定性: {c.case_type} | 公式: {c.compensation_formula}")
            print(f"金额: {c.compensation_amount:,.0f}元")
            print(f"建议: {c.advice_summary}")
        else:
            print(f"记录 {args.id} 不存在")
    elif args.cmd == "export":
        path = store.export_json()
        print(f"已导出: {path} ({path.stat().st_size} bytes)")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
