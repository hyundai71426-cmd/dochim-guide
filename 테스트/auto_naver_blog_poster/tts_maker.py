"""edge-tts로 나레이션 mp3를 만들고 길이를 재는 모듈.

PyQt5 무의존. 표준 라이브러리 + edge-tts(지연 import) + ffprobe(subprocess)만 사용한다.

- clean_narration(): 카드 텍스트의 강조 마커(**)를 제거하고 공백/개행을 정리하는 순수 함수.
- synthesize(): edge-tts로 mp3를 생성한다(async API를 asyncio.run으로 감싼다).
- probe_duration(): ffprobe로 오디오 길이(초)를 잰다.

edge-tts는 async 라이브러리이므로 synthesize 내부에서 지연 import 후 asyncio.run으로 실행한다.
미설치 시 명확한 안내 메시지를 담은 RuntimeError를 던진다(playwright 처리 방식과 동일 컨벤션).
"""

import os
import re
import shutil
import subprocess


# 기본 목소리(한국어 여성).
DEFAULT_VOICE = "ko-KR-SunHiNeural"

# 설정 UI에서 노출할 목소리 선택지. (voice_id, 표시 이름)
VOICES = [
    ("ko-KR-SunHiNeural", "선히 (여성)"),
    ("ko-KR-InJoonNeural", "인준 (남성)"),
    ("ko-KR-HyunsuMultilingualNeural", "현수 (남성)"),
]


def clean_narration(text):
    """나레이션용 텍스트를 정리한다(순수 함수).

    - 강조용 `**단어**` 마커의 `**`를 제거한다.
    - 연속된 공백/개행/탭을 공백 1칸으로 합치고 양끝을 다듬는다.
    이모지는 제거하지 않는다(edge-tts가 알아서 무시한다)."""
    if not text:
        return ""
    t = text.replace("**", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def synthesize(text, out_path, voice=DEFAULT_VOICE, rate="+0%"):
    """edge-tts로 text를 읽어 out_path(mp3)로 저장하고 절대경로를 반환한다.

    - 빈 텍스트(공백만 포함)면 ValueError.
    - edge-tts 미설치 시 안내 메시지를 담은 RuntimeError.
    - voice: edge-tts 음성 ID. rate: "+0%" 같은 속도 조절 문자열."""
    if not text or not text.strip():
        raise ValueError("나레이션 텍스트가 비어 있습니다.")

    try:
        import edge_tts  # 지연 import: 미설치 환경에서도 모듈 로드 자체는 되도록.
    except ImportError:
        raise RuntimeError(
            "edge-tts가 설치되어 있지 않습니다. "
            "다음 명령으로 설치하세요: pip install edge-tts"
        )

    import asyncio

    dest = os.path.abspath(out_path)

    async def _run():
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(dest)

    asyncio.run(_run())
    return dest


def probe_duration(path):
    """ffprobe로 오디오/영상 파일의 길이(초, float)를 반환한다.

    ffprobe가 PATH에 없거나 실패하면 RuntimeError."""
    if shutil.which("ffprobe") is None:
        raise RuntimeError(
            "ffprobe를 찾을 수 없습니다. ffmpeg(ffprobe 포함)를 설치하고 PATH에 추가하세요."
        )

    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        os.path.abspath(path),
    ]
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False
        )
    except Exception as e:
        raise RuntimeError(f"ffprobe 실행 실패: {e}")

    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffprobe 실패(코드 {proc.returncode}): {stderr}")

    out = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    try:
        return float(out)
    except (ValueError, TypeError):
        raise RuntimeError(f"ffprobe 길이 파싱 실패: {out!r}")
