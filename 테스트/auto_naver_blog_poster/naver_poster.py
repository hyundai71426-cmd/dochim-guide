"""네이버 블로그 자동 "임시저장" 모듈 (PyQt5 등 UI 의존성 없음).

생성된 글을 네이버 블로그 스마트에디터원(SmartEditor ONE)에 **순수 텍스트로만**
자동 입력하고 "임시저장"까지만 수행한다. 완전 자동 발행은 하지 않는다(발행 버튼 금지).
이미지 첨부·인용구 등 서식은 사용자가 에디터에서 직접 수동으로 처리하고,
검토 후 직접 발행한다.

Playwright(sync_api)를 사용하지만, playwright import는 함수 내부 지연 import로 처리해
playwright 미설치 환경에서도 이 모듈의 순수 로직(_clean_line, is_logged_in)은
import·테스트할 수 있다.

⚠️ 경고: naver_state.json에 로그인 세션(쿠키)이 저장된다.
   이 파일을 절대 공유·백업·git 커밋하지 말 것 (계정 탈취 위험).

세션 저장 방식 주의: 네이버 NID_AUT는 "로그인 상태 유지" 미체크 시 세션 쿠키라서
persistent context(프로필 폴더) 방식으로는 브라우저를 닫는 순간 소멸된다
(Chromium은 세션 쿠키를 디스크에 영속하지 않음). 그래서 닫기 전에
context.storage_state()로 JSON에 직접 저장한다(세션 쿠키도 storage_state에는 포함됨)."""

import os
import re
import json
import time
import shutil

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 로그인 세션(storage_state)이 저장되는 JSON 파일. 절대 공유/백업/커밋 금지.
STATE_FILE = os.path.join(_BASE_DIR, "naver_state.json")

# 구버전(persistent context 방식)이 만들던 프로필 폴더 — 발견되면 정리 대상.
_LEGACY_PROFILE_DIR = os.path.join(_BASE_DIR, "naver_profile")

# ── 셀렉터 상수 (네이버 UI 변경 시 이곳만 수정하면 되도록 한 곳에 모음) ──
# 각 항목은 [주 셀렉터, 대체 셀렉터] 형태의 2중 폴백 리스트.
SEL_TITLE = [
    ".se-title-text",
    "span.se-placeholder.__se_placeholder",
]
SEL_TITLE_PLACEHOLDER = "[placeholder*='제목']"
SEL_BODY = [
    ".se-component-content .se-text-paragraph",
    ".se-component-content",
]
SEL_SAVE_BUTTON = [
    '.se-save-button',
    'button[data-name="save"]',
    'button:has-text("저장")',
]
# "작성 중인 글" 이어쓰기 다이얼로그 취소 버튼
# 주의: 'button:has-text("취소")' 같은 부분 일치 폴백은 절대 금지 —
# 에디터 툴바의 "취소선" 버튼까지 매칭되어 본문 전체에 취소선이 켜지는 사고가
# 실사용에서 실제로 발생했다. 반드시 팝업 범위 + 정확 일치(text-is)로 제한한다.
SEL_CONTINUE_CANCEL = [
    'button.se-popup-button-cancel',
    '.se-popup button:text-is("취소")',
]
# 도움말 패널 닫기 버튼
SEL_HELP_CLOSE = [
    'button.se-help-panel-close-button',
    '.se-help-panel button[aria-label*="닫기"]',
]
BLOG_WRITE_URL = "https://blog.naver.com/GoBlogWrite.naver"
LOGIN_URL = "https://nid.naver.com/nidlogin.login"


def _clean_line(line):
    """마크다운 라인에서 서식 기호를 제거해 순수 텍스트만 남긴다.

    - "## " / "### " 접두어 제거 (서식 없는 v1 — 소제목도 일반 텍스트로 입력)
    - "**볼드**" 마크다운 기호(**) 제거
    - 앞뒤 공백 정리
    playwright import 없이 단독 테스트할 수 있도록 순수 문자열 로직으로 유지한다."""
    text = line.rstrip("\n")
    stripped = text.lstrip()
    # 소제목 접두어(## / ###) 제거. 더 긴 것부터 검사.
    for prefix in ("###", "##", "#"):
        if stripped.startswith(prefix + " "):
            stripped = stripped[len(prefix) + 1:]
            break
        if stripped.startswith(prefix) and len(stripped) > len(prefix):
            # "##소제목"처럼 공백 없이 붙은 경우도 방어
            rest = stripped[len(prefix):]
            if rest and not rest[0].isspace():
                stripped = rest
                break
    # 볼드/이탤릭 기호 제거 (** 먼저, 그다음 *)
    stripped = stripped.replace("**", "")
    # 남은 단일 * 는 목록 기호가 아닐 때만 제거하지 않고 그대로 둔다(과잉 제거 방지).
    stripped = stripped.strip()

    # 스마트에디터의 목록 자동변환 방지: "1. "을 타이핑하면 에디터가 자동으로 번호
    # 목록을 만들어 이후 줄의 숫자가 "2. 2."처럼 중복 표기되는 문제가 실사용에서
    # 발생했다. 숫자 뒤 공백을 NBSP( )로 바꾸면 보기엔 동일하지만 자동변환이
    # 걸리지 않는다. 불릿("- ", "* ")도 같은 이유로 가운뎃점으로 치환한다.
    m = re.match(r'^(\d+)\.\s+(.*)$', stripped)
    if m:
        stripped = f"{m.group(1)}. {m.group(2)}"
    elif stripped.startswith("- ") or stripped.startswith("* "):
        stripped = "· " + stripped[2:]
    return stripped


def _log(on_log, msg):
    """on_log 콜백이 있으면 호출한다(없으면 무시)."""
    if on_log:
        try:
            on_log(msg)
        except Exception:
            pass


def _has_nid_aut(context):
    """컨텍스트 쿠키에 NID_AUT(로그인 인증 쿠키)가 있는지 확인한다."""
    try:
        for cookie in context.cookies():
            if cookie.get("name") == "NID_AUT" and cookie.get("value"):
                return True
    except Exception:
        pass
    return False


def _cleanup_legacy_profile():
    """구버전(persistent context)이 만든 naver_profile/ 폴더가 있으면 삭제한다(실패 무시)."""
    try:
        if os.path.isdir(_LEGACY_PROFILE_DIR):
            shutil.rmtree(_LEGACY_PROFILE_DIR, ignore_errors=True)
    except Exception:
        pass


def login_naver(headless=False):
    """네이버 로그인 창을 열어 사용자가 직접 로그인하게 하고, 로그인 성공을 감지한다.

    로그인 성공(NID_AUT 감지) 시 컨텍스트를 닫기 **전에** storage_state를 STATE_FILE에
    저장한다. NID_AUT는 세션 쿠키라 persistent context로는 영속되지 않지만,
    storage_state JSON에는 세션 쿠키도 포함되므로 이 방식으로 세션이 유지된다.
    최대 300초 동안 1초 간격으로 NID_AUT 쿠키 생성을 폴링한다.
    성공 시 True, 타임아웃 시 False 반환.
    (headless 인자는 시그니처 호환용이며, 사용자가 직접 로그인해야 하므로 실제로는 창을 띄운다.)"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
            page.goto(LOGIN_URL)
            # 최대 300초 동안 1초 간격으로 NID_AUT 쿠키 확인
            deadline = time.time() + 300
            while time.time() < deadline:
                if _has_nid_aut(context):
                    # 닫기 전에 세션을 JSON으로 저장해야 세션 쿠키가 유실되지 않는다.
                    context.storage_state(path=STATE_FILE)
                    _cleanup_legacy_profile()
                    return True
                time.sleep(1)
            return False
        finally:
            browser.close()


def is_logged_in():
    """STATE_FILE JSON을 직접 읽어 NID_AUT 쿠키 존재 여부를 반환한다.

    브라우저를 띄우지 않으므로 매우 빠르고, playwright 미설치 환경에서도 동작한다."""
    if not os.path.isfile(STATE_FILE):
        return False
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        return False
    for cookie in state.get("cookies", []):
        if cookie.get("name") == "NID_AUT" and cookie.get("value"):
            return True
    return False


def _try_click(target, selectors, timeout=2000):
    """selectors(폴백 리스트)를 순서대로 시도해 첫 성공 클릭을 수행한다.

    target은 Page 또는 Frame 객체. 성공하면 True, 모두 실패하면 False.
    (팝업 정리 등 실패해도 진행해야 하는 곳에서 쓴다.)"""
    for sel in selectors:
        try:
            target.click(sel, timeout=timeout)
            return True
        except Exception:
            continue
    return False


def _find_editor_frame(page, on_log):
    """에디터가 들어있는 iframe(name='mainFrame')을 찾아 frame 객체를 반환한다.

    구형 구조: PostWriteForm.naver가 mainFrame iframe 안에 있음.
    신형 구조: 페이지 자체가 에디터. iframe을 못 찾으면 page를 그대로 반환(폴백)."""
    try:
        page.wait_for_selector("iframe[name='mainFrame']", timeout=8000)
        frame = page.frame(name="mainFrame")
        if frame is not None:
            _log(on_log, "에디터 iframe(mainFrame) 진입")
            return frame
    except Exception:
        pass
    _log(on_log, "mainFrame iframe 미발견 → 페이지 자체를 에디터로 사용(폴백)")
    return page


def _screenshot(page, save_dir, name):
    """실패 지점 스크린샷을 작업 폴더에 남긴다(디버깅용). 경로 문자열 반환(실패 시 빈 문자열)."""
    if not save_dir:
        return ""
    try:
        path = os.path.join(save_dir, name)
        page.screenshot(path=path)
        return path
    except Exception:
        return ""


def post_draft(title, content_lines, image_paths, hashtags,
               on_log=None, headless=False):
    """생성된 글을 네이버 블로그 스마트에디터원에 순수 텍스트로 입력하고 "임시저장"한다.

    인자:
      title: 블로그 제목(문자열)
      content_lines: 마크다운 라인 리스트(##/### 포함 원문 그대로 — 서식 기호는 제거 후 입력)
      image_paths: 작업 폴더의 이미지 절대경로 리스트 — 업로드하지 않는다.
        실패 스크린샷을 저장할 작업 폴더를 알아내는 용도로만 쓴다.
      hashtags: "#태그1 #태그2 ..." 형태의 해시태그 문자열
      on_log: 진행 로그 콜백(str) — 단계마다 호출
      headless: 기본 False(자동화 과정이 보이는 편이 신뢰성·디버깅에 유리)

    반환: 성공 시 True. 각 단계 실패 시 스크린샷을 남기고 RuntimeError를 던진다.

    입력 범위 (사용자 결정 — 텍스트만 자동화, 나머지는 수동):
      - 제목/본문/해시태그를 순수 텍스트로만 입력한다. 소제목(##/###)도 서식 기호만
        제거하고 일반 텍스트로 입력하며, 인용구·볼드 등 서식은 적용하지 않는다.
      - 이미지는 첨부하지 않는다. 사용자가 에디터에서 직접 첨부·배치한다.
      - "발행"이 아니라 "임시저장"까지만 수행한다.
    """
    from playwright.sync_api import sync_playwright

    # 저장된 로그인 세션(storage_state)이 없으면 브라우저를 띄울 필요도 없이 중단.
    # ("로그인이 필요합니다" 부분 문자열은 main.py가 매칭하므로 문구 유지)
    if not os.path.isfile(STATE_FILE):
        raise RuntimeError(
            "로그인이 필요합니다. 설정 탭에서 네이버 로그인을 먼저 해주세요."
        )

    image_paths = image_paths or []
    # 스크린샷을 남길 작업 폴더: 첫 이미지가 있으면 그 폴더, 없으면 모듈 폴더.
    save_dir = os.path.dirname(image_paths[0]) if image_paths else _BASE_DIR

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            storage_state=STATE_FILE,
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        try:
            # 1) 글쓰기 페이지 이동
            _log(on_log, "글쓰기 페이지로 이동 중...")
            page.goto(BLOG_WRITE_URL, wait_until="domcontentloaded")
            time.sleep(2)

            # 2) 로그인 필요 여부 확인 (세션 만료 시 로그인 페이지로 리다이렉트됨)
            if "nid.naver.com" in page.url:
                raise RuntimeError(
                    "로그인이 필요합니다. 설정 탭에서 네이버 로그인을 먼저 해주세요."
                )

            # 3) 에디터 iframe 진입 (없으면 page 폴백)
            frame = _find_editor_frame(page, on_log)

            # 4) 팝업 정리 (실패해도 진행)
            if _try_click(frame, SEL_CONTINUE_CANCEL, timeout=2000):
                _log(on_log, "'작성 중인 글' 이어쓰기 팝업 → 취소(새 글로 시작)")
            if _try_click(frame, SEL_HELP_CLOSE, timeout=1500):
                _log(on_log, "도움말 패널 닫음")

            # 5) 제목 입력 (contenteditable이라 fill 대신 클릭+키보드 타이핑)
            _log(on_log, "제목 입력 중...")
            if not _try_click(frame, SEL_TITLE, timeout=5000):
                if not _try_click(frame, [SEL_TITLE_PLACEHOLDER], timeout=3000):
                    _screenshot(page, save_dir, "err_title.png")
                    raise RuntimeError("제목 입력 영역을 찾지 못했습니다.")
            page.keyboard.type(title, delay=0)
            _log(on_log, "제목 입력 완료")

            # 6) 본문 입력
            _log(on_log, "본문 입력 중...")
            if not _try_click(frame, SEL_BODY, timeout=5000):
                _screenshot(page, save_dir, "err_body.png")
                raise RuntimeError("본문 입력 영역을 찾지 못했습니다.")

            for raw in content_lines:
                cleaned = _clean_line(raw)
                if cleaned:
                    page.keyboard.type(cleaned, delay=0)
                # 각 라인 뒤 Enter (빈 줄도 Enter 한 번으로 처리)
                page.keyboard.press("Enter")

            # 본문 마지막에 빈 줄 2개 + 해시태그
            if hashtags:
                page.keyboard.press("Enter")
                page.keyboard.press("Enter")
                page.keyboard.type(hashtags, delay=0)
            _log(on_log, "본문 입력 완료")

            # 7) 임시저장 ("발행" 버튼은 절대 클릭 금지 — 저장 버튼만)
            # (이미지는 첨부하지 않는다 — 사용자가 에디터에서 직접 수동 첨부)
            _log(on_log, "임시저장 중...")
            if not _try_click(frame, SEL_SAVE_BUTTON, timeout=5000):
                _screenshot(page, save_dir, "err_save.png")
                raise RuntimeError("임시저장(저장) 버튼을 찾지 못했습니다.")
            # 저장 완료 토스트/카운트 증가 대기
            time.sleep(3)

            _log(on_log, "✅ 임시저장 완료")
            return True
        except RuntimeError:
            raise
        except Exception as e:
            _screenshot(page, save_dir, "err_unexpected.png")
            raise RuntimeError(f"자동 임시저장 중 오류: {e}")
        finally:
            browser.close()
