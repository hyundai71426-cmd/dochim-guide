"""video_maker 순수 함수 단위 테스트 및 sns_package 세로 렌더 테스트.

ffmpeg 실행 없이 build_ffmpeg_cmd 인자 구성·오프셋 계산·total_duration을 검증한다.
실행: python -m unittest test_video_maker -v"""

import unittest

import video_maker
import sns_package


class TestTotalDuration(unittest.TestCase):
    def test_빈_슬라이드(self):
        self.assertEqual(video_maker.total_duration([]), 0.0)

    def test_한장은_xfade_없음(self):
        self.assertEqual(video_maker.total_duration([("a.png", 3.0)], 0.5), 3.0)

    def test_세장_누적_공식(self):
        slides = [("c.png", 3.0), ("1.png", 4.5), ("l.png", 3.5)]
        # 11.0 - 2*0.5 = 10.0
        self.assertAlmostEqual(video_maker.total_duration(slides, 0.5), 10.0)

    def test_네장_누적_공식(self):
        slides = [("c.png", 3.0), ("1.png", 4.5), ("2.png", 4.5), ("l.png", 3.5)]
        # 15.5 - 3*0.5 = 14.0
        self.assertAlmostEqual(video_maker.total_duration(slides, 0.5), 14.0)


class TestBuildFfmpegCmdBasic(unittest.TestCase):
    SLIDES = [("cover.png", 3.0), ("card1.png", 4.5), ("last.png", 3.5)]

    def test_입력_개수_및_t값(self):
        cmd = video_maker.build_ffmpeg_cmd(self.SLIDES, "out.mp4")
        # 이미지 입력 3개 → -i 3회, -loop 3회
        self.assertEqual(cmd.count("-loop"), 3)
        self.assertEqual(cmd.count("-i"), 3)
        # -t 값이 각 duration과 일치
        t_values = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-t"]
        self.assertEqual(t_values, ["3", "4.5", "3.5"])

    def test_출력_인코딩_옵션(self):
        cmd = video_maker.build_ffmpeg_cmd(self.SLIDES, "out.mp4", fps=30)
        self.assertIn("libx264", cmd)
        self.assertIn("yuv420p", cmd)
        self.assertIn("+faststart", cmd)
        self.assertIn("-y", cmd)
        # fps 반영
        self.assertIn("-r", cmd)
        self.assertEqual(cmd[cmd.index("-r") + 1], "30")

    def test_스케일_setsar_fps_정규화(self):
        cmd = video_maker.build_ffmpeg_cmd(self.SLIDES, "out.mp4", size=(1080, 1920), fps=30)
        fc = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("scale=1080:1920", fc)
        self.assertIn("setsar=1", fc)
        self.assertIn("fps=30", fc)

    def test_xfade_오프셋_누적_공식_3장(self):
        cmd = video_maker.build_ffmpeg_cmd(self.SLIDES, "out.mp4", xfade=0.5)
        fc = cmd[cmd.index("-filter_complex") + 1]
        # 전환1 offset = 3.0 - 0.5 = 2.5, 전환2 offset = 7.5 - 1.0 = 6.5
        self.assertIn("offset=2.5", fc)
        self.assertIn("offset=6.5", fc)
        self.assertIn("xfade=transition=fade", fc)
        # 최종 라벨 vout 매핑
        self.assertIn("[vout]", fc)
        self.assertIn("-map", cmd)
        self.assertEqual(cmd[cmd.index("-map") + 1], "[vout]")

    def test_xfade_오프셋_누적_공식_4장(self):
        slides = [("c.png", 3.0), ("1.png", 4.5), ("2.png", 4.5), ("l.png", 3.5)]
        cmd = video_maker.build_ffmpeg_cmd(slides, "out.mp4", xfade=0.5)
        fc = cmd[cmd.index("-filter_complex") + 1]
        # offsets: 2.5, 6.5, 10.5
        self.assertIn("offset=2.5", fc)
        self.assertIn("offset=6.5", fc)
        self.assertIn("offset=10.5", fc)


class TestBuildFfmpegCmdSingle(unittest.TestCase):
    def test_한장은_xfade_없이_인코딩(self):
        cmd = video_maker.build_ffmpeg_cmd([("only.png", 3.0)], "out.mp4")
        fc = cmd[cmd.index("-filter_complex") + 1]
        self.assertNotIn("xfade", fc)
        # 단일 입력은 [v0]가 곧 출력
        self.assertEqual(cmd[cmd.index("-map") + 1], "[v0]")

    def test_빈_슬라이드는_예외(self):
        with self.assertRaises(ValueError):
            video_maker.build_ffmpeg_cmd([], "out.mp4")


class TestBuildFfmpegCmdBgm(unittest.TestCase):
    SLIDES = [("cover.png", 3.0), ("card1.png", 4.5), ("last.png", 3.5)]

    def test_bgm_없으면_오디오_스트림_없음(self):
        cmd = video_maker.build_ffmpeg_cmd(self.SLIDES, "out.mp4", bgm_path=None)
        self.assertNotIn("-stream_loop", cmd)
        self.assertNotIn("-shortest", cmd)
        self.assertNotIn("aac", cmd)
        self.assertNotIn("[aout]", cmd)

    def test_bgm_있으면_stream_loop_shortest_aac(self):
        cmd = video_maker.build_ffmpeg_cmd(self.SLIDES, "out.mp4", bgm_path="bgm.mp3")
        self.assertIn("-stream_loop", cmd)
        self.assertIn("-shortest", cmd)
        self.assertIn("aac", cmd)
        # bgm 입력이 추가되어 -i 가 4회
        self.assertEqual(cmd.count("-i"), 4)
        # 두 스트림(vout, aout) 매핑
        maps = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-map"]
        self.assertEqual(maps, ["[vout]", "[aout]"])

    def test_bgm_afade_시작시각(self):
        cmd = video_maker.build_ffmpeg_cmd(self.SLIDES, "out.mp4", bgm_path="bgm.mp3", xfade=0.5)
        fc = cmd[cmd.index("-filter_complex") + 1]
        # total=10.0, fade_start = 10.0 - 1.5 = 8.5
        self.assertIn("afade=t=out:st=8.5:d=1.5", fc)


class TestPlanNarratedSlides(unittest.TestCase):
    def test_tts_없으면_default_유지(self):
        entries = [("c.png", 3.0, None), ("1.png", 4.5, None), ("l.png", 3.5, None)]
        slides, starts = video_maker.plan_narrated_slides(entries, 0.5)
        self.assertEqual([d for _, d in slides], [3.0, 4.5, 3.5])
        # 시작시각: i=0 → 0.3, i=1 → (3.0-0.5)+0.5=3.0, i=2 → (7.5-1.0)+0.5=7.0
        self.assertAlmostEqual(starts[0], 0.3)
        self.assertAlmostEqual(starts[1], 3.0)
        self.assertAlmostEqual(starts[2], 7.0)

    def test_tts_짧으면_default_유지(self):
        # tts+xfade+0.5 = 1.0+0.5+0.5 = 2.0 < default 4.5 → 4.5 유지
        entries = [("1.png", 4.5, 1.0)]
        slides, _ = video_maker.plan_narrated_slides(entries, 0.5)
        self.assertAlmostEqual(slides[0][1], 4.5)

    def test_tts_길면_슬라이드_연장(self):
        # tts+xfade+0.5 = 5.0+0.5+0.5 = 6.0 > default 4.5 → 6.0으로 연장
        entries = [("1.png", 4.5, 5.0)]
        slides, _ = video_maker.plan_narrated_slides(entries, 0.5)
        self.assertAlmostEqual(slides[0][1], 6.0)

    def test_나레이션_다음슬라이드_비침범(self):
        # 여러 길이의 tts를 섞어도 각 나레이션 끝이 다음 슬라이드 시작을 넘지 않아야 한다.
        entries = [
            ("c.png", 3.0, 4.0),   # 연장됨
            ("1.png", 4.5, 2.0),   # default 유지
            ("2.png", 4.5, 6.0),   # 연장됨
            ("l.png", 3.5, 3.0),   # default 유지
        ]
        xfade = 0.5
        slides, starts = video_maker.plan_narrated_slides(entries, xfade)
        durations = [d for _, d in slides]
        # 각 슬라이드 최종 시작시각 S_i = sum(d0..d_{i-1}) - i*xfade
        cum = 0.0
        slide_starts = []
        for i, d in enumerate(durations):
            slide_starts.append(cum - i * xfade)
            cum += d
        tts_durs = [4.0, 2.0, 6.0, 3.0]
        for i in range(len(entries)):
            narr_end = starts[i] + tts_durs[i]
            if i + 1 < len(entries):
                next_slide_start = slide_starts[i + 1]
                self.assertLessEqual(
                    narr_end, next_slide_start + 1e-9,
                    f"슬라이드 {i} 나레이션이 다음 슬라이드 구간을 침범"
                )


class TestBuildFfmpegCmdNarration(unittest.TestCase):
    SLIDES = [("cover.png", 3.0), ("card1.png", 4.5), ("last.png", 3.5)]

    def test_narrations_None이면_기존과_완전동일_무BGM(self):
        base = video_maker.build_ffmpeg_cmd(self.SLIDES, "out.mp4", bgm_path=None)
        withn = video_maker.build_ffmpeg_cmd(
            self.SLIDES, "out.mp4", bgm_path=None, narrations=None
        )
        self.assertEqual(base, withn)

    def test_narrations_None이면_기존과_완전동일_BGM(self):
        base = video_maker.build_ffmpeg_cmd(self.SLIDES, "out.mp4", bgm_path="bgm.mp3")
        withn = video_maker.build_ffmpeg_cmd(
            self.SLIDES, "out.mp4", bgm_path="bgm.mp3", narrations=None
        )
        self.assertEqual(base, withn)

    def test_나레이션_adelay_밀리초와_amix(self):
        narrations = [("n0.mp3", 0.3), ("n1.mp3", 3.0)]
        cmd = video_maker.build_ffmpeg_cmd(
            self.SLIDES, "out.mp4", bgm_path=None, narrations=narrations
        )
        fc = cmd[cmd.index("-filter_complex") + 1]
        # 0.3초 → 300ms, 3.0초 → 3000ms, 양채널
        self.assertIn("adelay=300|300", fc)
        self.assertIn("adelay=3000|3000", fc)
        self.assertIn("amix=inputs=2", fc)
        # 나레이션 mp3 2개가 -i 입력으로 추가됨(이미지 3 + 나레이션 2 = 5)
        self.assertEqual(cmd.count("-i"), 5)

    def test_나레이션_only_aac_인코딩(self):
        narrations = [("n0.mp3", 0.3)]
        cmd = video_maker.build_ffmpeg_cmd(
            self.SLIDES, "out.mp4", bgm_path=None, narrations=narrations
        )
        self.assertIn("aac", cmd)
        self.assertIn("-shortest", cmd)
        maps = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-map"]
        self.assertEqual(maps, ["[vout]", "[aout]"])

    def test_BGM와_나레이션_함께면_덕킹_volume_02(self):
        narrations = [("n0.mp3", 0.3), ("n1.mp3", 3.0)]
        cmd = video_maker.build_ffmpeg_cmd(
            self.SLIDES, "out.mp4", bgm_path="bgm.mp3", narrations=narrations
        )
        fc = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("volume=0.2", fc)
        # BGM afade 아웃 유지
        self.assertIn("afade=t=out", fc)
        # 나레이션 2 + 덕킹 BGM 1 = amix inputs=3
        self.assertIn("amix=inputs=3", fc)
        # 입력: 이미지 3 + bgm 1 + 나레이션 2 = -i 6회
        self.assertEqual(cmd.count("-i"), 6)


class TestSnsPackageVerticalRender(unittest.TestCase):
    THEME = sns_package.THEMES[0]

    def test_기본_호출은_1080_정사각(self):
        html = sns_package.render_cover("문구", self.THEME)
        self.assertIn("width:1080px", html)
        self.assertIn("height:1080px", html)
        self.assertNotIn("1920px", html)

    def test_세로_size_반영_cover(self):
        html = sns_package.render_cover("문구", self.THEME, size=(1080, 1920))
        self.assertIn("width:1080px", html)
        self.assertIn("height:1920px", html)

    def test_세로_size_반영_content(self):
        html = sns_package.render_content(1, 3, "제목", "본문", self.THEME, size=sns_package.CLIP_SIZE)
        self.assertIn("width:1080px", html)
        self.assertIn("height:1920px", html)

    def test_세로_size_반영_last(self):
        html = sns_package.render_last("요약", "CTA", self.THEME, size=(1080, 1920))
        self.assertIn("height:1920px", html)

    def test_CLIP_SIZE_상수(self):
        self.assertEqual(sns_package.CLIP_SIZE, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
