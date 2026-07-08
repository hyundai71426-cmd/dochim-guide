"""naver_poster 순수 로직 단위 테스트 (표준 라이브러리 unittest 사용).

playwright import 없이 테스트 가능하도록 _clean_line만 커버한다
(_clean_line은 모듈 최상단에서 playwright를 import하지 않는다).
실행: python -m unittest test_naver_poster -v"""

import unittest

import naver_poster


class TestCleanLine(unittest.TestCase):
    def test_H2_접두어_제거(self):
        self.assertEqual(naver_poster._clean_line("## 감자 보관법"), "감자 보관법")

    def test_H3_접두어_제거(self):
        self.assertEqual(naver_poster._clean_line("### 세부 항목"), "세부 항목")

    def test_H1_접두어_제거(self):
        self.assertEqual(naver_poster._clean_line("# 제목"), "제목")

    def test_공백없는_접두어도_제거(self):
        # "##소제목"처럼 공백 없이 붙은 경우도 처리
        self.assertEqual(naver_poster._clean_line("##소제목"), "소제목")

    def test_볼드_기호_제거(self):
        self.assertEqual(naver_poster._clean_line("이것은 **굵게** 입니다"), "이것은 굵게 입니다")

    def test_접두어와_볼드_혼합(self):
        self.assertEqual(naver_poster._clean_line("## **핵심** 정리"), "핵심 정리")

    def test_일반_텍스트는_그대로(self):
        self.assertEqual(naver_poster._clean_line("평범한 문장이다."), "평범한 문장이다.")

    def test_빈줄은_빈문자열(self):
        self.assertEqual(naver_poster._clean_line(""), "")
        self.assertEqual(naver_poster._clean_line("   "), "")

    def test_앞뒤_공백_정리(self):
        self.assertEqual(naver_poster._clean_line("  가운데  "), "가운데")

    def test_불릿_기호는_가운뎃점으로(self):
        # "- "/"* " 불릿은 에디터 목록 자동변환을 피하도록 가운뎃점+NBSP로 치환
        self.assertEqual(naver_poster._clean_line("* 항목 하나"), "·\xa0항목 하나")
        self.assertEqual(naver_poster._clean_line("- 항목 둘"), "·\xa0항목 둘")

    def test_번호목록은_NBSP로_자동변환_방지(self):
        # "1. " 그대로 타이핑하면 스마트에디터가 자동 번호목록으로 바꿔 "2. 2."처럼
        # 중복되는 실사용 버그가 있었음 → 숫자 뒤 공백을 NBSP로 치환해 방지
        self.assertEqual(naver_poster._clean_line("1. 카드 발급"), "1.\xa0카드 발급")
        self.assertEqual(naver_poster._clean_line("12. 열두 번째"), "12.\xa0열두 번째")

    def test_소수점_숫자는_변환하지_않음(self):
        # "1.5배"처럼 뒤에 공백이 없는 소수점은 목록이 아니므로 그대로 둔다
        self.assertEqual(naver_poster._clean_line("1.5배 빠르다"), "1.5배 빠르다")


if __name__ == "__main__":
    unittest.main()
