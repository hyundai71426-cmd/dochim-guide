"""naver_keywords 순수 API 함수 단위 테스트 (표준 라이브러리 unittest 사용).

네트워크 호출은 금지이므로 unittest.mock으로 requests.get을 모킹한다.
실행: python -m unittest test_naver_keywords -v"""

import unittest
from unittest import mock

import naver_keywords


class TestParseCount(unittest.TestCase):
    def test_정수는_그대로(self):
        self.assertEqual(naver_keywords.parse_count(15700), 15700)
        self.assertEqual(naver_keywords.parse_count(0), 0)

    def test_10미만_문자열은_5로(self):
        # "< 10"처럼 검색량이 10 미만이면 문자열로 오므로 5로 간주한다(함정1).
        self.assertEqual(naver_keywords.parse_count("< 10"), 5)

    def test_None은_5로(self):
        self.assertEqual(naver_keywords.parse_count(None), 5)


class TestGoldenScore(unittest.TestCase):
    def test_A등급_경계값(self):
        # 비율 정확히 2.0 → A (>= GRADE_A_RATIO)
        ratio, grade = naver_keywords.golden_score(2000, 1000)
        self.assertEqual(ratio, 2.0)
        self.assertEqual(grade, "A")

    def test_B등급_경계값(self):
        # 비율 정확히 0.5 → B (>= GRADE_B_RATIO)
        ratio, grade = naver_keywords.golden_score(500, 1000)
        self.assertEqual(ratio, 0.5)
        self.assertEqual(grade, "B")

    def test_C등급(self):
        # 비율 0.5 미만 → C
        ratio, grade = naver_keywords.golden_score(100, 1000)
        self.assertEqual(grade, "C")

    def test_문서수0_나누기방지(self):
        # 문서수 0이어도 max(blog_docs, 1)로 0나누기 없이 계산된다.
        ratio, grade = naver_keywords.golden_score(50, 0)
        self.assertEqual(ratio, 50.0)
        self.assertEqual(grade, "A")


def _make_response(status_code=200, json_data=None, text=""):
    """requests.get 반환값을 흉내내는 가짜 응답 객체."""
    resp = mock.Mock()
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("no json")
    return resp


class TestFetchRelatedKeywords(unittest.TestCase):
    SEARCHAD_CFG = {
        "searchad_customer_id": "123",
        "searchad_access_license": "lic",
        "searchad_secret_key": "sec",
    }

    def test_응답_파싱(self):
        json_data = {
            "keywordList": [
                {"relKeyword": "감자", "monthlyPcQcCnt": 15700,
                 "monthlyMobileQcCnt": 78400, "compIdx": "중간"},
                {"relKeyword": "감자싹", "monthlyPcQcCnt": "< 10",
                 "monthlyMobileQcCnt": "< 10", "compIdx": "낮음"},
            ]
        }
        with mock.patch("naver_keywords.requests.get",
                        return_value=_make_response(json_data=json_data)):
            result = naver_keywords.fetch_related_keywords(self.SEARCHAD_CFG, "감자")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["keyword"], "감자")
        self.assertEqual(result[0]["pc"], 15700)
        self.assertEqual(result[0]["mobile"], 78400)
        self.assertEqual(result[0]["total"], 15700 + 78400)
        self.assertEqual(result[0]["comp_idx"], "중간")
        # "< 10" 문자열은 5로 파싱되어 total=10
        self.assertEqual(result[1]["pc"], 5)
        self.assertEqual(result[1]["mobile"], 5)
        self.assertEqual(result[1]["total"], 10)

    def test_복합시드_힌트_다중전송(self):
        # 복합 시드 "감자 보관법"은 공백 제거 전체 + 각 토큰(2글자 이상)을
        # 콤마 구분 힌트로 함께 보내야 한다 (복합어 힌트 1개만 보내면 연관 확장이 안 됨).
        with mock.patch("naver_keywords.requests.get",
                        return_value=_make_response(json_data={"keywordList": []})) as mget:
            naver_keywords.fetch_related_keywords(self.SEARCHAD_CFG, "감자 보관법")
        _, kwargs = mget.call_args
        self.assertEqual(kwargs["params"]["hintKeywords"], "감자보관법,감자,보관법")

    def test_한단어시드_힌트_하나(self):
        # 한 단어 시드 "감자"는 힌트가 "감자" 하나여야 한다 (중복 제거 확인).
        with mock.patch("naver_keywords.requests.get",
                        return_value=_make_response(json_data={"keywordList": []})) as mget:
            naver_keywords.fetch_related_keywords(self.SEARCHAD_CFG, "감자")
        _, kwargs = mget.call_args
        self.assertEqual(kwargs["params"]["hintKeywords"], "감자")

    def test_중복_relKeyword_제거(self):
        # 여러 힌트의 결과가 합쳐져 relKeyword가 중복되면 먼저 나온 항목만 남아야 한다.
        json_data = {
            "keywordList": [
                {"relKeyword": "감자", "monthlyPcQcCnt": 15700,
                 "monthlyMobileQcCnt": 78400, "compIdx": "중간"},
                {"relKeyword": "감자보관법", "monthlyPcQcCnt": 100,
                 "monthlyMobileQcCnt": 200, "compIdx": "낮음"},
                {"relKeyword": "감자", "monthlyPcQcCnt": 1,
                 "monthlyMobileQcCnt": 2, "compIdx": "높음"},
            ]
        }
        with mock.patch("naver_keywords.requests.get",
                        return_value=_make_response(json_data=json_data)):
            result = naver_keywords.fetch_related_keywords(self.SEARCHAD_CFG, "감자 보관법")
        self.assertEqual(len(result), 2)
        self.assertEqual([r["keyword"] for r in result], ["감자", "감자보관법"])
        # 먼저 나온 항목이 우선 → "감자"의 값은 첫 항목 기준이어야 한다.
        self.assertEqual(result[0]["pc"], 15700)
        self.assertEqual(result[0]["comp_idx"], "중간")

    def test_HTTP오류_RuntimeError(self):
        with mock.patch("naver_keywords.requests.get",
                        return_value=_make_response(status_code=401, text="Unauthorized")):
            with self.assertRaises(RuntimeError):
                naver_keywords.fetch_related_keywords(self.SEARCHAD_CFG, "감자")


class TestFetchBlogDocCount(unittest.TestCase):
    SEARCH_CFG = {"search_client_id": "id", "search_client_secret": "secret"}

    def test_total_파싱(self):
        with mock.patch("naver_keywords.requests.get",
                        return_value=_make_response(json_data={"total": 123456})):
            total = naver_keywords.fetch_blog_doc_count(self.SEARCH_CFG, "감자")
        self.assertEqual(total, 123456)

    def test_HTTP오류_RuntimeError(self):
        with mock.patch("naver_keywords.requests.get",
                        return_value=_make_response(status_code=500, text="err")):
            with self.assertRaises(RuntimeError):
                naver_keywords.fetch_blog_doc_count(self.SEARCH_CFG, "감자")


if __name__ == "__main__":
    unittest.main()
