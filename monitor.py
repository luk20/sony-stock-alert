# -*- coding: utf-8 -*-
"""
입고 알리미 — 클라우드(GitHub Actions)용 감시 스크립트.

지원 사이트:
  - 소니코리아 공식스토어 (type: "sony", shopby API 방식)
  - 후지필름코리아 공식스토어 (type: "fuji", HTML 파싱 방식)

- 텔레그램 토큰/챗ID 는 환경변수(=GitHub Secrets)에서 읽습니다.
  절대 파일에 토큰을 저장하지 않아 공개 저장소에서도 안전합니다.
- 감시할 상품은 products.json 에서 읽습니다.
- 마지막 재고 상태는 state.json 에 저장하며, GitHub Actions 캐시로
  실행 간에 유지됩니다. (품절->입고로 바뀌는 순간에만 알림)

환경변수:
  TELEGRAM_BOT_TOKEN  (필수)
  TELEGRAM_CHAT_ID    (필수)
  SEND_TEST=1         (선택) 연결 확인용 테스트 메시지 1건만 보내고 종료
  SEND_PREVIEW=값     (선택) 입고 알림 미리보기 1건만 보내고 종료
                      값: 숫자(상품 순번, 1부터) 또는 상품명/타입 일부 문자열
"""

import html
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_PATH = os.path.join(BASE_DIR, "products.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")

# 소니 스토어(shopby) 공개 API 정보 — bundle.js 에서 확인된 값
SHOP_API = "https://shop-api.e-ncp.com"
SHOP_CLIENT_ID = "jkEJfXWkjf3NDwFlgc37xQ=="

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"

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


def url_read(req, timeout=20, retries=2, backoff=2):
    """네트워크 순간 오류에 대비해 몇 번 재시도하며 응답 본문(bytes)을 반환."""
    last = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            last = e
            if attempt < retries:
                time.sleep(backoff)
    raise last


def won(n):
    try:
        return "{:,}원".format(int(float(n)))
    except Exception:
        return str(n)


# ---------------------------------------------------------------------------
# 사이트별 재고 조회
# 각 함수는 다음 형태의 dict 를 반환:
#   {"available": bool, "detail": "로그용 문자열", "alert_lines": ["알림 본문 줄", ...]}
# ---------------------------------------------------------------------------

def fetch_sony_status(p):
    product_no = p["product_no"]
    url = "{}/products/{}/options".format(SHOP_API, product_no)
    headers = {
        "clientId": SHOP_CLIENT_ID,
        "version": "1.0",
        "platform": "PC",
        "Accept": "application/json",
        "User-Agent": BROWSER_UA,
    }
    req = urllib.request.Request(url, headers=headers)
    data = json.loads(url_read(req).decode("utf-8", errors="replace"))

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

    price = data.get("productSalePrice") or 0
    return {
        "available": available,
        "detail": " / ".join(detail) if detail else "(옵션 정보 없음)",
        "alert_lines": ["💰 가격: {}".format(won(price)), "📦 재고: {}".format(total_stock)],
    }


def fetch_fuji_status(p):
    url = p["page_url"]
    headers = {"User-Agent": BROWSER_UA, "Accept-Language": "ko-KR,ko;q=0.9"}
    req = urllib.request.Request(url, headers=headers)
    page_html = url_read(req).decode("utf-8", errors="replace")

    # 페이지 구조 검증: 차단/리다이렉트/개편 등으로 상품 페이지가 아니면
    # 조용히 "품절"로 오인하지 않도록 오류로 처리(다음 실행에서 재시도).
    if "selected-product__item" not in page_html and "data-soldout" not in page_html:
        raise RuntimeError("상품 페이지 구조를 찾지 못함 (차단 또는 페이지 변경 가능)")

    # 각 옵션(색상)은 selected-product__item 블록에 data-soldout="true/false" 로 표시됨
    chunks = page_html.split('class="selected-product__item"')
    available = False
    detail = []
    avail = []
    for chunk in chunks[1:]:
        sm = re.search(r'data-soldout="([^"]*)"', chunk)
        nmm = re.search(r'selected-product__name">([^<]*)<', chunk)
        prm = re.search(r'selected-product__price">([^<]*)<', chunk)
        if not (sm and nmm):
            continue
        soldout = sm.group(1).strip().lower() == "true"
        # 외부 페이지에서 가져온 문자열은 텔레그램 HTML 메시지에 들어가므로 이스케이프 (인젝션 방지)
        nm = html.escape(nmm.group(1).strip())
        price = html.escape(prm.group(1).strip()) if prm else ""
        if not soldout:
            available = True
            avail.append("{}{}".format(nm, " (" + price + ")" if price else ""))
        detail.append("{}: {}".format(nm, "품절" if soldout else ("구매가능 " + price)))

    if not detail:
        # 파싱 실패 시 최후의 판단: data-soldout="false" 존재 여부
        available = 'data-soldout="false"' in page_html
        detail.append("(옵션 파싱 실패, data-soldout=false 여부로 판단)")

    lines = []
    if avail:
        lines.append("🎨 구매 가능: " + ", ".join(avail))
    return {"available": available, "detail": " / ".join(detail), "alert_lines": lines}


def fetch_status(p):
    ptype = (p.get("type") or "sony").lower()
    if ptype == "fuji":
        return fetch_fuji_status(p)
    return fetch_sony_status(p)


def default_url(p):
    if p.get("page_url"):
        return p["page_url"]
    return "https://store.sony.co.kr/product-view/{}".format(p.get("product_no"))


def product_key(p):
    return str(p.get("product_no") or p.get("page_url") or p.get("name"))


# ---------------------------------------------------------------------------
# 텔레그램 / 메시지
# ---------------------------------------------------------------------------

def send_telegram(token, chat_id, text):
    url = "https://api.telegram.org/bot{}/sendMessage".format(token)
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload)
    result = json.loads(url_read(req).decode("utf-8", errors="replace"))
    if not result.get("ok"):
        raise RuntimeError("텔레그램 전송 실패: {}".format(result))
    return result


def build_alert_text(name, alert_lines, url):
    body = ("\n".join(alert_lines) + "\n") if alert_lines else ""
    return (
        "🚨🚨 <b>입고 알림!</b> 🚨🚨\n\n"
        "<b>{name}</b>\n지금 구매 가능합니다!\n\n"
        "{body}"
        "🔗 <a href=\"{url}\">바로 구매하러 가기</a>"
    ).format(name=name, body=body, url=url)


# ---------------------------------------------------------------------------

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        log("환경변수 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없습니다. GitHub Secrets 를 확인하세요.")
        sys.exit(1)

    # 설정 확인용 테스트 메시지
    if os.environ.get("SEND_TEST", "").strip() == "1":
        send_telegram(token, chat_id,
                      "✅ <b>테스트 성공</b>\n입고 알리미가 정상적으로 연결되었습니다.")
        log("테스트 메시지 전송 완료.")
        return

    cfg = load_json(PRODUCTS_PATH, {"products": []})
    products = cfg.get("products", [])
    if not products:
        log("products.json 에 감시할 상품이 없습니다.")
        sys.exit(1)

    # 미리보기: 실제 입고 알림과 동일한 모양을 1회만 보냄 (상태는 건드리지 않음)
    # SEND_PREVIEW 값: "1"=첫 상품, 숫자=해당 순번, 문자=상품명/타입에 포함되는 상품 선택
    preview_sel = os.environ.get("SEND_PREVIEW", "").strip()
    if preview_sel:
        p = None
        if preview_sel.isdigit():
            idx = int(preview_sel) - 1
            if 0 <= idx < len(products):
                p = products[idx]
        if p is None:
            for pp in products:
                hay = (str(pp.get("name", "")) + " " + str(pp.get("type", ""))).lower()
                if preview_sel.lower() in hay:
                    p = pp
                    break
        if p is None:
            p = products[0]
        name = p.get("name", product_key(p))
        try:
            status = fetch_status(p)
            lines = status["alert_lines"] or ["(재고 상세 정보 없음)"]
        except Exception:
            lines = ["(재고 상세 정보 없음)"]
        preview = ("🔔 <b>[미리보기]</b> 실제 입고 시 아래처럼 알림이 옵니다.\n"
                   "(지금은 실제 입고가 아닙니다)\n"
                   "──────────────\n" + build_alert_text(name, lines, default_url(p)))
        send_telegram(token, chat_id, preview)
        log("미리보기 알림 전송 완료.")
        return

    state = load_json(STATE_PATH, {})

    for p in products:
        name = p.get("name", product_key(p))
        key = product_key(p)
        was_available = bool(state.get(key, {}).get("available", False))

        try:
            status = fetch_status(p)
        except Exception as e:
            log("[{}] 조회 오류: {}".format(name, e))
            continue

        is_available = status["available"]
        log("[{}] {} | {}".format(
            name, "✅ 구매가능" if is_available else "⛔ 품절", status["detail"]))

        # 품절 -> 입고로 바뀌는 순간에만 알림
        alert_failed = False
        if is_available and not was_available:
            text = build_alert_text(name, status["alert_lines"], default_url(p))
            try:
                send_telegram(token, chat_id, text)
                log("[{}] 📨 입고 알림 전송 완료".format(name))
            except Exception as e:
                alert_failed = True
                log("[{}] 알림 전송 실패(다음 실행에서 재시도): {}".format(name, e))

        # 알림을 보내야 했는데 실패했다면 상태를 넘기지 않아 다음 실행에서 다시 알림 시도
        state[key] = {"available": is_available and not alert_failed}

    save_json(STATE_PATH, state)


if __name__ == "__main__":
    main()
