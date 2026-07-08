"""sns_package 순수 함수 단위 테스트 (표준 라이브러리 unittest 사용).

LLM/네트워크 호출 없이 파서·렌더러·테마 선택·프롬프트 생성만 검증한다.
실행: python -m unittest test_sns_package -v"""

import unittest

import sns_package


# 정상 전체 응답(카드 3장) 샘플
FULL_RAW = """===COVER===
알바생을 위한
**노동법 7가지**
===CARD===
제목: 최저임금 확인
내용: 2026년 최저임금은 시급 기준으로 반드시 확인해야 한다.
===CARD===
제목: 주휴수당
내용: 주 15시간 이상 일하면 주휴수당을 받을 수 있다.
===CARD===
제목: 근로계약서
내용: 근로계약서는 반드시 서면으로 받아둬야 한다.
===LAST===
요약: 알바 전 노동법 핵심만 챙기자
CTA: 저장해두고 필요할 때 보세요
===SNS===
알바 시작 전에 이것만은 꼭 확인하세요. 최저임금, 주휴수당, 근로계약서까지 핵심만 정리했습니다. 블로그에 전문.
===CLIP===
알바 첫 출근 전 꼭 알아야 할 노동법! 최저임금, 주휴수당, 근로계약서 핵심만 정리했어요. 자세한 전문은 블로그에 있습니다.
===HASHTAGS===
#알바 #노동법 #최저임금 #주휴수당 #근로계약서
"""


class TestParseSnsPackage(unittest.TestCase):
    def test_정상_전체_파싱(self):
        data = sns_package.parse_sns_package(FULL_RAW)
        self.assertEqual(data["cover"], "알바생을 위한\n**노동법 7가지**")
        self.assertEqual(len(data["cards"]), 3)
        self.assertEqual(data["cards"][0]["title"], "최저임금 확인")
        self.assertIn("최저임금", data["cards"][0]["body"])
        self.assertEqual(data["summary"], "알바 전 노동법 핵심만 챙기자")
        self.assertEqual(data["cta"], "저장해두고 필요할 때 보세요")
        self.assertIn("블로그에 전문", data["sns_text"])
        self.assertIn("#알바", data["hashtags"])

    def test_클립_설명_파싱_및_비혼입(self):
        # CLIP 마커가 있으면 clip_text에 정확히 들어가고,
        # sns_text/hashtags에는 클립 내용이 섞이지 않아야 한다.
        data = sns_package.parse_sns_package(FULL_RAW)
        self.assertIn("알바 첫 출근 전", data["clip_text"])
        self.assertIn("자세한 전문은 블로그에 있습니다", data["clip_text"])
        # sns_text에는 클립 고유 문장이 섞이면 안 된다
        self.assertNotIn("알바 첫 출근 전", data["sns_text"])
        self.assertNotIn("===CLIP===", data["sns_text"])
        # hashtags에도 클립 문장이 섞이면 안 된다
        self.assertNotIn("알바 첫 출근 전", data["hashtags"])
        self.assertNotIn("===CLIP===", data["hashtags"])

    def test_클립_마커_누락(self):
        # CLIP 마커가 없으면 clip_text는 빈 문자열, 나머지 필드는 기존과 동일해야 한다.
        raw = """===COVER===
알바생을 위한
**노동법 7가지**
===CARD===
제목: 최저임금 확인
내용: 2026년 최저임금은 시급 기준으로 반드시 확인해야 한다.
===CARD===
제목: 주휴수당
내용: 주 15시간 이상 일하면 주휴수당을 받을 수 있다.
===LAST===
요약: 알바 전 노동법 핵심만 챙기자
CTA: 저장해두고 필요할 때 보세요
===SNS===
알바 시작 전에 이것만은 꼭 확인하세요. 블로그에 전문.
===HASHTAGS===
#알바 #노동법
"""
        data = sns_package.parse_sns_package(raw)
        self.assertEqual(data["clip_text"], "")
        self.assertIn("블로그에 전문", data["sns_text"])
        self.assertNotIn("#", data["sns_text"])
        self.assertEqual(data["summary"], "알바 전 노동법 핵심만 챙기자")
        self.assertEqual(data["cta"], "저장해두고 필요할 때 보세요")
        self.assertIn("#알바", data["hashtags"])

    def test_카드_3장_파싱(self):
        data = sns_package.parse_sns_package(FULL_RAW)
        titles = [c["title"] for c in data["cards"]]
        self.assertEqual(titles, ["최저임금 확인", "주휴수당", "근로계약서"])

    def test_마커_일부_누락(self):
        # LAST/SNS/HASHTAGS 마커가 없는 경우 → 해당 필드는 빈 값, cover/cards만 채워짐
        raw = """===COVER===
표지 문구
===CARD===
제목: 카드1
내용: 내용1
===CARD===
제목: 카드2
내용: 내용2
"""
        data = sns_package.parse_sns_package(raw)
        self.assertEqual(data["cover"], "표지 문구")
        self.assertEqual(len(data["cards"]), 2)
        self.assertEqual(data["summary"], "")
        self.assertEqual(data["cta"], "")
        self.assertEqual(data["sns_text"], "")
        self.assertEqual(data["hashtags"], "")

    def test_제목_라벨_없는_카드_방어(self):
        # "제목:"/"내용:" 라벨이 없는 카드 → 첫 줄 제목, 나머지 내용으로 방어
        raw = """===COVER===
표지
===CARD===
그냥 제목 한 줄
그리고 본문 한 줄
===CARD===
제목: 라벨있음
내용: 라벨본문
"""
        data = sns_package.parse_sns_package(raw)
        self.assertEqual(len(data["cards"]), 2)
        self.assertEqual(data["cards"][0]["title"], "그냥 제목 한 줄")
        self.assertEqual(data["cards"][0]["body"], "그리고 본문 한 줄")
        self.assertEqual(data["cards"][1]["title"], "라벨있음")
        self.assertEqual(data["cards"][1]["body"], "라벨본문")

    def test_빈_입력(self):
        data = sns_package.parse_sns_package("")
        self.assertEqual(data["cover"], "")
        self.assertEqual(data["cards"], [])
        self.assertEqual(data["summary"], "")
        self.assertEqual(data["cta"], "")
        self.assertEqual(data["sns_text"], "")
        self.assertEqual(data["hashtags"], "")


class TestRenderCover(unittest.TestCase):
    THEME = sns_package.THEMES[0]

    def test_1080_지정(self):
        html = sns_package.render_cover("테스트 문구", self.THEME)
        self.assertIn("1080px", html)

    def test_테마색_포함(self):
        html = sns_package.render_cover("문구", self.THEME)
        self.assertIn(self.THEME["bg"], html)
        self.assertIn(self.THEME["text"], html)

    def test_escape_적용(self):
        # <script> 입력이 그대로 실행 태그로 남지 않고 이스케이프돼야 한다
        html = sns_package.render_cover("<script>alert(1)</script>", self.THEME)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_강조_accent_span_변환(self):
        html = sns_package.render_cover("**중요** 단어", self.THEME)
        # **중요** → accent 색 span으로 변환, 별표는 남지 않음
        self.assertIn(f'color:{self.THEME["accent"]}', html)
        self.assertIn("중요", html)
        self.assertNotIn("**", html)

    def test_줄바꿈_br_변환(self):
        html = sns_package.render_cover("첫줄\n둘째줄", self.THEME)
        self.assertIn("<br>", html)

    def test_리터럴_백슬래시n도_br로_변환(self):
        # LLM이 실제 개행 대신 "\n"이라는 두 글자(백슬래시+n)를 문자 그대로 출력하는 경우가
        # 있었다(회귀 케이스: 카드뉴스 표지에 "\n" 글자가 그대로 노출됨). 이것도 <br>로
        # 정규화되어야 하고, 화면에 "\n" 텍스트가 그대로 남으면 안 된다.
        html = sns_package.render_cover("첫줄\\n둘째줄", self.THEME)
        self.assertIn("<br>", html)
        self.assertNotIn("\\n", html)
        self.assertNotIn("n둘째줄", html)


class TestRenderContent(unittest.TestCase):
    THEME = sns_package.THEMES[1]

    def test_1080_지정(self):
        html = sns_package.render_content(2, 7, "제목", "본문", self.THEME)
        self.assertIn("1080px", html)

    def test_진행표시_포함(self):
        html = sns_package.render_content(2, 7, "제목", "본문", self.THEME)
        self.assertIn("2/7", html)

    def test_테마색_포함(self):
        html = sns_package.render_content(1, 3, "제목", "본문", self.THEME)
        self.assertIn(self.THEME["bg"], html)
        self.assertIn(self.THEME["sub"], html)

    def test_escape_적용(self):
        html = sns_package.render_content(1, 3, "<script>", "본문", self.THEME)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestRenderLast(unittest.TestCase):
    THEME = sns_package.THEMES[2]

    def test_1080_지정(self):
        html = sns_package.render_last("요약", "저장하세요", self.THEME)
        self.assertIn("1080px", html)

    def test_테마색_포함(self):
        html = sns_package.render_last("요약", "저장하세요", self.THEME)
        self.assertIn(self.THEME["accent"], html)

    def test_강조_accent_span_변환(self):
        html = sns_package.render_last("**저장** 필수", "CTA", self.THEME)
        self.assertNotIn("**", html)

    def test_escape_적용(self):
        html = sns_package.render_last("<script>", "CTA", self.THEME)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestPickTheme(unittest.TestCase):
    def test_같은입력_같은테마(self):
        t1 = sns_package.pick_theme("감자 보관법")
        t2 = sns_package.pick_theme("감자 보관법")
        self.assertEqual(t1, t2)

    def test_반환값이_THEMES_원소(self):
        self.assertIn(sns_package.pick_theme("아무 제목"), sns_package.THEMES)


class TestBuildSnsPrompt(unittest.TestCase):
    def test_마커와_본문_포함(self):
        prompt = sns_package.build_sns_prompt("블로그 본문 내용입니다", "블로그 제목")
        # 출력 형식 마커들이 프롬프트에 포함돼야 한다
        self.assertIn("===COVER===", prompt)
        self.assertIn("===CARD===", prompt)
        self.assertIn("===LAST===", prompt)
        self.assertIn("===SNS===", prompt)
        self.assertIn("===CLIP===", prompt)
        self.assertIn("===HASHTAGS===", prompt)
        # blog_text와 blog_title도 포함
        self.assertIn("블로그 본문 내용입니다", prompt)
        self.assertIn("블로그 제목", prompt)

    def test_클립_규칙_포함(self):
        prompt = sns_package.build_sns_prompt("본문", "제목")
        # 클립 설명 규칙과 300자 한도가 프롬프트에 포함돼야 한다
        self.assertIn("클립 설명 규칙", prompt)
        self.assertIn("300자", prompt)


if __name__ == "__main__":
    unittest.main()
