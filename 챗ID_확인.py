# -*- coding: utf-8 -*-
"""
텔레그램 chat_id 확인 도우미.

준비:
  1) 텔레그램에서 @BotFather 로 봇을 만들고 봇 토큰을 받습니다.
  2) 만든 봇과 대화창을 열고 아무 메시지(예: 안녕)나 한 번 보냅니다.
  3) 아래 실행 후 나오는 chat_id 를 config.json 에 넣습니다.

사용법:
  python 챗ID_확인.py
"""

import json
import os
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def main():
    token = ""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                token = str(json.load(f).get("telegram_bot_token", "")).strip()
        except Exception:
            pass

    if not token or "여기에" in token:
        token = input("봇 토큰을 입력하세요: ").strip()

    url = "https://api.telegram.org/bot{}/getUpdates".format(token)
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print("요청 실패:", e)
        sys.exit(1)

    if not data.get("ok"):
        print("토큰이 올바르지 않은 것 같습니다:", data)
        sys.exit(1)

    updates = data.get("result", [])
    if not updates:
        print("아직 받은 메시지가 없습니다.")
        print("→ 텔레그램에서 만든 봇과 대화창을 열고 아무 메시지나 보낸 뒤 다시 실행하세요.")
        sys.exit(0)

    seen = {}
    for u in updates:
        msg = u.get("message") or u.get("edited_message") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if "id" in chat:
            seen[chat["id"]] = chat.get("title") or chat.get("username") or \
                (str(chat.get("first_name", "")) + " " + str(chat.get("last_name", ""))).strip()

    if not seen:
        print("메시지에서 chat_id 를 찾지 못했습니다. 봇에게 메시지를 한 번 보내보세요.")
        return

    print("\n찾은 chat_id 목록:")
    for cid, who in seen.items():
        print("  chat_id = {}   ({})".format(cid, who))
    print("\n위 chat_id 값을 config.json 의 telegram_chat_id 에 넣으세요.")


if __name__ == "__main__":
    main()
