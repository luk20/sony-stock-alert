# -*- coding: utf-8 -*-
"""
소니 입고 알리미 — 클라우드(GitHub Actions)용 감시 스크립트.

- 텔레그램 토큰/챗ID 는 환경변수(=GitHub Secrets)에서 읽습니다.
  절대 파일에 토큰을 저장하지 않아 공개 저장소에서도 안전합니다.
- 감시할 상품은 products.json 에서 읽습니다.
- 마지막 재고 상태는 state.json 에 저장하며, GitHub Actions 캐시로
  실행 간에 유지됩니다. (품절->입고로 바뀌는 순간에만 알림)

환경변수:
  TELEGRAM_BOT_TOKEN  (필수)
  TELEGRAM_CHAT_ID    (필수)
  SEND_TEST=1         (선택) 실제 감시 대신 테스트 메시지 1건만 보내고 종료
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_PATH = os.path.join(BASE_DIR, "products.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")

SHOP_API = "https://shop-api.e-ncp.com"
SHOP_CLIENT_ID = "jkEJfXWkjf3NDwFlgc37xQ=="

KST = timezone(timedelta(hours=9))

# Windows 콘솔(cp949) 등에서 이모지 출력 시 죽지 않도록 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    print("[{}] {}".format(now, msg), flush=True)


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def http_get_json(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_product_status(product_no):
    url = "{}/products/{}/options".format(SHOP_API, product_no)
    headers = {
        "clientId": SHOP_CLIENT_ID,
        "version": "1.0",
        "platform": "PC",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) sony-stock-alert",
    }
    data = http_get_json(url, headers=headers)
    options = data.get("flatOptions") or data.get("multiLevelOptions") or []
    total_stock = 0
    available = False
    detail = []
    for opt in options:
        sale_type = str(opt.get("saleType", "")).upper()
        stock = opt.get("stockCnt", 0) or 0
        forced_soldout = bool(opt.get("forcedSoldOut", False))
        label = opt.get("value") or opt.get("label") or ""
        total_stock += max(stock, 0)
        if (sale_type != "SOLDOUT") and (not forced_soldout):
            available = True
        detail.append("{}: {} (재고 {})".format(label, sale_type or "?", stock))
    return {
        "available": available,
        "stock": total_stock,
        "price": data.get("productSalePrice") or 0,
        "detail": " / ".join(detail) if detail else "(옵션 정보 없음)",
    }


def send_telegram(token, chat_id, text):
    url = "https://api.telegram.org/bot{}/sendMessage".format(token)
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload)
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read().decode("utf-8", errors="replace"))
    if not result.get("ok"):
        raise RuntimeError("텔레그램 전송 실패: {}".format(result))
    return result


def won(n):
    try:
        return "{:,}원".format(int(float(n)))
    except Exception:
        return str(n)


def build_alert_text(name, price, stock, url):
    return (
        "🚨🚨 <b>입고 알림!</b> 🚨🚨\n\n"
        "<b>{name}</b>\n지금 구매 가능합니다!\n\n"
        "💰 가격: {price}\n📦 재고: {stock}\n"
        "🔗 <a href=\"{url}\">바로 구매하러 가기</a>"
    ).format(name=name, price=won(price), stock=stock, url=url)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        log("환경변수 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없습니다. GitHub Secrets 를 확인하세요.")
        sys.exit(1)

    # 설정 확인용 테스트 메시지
    if os.environ.get("SEND_TEST", "").strip() == "1":
        send_telegram(token, chat_id,
                      "✅ <b>테스트 성공</b>\n소니 입고 알리미가 정상적으로 연결되었습니다.")
        log("테스트 메시지 전송 완료.")
        return

    cfg = load_json(PRODUCTS_PATH, {"products": []})
    products = cfg.get("products", [])
    if not products:
        log("products.json 에 감시할 상품이 없습니다.")
        sys.exit(1)

    # 미리보기: 실제 입고 알림과 동일한 모양을 1회만 보냄 (상태는 건드리지 않음)
    if os.environ.get("SEND_PREVIEW", "").strip() == "1":
        p = products[0]
        pno = p.get("product_no")
        name = p.get("name", str(pno))
        page_url = p.get("page_url", "https://store.sony.co.kr/product-view/{}".format(pno))
        try:
            status = fetch_product_status(pno)
            price, stock = status["price"], status["stock"]
        except Exception:
            price, stock = 0, 0
        preview = ("🔔 <b>[미리보기]</b> 실제 입고 시 아래처럼 알림이 옵니다.\n"
                   "(지금은 실제 입고가 아닙니다)\n"
                   "──────────────\n" + build_alert_text(name, price, stock, page_url))
        send_telegram(token, chat_id, preview)
        log("미리보기 알림 전송 완료.")
        return

    state = load_json(STATE_PATH, {})

    for p in products:
        pno = p.get("product_no")
        name = p.get("name", str(pno))
        page_url = p.get("page_url", "https://store.sony.co.kr/product-view/{}".format(pno))
        key = str(pno)
        was_available = bool(state.get(key, {}).get("available", False))

        try:
            status = fetch_product_status(pno)
        except Exception as e:
            log("[{}] 조회 오류: {}".format(name, e))
            continue

        is_available = status["available"]
        log("[{}] {} | {}".format(
            name, "✅ 구매가능" if is_available else "⛔ 품절", status["detail"]))

        # 품절 -> 입고로 바뀌는 순간에만 알림
        if is_available and not was_available:
            text = build_alert_text(name, status["price"], status["stock"], page_url)
            try:
                send_telegram(token, chat_id, text)
                log("[{}] 📨 입고 알림 전송 완료".format(name))
            except Exception as e:
                log("[{}] 알림 전송 실패: {}".format(name, e))

        state[key] = {"available": is_available}

    save_json(STATE_PATH, state)


if __name__ == "__main__":
    main()
