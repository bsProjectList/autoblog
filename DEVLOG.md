# 개발 기록 (DEVLOG)

프로젝트의 주요 개발 변경 사항을 시간순으로 기록합니다.

## 2026-07-29

### 제휴 글 생성 탭에 플랫폼별 서브탭 추가

- `gui.py`의 "제휴 글 생성" 탭을 단일 폼에서 내부 `ttk.Notebook`으로 전환.
  네이버 커넥트 / 쿠팡 파트너스 / 토스 쇼핑 3개 서브탭으로 분리.
- 쿠팡 상품 검색(Open API) 박스는 쿠팡 파트너스 탭에만 표시.
- 각 서브탭은 독립된 상태(URL, 상품 정보, 이미지, 생성 결과 등)를 가지도록
  `SimpleNamespace` 기반 `self.affiliate_states = {"naver": ns, "coupang": ns, "toss": ns}` 구조로 리팩터링.
  기존에 `self.url_entry`, `self.platform_var` 등 인스턴스 속성 하나로 공유하던 상태를
  탭별 네임스페이스(`ns`)로 분리해서, 세 탭을 동시에 열어놔도 서로 값이 덮어써지지 않음.
- 관련 핸들러(`_search_coupang`, `_fetch_product`, `_generate_post`, `_save_post` 등)를
  전부 `ns` 인자를 받도록 시그니처 변경.
- `python -m py_compile gui.py` 통과, GUI 기동 확인(백그라운드 실행 시 예외 없음).

### "총 예상 비용"이 항상 0으로 보이는 문제 조사 및 수정

- 증상: gui.py 하단 사용량 바의 "총 예상 비용"이 계속 $0.000으로 표시됨.
- 원인 조사: `src/usage_tracker.py`의 기록/조회 로직 자체는 정상 동작 확인
  (실제 Groq 호출로 토큰 기록 → 즉시 반영되는 것을 라이브 테스트로 확인, 테스트 데이터는 복구함).
  진짜 원인은 계산 범위였음 — 기존 "총 예상 비용"은 `get_today_usage()`만 사용해서
  **오늘 하루치**만 합산했고, 자정이 지나 새 날짜가 되면 무조건 0에서 다시 시작함.
  실제로 이번 세션 시작 시점엔 오늘자 기록이 아예 없어서 0이 맞았지만, 지난 7일치를 전부
  합산하면 실제 누적 비용은 약 $0.058이었음 (OpenAI 폴백 토큰 기준. 이미지 생성 비용은
  7일간 한 번도 기록된 적이 없음 — AI 썸네일 생성 기능을 실제로 안 써봤을 가능성 있음, 별도 확인 필요).
- 수정:
  - `src/usage_tracker.py`에 `get_cumulative_cost_usd()` 추가 — 전체 날짜의 OpenAI 토큰 비용 +
    이미지 비용을 합산해서 반환. 가격 상수도 `OPENAI_COST_PER_MILLION_TOKENS`로 뽑아서
    `gui.py`와 공유(매직 넘버 중복 제거).
  - `gui.py`의 `_refresh_usage_bar`가 "오늘 예상 비용"과 "누적 총 예상 비용"을 둘 다 표시하도록 변경.
- 참고: 이미지 생성 비용(`record_image_cost`)이 실제로 한 번도 기록되지 않았다는 점은 여전히
  의심스러운 부분 — 사용자가 AI 썸네일 생성 버튼을 써본 뒤에도 $0.00으로 남아있다면
  `src/generator/image_gen.py`의 `response.usage` 파싱을 다시 확인할 것.
