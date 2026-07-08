# ☁️ 24시간 클라우드 감시 설정 (GitHub Actions)

내 PC를 꺼도 **GitHub 서버가 5분마다 자동으로** 재고를 확인하고,
입고되면 **폰 텔레그램으로 알림**을 보냅니다. **완전 무료**입니다.

> 준비물: 무료 **GitHub 계정**, 텔레그램 **봇 토큰**과 **chat_id**
> (봇 토큰·chat_id 만드는 법은 `README.md` 의 2번을 먼저 보세요.)

---

## 한눈에 보는 순서
1. GitHub 계정 만들기 → 2. 저장소(repository) 만들기 → 3. 파일 올리기
→ 4. 봇 토큰/챗ID 를 Secrets 에 넣기 → 5. 자동 실행 켜고 테스트

---

## 1. GitHub 계정 만들기
- https://github.com 에서 무료 회원가입 (이미 있으면 넘어가기)

## 2. 저장소 만들기
1. 오른쪽 위 **+** → **New repository**
2. **Repository name**: 예) `sony-stock-alert`
3. 공개 설정: **Public** 선택 ✅
   - Public 이어야 무료 실행 시간이 **무제한**입니다.
   - 걱정 마세요 — 토큰은 파일이 아니라 **Secrets(암호화 저장)** 에 넣기 때문에
     공개 저장소여도 **절대 노출되지 않습니다.**
4. **Create repository** 클릭

## 3. 파일 올리기 (업로드)
이 폴더의 파일들을 저장소에 올립니다. 올릴 파일:

```
monitor.py
products.json
.gitignore
.github/workflows/stock-check.yml   ← 폴더 구조 그대로!
```

> `config.json`(내 토큰이 든 로컬 파일)은 **올리지 마세요.** `.gitignore` 가 막아줍니다.

**쉬운 업로드 방법 (드래그 앤 드롭):**
1. 저장소 첫 화면에서 **uploading an existing file** 링크 클릭
2. `monitor.py`, `products.json`, `.gitignore` 를 끌어다 놓기
3. **Commit changes** 클릭
4. 워크플로 파일은 폴더 경로가 중요합니다. 다시 **Add file → Create new file** →
   이름 칸에 정확히 `.github/workflows/stock-check.yml` 입력 →
   이 폴더의 같은 파일 내용을 복사해 붙여넣기 → **Commit changes**

## 4. 봇 토큰/챗ID 를 Secrets 에 넣기 (가장 중요)
1. 저장소 상단 **Settings** → 왼쪽 메뉴 **Secrets and variables** → **Actions**
2. **New repository secret** 클릭
   - Name: `TELEGRAM_BOT_TOKEN` / Secret: 내 봇 토큰 붙여넣기 → **Add secret**
3. 다시 **New repository secret**
   - Name: `TELEGRAM_CHAT_ID` / Secret: 내 chat_id 붙여넣기 → **Add secret**

> 이름(대문자)을 **정확히** 위와 같이 입력해야 합니다.

## 5. 자동 실행 켜기 + 테스트
1. 저장소 상단 **Actions** 탭 클릭
2. (처음이면) *"I understand my workflows, enable them"* 같은 버튼이 보이면 눌러 활성화
3. 왼쪽에서 **소니 입고 감시** 워크플로 클릭
4. 오른쪽 **Run workflow** 버튼 → **테스트 메시지 보내기** 칸에 `1` 입력 → **Run workflow**
5. 잠시 뒤 텔레그램으로 **"✅ 테스트 성공"** 메시지가 오면 **설정 완료!** 🎉

이제부터는 **5분마다 자동으로** 재고를 확인하고, 입고되는 순간 알림이 옵니다.
PC를 꺼도 됩니다.

---

## 감시 상품 추가/변경
`products.json` 파일을 저장소에서 직접 수정(연필 아이콘 ✏️)하면 됩니다.
사이트마다 넣는 값이 다릅니다:

- **소니 스토어**: `"type": "sony"` + `product_no` (주소 `store.sony.co.kr/product-view/`**숫자**의 그 숫자)
- **후지필름 스토어**: `"type": "fuji"` + `page_url` (상품 페이지 주소 그대로)

```json
{
  "products": [
    { "name": "RX100M7", "type": "sony", "product_no": 102263765, "page_url": "https://store.sony.co.kr/product-view/102263765" },
    { "name": "후지필름 X100VI", "type": "fuji", "page_url": "https://www.fujifilm-korea.co.kr/products/id/1330" }
  ]
}
```

> 다른 브랜드 공식몰을 추가하고 싶으면 그 사이트의 재고 확인 방식이 달라서 코드 보완이 필요합니다. 필요하면 요청하세요.

---

## 알아두면 좋은 점
- **확인 간격**: GitHub Actions 는 최소 5분입니다. (더 짧게는 불가)
  실행이 몰릴 땐 몇 분 더 늦어질 수 있지만 재고 알림엔 충분합니다.
- **알림 시점**: 품절 → 판매중으로 **바뀌는 순간 1회** 보냅니다. (도배 방지)
  텔레그램 알림은 남아 있으니 놓치지 않습니다.
- **60일 규칙**: 저장소에 60일간 아무 변화가 없으면 GitHub 이 예약 실행을 자동 중지합니다.
  가끔 Actions 탭에서 수동 실행하거나 파일을 살짝 수정하면 유지됩니다.
- **비용**: Public 저장소는 무료 무제한입니다.

## 문제가 생기면
- 알림이 안 와요 → Actions 탭에서 실행 기록의 로그를 확인하세요. 보통 Secrets 이름
  오타(`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`) 거나, 봇에게 먼저 메시지를
  안 보내서 chat_id 가 틀린 경우입니다.
