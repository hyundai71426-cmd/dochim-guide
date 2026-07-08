# 제목 기반 금융 글 기획 파이프라인 설계

## 목표

제공된 제목 목록 중 `금융 & 재테크` 30개 글을 먼저 처리한다. 새 니치를 발굴하지 않고, 이미 정해진 제목을 입력으로 받아 글별 작성 가이드와 내부링크 구조를 만든다. 이후 기존 `generator.py`, `publisher.py`, `linker.py` 흐름을 사용해 Blogger에 모든 글을 임시저장하고 내부링크를 실제 URL로 치환한다.

1차 검증이 끝나면 같은 구조를 정부 지원, 건강, 자동차, 교육, IT 카테고리로 확장한다.

## 범위

### 포함한다

- `title_inputs/finance_2026.json` 입력 파일 생성.
- `title_planner.py` 신규 추가.
- `plan_finance_2026.json` 생성.
- 기존 `generator.py`로 `articles_finance_2026.json` 생성.
- 기존 `publisher.py`로 Blogger 초안 저장.
- 기존 `linker.py`로 내부링크 실제 URL 치환.
- 필요한 경우 `generator.py` 또는 `linker.py`를 최소 수정.

### 포함하지 않는다

- 새 니치 발굴.
- 제목 재작성.
- 공개 발행.
- 썸네일 생성 자동화.
- CTA 외부 링크 자동 매핑 고도화.
- 전체 180개 글 동시 실행.

## 1차 대상

카테고리는 `금융 & 재테크` 하나로 제한한다.

클러스터는 5개다.

- ISA 계좌.
- 연말정산 간소화.
- 청년 내일채움공제.
- 신용카드 포인트 전환.
- 전세자금대출.

각 클러스터는 허브글 1개와 세부글 5개로 구성한다. 총 30개 글이다.

## 파일 구조

```text
title_inputs/finance_2026.json
title_planner.py
plan_finance_2026.json
articles_finance_2026.json
url_map_finance_2026.json
```

`title_inputs/finance_2026.json`은 사람이 수정하기 쉬운 입력 파일이다. `title_planner.py`는 이 파일을 읽고 기존 생성기가 이해하는 `plan_*.json`을 만든다.

## 입력 데이터 형식

```json
{
  "name": "finance_2026",
  "category": "금융 & 재테크",
  "clusters": [
    {
      "cluster": "ISA 계좌",
      "hub_title": "ISA 계좌 신청하기",
      "titles": [
        "증권사별 ISA 계좌 수수료 비교하기",
        "ISA 계좌 개설 이벤트 사은품 받으러 가기",
        "중개형 ISA 계좌 개설 방법 모바일로 따라하기",
        "ISA 계좌 은행 증권사 차이점 알아보기",
        "비과세 ISA 계좌 한도 조건 확인하기"
      ]
    }
  ]
}
```

입력 파일의 제목은 그대로 유지한다. `title_planner.py`는 제목을 바꾸지 않는다.

## 출력 plan 형식

`plan_finance_2026.json`은 기존 `generator.py`와 호환되는 구조를 쓴다.

```json
{
  "persona": {
    "name": "오피스매거진 편집자",
    "age_range": "30대",
    "job": "생활정보 블로그 운영자",
    "background": "금융, 세금, 지원 제도 정보를 독자 입장에서 정리한다.",
    "reason_for_blog": "신청 경로와 조건을 몰라 놓치는 일을 줄이기 위해 운영한다.",
    "limitation": "제도와 금리는 바뀔 수 있어 공식 기관 확인을 함께 안내한다.",
    "short_bio": "생활 금융과 지원 제도를 쉽게 정리하는 오피스매거진 편집자"
  },
  "articles": [
    {
      "id": 1,
      "category": "금융 & 재테크",
      "cluster": "ISA 계좌",
      "title": "ISA 계좌 신청하기",
      "search_query": "ISA 계좌 신청하기",
      "is_hub": true,
      "article_role": "실행형",
      "character": "실무 전문가",
      "situation": "ISA 계좌를 처음 신청하려는 사람",
      "reader_feeling": "어디서 어떤 순서로 신청하면 되는지 알겠다",
      "reader_flow_guide": [
        "내가 지금 ISA 계좌를 만들 수 있나?",
        "은행과 증권사 중 어디가 맞나?",
        "신청 전에 조건과 한도는 뭘 봐야 하나?",
        "모바일로 바로 신청하려면 어떤 순서로 하면 되나?"
      ],
      "internal_links": {
        "prev": null,
        "next": "ISA 계좌 은행 증권사 차이점 알아보기",
        "hub": null
      }
    }
  ]
}
```

## 글 역할 분류

`title_planner.py`는 제목 패턴으로 `article_role`을 정하고, 그 역할을 기존 `characters.py`의 실제 성격명으로 매핑한다. `generator.py`는 `character`로 `characters.py`의 키를 조회하므로 `character`에는 반드시 기존 성격명만 넣는다.

- `신청하기`, `바로가기`, `신청 방법`, `따라하기`는 실행형.
- `조건`, `자격`, `한도`, `기준`, `요건`은 조건 확인형.
- `비교`, `차이점`, `수수료`, `금리`는 비교형.
- `계산기`, `환급금`, `지급일`, `조회`는 조회·계산형.
- `이벤트`, `사은품`, `현금화`, `계좌입금`은 전환형.
- `중도해지`, `연장`, `서류`, `추가 제출`은 절차·주의형.

역할별 기본 성격 매핑은 다음과 같다.

- 실행형은 `실무 전문가`.
- 조건 확인형은 `차분한 선생님`.
- 비교형은 `비교해주는 친구` 또는 `분석가`.
- 조회·계산형은 `실무 전문가`.
- 전환형은 `비교해주는 친구`.
- 절차·주의형은 `꼼꼼한 경고자`.

여러 패턴이 겹치면 더 구체적인 의도를 우선한다. 예를 들어 `중도해지 환급금 계산하기`는 단순 조회형이 아니라 절차·주의형에 가깝다.

## 내부링크 설계

1차에서는 기존 `linker.py`가 처리하는 `prev`, `next`, `hub`만 사용한다.

규칙은 다음과 같다.

- 클러스터의 첫 제목은 허브글이다.
- 허브글은 클러스터 안에서 가장 자연스러운 첫 세부글을 `next`로 가진다.
- 모든 세부글은 `hub`에 허브글 제목을 가진다.
- 세부글은 독자 흐름 순서대로 `prev`, `next`를 가진다.
- 조건 확인 글은 신청 방법 글로 연결한다.
- 비교 글은 신청 방법 또는 전환형 글로 연결한다.
- 전환형 글은 비교 글이나 조건 확인 글에서 넘어오게 한다.

ISA 계좌 예시는 다음 순서를 쓴다.

```text
ISA 계좌 신청하기
→ ISA 계좌 은행 증권사 차이점 알아보기
→ 증권사별 ISA 계좌 수수료 비교하기
→ 비과세 ISA 계좌 한도 조건 확인하기
→ 중개형 ISA 계좌 개설 방법 모바일로 따라하기
→ ISA 계좌 개설 이벤트 사은품 받으러 가기
```

## 데이터 흐름

```text
title_inputs/finance_2026.json
→ title_planner.py
→ plan_finance_2026.json
→ generator.py
→ articles_finance_2026.json
→ publisher.py
→ Blogger 초안 + url_map_finance_2026.json
→ linker.py
→ Blogger 초안 내부링크 업데이트
```

`publisher.py`는 `isDraft=True`를 이미 사용하므로 공개 발행이 아니라 초안 저장이다.

## 오류 처리

`title_planner.py`는 다음 조건을 검사한다.

- 입력 파일에 `name`, `category`, `clusters`가 있는지 확인한다.
- 각 클러스터에 `cluster`, `hub_title`, `titles`가 있는지 확인한다.
- 각 클러스터의 전체 글 수가 6개인지 확인한다.
- 중복 제목이 있으면 중단한다.
- 기존 출력 파일이 있으면 기본 동작은 덮어쓰지 않는다. `--force`를 주면 덮어쓴다.

기존 생성·발행 단계는 현재 동작을 따른다.

- `generator.py`는 글 하나마다 중간 저장한다.
- `publisher.py`는 기존 `url_map`을 읽고 이미 저장된 글은 건너뛴다.
- `linker.py`는 Blogger의 현재 초안 본문을 읽어온 뒤 수정하므로 기존 변경을 덮어쓰지 않는다.

## 실행 명령

1차 검증 명령은 다음과 같다.

```bash
python title_planner.py title_inputs/finance_2026.json
python generator.py plan_finance_2026.json
python publisher.py articles_finance_2026.json <blog_id>
python linker.py articles_finance_2026.json plan_finance_2026.json url_map_finance_2026.json <blog_id>
```

필요하면 일부 글만 생성한다.

```bash
python generator.py plan_finance_2026.json 0 5
```

## 검증 기준

1차 완료 조건은 다음과 같다.

- `plan_finance_2026.json`에 30개 글이 있다.
- 각 글에 `id`, `title`, `search_query`, `situation`, `reader_feeling`, `reader_flow_guide`, `internal_links`가 있다.
- `articles_finance_2026.json`에 30개 글이 있다.
- Blogger 초안 글 수와 `articles_finance_2026.json` 글 수가 일치한다.
- `url_map_finance_2026.json`에 30개 `post_id`와 `url`이 있다.
- `linker.py` 실행 후 초안 본문에 `href="#"` 또는 `href="#HUB"`가 남지 않는다.
- Blogger 글은 공개 발행이 아니라 초안 상태다.

## 확장 계획

금융 30개 글 검증이 끝나면 같은 입력 형식으로 다음 파일을 추가한다.

```text
title_inputs/support_2026.json
title_inputs/health_2026.json
title_inputs/auto_2026.json
title_inputs/education_2026.json
title_inputs/it_2026.json
```

각 카테고리는 독립적으로 plan, articles, url_map을 만든다. 전체 카테고리를 한 번에 발행하지 않고 카테고리별로 검증한다.
