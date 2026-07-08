"""textutils 순수 함수 단위 테스트 (표준 라이브러리 unittest 사용).

실행: python -m unittest test_textutils -v
PyQt5 없이도 돌아가야 하므로 textutils만 import한다."""

import unittest

import textutils


class TestCleanTitleLines(unittest.TestCase):
    def test_순번줄_제거(self):
        raw = "1\n감자 보관법 총정리\n12.\n감자 오래 두는 법\n3)"
        result = textutils.clean_title_lines(raw)
        # 순번만 있는 줄("1", "12.", "3)")은 제거되고 실제 제목만 남아야 한다
        self.assertEqual(result, ["감자 보관법 총정리", "감자 오래 두는 법"])

    def test_빈줄_제거(self):
        raw = "\n제목A\n\n제목B\n"
        self.assertEqual(textutils.clean_title_lines(raw), ["제목A", "제목B"])


class TestExtractMainKeyword(unittest.TestCase):
    def test_감자_보관_파생어_그룹_합산(self):
        # progress.md에 기록된 실제 회귀 케이스: 보관/보관법/보관방법/보관하는 파생어가
        # 철자만 갈려 표가 쪼개지면 '감자'만 뽑히던 문제 → 파생어 그룹 합산으로 '감자 보관'이 나와야 한다.
        title_lines = [
            "감자 보관법 총정리",
            "감자 보관방법 꿀팁",
            "감자 오래 보관하는 법",
            "감자 싹 안나게 보관법",
            "감자 보관 온도",
        ]
        self.assertEqual(textutils.extract_main_keyword(title_lines), "감자 보관")

    def test_빈_입력(self):
        self.assertEqual(textutils.extract_main_keyword([]), "")


class TestTitleContainsKeyword(unittest.TestCase):
    def test_키워드_연속_포함_통과(self):
        self.assertTrue(textutils.title_contains_keyword("대장암 초기증상 놓치면 안되는 이유", "대장암 초기증상"))

    def test_키워드_중간에_다른_단어_삽입_실패(self):
        self.assertFalse(textutils.title_contains_keyword("대장암 이럴 때 초기증상 나타난다", "대장암 초기증상"))

    def test_공백_유무_차이는_허용(self):
        self.assertTrue(textutils.title_contains_keyword("대장암초기증상 총정리", "대장암 초기증상"))

    def test_빈_키워드는_항상_통과(self):
        self.assertTrue(textutils.title_contains_keyword("아무 제목", ""))

    def test_단일_단어_키워드(self):
        self.assertTrue(textutils.title_contains_keyword("감자 보관하는 완벽한 방법", "감자"))
        self.assertFalse(textutils.title_contains_keyword("고구마 보관법 총정리", "감자"))


class TestTitleStartsWithKeyword(unittest.TestCase):
    def test_키워드로_시작하면_통과(self):
        self.assertTrue(textutils.title_starts_with_keyword("대장암 초기증상 놓치면 안되는 이유", "대장암 초기증상"))

    def test_키워드가_뒤쪽에_있으면_실패(self):
        self.assertFalse(textutils.title_starts_with_keyword("놓치면 안되는 대장암 초기증상", "대장암 초기증상"))

    def test_공백_유무_차이는_허용(self):
        self.assertTrue(textutils.title_starts_with_keyword("대장암초기증상 총정리", "대장암 초기증상"))

    def test_빈_키워드는_항상_통과(self):
        self.assertTrue(textutils.title_starts_with_keyword("아무 제목", ""))


class TestParseKeywordAnalysis(unittest.TestCase):
    def test_정상_마커_파싱(self):
        raw = (
            "===KEYWORD===\n대장암 초기증상\n"
            "===TONE===\n정보성, 30~50대 건강 관심층\n"
            "===OUTLINE===\n- 초기증상 종류\n- 검진 시기\n- 예방법\n"
        )
        result = textutils.parse_keyword_analysis(raw, fallback_keyword="폴백")
        self.assertEqual(result["keyword"], "대장암 초기증상")
        self.assertEqual(result["tone"], "정보성, 30~50대 건강 관심층")
        self.assertEqual(result["outline"], ["초기증상 종류", "검진 시기", "예방법"])

    def test_마커_없으면_폴백_키워드로_대체(self):
        result = textutils.parse_keyword_analysis("엉뚱한 응답 텍스트", fallback_keyword="감자 보관")
        self.assertEqual(result["keyword"], "감자 보관")
        self.assertEqual(result["tone"], "")
        self.assertEqual(result["outline"], [])

    def test_OUTLINE_마커_없어도_KEYWORD_TONE은_파싱(self):
        raw = "===KEYWORD===\n감자 보관\n===TONE===\n정보성\n"
        result = textutils.parse_keyword_analysis(raw, fallback_keyword="폴백")
        self.assertEqual(result["keyword"], "감자 보관")
        self.assertEqual(result["tone"], "정보성")
        self.assertEqual(result["outline"], [])


class TestExtractHeadings(unittest.TestCase):
    def test_H2만_추출_H3제외(self):
        text = (
            "# 대제목\n"
            "## 소제목1\n"
            "본문\n"
            "### 세부제목\n"
            "## 소제목2\n"
        )
        # ##만 추출하고 #(H1)이나 ###(H3)는 제외해야 한다
        self.assertEqual(textutils.extract_headings(text), ["소제목1", "소제목2"])


class TestFormatForNaver(unittest.TestCase):
    def test_연속리스트_ul래핑_및_볼드_이미지_썸네일(self):
        text = (
            "## 소제목1\n"
            "- 항목A\n"
            "- 항목B\n"
            "일반 문장 **굵게** 끝\n"
            "## 소제목2\n"
            "내용\n"
        )
        heading_files = ["img1.png", None]
        html = textutils.format_for_naver(
            text, thumbnail_file="thumb.png", heading_files=heading_files,
            hashtags="#태그", title="",
        )
        # ① 연속된 리스트가 <ul>...</ul>로 래핑되고 <li>가 2개
        self.assertIn("<ul>", html)
        self.assertIn("</ul>", html)
        self.assertEqual(html.count("<li>"), 2)
        # ② **볼드** → <b>
        self.assertIn("<b>굵게</b>", html)
        # ③ 첫 소제목은 이미지가 있으므로 <img> 삽입, 둘째는 None이라 미삽입 → 소제목 이미지 1개
        self.assertIn('src="img1.png"', html)
        self.assertEqual(html.count('alt="소제목 이미지"'), 1)
        # ④ 썸네일 있음
        self.assertIn('src="thumb.png"', html)
        self.assertIn('alt="썸네일"', html)

    def test_썸네일_없음(self):
        html = textutils.format_for_naver(
            "## 소제목\n내용\n", thumbnail_file=None, heading_files=[None],
            hashtags="#태그", title="",
        )
        # 썸네일이 없으면 썸네일 img가 들어가지 않아야 한다
        self.assertNotIn('src="thumb.png"', html)
        self.assertNotIn('alt="썸네일"', html)

    def test_마크다운_표가_실제_table로_변환(self):
        text = (
            "## 비교\n"
            "| 항목 | 가격 | 특징 |\n"
            "|---|---|---|\n"
            "| A | 10000 | **가볍다** |\n"
            "| B | 20000 | 튼튼하다 |\n"
            "표 다음 문장\n"
        )
        html = textutils.format_for_naver(
            text, thumbnail_file=None, heading_files=[None],
            hashtags="#태그", title="",
        )
        self.assertIn("<table", html)
        self.assertEqual(html.count("<tr>"), 3)  # 헤더 1 + 데이터 2
        self.assertEqual(html.count("<th"), 3)
        self.assertEqual(html.count("<td"), 6)
        self.assertIn("<th", html.split("<table")[1].split("</tr>")[0])
        self.assertIn("가격", html)
        self.assertIn("<b>가볍다</b>", html)  # 셀 안 볼드도 변환
        # 구분선(|---|)이나 파이프 기호가 텍스트로 그대로 남으면 안 된다
        self.assertNotIn("---", html)
        self.assertIn("표 다음 문장", html)  # 표 뒤 일반 문단도 정상 처리

    def test_표가_아닌_파이프_한줄은_문단으로_처리(self):
        # 다음 줄이 구분선이 아니면 표로 인식하지 않아야 한다(오탐 방지)
        html = textutils.format_for_naver(
            "이건 | 표가 아님\n다음 문장\n", thumbnail_file=None, heading_files=[None],
            hashtags="#태그", title="",
        )
        self.assertNotIn("<table", html)
        self.assertIn("<p>이건 | 표가 아님</p>", html)


if __name__ == "__main__":
    unittest.main()
