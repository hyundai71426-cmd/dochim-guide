"""네이버 황금키워드 발굴용 순수 API 함수 모음 (PyQt5 등 UI 의존성 없음).

시드 키워드 → 검색광고 API 연관 키워드/검색량 조회, 검색 API 블로그 문서수 조회,
그리고 검색량÷문서수 기반 "황금점수" 계산 로직을 담는다.
표준 라이브러리 + requests만 사용하므로 PyQt5 없이 단독 import·테스트할 수 있다."""

import time
import hmac
import hashlib
import base64

import requests

# 황금점수 등급 기준(튜닝 가능). 비율 = 월간 검색량 ÷ 블로그 문서수.
GRADE_A_RATIO = 2.0   # 이 이상이면 A (검색 수요 대비 경쟁 문서가 적음)
GRADE_B_RATIO = 0.5   # 이 이상이면 B, 그 미만이면 C


def parse_count(value):
    """검색광고 API의 월간 검색량 값을 정수로 변환한다.

    monthlyPcQcCnt/monthlyMobileQcCnt는 검색량이 10 미만이면 정수가 아니라
    문자열 "< 10"으로 오므로(함정1), int면 그대로 쓰고 문자열/None이면 5로 간주한다."""
    if isinstance(value, bool):
        # bool은 int의 서브클래스라 아래 int 분기에 걸리므로 먼저 걸러 5로 처리한다.
        return 5
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    # "< 10", None 등 정수가 아닌 값은 소량 검색으로 보고 5로 간주한다.
    return 5


def golden_score(total_search, blog_docs):
    """월간 검색량과 블로그 문서수로 황금점수(비율)와 등급을 계산한다.

    비율 = 검색량 ÷ max(문서수, 1) (문서수 0으로 나누기 방지).
    등급: 비율 >= GRADE_A_RATIO → "A", >= GRADE_B_RATIO → "B", 그 외 "C"."""
    ratio = total_search / max(blog_docs, 1)
    if ratio >= GRADE_A_RATIO:
        grade = "A"
    elif ratio >= GRADE_B_RATIO:
        grade = "B"
    else:
        grade = "C"
    return ratio, grade


def _make_signature(secret_key, timestamp, method, path):
    """검색광고 API용 HMAC-SHA256 서명 생성. msg는 쿼리스트링 제외, path만 사용한다."""
    msg = f"{timestamp}.{method}.{path}"
    signature = hmac.new(secret_key.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.b64encode(signature).decode()


def _build_hint_keywords(seed):
    """시드에서 hintKeywords로 보낼 힌트 목록(최대 5개)을 만든다.

    복합 키워드("감자 보관법")를 공백만 제거해 힌트 1개로 보내면 keywordstool이
    연관 확장 없이 자기 자신 1개만 반환한다(단일어는 ~200개 반환, 실측 확인).
    그래서 ① 공백 제거한 시드 전체 ② 공백 분리 토큰 중 2글자 이상인 것들을
    함께 보내 연관 키워드를 넓게 받는다. 중복 제거(순서 유지), 최대 5개."""
    hints = []
    whole = seed.replace(" ", "")
    if whole:
        hints.append(whole)
    for token in seed.split():
        if len(token) >= 2 and token not in hints:
            hints.append(token)
    return hints[:5]


def fetch_related_keywords(searchad_cfg, seed):
    """검색광고 keywordstool로 시드의 연관 키워드+월간 검색량을 조회한다.

    반환: [{"keyword", "pc", "mobile", "total"(pc+mobile), "comp_idx"}, ...]
    시드에 공백이 들어가면 API가 거부하므로 공백을 제거해 전송하고(함정2),
    복합 키워드도 연관 확장이 되도록 토큰별 힌트를 함께 보낸다(_build_hint_keywords).
    여러 힌트의 결과가 합쳐져 오면서 중복 키워드가 생길 수 있어 relKeyword 기준으로
    중복 제거한다(먼저 나온 항목 우선).
    실패 시 HTTP 상태/응답 본문 일부를 담은 RuntimeError를 던진다."""
    customer_id = searchad_cfg.get("searchad_customer_id", "")
    access_license = searchad_cfg.get("searchad_access_license", "")
    secret_key = searchad_cfg.get("searchad_secret_key", "")

    # 힌트 최대 5개를 콤마 구분으로 전송 (예: "감자보관법,감자,보관법")
    hint = ",".join(_build_hint_keywords(seed))

    path = "/keywordstool"
    timestamp = str(round(time.time() * 1000))
    signature = _make_signature(secret_key, timestamp, "GET", path)
    headers = {
        "X-Timestamp": timestamp,
        "X-API-KEY": access_license,
        "X-Customer": str(customer_id),
        "X-Signature": signature,
    }
    url = f"https://api.searchad.naver.com{path}"
    params = {"hintKeywords": hint, "showDetail": "1"}

    resp = requests.get(url, headers=headers, params=params, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(
            f"검색광고 API 오류 (HTTP {resp.status_code}): {resp.text[:200]}"
        )
    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(f"검색광고 API 응답 파싱 실패: {e} / 본문: {resp.text[:200]}")

    results = []
    seen = set()  # 여러 힌트의 결과가 합쳐지며 생기는 중복 relKeyword 제거용
    for item in data.get("keywordList", []):
        keyword = item.get("relKeyword", "")
        if keyword in seen:
            continue
        seen.add(keyword)
        pc = parse_count(item.get("monthlyPcQcCnt"))
        mobile = parse_count(item.get("monthlyMobileQcCnt"))
        results.append({
            "keyword": keyword,
            "pc": pc,
            "mobile": mobile,
            "total": pc + mobile,
            "comp_idx": item.get("compIdx", ""),
        })
    return results


def fetch_blog_doc_count(search_cfg, keyword):
    """네이버 검색 API(blog.json)로 해당 키워드의 블로그 총 발행문서 수(total)를 반환한다.

    실패 시 HTTP 상태/응답 본문 일부를 담은 RuntimeError를 던진다."""
    client_id = search_cfg.get("search_client_id", "")
    client_secret = search_cfg.get("search_client_secret", "")

    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {"query": keyword, "display": 1}

    resp = requests.get(url, headers=headers, params=params, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(
            f"검색 API 오류 (HTTP {resp.status_code}): {resp.text[:200]}"
        )
    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(f"검색 API 응답 파싱 실패: {e} / 본문: {resp.text[:200]}")
    return int(data.get("total", 0))
