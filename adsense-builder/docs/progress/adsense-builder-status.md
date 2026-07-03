# adsense-builder 파이프라인 진행상황

> 마지막 업데이트: 2026-07-03

## 현재 상태

niches/ 설정 파일 기반 콘텐츠 자동화 파이프라인 완성. 정부지원금 50개 글 생성, Blogger 임시저장 업로드, 내부링크 연결, 썸네일 삽입, AdSense 승인 페이지 4개 발행 완료.

파이프라인: planner.py → generator.py → publisher.py (임시저장) → linker.py → thumbnailer.py → page_publisher.py

니치별 맞춤형 콘텐츠 구조 지원 (informational vs action intent).

## 완료된 작업

### 아키텍처 개편
- [x] `niches/` 디렉토리 + JSON 스키마 도입
  - 1인사업자세금.json (informational, 홈택스/국세청 링크)
  - 부동산.json (informational, 실거래가/등기소 링크)
  - 정부지원금.json (action, CTA 버튼, 복지로/고용24 링크)
- [x] generator.py 리팩토링 — niche_config 기반 동적 프롬프트 조립
- [x] DISCLAIMER_HTML, EXTERNAL_LINKS 하드코딩 제거
- [x] intent_type 분기: informational vs action 구조 분리
- [x] content_structure 배열로 섹션 순서 제어 (templates 함수)
- [x] fact_check_search_suffix 니치별 설정 (세금/부동산/정부 기준)

### 안정성 개선
- [x] utils.py 파싱 견고화
  - parse_json_with_retry: 빈 결과 가드 + 재시도 3회
  - parse_dict_with_retry: 동일 처리
- [x] generator.py 예외 처리
  - ask(): StopIteration → 빈 문자열 폴백
  - generate_faq(): JSON 파싱 실패 → 빈 FAQ 반환
  - verify_facts(): 팩트체크 실패 → 기본 결과 반환
- [x] thumbnailer.py 임시저장 글 접근
  - posts().get(..., view='ADMIN') 추가로 draft 글 조회 가능

### publisher.py 임시저장 지원
- [x] isDraft=False → isDraft=True 변경
- [x] Blogger 초안 상태로 업로드 (한꺼번에 또는 개별 발행 가능)

### 정부지원금 니치 완성
- [x] planner.py: 김지훈 페르소나, 50개 콘텐츠 설계
- [x] generator.py: action intent 글 50개 생성 (CTA 포함)
- [x] publisher.py: 블로그 1503492112901948361에 임시저장 업로드
- [x] linker.py: 허브-앤-스포크 내부링크 연결
- [x] thumbnailer.py: 50개 글에 썸네일 삽입
- [x] page_publisher.py: 지원금 사냥꾼 블로그에 AdSense 승인 페이지 4개 발행
  - 소개 (저자: 김지훈)
  - 개인정보처리방침
  - 연락처
  - 이용약관

## 진행 중 / 막힌 부분

- [ ] CTA 링크 교체 — 글 안의 `#APPLY` 플레이스홀더를 실제 신청 기관 URL로
  - 청년월세: 주거급여사이트
  - 고용보험: 고용24
  - 기초생활: 복지로
  - 등등...
  (search_query 기준 자동 매핑 스크립트 검토 필요)

- [ ] 블로그 검색 설명(메타태그) 작성 필요
  - 현재: 기본값만 있음
  - 필요: "2026년 정부지원금 정보 | 청년, 소상공인, 실직자 지원금"

- [ ] 팩트경고 확인 및 글 수정 (옵션)
  - 청년월세: 12개월 vs 24개월 기준
  - 고용보험: 주 30시간 vs 주 15시간 기준
  - 의료비: 지원 비율 세부 기준
  (문제 있는 글만 수동 수정 또는 재생성)

## 다음에 할 일

1. 다음 니치 선정 (예: 창업지원금, 저소득층지원, 의료비)
2. `niches/새니치.json` 작성 (5분)
3. `python planner.py 새니치` 실행 (2~3분)
4. `python generator.py plan_새니치.json` 실행 (5~10분)
5. publisher → linker → thumbnailer → page_publisher 순차 실행

파이프라인이 안정화됐으므로 새 니치 추가는 JSON 설정만으로 가능. Python 코드 수정 불필요.

## 절대 지켜야 할 규칙

- **니치 추가 = niches/*.json만 작성** — generator.py 수정 금지
- **intent_type 두 가지만 지원**: 
  - `"informational"`: 도입 → 경험담 → 정보 → 마무리
  - `"action"`: 요약박스 → 자격체크 → 단계별 → FAQ → CTA
- **content_structure 배열 순서는 필수** — 이 순서대로 HTML 섹션 조립
- **disclaimer**: 니치별로 다름 (세금/부동산/지원금 각각 다른 면책문구)
- **external_links**: 각 니치가 자기 기관 URL만 포함
- **CTA**: action intent일 때만 활성화 (enabled: true)
- **experience_weight**: 
  - `"high"`: 도입부 또는 본론 한 곳에 1인칭 경험 포함
  - `"low"`: 간략하게 1~2문단만
  - `"none"`: 경험 제외
- **fact_check_search_suffix**: 검색할 때 추가 키워드 (예: "2026 국세청 기준", "2026 정부 공식")

## 관련 파일 위치

### 핵심 코드
- `niches/`: 각 니치 설정 JSON (단일 소스 오브 트루스)
- `generator.py`: 리팩토링된 콘텐츠 생성 엔진
- `planner.py`: 콘텐츠 설계 (페르소나, 50개 글 구조)

### 파이프라인 스크립트
- `publisher.py`: Blogger API 발행 (isDraft=True 임시저장)
- `linker.py`: 허브-앤-스포크 내부링크 연결
- `thumbnailer.py`: 썸네일 생성 및 삽입 (PIL)
- `page_publisher.py`: AdSense 승인 페이지 4개 발행

### 유틸리티
- `utils.py`: JSON 파싱 안정화 (재시도 3회, 빈 결과 가드)
- `characters.py`: 페르소나 풀

### 데이터 파일
- `plan_*.json`: planner 출력
- `articles_*.json`: generator 출력
- `url_map_*.json`: publisher → linker용 URL 매핑

### 문서
- `CONCEPTS.md`: 프로젝트 도메인 용어 (허브-앤-스포크, YMYL, 파이프라인 등)
- `CLAUDE.md`: 프로젝트 규칙 및 docs/solutions/ 참고
- `docs/progress/`: 이 파일

## 블로그 ID 기록

| 니치 | 블로그명 | 블로그ID | 상태 |
|---|---|---|---|
| 1인사업자세금 | 도윤이의 세금공부 | 6431963952904848703 | 발행 완료 |
| 부동산 | (별도) | TBD | 스팩 대기 |
| 정부지원금 | 지원금 사냥꾼 | 1503492112901948361 | 임시저장 50개 + AdSense 페이지 완료 |

## 마지막 세션 요약

- 니치별 콘텐츠 구조 다양화 (informational vs action) ✅
- generator.py 완전 리팩토링: 하드코딩 제거, config 기반 ✅
- 정부지원금 50개 글 생성 및 Blogger 업로드 ✅
- 예외 처리 강화 (빈 응답, JSON 파싱 실패) ✅
- page_publisher 지원금 버전 지원 ✅

다음 니치부터는 `niches/` JSON만 작성하면 파이프라인 자동 실행 가능.
