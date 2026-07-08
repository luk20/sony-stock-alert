# -*- coding: utf-8 -*-
"""
입고 알리미 — 로컬 PC용 실행기.

감지/알림 로직은 클라우드용 monitor.py 를 그대로 재사용합니다.
(로직이 한 곳에만 있으므로 버그 수정도 한 곳에서 끝납니다)

- 감시 상품: products.json  (클라우드와 공용, 소니/후지 모두 지원)
- 텔레그램 토큰/챗ID/주기: config.json  (git 에 올라가지 않는 로컬 전용)
- 마지막 재고 상태: state_local.json  (자동 생성)

사용법:
  1) config.json 에 텔레그램 봇 토큰 / 챗ID 입력 (README.md 참고)
  2) python sony_stock_alert.py   (또는 실행.bat 더블클릭)
"""

import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import monitor  # noqa: E402  (같은 폴더의 monitor.py 재사용)

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOCAL_STATE_PATH = os.path.join(BASE_DIR, "state_local.json")

log = monitor.log


def load_config():
    if not os.path.exists(CONFIG_PATH):
        log("config.json 파일이 없습니다. README.md 를 참고해 만들어 주세요.")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        log("config.json 을 읽지 못했습니다 (JSON 문법 오류일 수 있음): {}".format(e))
        sys.exit(1)
    token = str(cfg.get("telegram_bot_token", "")).strip()
    chat_id = str(cfg.get("telegram_chat_id", "")).strip()
    if not token or "여기에" in token:
        log("config.json 의 telegram_bot_token 을 먼저 설정하세요.")
        sys.exit(1)
    if not chat_id or "여기에" in chat_id:
        log("config.json 의 telegram_chat_id 을 먼저 설정하세요.")
        sys.exit(1)
    return cfg, token, chat_id


def main():
    cfg, token, chat_id = load_config()
    interval = max(int(cfg.get("check_interval_seconds", 60)), 30)  # 30초 미만은 차단 위험
    repeat_minutes = int(cfg.get("repeat_alert_minutes", 10))
    send_startup = bool(cfg.get("send_startup_message", True))

    products = monitor.load_json(monitor.PRODUCTS_PATH, {"products": []}).get("products", [])
    if not products:
        log("products.json 에 감시할 상품이 없습니다.")
        sys.exit(1)

    state = monitor.load_json(LOCAL_STATE_PATH, {})

    log("입고 알리미(로컬) 시작. 감시 상품 {}개, 확인 주기 {}초.".format(len(products), interval))
    if send_startup:
        try:
            names = "\n".join("• " + p.get("name", monitor.product_key(p)) for p in products)
            monitor.send_telegram(
                token, chat_id,
                "🟢 <b>입고 알리미(로컬) 시작</b>\n{}초마다 확인합니다.\n\n{}".format(interval, names),
            )
        except Exception as e:
            log("시작 알림 전송 실패(무시하고 계속): {}".format(e))

    while True:
        for p in products:
            name = p.get("name", monitor.product_key(p))
            key = monitor.product_key(p)
            pstate = state.get(key, {"available": False, "last_alert_ts": 0})

            try:
                status = monitor.fetch_status(p)
            except Exception as e:
                log("[{}] 조회 오류: {}".format(name, e))
                continue

            now_ts = time.time()
            was_available = bool(pstate.get("available", False))
            is_available = status["available"]

            log("[{}] {} | {}".format(
                name, "✅ 구매가능" if is_available else "⛔ 품절", status["detail"]))

            should_alert = False
            if is_available and not was_available:
                should_alert = True  # 품절 -> 입고 전환 순간
            elif is_available and was_available:
                # 재고가 계속 남아 있으면 놓치지 않도록 일정 간격으로 반복 알림
                if (now_ts - pstate.get("last_alert_ts", 0)) / 60.0 >= repeat_minutes:
                    should_alert = True

            alert_failed = False
            if should_alert:
                text = monitor.build_alert_text(name, status["alert_lines"], monitor.default_url(p))
                try:
                    monitor.send_telegram(token, chat_id, text)
                    pstate["last_alert_ts"] = now_ts
                    log("[{}] 📨 입고 알림 전송 완료".format(name))
                except Exception as e:
                    alert_failed = True
                    log("[{}] 알림 전송 실패(다음 확인 때 재시도): {}".format(name, e))

            # 전송 실패 시 상태를 넘기지 않아 다음 루프에서 다시 알림 시도
            pstate["available"] = is_available and not alert_failed
            state[key] = pstate

        monitor.save_json(LOCAL_STATE_PATH, state)
        time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("사용자 종료(Ctrl+C).")
