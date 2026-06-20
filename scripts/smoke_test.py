#!/usr/bin/env python3
"""End-to-end smoke test for Stock Cockpit. Run on host against localhost:8000.

Validates the full commercial flow:
  auth -> add holdings -> overview -> history -> news -> briefing
Controls Alpha Vantage rate (13s spacing) to avoid 429.
"""
import json
import sys
import time
import urllib.request

BASE = "http://localhost:8000/api"
PASS = 0
FAIL = 0


def req(path, method="GET", token=None, data=None, form=None, timeout=60):
    """HTTP helper. `data` = JSON body; `form` = urlencoded string for login."""
    import subprocess
    url = f"{BASE}{path}"
    cmd = ["curl", "-s", "-X", method, "-w", "\n%{http_code}", "--max-time", str(timeout)]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if form is not None:
        cmd += ["-H", "Content-Type: application/x-www-form-urlencoded", "-d", form]
    elif data is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
    lines = result.stdout.rsplit("\n", 1)
    code = int(lines[1]) if len(lines) == 2 else 0
    body = lines[0]
    try:
        return code, (json.loads(body) if body else None)
    except Exception:
        return code, {"raw": body}


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def main():
    print("=== 1. 认证 ===")
    st, tok_res = req("/auth/token", method="POST", form="username=admin&password=cockpit2026")
    check("登录 200", st == 200, f"got {st}")
    token = tok_res["access_token"]
    check("返回 access_token", bool(token))
    st, me = req("/auth/me", token=token)
    check("/auth/me 返回 admin", me.get("username") == "admin", str(me))

    print("=== 2. 行情（Alpha Vantage，13s间隔避免限流）===")
    st, q = req("/market/quote/QQQ", token=token)
    check("QQQ 行情 200", st == 200, f"got {st}")
    check("QQQ 价格>0", q.get("price", 0) > 0, str(q))
    print(f"     QQQ = ${q.get('price')} ({q.get('day_change_pct')}%)")
    time.sleep(14)
    st, q = req("/market/quote/VOO", token=token)
    check("VOO 价格>0", q.get("price", 0) > 0, str(q))
    print(f"     VOO = ${q.get('price')} ({q.get('day_change_pct')}%)")

    print("=== 3. 持仓 CRUD ===")
    time.sleep(14)
    st, h = req("/portfolio/holdings", "POST", token=token,
                data={"symbol": "QQQ", "shares": 10, "cost_basis": 400, "note": "long"})
    check("添加 QQQ 持仓 201", st in (200, 201), f"got {st} {h}")
    check("持仓有真实价格", h.get("current_price", 0) > 0, str(h))
    qqq_id = h.get("id")
    print(f"     QQQ: ${h.get('current_price')} x{h.get('shares')} = ${h.get('market_value')} PnL ${h.get('pnl')}")

    time.sleep(14)
    st, h2 = req("/portfolio/holdings", "POST", token=token,
                 data={"symbol": "VOO", "shares": 5, "cost_basis": 450})
    check("添加 VOO 持仓", st in (200, 201) and h2.get("current_price", 0) > 0, str(h2))
    voo_id = h2.get("id")

    st, hs = req("/portfolio/holdings", token=token)
    check("列出持仓 = 2个", isinstance(hs, list) and len(hs) == 2, str(hs))

    st, upd = req(f"/portfolio/holdings/{qqq_id}", "PUT", token=token,
                  data={"shares": 15, "cost_basis": 410})
    check("更新持仓", upd.get("shares") == 15, str(upd))

    st, ov = req("/portfolio/overview", token=token)
    check("overview 总市值>0", ov.get("total_market_value", 0) > 0, str(ov))
    check("overview 配置含2项", len(ov.get("allocation", [])) == 2, str(ov))
    print(f"     总市值 ${ov.get('total_market_value')} | 今日 ${ov.get('day_pnl')} ({ov.get('day_pnl_pct')}%)")

    print("=== 4. 删除持仓 ===")
    st, _ = req(f"/portfolio/holdings/{voo_id}", "DELETE", token=token)
    check("删除 VOO", st in (200, 204), f"got {st}")
    st, hs = req("/portfolio/holdings", token=token)
    check("删除后剩1个", len(hs) == 1, str(hs))

    print("=== 5. 新闻 ===")
    st, news = req("/news?limit=3", token=token)
    check("新闻接口通", st == 200, f"got {st}")
    print(f"     当前新闻 {len(news.get('items', []))} 条")

    print("=== 6. 简报（未配LLM应降级stub）===")
    st, b = req("/briefing/generate", "POST", token=token, timeout=90)
    check("简报生成 200", st == 200, f"got {st}")
    check("简报有内容", len(b.get("content", "")) > 50, str(b)[:200])
    print(f"     model={b.get('model')} 长度{len(b.get('content', ''))}")

    print(f"\n{'='*50}")
    print(f"结果: {PASS} 通过 / {FAIL} 失败")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
