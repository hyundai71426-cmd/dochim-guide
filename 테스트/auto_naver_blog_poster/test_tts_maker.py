"""tts_maker 단위 테스트.

네트워크(edge-tts) 및 ffprobe 실행 없이 모킹으로 검증한다.
실행: python -m unittest test_tts_maker -v"""

import sys
import types
import unittest
from unittest import mock

import tts_maker


class TestCleanNarration(unittest.TestCase):
    def test_강조마커_제거(self):
        self.assertEqual(
            tts_maker.clean_narration("이건 **중요한** 문장"),
            "이건 중요한 문장",
        )

    def test_연속공백_개행_정리(self):
        self.assertEqual(
            tts_maker.clean_narration("제목입니다.\n\n본문   내용\t끝"),
            "제목입니다. 본문 내용 끝",
        )

    def test_빈값_방어(self):
        self.assertEqual(tts_maker.clean_narration(""), "")
        self.assertEqual(tts_maker.clean_narration(None), "")

    def test_양끝_공백_제거(self):
        self.assertEqual(tts_maker.clean_narration("  **A** B  "), "A B")


class TestConstants(unittest.TestCase):
    def test_기본_목소리(self):
        self.assertEqual(tts_maker.DEFAULT_VOICE, "ko-KR-SunHiNeural")

    def test_목소리_선택지(self):
        ids = [v for v, _ in tts_maker.VOICES]
        self.assertIn("ko-KR-SunHiNeural", ids)
        self.assertIn("ko-KR-InJoonNeural", ids)
        self.assertIn("ko-KR-HyunsuMultilingualNeural", ids)


class TestSynthesize(unittest.TestCase):
    def test_빈텍스트_ValueError(self):
        with self.assertRaises(ValueError):
            tts_maker.synthesize("   ", "out.mp3")

    def test_edge_tts_미설치시_RuntimeError(self):
        # edge_tts import를 실패시키기 위해 sys.modules에 None을 심는다.
        with mock.patch.dict(sys.modules, {"edge_tts": None}):
            with self.assertRaises(RuntimeError) as cm:
                tts_maker.synthesize("안녕하세요", "out.mp3")
            self.assertIn("edge-tts", str(cm.exception))

    def test_edge_tts_모킹_정상호출(self):
        # 가짜 edge_tts 모듈: Communicate(text, voice, rate).save(path) 코루틴.
        saved = {}

        class FakeCommunicate:
            def __init__(self, text, voice, rate="+0%"):
                saved["text"] = text
                saved["voice"] = voice
                saved["rate"] = rate

            async def save(self, path):
                saved["path"] = path

        fake_edge = types.ModuleType("edge_tts")
        fake_edge.Communicate = FakeCommunicate

        with mock.patch.dict(sys.modules, {"edge_tts": fake_edge}):
            result = tts_maker.synthesize(
                "안녕하세요", "sub/out.mp3", voice="ko-KR-InJoonNeural", rate="+10%"
            )
        self.assertEqual(saved["text"], "안녕하세요")
        self.assertEqual(saved["voice"], "ko-KR-InJoonNeural")
        self.assertEqual(saved["rate"], "+10%")
        # 절대경로로 저장·반환되는지
        self.assertTrue(saved["path"].endswith("out.mp3"))
        self.assertEqual(result, saved["path"])


class TestProbeDuration(unittest.TestCase):
    def test_정상_길이_파싱(self):
        fake_proc = mock.Mock()
        fake_proc.returncode = 0
        fake_proc.stdout = b"12.345\n"
        fake_proc.stderr = b""
        with mock.patch("tts_maker.shutil.which", return_value="ffprobe"), \
                mock.patch("tts_maker.subprocess.run", return_value=fake_proc):
            self.assertAlmostEqual(tts_maker.probe_duration("a.mp3"), 12.345)

    def test_ffprobe_없으면_RuntimeError(self):
        with mock.patch("tts_maker.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                tts_maker.probe_duration("a.mp3")

    def test_ffprobe_실패코드_RuntimeError(self):
        fake_proc = mock.Mock()
        fake_proc.returncode = 1
        fake_proc.stdout = b""
        fake_proc.stderr = b"boom"
        with mock.patch("tts_maker.shutil.which", return_value="ffprobe"), \
                mock.patch("tts_maker.subprocess.run", return_value=fake_proc):
            with self.assertRaises(RuntimeError):
                tts_maker.probe_duration("a.mp3")

    def test_파싱불가_출력_RuntimeError(self):
        fake_proc = mock.Mock()
        fake_proc.returncode = 0
        fake_proc.stdout = b"N/A\n"
        fake_proc.stderr = b""
        with mock.patch("tts_maker.shutil.which", return_value="ffprobe"), \
                mock.patch("tts_maker.subprocess.run", return_value=fake_proc):
            with self.assertRaises(RuntimeError):
                tts_maker.probe_duration("a.mp3")


if __name__ == "__main__":
    unittest.main()
