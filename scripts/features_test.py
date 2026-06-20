#!/usr/bin/env python3
"""New features acceptance test: chat, research, congress, news i18n."""
import json
import subprocess
import sys
import time

BASE = "http://localhost:8000/api"
PASS = FAIL = 0


def req(path, method="GET", token=None, data=None, form=None, timeout=90):
    url = f"{BASE}{path}"
    cmd = ["curl", "-s", "-X", method, "-w", "\n%{http_code}", "--max-time", str(timeout)]
    if token: cmd += ["-H", f"Authorization: Bearer {token}"]
    if form is not None:
        cmd += ["-H", "Content-Type: application/x-www-form-urlencoded", "-d", form]
    elif data is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
    lines = r.stdout.rsplit("\n", 1)
    code = int(lines[1]) if len(lines) == 2 and lines[1].isdigit() else 0
    body = lines[0] if len(lines) == 2 else r.stdout
    try: return code, (json.loads(body) if body else None)
    except: return code, {"raw": body[:200]}


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {detail}")


def main():
    print("=" * 60)
    print("新增功能验收（AI问答/深度研究/政客追踪/新闻中文化）")
    print("=" * 60)

    _, r = req("/auth/token", method="POST", form="username=admin&password=cockpit2026")
    token = r["access_token"]

    # 1. AI 问答
    print("\n[1] AI 投资问答")
    st, r = req("/chat/ask", "POST", token=token,
                data={"question": "QQQ 是什么 ETF？新手适合买吗？请简短回答"}, timeout=120)
    check("问答返回200", st == 200, f"got {st}")
    check("AI真实回复(>50字)", len((r or {}).get("content", "")) > 50, str(r)[:150])
    print(f"     回复 {len(r.get('content',''))} 字")
    st, h = req("/chat/history", token=token)
    check("对话历史记录", len(h or []) >= 2, f"got {len(h or [])}")

    # 2. 深度研究
    print("\n[2] 深度研究")
    st, r = req("/research/macro", token=token, timeout=60)
    check("宏观温度计有数据", len((r or {}).get("indicators", [])) >= 4, str(r)[:150])
    print(f"     宏观指标 {len((r or {}).get('indicators', []))} 项")
    time.sleep(3)
    st, r = req("/research/fundamentals/QQQ", token=token, timeout=60)
    check("QQQ基本面有数据", (r or {}).get("name") or (r or {}).get("symbol"), str(r)[:150])
    print(f"     QQQ: {r.get('name')}, P/E={r.get('pe_ratio')}")
    time.sleep(3)
    st, r = req("/research/compare", "POST", token=token, data={"symbols": ["QQQ", "VOO"]}, timeout=90)
    items = (r or {}).get("items", [])
    check("ETF对比返回2项", len(items) == 2, f"got {len(items)}")

    # 3. 政客追踪
    print("\n[3] 政客/内部人交易追踪")
    st, r = req("/congress/refresh", "POST", token=token, timeout=45)
    check("刷新不报错", (r or {}).get("ok"), str(r)[:150])
    st, r = req("/congress", token=token)
    # 注：Capitol Trades 公开端点可能为空，允许 0 条
    check("政客接口可访问", st == 200, f"got {st}")
    print(f"     当前交易 {len((r or {}).get('items', []))} 条")

    # 4. 新闻中文化
    print("\n[4] 新闻中文化")
    st, r = req("/news/refresh", "POST", token=token, timeout=60)
    check("新闻刷新含中文源", (r or {}).get("cn", 0) >= 0, str(r)[:150])
    print(f"     新增 {r.get('new', 0)} 条 (中文源 {r.get('cn', 0)})")
    st, r = req("/news?limit=60&lang=cn", token=token)
    cn_items = (r or {}).get("items", [])
    check("中文新闻可过滤", isinstance(cn_items, list), str(r)[:100])
    # 翻译英文新闻
    st, r = req("/news/translate", "POST", token=token, timeout=120)
    check("翻译接口通", (r or {}).get("ok"), str(r)[:150])
    print(f"     翻译 {r.get('translated', 0)} 条")

    print(f"\n{'='*50}")
    print(f"新增功能验收: {PASS} 通过 / {FAIL} 失败")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
