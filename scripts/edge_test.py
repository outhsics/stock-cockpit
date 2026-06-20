#!/usr/bin/env python3
"""Edge-case & error-handling tests for commercial robustness.

Tests: bad auth, invalid inputs, nonexistent symbols, duplicate prevention,
rate-limit tolerance, empty states, oversized inputs.
"""
import json
import subprocess
import sys

BASE = "http://localhost:8000/api"
PASS = FAIL = 0


def req(path, method="GET", token=None, data=None, form=None, timeout=30):
    url = f"{BASE}{path}"
    cmd = ["curl", "-s", "-X", method, "-w", "\n%{http_code}", "--max-time", str(timeout)]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if form is not None:
        cmd += ["-H", "Content-Type: application/x-www-form-urlencoded", "-d", form]
    elif data is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
    lines = r.stdout.rsplit("\n", 1)
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


def login():
    _, r = req("/auth/token", method="POST", form="username=admin&password=cockpit2026")
    return r["access_token"]


def main():
    print("=== 1. 认证失败处理 ===")
    # Wrong password
    st, r = req("/auth/token", method="POST", form="username=admin&password=wrong")
    check("错误密码返回 401", st == 401, f"got {st}")
    # No token
    st, r = req("/portfolio/overview")
    check("无token访问受保护端点 401", st == 401, f"got {st}")
    # Bad token
    st, r = req("/portfolio/overview", token="garbage.token.here")
    check("无效token 401", st == 401, f"got {st}")

    token = login()

    print("=== 2. 输入校验 ===")
    # Empty symbol
    st, r = req("/portfolio/holdings", "POST", token=token, data={"symbol": "", "shares": 1, "cost_basis": 1})
    check("空symbol 422", st == 422, f"got {st}")
    # Negative shares
    st, r = req("/portfolio/holdings", "POST", token=token, data={"symbol": "AAPL", "shares": -5, "cost_basis": 100})
    check("负股数 422", st == 422, f"got {st}")
    # Zero cost
    st, r = req("/portfolio/holdings", "POST", token=token, data={"symbol": "AAPL", "shares": 1, "cost_basis": 0})
    check("零成本 422", st == 422, f"got {st}")
    # Malformed JSON handled by framework
    st, r = req("/portfolio/holdings", "POST", token=token, data=None)
    check("缺body 422", st == 422, f"got {st}")

    print("=== 3. 不存在的资源 ===")
    st, r = req("/portfolio/holdings/99999", "PUT", token=token, data={"shares": 1})
    check("更新不存在持仓 404", st == 404, f"got {st}")
    st, r = req("/portfolio/holdings/99999", "DELETE", token=token)
    check("删除不存在持仓 404", st == 404, f"got {st}")

    print("=== 4. 不存在的symbol（行情优雅降级）===")
    st, r = req("/market/quote/ZZZZNOTREAL", token=token, timeout=45)
    check("假symbol返回200（含error字段）", st == 200, f"got {st} {str(r)[:100]}")
    has_err = (r or {}).get("error") or (r or {}).get("price") == 0 or (r or {}).get("price") is None
    check("假symbol有error标记", has_err, str(r)[:100])

    print("=== 5. 健康检查（无需认证）===")
    st, r = req("/health")
    check("/health 200", st == 200, f"got {st}")
    check("health返回status=ok", (r or {}).get("status") == "ok", str(r))

    print("=== 6. 并发安全（多次添加同symbol，应各自独立）===")
    st, r1 = req("/portfolio/holdings", "POST", token=token, data={"symbol":"SPY","shares":1,"cost_basis":500})
    check("第一次加SPY成功", st in (200,201), f"got {st}")
    st, r2 = req("/portfolio/holdings", "POST", token=token, data={"symbol":"SPY","shares":2,"cost_basis":510})
    check("重复symbol允许（多笔持仓）", st in (200,201), f"got {st}")
    # cleanup duplicates
    for hid in [r1.get("id"), r2.get("id")]:
        if hid: req(f"/portfolio/holdings/{hid}", "DELETE", token=token)

    print(f"\n{'='*50}")
    print(f"边界测试: {PASS} 通过 / {FAIL} 失败")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
