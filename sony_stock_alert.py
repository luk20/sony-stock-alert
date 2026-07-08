# -*- coding: utf-8 -*-
"""
소니코리아 공식스토어 입고 알리미 (텔레그램 알림)

- 소니 스토어(shopby/e-ncp) 상품 재고 API를 주기적으로 조회합니다.
- 품절(SOLDOUT) 상태가 판매중으로 바뀌면 텔레그램으로 알림을 보냅니다.
- 추가 라이브러리 설치가 필요 없습니다 (파이썬 표준 라이브러리만 사용).

사용법:
  1) config.json 에 텔레그램 봇 토큰 / 챗ID / 감시할 상품을 입력
  2) python sony_stock_alert.py   (또는 실행.bat 더블클릭)

설정 방법은 README.md 참고.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")

# Windows 콘솔(cp949) 등에서 이모지 출력 시 죽지 않도록 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 소니 스토어(shopby) 공개 API 정보 — bundle.js 에서 확인된 값
SHOP_API = "https://shop-api.e-ncp.com"
SHOP_CLIENT_ID = "jkEJfXWkjf3NDwFlgc37xQ=="


def log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[{}] {}".format(now, msg), flush=True)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        log("config.json 파일이 없습니다. README.md 를 참고해 설정하세요.")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    token = cfg.get("telegram_bot_token", "")
    chat_id = cfg.get("telegram_chat_id", "")
    if not token or "여기에" in str(token):
        log("config.json 의 telegram_bot_token 을 먼저 설정하세요.")
        sys.exit(1)
    if not chat_id or "여기에" in str(chat_id):
        log("config.json 의 telegram_chat_id 을 먼저 설정하세요.")
        sys.exit(1)
    return cfg


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("상태 저장 실패: {}".format(e))


def http_get_json(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def fetch_product_status(product_no):
    """
    상품 옵션 API를 조회해 (판매가능여부, 재고수, 가격, 상세문구)를 반환.
    available=True 이면 구매 가능(입고).
    """
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
        # 판매중 판정: SOLDOUT 이 아니고, 강제품절이 아니면 구매 가능으로 본다.
        opt_available = (sale_type != "SOLDOUT") and (not forced_soldout)
        if opt_available:
            available = True
        detail.append("{}: {} (재고 {})".format(label, sale_type or "?", stock))

    price = data.get("productSalePrice") or 0
    return {
        "available": available,
        "stock": total_stock,
        "price": price,
        "detail": " / ".join(detail) if detail else "(옵션 정보 없음)",
    }


def send_telegram(token, chat_id, text):
    url = "https://api.telegram.org/bot{}/sendMessage".format(token)
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
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


def main():
    cfg = load_config()
    token = str(cfg["telegram_bot_token"]).strip()
    chat_id = str(cfg["telegram_chat_id"]).strip()
    products = cfg.get("products", [])
    interval = int(cfg.get("check_interval_seconds", 60))
    repeat_minutes = int(cfg.get("repeat_alert_minutes", 10))
    send_startup = bool(cfg.get("send_startup_message", True))

    if not products:
        log("config.json 의 products 가 비어 있습니다.")
        sys.exit(1)

    state = load_state()

    log("입고 알리미 시작. 감시 상품 {}개, 확인 주기 {}초.".format(len(products), interval))
    if send_startup:
        try:
            names = "\n".join("• " + p.get("name", str(p.get("product_no"))) for p in products)
            send_telegram(
                token, chat_id,
                "🟢 <b>소니 입고 알리미 시작</b>\n{}초마다 확인합니다.\n\n{}".format(interval, names),
            )
        except Exception as e:
            log("시작 알림 전송 실패(무시하고 계속): {}".format(e))

    while True:
        for p in products:
            pno = p.get("product_no")
            name = p.get("name", str(pno))
            page_url = p.get("page_url", "https://store.sony.co.kr/product-view/{}".format(pno))
            key = str(pno)
            pstate = state.get(key, {"available": False, "last_alert_ts": 0})

            try:
                status = fetch_product_status(pno)
            except Exception as e:
                log("[{}] 조회 오류: {}".format(name, e))
                continue

            now_ts = time.time()
            was_available = bool(pstate.get("available", False))
            is_available = status["available"]

            log("[{}] {} | {}".format(
                name,
                "✅ 구매가능" if is_available else "⛔ 품절",
                status["detail"],
            ))

            should_alert = False
            if is_available and not was_available:
                should_alert = True  # 품절 -> 입고 전환 순간
            elif is_available and was_available:
                # 아직 재고가 있으면 반복 알림(놓치지 않도록)
                elapsed_min = (now_ts - pstate.get("last_alert_ts", 0)) / 60.0
                if elapsed_min >= repeat_minutes:
                    should_alert = True

            if should_alert:
                text = (
                    "🚨🚨 <b>입고 알림!</b> 🚨🚨\n\n"
                    "<b>{name}</b>\n"
                    "지금 구매 가능합니다!\n\n"
                    "💰 가격: {price}\n"
                    "📦 재고: {stock}\n"
                    "🔗 <a href=\"{url}\">바로 구매하러 가기</a>"
                ).format(
                    name=name,
                    price=won(status["price"]),
                    stock=status["stock"],
                    url=page_url,
                )
                try:
                    send_telegram(token, chat_id, text)
                    pstate["last_alert_ts"] = now_ts
                    log("[{}] 📨 입고 알림 전송 완료".format(name))
                except Exception as e:
                    log("[{}] 알림 전송 실패: {}".format(name, e))

            pstate["available"] = is_available
            state[key] = pstate

        save_state(state)
        time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("사용자 종료(Ctrl+C).")
