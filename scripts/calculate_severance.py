#!/usr/bin/env python3
"""Soul Badman 赔偿金计算器 — 纯 Python 实现，零外部依赖。

用法：
    # 命令行模式
    python calculate_severance.py --years 3.67 --salary 18000 --type 2N
    python calculate_severance.py --years 5.5 --salary 25000 --type N+1 --unused-leave 5 --overtime-weekend 8
    python calculate_severance.py --help

    # Python 导入模式
    from calculate_severance import calculate, CompensationResult
    result = calculate(years=3.67, salary=18000, severance_type="2N")
    print(result.summary())
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CompensationResult:
    """赔偿计算结果"""
    years: float
    salary: float
    severance_type: str
    N: float = 0.0
    N_plus_1: float = 0.0
    double_N: float = 0.0
    severance_amount: float = 0.0
    unused_leave_amount: float = 0.0
    overtime_workday_amount: float = 0.0
    overtime_weekend_amount: float = 0.0
    overtime_holiday_amount: float = 0.0
    double_salary_amount: float = 0.0
    bonus_amount: float = 0.0
    other_notes: list = field(default_factory=list)

    def total(self) -> float:
        return (
            self.severance_amount
            + self.unused_leave_amount
            + self.overtime_workday_amount
            + self.overtime_weekend_amount
            + self.overtime_holiday_amount
            + self.double_salary_amount
            + self.bonus_amount
        )

    def summary(self) -> str:
        lines = [
            "═══════════════════════════════════",
            " Soul Badman 赔偿金计算结果",
            "═══════════════════════════════════",
            f" 工作年限: {self.years:.2f} 年 (计算基数 {self._effective_years_str()})",
            f" 月均工资: {self.salary:,.0f} 元",
            f" 解除类型: {self.severance_type}",
            "",
            f" N       = {self.N:,.0f} 元",
        ]
        if self.N_plus_1 > 0:
            lines.append(f" N+1     = {self.N_plus_1:,.0f} 元")
        if self.double_N > 0:
            lines.append(f" 2N      = {self.double_N:,.0f} 元")
        lines.append(f" → 赔偿金   = {self.severance_amount:,.0f} 元")
        if self.unused_leave_amount > 0:
            lines.append(f" → 年假折算 = {self.unused_leave_amount:,.0f} 元")
        if self.overtime_workday_amount > 0:
            lines.append(f" → 平日加班 = {self.overtime_workday_amount:,.0f} 元")
        if self.overtime_weekend_amount > 0:
            lines.append(f" → 周末加班 = {self.overtime_weekend_amount:,.0f} 元")
        if self.overtime_holiday_amount > 0:
            lines.append(f" → 假日加班 = {self.overtime_holiday_amount:,.0f} 元")
        if self.double_salary_amount > 0:
            lines.append(f" → 双倍工资 = {self.double_salary_amount:,.0f} 元")
        if self.bonus_amount > 0:
            lines.append(f" → 年终奖金 = {self.bonus_amount:,.0f} 元")
        total = self.total()
        lines.append("")
        lines.append(f" 合计可主张: {total:,.0f} 元")
        if self.other_notes:
            lines.append("")
            lines.append(" 注意事项:")
            for note in self.other_notes:
                lines.append(f"   ⚠ {note}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "years": self.years,
            "salary": self.salary,
            "severance_type": self.severance_type,
            "N": self.N,
            "N_plus_1": self.N_plus_1,
            "double_N": self.double_N,
            "severance_amount": self.severance_amount,
            "unused_leave_amount": self.unused_leave_amount,
            "overtime_workday_amount": self.overtime_workday_amount,
            "overtime_weekend_amount": self.overtime_weekend_amount,
            "overtime_holiday_amount": self.overtime_holiday_amount,
            "double_salary_amount": self.double_salary_amount,
            "bonus_amount": self.bonus_amount,
            "total": self.total(),
            "other_notes": self.other_notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def _calc_years(self) -> float:
        """按劳动合同法第47条计算有效年限：满半年按1年，不满按0.5"""
        full_years = int(self.years)
        remainder = self.years - full_years
        if remainder >= 0.5:
            return full_years + 1.0
        elif remainder > 0:
            return full_years + 0.5
        return float(full_years)

    def _effective_years_str(self) -> str:
        """显示计算年限，不四舍五入误导"""
        ey = self._calc_years()
        if ey == int(ey):
            return str(int(ey))
        return str(ey)


def calculate(
    years: float,
    salary: float,
    severance_type: str = "N",
    *,
    unused_leave_days: float = 0.0,
    overtime_workday_hours: float = 0.0,
    overtime_weekend_days: float = 0.0,
    overtime_holiday_days: float = 0.0,
    double_salary_months: float = 0.0,
    bonus_ratio: Optional[float] = None,
    months_worked_this_year: int = 0,
    salary_cap: Optional[float] = None,
    cap_mode: str = "statutory",
) -> CompensationResult:
    """计算赔偿金。

    参数:
        years: 工作年限（如 3.67 = 3年8个月）
        salary: 离职前12个月平均税前月工资
        severance_type: 解除类型 — "N" | "N+1" | "2N" | "0"
        unused_leave_days: 未休年假天数
        overtime_workday_hours: 工作日加班小时数
        overtime_weekend_days: 周末加班天数（不补休的）
        overtime_holiday_days: 法定节假日加班天数
        double_salary_months: 未签合同可主张双倍工资的月数（最多11）
        bonus_ratio: 年终奖比例（如 0.75 = 今年工作了9个月，主张75%）
        months_worked_this_year: 今年已工作月数（用于计算年终奖比例）
        salary_cap: 社平工资3倍封顶值（如有）
        cap_mode: 2N封顶争议口径 — "statutory"(保守,仅第47条) "claim"(争取,第25条不封顶) "both"(双口径)
    """
    result = CompensationResult(years=years, salary=salary, severance_type=severance_type)

    # 有效年限
    effective_years = result._calc_years()

    # 计算基数（考虑封顶）
    calc_salary = salary
    if salary_cap is not None and salary > salary_cap:
        calc_salary = salary_cap
        result.other_notes.append(f"月工资超过社平3倍({salary_cap:,.0f})，按{salary_cap:,.0f}计算")

    # 日工资和小时工资
    daily_rate = calc_salary / 21.75
    hourly_rate = daily_rate / 8

    # N
    result.N = effective_years * calc_salary
    result.N_plus_1 = result.N + calc_salary
    result.double_N = result.N * 2

    # 2N 双口径（高收入+长年限场景）
    st = severance_type.upper().replace(" ", "")
    if cap_mode in ("both", "claim") and st == "2N" and salary_cap is not None:
        # 争取口径：2N 年限不受第47条12年封顶（依据实施条例第25条）
        claim_2n = effective_years * salary * 2
        if cap_mode == "both":
            result.other_notes.append(
                f"2N 双口径 — 保守(第47条封顶): {result.double_N:,.0f}元 | "
                f"争取(第25条不封顶): {claim_2n:,.0f}元。各地裁判口径存在差异，建议咨询当地律师"
            )
        else:
            result.double_N = claim_2n
            result.severance_amount = claim_2n

    # 主赔偿
    st = severance_type.upper().replace(" ", "")
    if st == "N":
        result.severance_amount = result.N
    elif st == "N+1":
        result.severance_amount = result.N_plus_1
    elif st == "2N":
        result.severance_amount = result.double_N
    elif st == "0":
        result.severance_amount = 0.0
        result.other_notes.append("主动辞职或过失性解除，无经济补偿")
    else:
        raise ValueError(f"未知解除类型: {severance_type}，可选: N, N+1, 2N, 0")

    # 未休年假（300%）
    if unused_leave_days > 0:
        result.unused_leave_amount = unused_leave_days * daily_rate * 3

    # 加班费
    if overtime_workday_hours > 0:
        result.overtime_workday_amount = overtime_workday_hours * hourly_rate * 1.5
    if overtime_weekend_days > 0:
        result.overtime_weekend_amount = overtime_weekend_days * daily_rate * 2
    if overtime_holiday_days > 0:
        result.overtime_holiday_amount = overtime_holiday_days * daily_rate * 3

    # 未签合同双倍工资
    if double_salary_months > 0:
        capped_months = min(double_salary_months, 11)
        result.double_salary_amount = capped_months * calc_salary
        if double_salary_months > 11:
            result.other_notes.append("双倍工资法定上限11个月，已按11个月计算")

    # 年终奖
    if bonus_ratio is not None and bonus_ratio > 0:
        result.bonus_amount = calc_salary * bonus_ratio
    elif months_worked_this_year > 0 and months_worked_this_year < 12:
        # 默认按已工作月数/12主张
        result.bonus_amount = calc_salary * (months_worked_this_year / 12)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Soul Badman 赔偿金计算器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --years 3.67 --salary 18000 --type 2N
  %(prog)s --years 5.5 --salary 25000 --type N+1 --unused-leave 5 --overtime-weekend 8
  %(prog)s --years 2 --salary 12000 --type N --double-salary 3 --months-worked 8
        """,
    )
    parser.add_argument("--years", type=float, required=True, help="工作年限（如 3.67 = 3年8个月）")
    parser.add_argument("--salary", type=float, required=True, help="离职前12个月平均月工资（税前）")
    parser.add_argument("--type", dest="severance_type", default="N", help="解除类型: N, N+1, 2N, 0 (默认: N)")
    parser.add_argument("--unused-leave", type=float, default=0, help="未休年假天数")
    parser.add_argument("--overtime-workday", type=float, default=0, help="工作日加班小时数")
    parser.add_argument("--overtime-weekend", type=float, default=0, help="周末加班天数")
    parser.add_argument("--overtime-holiday", type=float, default=0, help="法定节假日加班天数")
    parser.add_argument("--double-salary", type=float, default=0, help="未签合同的月数（最多11个月）")
    parser.add_argument("--bonus-ratio", type=float, default=None, help="年终奖比例 (0.75 = 主张75%%)")
    parser.add_argument("--months-worked", type=int, default=0, help="今年已工作月数（用于年终奖比例）")
    parser.add_argument("--salary-cap", type=float, default=None, help="社平工资3倍封顶值")
    parser.add_argument("--cap-mode", type=str, default="statutory",
                        choices=["statutory", "claim", "both"],
                        help="2N封顶口径: statutory(保守) claim(争取) both(双口径)")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    args = parser.parse_args()

    try:
        result = calculate(
            years=args.years,
            salary=args.salary,
            severance_type=args.severance_type,
            unused_leave_days=args.unused_leave,
            overtime_workday_hours=args.overtime_workday,
            overtime_weekend_days=args.overtime_weekend,
            overtime_holiday_days=args.overtime_holiday,
            double_salary_months=args.double_salary,
            bonus_ratio=args.bonus_ratio,
            months_worked_this_year=args.months_worked,
            salary_cap=args.salary_cap,
            cap_mode=args.cap_mode,
        )
        if args.json:
            print(result.to_json())
        else:
            print(result.summary())
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
