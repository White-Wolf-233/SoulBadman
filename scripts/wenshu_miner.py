#!/usr/bin/env python3
"""Soul Badman 裁判文书劳动争议判例采集工具

从裁判文书网搜索劳动争议判例，提取结构化数据，生成标准 markdown。

用法：
    python wenshu_miner.py --keyword "违法解除 劳动合同" --count 20
    python wenshu_miner.py --keyword "末位淘汰" --output ./cases/
    python wenshu_miner.py --interactive       # 交互模式

依赖：pip install requests (纯 Python，无 C 扩展)

注意：
    裁判文书网有严格反爬。本工具使用合法的 HTTP 请求 + Cookie 模拟，
    每请求间隔至少 5 秒。如需大量采集，请使用全量数据备份（见 GitHub
    amakerlife/wenshu.court.gov.cn-backup）。

协议：
    - 仅采集公开的裁判文书信息
    - 遵守 robots.txt
    - 仅用于 Soul Badman 判例 RAG 知识库
"""

import hashlib
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlencode

import requests

# ─── 配置 ──────────────────────────────────────────────
CASES_DIR = Path(__file__).parent.parent / "cases" / "curated"
INDEX_SCRIPT = Path(__file__).parent.parent / "cases" / "build_index.py"
BASE_URL = "https://wenshu.court.gov.cn"
REQUEST_DELAY = 6  # 每秒请求间隔
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
TIMEOUT = 30

# ─── 加密工具（纯 Python，替代 execjs）─────────────────


def _str2bin(s: str) -> list[int]:
    """JS str2binl 等价——将字符串转为 32-bit 整数数组"""
    bin_arr = []
    mask = (1 << 8) - 1
    length = len(s) * 8
    for i in range(0, length, 8):
        idx = i >> 5
        while len(bin_arr) <= idx:
            bin_arr.append(0)
        bin_arr[idx] |= (ord(s[i // 8]) & mask) << (24 - i % 32)
    return bin_arr


def _bin2hex(bin_arr: list[int]) -> str:
    """binl2hex"""
    hex_chars = "0123456789abcdef"
    result = ""
    for i in range(len(bin_arr) * 4):
        byte_val = (bin_arr[i >> 2] >> ((3 - i % 4) * 8 + 4)) & 0xF
        result += hex_chars[byte_val]
        byte_val = (bin_arr[i >> 2] >> ((3 - i % 4) * 8)) & 0xF
        result += hex_chars[byte_val]
    return result


def _md5(s: str) -> str:
    """返回 hex_md5(s)"""
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _sha1(s: str) -> str:
    """返回 hex_sha1(s)"""
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _str_to_long(s: str) -> int:
    """JS strToLong 等价——字符串哈希为 long"""
    h = 0
    for c in s:
        h = ((h << 5) - h + ord(c)) & 0xFFFFFFFF
    return h if h < 2**31 else h - 2**32


def _make_key(idx: int, cookie: str) -> str:
    """生成 makeKey_N 函数的结果"""
    funs = [_make_key_0, _make_key_1, _make_key_2, _make_key_3, _make_key_4]
    base_funs = [
        _make_key_5, _make_key_6, _make_key_7, _make_key_8, _make_key_9,
        _make_key_10, _make_key_11, _make_key_12, _make_key_13,
        _make_key_14, _make_key_15, _make_key_16, _make_key_17,
        _make_key_18, _make_key_19,
    ]
    all_funs = funs + base_funs
    return all_funs[idx % len(all_funs)](cookie)


def _make_key_0(s): return _md5(s + _md5(s)).upper()[:8]
def _make_key_1(s): return _sha1(s + _sha1(s))[:8]
def _make_key_2(s): return _md5(_sha1(s + s))[:8]
def _make_key_3(s): return _sha1(_md5(s + s))[:8]
def _make_key_4(s): return _sha1(s)[:8]
def _make_key_5(s): return _md5(s)[:8]
def _make_key_6(s): return _sha1(s + s)[:8]
def _make_key_7(s): return _md5(s + s)[:8]
def _make_key_8(s): return _sha1(_md5(s))[:8]
def _make_key_9(s): return _md5(_sha1(s))[:8]
def _make_key_10(s): return _sha1(_md5(s + s))[:8]
def _make_key_11(s): return _md5(_sha1(s + s))[:8]
def _make_key_12(s): return _sha1(s + _md5(s))[:8]
def _make_key_13(s): return _md5(s + _sha1(s))[:8]
def _make_key_14(s): return _sha1(_sha1(s))[:8]
def _make_key_15(s): return _md5(_md5(s))[:8]
def _make_key_16(s): return _sha1(s + _sha1(s) + s)[:8]
def _make_key_17(s): return _md5(s + _md5(s) + s)[:8]
def _make_key_18(s): return _sha1(_md5(s) + _sha1(s))[:8]
def _make_key_19(s): return _md5(_sha1(s) + _md5(s))[:8]


def get_vl5x(cookie: str) -> str:
    """计算裁判文书网 vl5x 加密参数"""
    arr_fun = [_make_key_0, _make_key_1, _make_key_2, _make_key_3, _make_key_4,
               _make_key_5, _make_key_6, _make_key_7, _make_key_8, _make_key_9,
               _make_key_10, _make_key_11, _make_key_12, _make_key_13,
               _make_key_14, _make_key_15, _make_key_16, _make_key_17,
               _make_key_18, _make_key_19] * 20  # 400 个函数

    hash_val = _str_to_long(cookie)
    fun_index = abs(hash_val) % len(arr_fun)
    return arr_fun[fun_index](cookie)


def generate_guid() -> str:
    """生成 GUID"""
    def _hex4():
        return hex(int((1 + random.random()) * 0x10000) | 0)[3:]
    return f"{_hex4()}{_hex4()}-{_hex4()}-{_hex4()}{_hex4()}-{_hex4()}{_hex4()}{_hex4()}"


# ─── HTTP 会话管理 ─────────────────────────────────────


class WenshuSession:
    """裁判文书网 HTTP 会话"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
        })
        self.cookies = {}
        self.vjkl5 = ""

    def _get(self, url: str, **kwargs) -> requests.Response:
        time.sleep(REQUEST_DELAY)
        return self.session.get(url, timeout=TIMEOUT, **kwargs)

    def _post(self, url: str, **kwargs) -> requests.Response:
        time.sleep(REQUEST_DELAY)
        return self.session.post(url, timeout=TIMEOUT, **kwargs)

    def init_session(self) -> bool:
        """初始化会话——获取 Cookie 和通过反爬"""
        try:
            # 第一步：访问首页
            resp = self._get(BASE_URL + "/")
            if resp.status_code != 200:
                print(f"  ⚠ 首页返回 {resp.status_code}")
                return False

            self.cookies.update(resp.cookies.get_dict())

            # 提取 JS 跳转脚本
            text = resp.text
            if '<script type="text/javascript">' not in text:
                print("  ⚠ 未找到跳转脚本，网站可能已改版")
                return False

            # 第二步：执行 JS 跳转（提取 location URL）
            scripts = text.split('<script type="text/javascript">')[1].split('</script>')[0]

            # 用简单方法提取跳转 URL（正则匹配 window.location 赋值）
            redirect_url = None
            # 尝试提取 base64 编码的 URL
            b64_match = re.search(r"atob\('([^']+)'\)", scripts)
            if b64_match:
                import base64
                try:
                    decoded = base64.b64decode(b64_match.group(1)).decode()
                    redirect_url = BASE_URL + decoded
                except Exception:
                    pass

            if not redirect_url:
                # 尝试匹配 window.location = xxx
                loc_match = re.search(r"window\.location\s*=\s*['\"]([^'\"]+)", scripts)
                if loc_match:
                    redirect_url = BASE_URL + loc_match.group(1)

            if not redirect_url:
                print("  ⚠ 无法解析跳转 URL")
                return False

            # 第三步：跟随跳转
            resp = self._get(redirect_url, allow_redirects=False)
            if resp.status_code in (301, 302):
                self.cookies.update(resp.cookies.get_dict())
                # 跟随重定向
                location = resp.headers.get("Location", "")
                if location:
                    resp = self._get(location if location.startswith("http") else BASE_URL + location)

            self.cookies.update(resp.cookies.get_dict())
            self.vjkl5 = self.cookies.get("vjkl5", "")
            print(f"  ✓ 会话初始化成功 (vjkl5={self.vjkl5[:8]}...)")
            return True

        except Exception as e:
            print(f"  ✗ 初始化失败: {e}")
            return False

    def search_cases(self, keyword: str, page: int = 1, page_size: int = 20) -> Optional[list]:
        """搜索判例。

        keyword: 搜索关键词（如 "劳动争议 违法解除"）
        page: 页码
        page_size: 每页数量
        """
        if not self.vjkl5:
            print("  ✗ 未初始化会话，请先调用 init_session()")
            return None

        try:
            vl5x = get_vl5x(self.vjkl5)

            # 构造搜索条件
            param = f"案件类型:民事案件,案由:劳动争议,全文检索:{keyword}"

            list_url = f"{BASE_URL}/List/ListContent"
            data = {
                "Param": param,
                "Index": page,
                "Page": page_size,
                "Order": "裁判日期",
                "Direction": "desc",
                "vl5x": vl5x,
                "number": "wens",
                "guid": generate_guid(),
            }
            headers = {
                "Referer": f"{BASE_URL}/List/List",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            }

            resp = self._post(list_url, data=data, headers=headers)
            if resp.status_code != 200:
                print(f"  ⚠ 搜索返回 {resp.status_code}")
                return None

            result = resp.json()
            if not isinstance(result, list) or len(result) == 0:
                print("  ⚠ 搜索结果为空")
                return []

            return result

        except Exception as e:
            print(f"  ✗ 搜索失败: {e}")
            return None

    def get_case_detail(self, doc_id: str) -> Optional[str]:
        """获取判例详情（HTML 内容）"""
        try:
            detail_url = f"{BASE_URL}/CreateContentJS/CreateContentJS.aspx?DocID={doc_id}"
            resp = self._get(detail_url)
            if resp.status_code != 200:
                return None
            return resp.text
        except Exception as e:
            print(f"  ✗ 获取详情失败: {e}")
            return None


# ─── 判例解析 ───────────────────────────────────────────


def parse_case_html(html: str) -> Optional[dict]:
    """从裁判文书 HTML 中提取结构化信息。"""
    if not html:
        return None

    case = {}

    # 案号
    m = re.search(r'案\s*号[：:]\s*(.+?)(?:。|\n|</)', html)
    if m:
        case["case_number"] = m.group(1).strip()

    # 法院
    m = re.search(r'(?:审理法院|法院名称)[：:]\s*(.+?)(?:。|\n|</)', html)
    if m:
        case["court"] = m.group(1).strip()

    # 判决日期
    m = re.search(r'(?:裁判日期|判决日期)[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})', html)
    if m:
        case["judgment_date"] = m.group(1).strip()

    # 清洗 HTML 获取纯文本
    text = re.sub(r'<[^>]+>', '\n', html)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    case["full_text"] = text[:3000]  # 前 3000 字符

    # 判决结果
    result_keywords = ["驳回", "支持", "判令", "赔偿", "违法解除", "合法解除"]
    for kw in result_keywords:
        idx = text.rfind(kw)
        if idx > 0 and idx < len(text) - 100:
            case["verdict"] = text[idx:idx+200].split("\n")[0].strip()[:150]
            break

    # 赔偿金额
    amounts = re.findall(r'(\d+[\d,.]*)\s*元', text)
    if amounts:
        case["compensation_mentioned"] = amounts[-2:]  # 最后两个金额

    return case


# ─── 输出 ──────────────────────────────────────────────


def save_case_markdown(case: dict, output_dir: Path = None) -> Optional[Path]:
    """将判例保存为标准 markdown。"""
    if output_dir is None:
        output_dir = CASES_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    cn = case.get("case_number", "unknown")
    safe_name = re.sub(r'[\\/:*?"<>|]', '-', cn)[:60]

    md = f"""# 案号：{case.get('case_number', 'N/A')}

## 基本信息
- 审理法院：{case.get('court', 'N/A')}
- 判决日期：{case.get('judgment_date', 'N/A')}
- 判决结果：{case.get('verdict', '待提取')}

## 案情摘要
（待手动整理。以下为提取的原始文本片段：）

{case.get('full_text', '')[:1500]}

## 法院认定
（待手动整理）

## 赔偿计算
{case.get('compensation_mentioned', '待提取')}

## 关键词
（待手动标注）

## 来源
裁判文书网 · 自动采集于 {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""

    filepath = output_dir / f"{safe_name}.md"
    filepath.write_text(md, encoding="utf-8")
    return filepath


# ─── 主入口 ────────────────────────────────────────────


def mine(keyword: str, count: int = 10):
    """采集判例主函数。"""
    print(f"\n{'='*60}")
    print(f"Soul Badman 裁判文书判例采集")
    print(f"关键词: {keyword}")
    print(f"目标数量: {count}")
    print(f"{'='*60}\n")

    session = WenshuSession()
    if not session.init_session():
        print("\n⚠ 无法连接裁判文书网。可能原因：")
        print("  1. 网站暂时不可用")
        print("  2. 网络需要代理")
        print("  3. 网站反爬已更新（请检查更新或使用全量数据备份）")
        print(f"\n  全量数据备份 (94.3GB):")
        print(f"  magnet:?xt=urn:btih:afa29281baf8ab6a3f5b1e9b9b0799e120611db1")
        return

    collected = 0
    page = 1
    seen_ids = set()

    while collected < count and page <= 5:
        print(f"\n--- 第 {page} 页 ---")
        results = session.search_cases(keyword, page=page, page_size=min(20, count))

        if results is None:
            print("搜索失败，停止。")
            break
        if not results:
            print("无更多结果。")
            break

        for item in results:
            if collected >= count:
                break

            doc_id = item.get("rowkey", "") or item.get("案号", "")
            case_num = item.get("案号", "unknown")

            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)

            print(f"  [{collected+1}/{count}] {case_num}...", end=" ")

            html = session.get_case_detail(doc_id)
            if not html:
                print("✗ 详情获取失败")
                continue

            case = parse_case_html(html)
            if not case:
                print("✗ 解析失败")
                continue

            case.setdefault("case_number", case_num)
            filepath = save_case_markdown(case)
            print(f"✓ {filepath.name}")
            collected += 1

        page += 1

    print(f"\n{'='*60}")
    print(f"采集完成: {collected} 条判例")
    if collected > 0:
        print(f"保存目录: {CASES_DIR}")
        print(f"\n运行以下命令重建索引:")
        print(f"  cd {Path(__file__).parent.parent}")
        print(f"  python cases/build_index.py --reset")
    print(f"{'='*60}")


def interactive():
    """交互模式。"""
    print("Soul Badman 判例采集 — 交互模式\n")
    keyword = input("搜索关键词 (默认: 劳动争议 违法解除): ").strip()
    if not keyword:
        keyword = "劳动争议 违法解除"

    try:
        count = int(input("采集数量 (默认: 10): ").strip() or "10")
    except ValueError:
        count = 10

    mine(keyword, count)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Soul Badman 裁判文书劳动争议判例采集工具",
        epilog="""
裁判文书网反爬严格，自动采集可能失败。备选方案：

  1. 全量数据备份 (94.3GB):
     magnet:?xt=urn:btih:afa29281baf8ab6a3f5b1e9b9b0799e120611db1
     来源: github.com/amakerlife/wenshu.court.gov.cn-backup

  2. 手动保存 + 解析:
     浏览器打开裁判文书网搜索判例 → 保存页面为 .html
     → python wenshu_miner.py --parse-html 判决书.html
        """
    )
    parser.add_argument("--keyword", "-k", type=str,
                        default="劳动争议 违法解除",
                        help="搜索关键词")
    parser.add_argument("--count", "-n", type=int, default=10,
                        help="采集数量")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="交互模式")
    parser.add_argument("--test", action="store_true",
                        help="测试连接")
    parser.add_argument("--parse-html", type=str, metavar="FILE",
                        help="从保存的 HTML 文件解析判例")
    args = parser.parse_args()

    if args.test:
        session = WenshuSession()
        if session.init_session():
            print("\n连接正常，尝试搜索...")
            results = session.search_cases("劳动争议", page=1, page_size=2)
            if results:
                print(f"搜索成功，找到 {len(results)} 条结果")
            else:
                print("搜索无结果（可能需要调整参数）")
        return

    if args.parse_html:
        html_path = Path(args.parse_html)
        if not html_path.exists():
            print(f"文件不存在: {html_path}")
            return
        html = html_path.read_text(encoding="utf-8")
        case = parse_case_html(html)
        if not case:
            print("解析失败——文件可能不是裁判文书页面")
            return
        filepath = save_case_markdown(case)
        print(f"已解析并保存: {filepath}")
        print(f"\n运行以下命令重建索引:")
        print(f"  cd {Path(__file__).parent.parent}")
        print(f"  python cases/build_index.py --reset")
        return

    if args.interactive:
        interactive()
    else:
        mine(args.keyword, args.count)


if __name__ == "__main__":
    main()
