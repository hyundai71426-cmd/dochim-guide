# 구현 계획 — 제목 작성 모드 (홈판용 / 정보 전달용)

설계 문서: `2026-07-08-title-mode-design.md`

각 단계 끝에 검증 방법을 명시한다. 전체 완료 후 `python -m unittest test_textutils test_naver_keywords
test_naver_poster test_sns_package test_video_maker test_tts_maker`로 회귀를 확인한다.

## 1. `textutils.py` — 제목 검증 함수 + 테스트

- [ ] `title_starts_with_keyword(title, keyword)` 추가. `title_contains_keyword`와 동일하게 공백을
      제거해 정규화한 뒤, `normalized_title.startswith(normalized_keyword)`로 판단. 빈 키워드는 항상
      통과(기존 함수와 동일 정책).
- [ ] `test_textutils.py`에 `TestTitleStartsWithKeyword` 클래스 추가: 정상(맨 앞 포함) 통과, 키워드가
      뒤쪽에 있으면 실패, 공백 유무 차이는 허용, 빈 키워드는 항상 통과 — 4케이스.
- 검증: `python -m unittest test_textutils -v`

## 2. `main.py` — UI: 라디오버튼 추가

### 2-1. `MainWindow`(글 작성 탭, `option_layout` 블록 — 약 1398~1423행)
- [ ] `QButtonGroup`(이미 import된 `QRadioButton`은 없으므로 `PyQt5.QtWidgets` import에
      `QRadioButton`, `QButtonGroup` 추가) 사용해 라디오버튼 2개 생성:
      `self.radio_home = QRadioButton("🏠 홈판용 (클릭 유도형)")`,
      `self.radio_info = QRadioButton("📖 정보 전달용 (SEO형)")`.
- [ ] `self.radio_home.setChecked(True)` (기본값 = 홈판용).
- [ ] `self.title_mode_group = QButtonGroup(self)`에 두 라디오버튼을 추가(상호배타 보장 — 같은
      부모 레이아웃 안 QRadioButton은 QButtonGroup 없이도 상호배타적이지만, 코드에서 값을 명시적으로
      읽기 위해 그룹으로 관리).
- [ ] 기존 `option_layout`(QHBoxLayout)에 라디오버튼 2개를 체크박스들 앞이나 별도 줄에 추가. 한 줄이
      너무 길어지면 별도 `QHBoxLayout`(`title_mode_layout`)을 만들어 체크박스 줄 위에 추가.
- [ ] `def get_title_mode(self): return "home" if self.radio_home.isChecked() else "info"` 헬퍼 추가.

### 2-2. `AddTaskDialog` (약 952~1024행)
- [ ] 생성자에 `default_title_mode="home"` 파라미터 추가.
- [ ] 동일한 라디오버튼 2개 + `QButtonGroup` 추가(다이얼로그의 `option_layout`에 배치).
      `default_title_mode`에 따라 초기 선택 반영.
- [ ] `get_data()` 반환 dict에 `"title_mode": "home" if self.radio_home.isChecked() else "info"` 추가.

### 2-3. 호출부 갱신
- [ ] `start_generation()`(1658행)의 `job` dict에 `"title_mode": self.get_title_mode()` 추가.
- [ ] `on_add_task()`(1677행)에서 `AddTaskDialog(...)` 생성 시 `self.get_title_mode()`를
      `default_title_mode` 인자로 전달.
- 검증: 앱 실행(`python main.py`) 후 육안으로 라디오버튼이 상호배타적으로 동작하는지, 예약 추가
  다이얼로그에 현재 선택이 그대로 반영되는지 확인.

## 3. `main.py` — `BlogGeneratorThread` 파이프라인 분기

### 3-1. 생성자(40~67행)
- [ ] `__init__`에 `title_mode="home"` 파라미터 추가, `self.title_mode = title_mode` 저장.

### 3-2. `run_job()`(1728행) 호출부
- [ ] `BlogGeneratorThread(...)` 생성 인자에 `job.get("title_mode", "home")` 추가.

### 3-3. `run()` 내부 — 크롤링 개수 분기 (약 289~293행)
- [ ] `blog_count = 5 if self.title_mode == "info" else 3`으로 바꾸고
      `self.crawl_naver_blogs(main_keyword, count=blog_count)` 호출.

### 3-4. `run()` 내부 — 정보 초안 프롬프트 분기 (약 309~363행, `prompt_draft`)
- [ ] `title_mode`에 따라 `[제목 규칙]`·`[작성 규칙]` 중 분량/톤/난이도 관련 섹션을 분기하는
      f-string을 두 갈래로 구성한다. 공통 서두(핵심 원칙, 참고 자료, 사실관계 문단)는 재사용하고,
      아래 항목만 모드별로 교체:
      - **홈판용**: 기존 문구 그대로 유지. `[제목 규칙]`을 4가지 패턴 설명으로 교체
        (① 의외의 반전으로 호기심 자극, ② 손해/실패 회피 심리 자극, ③ 현실감 100%
        내돈내산/경험담, ④ 가성비/효율 극대화 리스트 — "이 중 글감에 가장 잘 맞는 패턴 하나를
        골라 활용하라"는 지시 + 기존 "메인키워드 통째 포함" 규칙 유지). 분량 2000~2500자 유지.
      - **정보 전달용**: `[제목 규칙]`을 "메인키워드를 제목 맨 앞에 배치하고, 위 검색 자료에서
        자연스럽게 등장하는 연관어를 이어 붙이라"는 규칙으로 교체. `[작성 규칙]`에 존댓말
        지시, 분량 2500~5000자, "어린이도 이해할 수 있게 쉬운 단어로 설명", "모바일에서 읽기
        편하도록 한 문장이 너무 길어지지 않게 끊어 쓰라"는 규칙 추가.
- [ ] `raw_draft = self.call_api(prompt_draft, max_tokens=5000)`은 정보 전달용 분량이 최대
      5000자(≈7000토큰 이상)라 잘릴 수 있으므로 `max_tokens`를 `7000 if self.title_mode == "info"
      else 5000`으로 상향.

### 3-5. `run()` 내부 — 제목 검증/재시도 분기 (약 387~419행)
- [ ] 검증 함수와 재시도 프롬프트를 모드별로 분기:
      - 홈판용: 기존 `textutils.title_contains_keyword` + 기존 `prompt_fix_title` 그대로.
      - 정보 전달용: `textutils.title_starts_with_keyword` + 신규 `prompt_fix_title_info`(맨 앞
        배치 규칙을 명시, 기존 `prompt_fix_title`과 동일 구조로 문구만 교체).
      - 공통 로직(재시도 횟수, 로그 문구)은 `validator`/`fix_prompt_builder`를 변수로 뽑아 재사용
        (분기 안에서 함수를 두 번 복붙하지 않도록).

### 3-6. `run()` 내부 — 경험 오버레이·윤문 단계 분기 (약 420~505행)
- [ ] `if self.title_mode == "home":` 분기로 기존 3단계(경험 관점 오버레이 `prompt_experience` →
      기존 `prompt_proofread`)를 그대로 실행.
- [ ] `else:`(정보 전달용) 분기에서 경험 오버레이 단계를 건너뛰고, `draft_text`를 바로 신규
      `prompt_proofread_info`(존댓말 유지·쉬운 설명 유지·모바일 문장 길이 유지하며 톤만 다듬는
      윤문 프롬프트, 기존 `prompt_proofread`의 [절대 지킬 것]·분량 유지 규칙은 동일하게 포함)에
      넣어 바로 `final_text`를 만든다. `experience_text` 변수는 이 분기에서 안 쓰이므로 로그에서도
      제외.
- [ ] `self.log(...)` 호출들의 `Step N/6` 문구를 모드별 총 단계 수에 맞게 조정:
      - 홈판용: 기존 그대로 `Step 1/6 ~ Step 6/6` 유지.
      - 정보 전달용: 경험 단계가 빠지므로 `Step 1/5 ~ Step 5/5`로 재넘버링(키워드분석→크롤링→
        정보초안→윤문→이미지).
- 검증: 코드 리뷰로 두 분기 모두 `final_text`/`blog_title`/`hashtags`가 이후 로직(이미지 생성,
  `format_for_naver` 호출 등)에 동일한 타입/형태로 들어가는지 확인 — 이 아래 코드는 수정하지 않는다.

## 4. 회귀 테스트 및 수동 검증

- [ ] `python -m unittest test_textutils test_naver_keywords test_naver_poster test_sns_package
      test_video_maker test_tts_maker` 전체 통과 확인.
- [ ] `python main.py` 실행 → 홈판용 기본 선택 확인 → 정보 전달용으로 전환해 예약 추가 다이얼로그에
      반영되는지 확인(UI 레벨, LLM 호출 없이 확인 가능한 부분까지).
- [ ] **실 LLM 호출 검증은 사용자 몫**: 두 모드로 각각 실제 글감을 넣어 생성해보고 (a) 홈판용 제목이
      4패턴 중 하나의 느낌으로 나오는지, (b) 정보전달용 제목이 메인키워드로 시작하는지, (c) 정보전달용
      본문이 존댓말·2500~5000자 범위인지 확인 필요. 이 항목은 구현 완료 보고 시 "실사용 미검증"으로
      progress.md에 남긴다(기존 프로젝트 관례).

## 5. 문서화

- [ ] `progress.md`에 이번 기능 추가 내역 기록(항목 번호 이어서, 설계 배경·구현 요약·검증 상태 포함).
