"""카드뉴스 PNG들을 네이버 클립(세로 9:16) 슬라이드쇼 mp4로 묶는 모듈.

PyQt5·네트워크 무의존. 표준 라이브러리 + ffmpeg(subprocess)만 사용한다.

- build_ffmpeg_cmd(): 순수 함수. slides로부터 ffmpeg 인자 리스트를 만든다(실행하지 않음).
- make_clip(): 실제로 ffmpeg를 subprocess로 실행해 mp4를 생성한다.
- total_duration(): xfade 크로스페이드를 고려한 최종 영상 길이(초)를 계산한다.

xfade 오프셋 공식(직접 도출):
  슬라이드 durations = [d0, d1, ..., d_{n-1}] 를 xfade로 크로스페이드 연결할 때,
  i번째 전환(0-indexed, 누적 스트림과 입력 i+1을 합침)의 offset은
      offset_i = (d0 + ... + d_i) - (i+1) * xfade
  이며, 최종 영상 길이는
      total = sum(d) - (n-1) * xfade
  이다. (n=1이면 xfade 없이 d0.)
"""

import os
import shutil
import subprocess


# 각 카드 유형별 기본 노출 시간(초). 표지/본문/마지막.
DEFAULT_DURATIONS = {
    "cover": 3.0,
    "content": 4.5,
    "last": 3.5,
}

# 크로스페이드(xfade) 지속 시간(초).
XFADE_DURATION = 0.5

# BGM 페이드아웃 길이(초).
BGM_FADEOUT = 1.5


def total_duration(slides, xfade=XFADE_DURATION):
    """xfade 크로스페이드를 고려한 최종 영상 길이(초).

    slides: [(png_path, duration), ...]. 슬라이드가 0장이면 0, 1장이면 그 길이.
    2장 이상이면 sum(dur) - (n-1)*xfade."""
    n = len(slides)
    if n == 0:
        return 0.0
    total = sum(float(d) for _, d in slides)
    if n == 1:
        return total
    return total - (n - 1) * xfade


def _norm(path):
    """ffmpeg 인자로 안전하게 넘기기 위해 경로를 절대 정규화한다."""
    return os.path.abspath(path)


def build_ffmpeg_cmd(slides, out_path, bgm_path=None, size=(1080, 1920),
                     fps=30, xfade=XFADE_DURATION, narrations=None):
    """slides로부터 ffmpeg 인자 리스트(list[str])를 만든다 (순수 함수, 실행 안 함).

    slides: [(png_path, duration), ...]
    - 각 이미지는 `-loop 1 -t {dur} -i {png}` 입력으로 넣는다.
    - filter_complex에서 각 입력을 scale/setsar/fps로 정규화한 뒤 xfade 체인으로 연결한다.
    - 슬라이드가 1장뿐이면 xfade 없이 단순 인코딩.
    - bgm_path가 있으면 `-stream_loop -1`로 반복 입력하고 -shortest, 끝에서 1.5초 afade=out.
    - narrations: [(audio_path, start_sec), ...] 나레이션 오디오. 각각을 adelay로 지정 시각에
      배치한 뒤 amix로 합성한다. BGM이 함께 있으면 BGM은 volume=0.2로 덕킹된다.
      나레이션이 하나라도 있으면(BGM 유무와 무관) -c:a aac로 인코딩된다.

    narrations=None(기본)이면 나레이션 관련 인자/필터가 전혀 추가되지 않아
    기존 호출 결과와 완전히 동일하다(회귀 안전)."""
    if not slides:
        raise ValueError("slides가 비어 있습니다. 최소 1장의 이미지가 필요합니다.")

    width, height = size
    n = len(slides)

    cmd = ["ffmpeg", "-y"]

    # ── 이미지 입력들 ──
    for png_path, dur in slides:
        cmd += ["-loop", "1", "-t", f"{float(dur):g}", "-i", _norm(png_path)]

    # ── BGM 입력(무한 반복) ──
    has_bgm = bool(bgm_path)
    next_index = n  # 이미지 입력 n개 다음부터 오디오 입력이 붙는다
    bgm_index = None
    if has_bgm:
        cmd += ["-stream_loop", "-1", "-i", _norm(bgm_path)]
        bgm_index = next_index
        next_index += 1

    # ── 나레이션 오디오 입력들 ──
    narr_specs = []  # (input_index, start_sec)
    if narrations:
        for apath, start in narrations:
            cmd += ["-i", _norm(apath)]
            narr_specs.append((next_index, float(start)))
            next_index += 1
    has_narr = bool(narr_specs)

    # ── filter_complex 구성 ──
    filters = []
    # 각 입력 정규화: 크기·SAR·fps
    for i in range(n):
        filters.append(
            f"[{i}:v]scale={width}:{height},setsar=1,fps={fps}[v{i}]"
        )

    if n == 1:
        video_out = "[v0]"
    else:
        cum = 0.0
        prev = "[v0]"
        for i in range(1, n):
            cum += float(slides[i - 1][1])
            # i번째(1-indexed) 전환: 누적 sum(d0..d_{i-1}) 시점에서 xfade 시작하되
            # 이전까지의 xfade 겹침을 빼야 한다 → offset = cum - i*xfade
            offset = cum - i * xfade
            out_label = "[vout]" if i == n - 1 else f"[x{i}]"
            filters.append(
                f"{prev}[v{i}]xfade=transition=fade:"
                f"duration={xfade:g}:offset={offset:g}{out_label}"
            )
            prev = out_label
        video_out = "[vout]"

    # ── 오디오 필터 ──
    audio_out = None
    if has_narr:
        # 나레이션 각각을 지정 시각으로 밀어 넣는다(스테레오 대비 양채널 adelay).
        narr_labels = []
        for k, (idx, start) in enumerate(narr_specs):
            ms = int(round(start * 1000))
            filters.append(f"[{idx}:a]adelay={ms}|{ms}[na{k}]")
            narr_labels.append(f"[na{k}]")

        mix_inputs = list(narr_labels)
        if has_bgm:
            # BGM은 기존 afade 아웃을 유지하면서 volume=0.2로 덕킹.
            fade_start = total_duration(slides, xfade) - BGM_FADEOUT
            if fade_start < 0:
                fade_start = 0.0
            filters.append(
                f"[{bgm_index}:a]afade=t=out:st={fade_start:g}:"
                f"d={BGM_FADEOUT:g},volume=0.2[bgmd]"
            )
            mix_inputs.append("[bgmd]")

        # amix로 합성 후 apad로 영상 길이까지 무음 패딩(-shortest가 최종 길이를 맞춘다).
        # normalize=0: 입력 개수로 볼륨을 나누지 않아 나레이션이 작아지지 않는다.
        filters.append(
            f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:"
            f"duration=longest:dropout_transition=0:normalize=0,apad[aout]"
        )
        audio_out = "[aout]"
    elif has_bgm:
        fade_start = total_duration(slides, xfade) - BGM_FADEOUT
        if fade_start < 0:
            fade_start = 0.0
        filters.append(
            f"[{bgm_index}:a]afade=t=out:st={fade_start:g}:d={BGM_FADEOUT:g}[aout]"
        )
        audio_out = "[aout]"

    cmd += ["-filter_complex", ";".join(filters)]

    # ── 매핑 ──
    cmd += ["-map", video_out]
    has_audio = audio_out is not None
    if has_audio:
        cmd += ["-map", audio_out]

    # ── 출력 인코딩 옵션 ──
    cmd += [
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-r", str(fps),
    ]
    if has_audio:
        cmd += ["-c:a", "aac", "-shortest"]

    cmd.append(_norm(out_path))
    return cmd


def plan_narrated_slides(entries, xfade=XFADE_DURATION):
    """나레이션 길이에 맞춰 슬라이드 노출 시간과 나레이션 시작 시각을 계산한다(순수 함수).

    entries: [(png_path, default_duration, tts_duration_or_None), ...]
      - tts_duration이 None이면 나레이션 없음 → 슬라이드 길이 = default_duration.
      - tts가 있으면 슬라이드 길이 d = max(default, tts + xfade + 0.5)로 늘려
        나레이션이 다음 슬라이드로 넘어가지 않도록 여유를 둔다.

    반환: (slides, narration_starts)
      - slides: [(png_path, duration), ...] → make_clip/build_ffmpeg_cmd에 그대로 넘길 수 있다.
      - narration_starts: entries와 1:1 대응하는 나레이션 시작 시각(초) 리스트.
        (나레이션이 없는 슬라이드도 시작 시각을 담는다. 오디오가 없으면 무시하면 된다.)
        · 슬라이드 i의 최종 타임라인 시작 = sum(d0..d_{i-1}) - i*xfade
        · i==0이면 +0.3초, i>0이면 +xfade(전환 완료 후)에서 나레이션이 시작한다.

    수식상 어떤 나레이션도 다음 슬라이드 구간을 침범하지 않는다
    (offset + tts <= d - xfade 가 항상 성립)."""
    slides = []
    durations = []
    for png, default_dur, tts_dur in entries:
        if tts_dur is None:
            d = float(default_dur)
        else:
            d = max(float(default_dur), float(tts_dur) + xfade + 0.5)
        slides.append((png, d))
        durations.append(d)

    narration_starts = []
    cum = 0.0  # sum(d0..d_{i-1})
    for i in range(len(entries)):
        slide_start = cum - i * xfade
        offset = 0.3 if i == 0 else xfade
        narration_starts.append(slide_start + offset)
        cum += durations[i]

    return slides, narration_starts


def make_clip(slides, out_path, bgm_path=None, on_log=None,
              size=(1080, 1920), fps=30, xfade=XFADE_DURATION, narrations=None):
    """ffmpeg를 실제로 실행해 슬라이드쇼 mp4를 만든다.

    - ffmpeg가 PATH에 없으면 RuntimeError.
    - 실패 시 stderr 마지막 부분을 포함한 RuntimeError.
    - 성공 시 out_path(절대경로)를 반환한다.
    - narrations: [(audio_path, start_sec), ...] TTS 나레이션(선택). build_ffmpeg_cmd 참고.
    on_log: 로그 콜백(문자열 1개 인자). None이면 무시."""
    def _log(msg):
        if on_log:
            on_log(msg)

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg를 찾을 수 없습니다. ffmpeg를 설치하고 PATH에 추가하세요."
        )
    if not slides:
        raise ValueError("slides가 비어 있습니다.")

    cmd = build_ffmpeg_cmd(
        slides, out_path, bgm_path=bgm_path, size=size, fps=fps, xfade=xfade,
        narrations=narrations,
    )
    dur = total_duration(slides, xfade)
    _log(f"🎬 클립 인코딩 시작: {len(slides)}장 → 약 {dur:.1f}초")

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except Exception as e:
        raise RuntimeError(f"ffmpeg 실행 실패: {e}")

    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        tail = "\n".join(stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"ffmpeg 인코딩 실패(코드 {proc.returncode}):\n{tail}")

    _log(f"🎬 클립 생성 완료: {os.path.basename(out_path)} (약 {dur:.1f}초)")
    return _norm(out_path)
