"""네이버 자동 임시저장 수동 검증용 CLI 스크립트 (unittest 아님).

실제 네이버 계정 로그인이 필요하므로 자동 테스트로 돌릴 수 없다.
사용자가 본인 계정으로 직접 동작을 확인할 때 쓰는 도구다.

사용법:
  python test_post_draft.py login   → 로그인 창을 띄워 직접 로그인(세션 저장)
  python test_post_draft.py draft   → 더미 제목/본문 3줄/이미지 없음으로 임시저장 테스트
"""

import sys

import naver_poster


def _log(msg):
    print(f"[LOG] {msg}")


def do_login():
    print("네이버 로그인 창을 엽니다. 창에서 직접 로그인하세요 (최대 300초 대기)...")
    ok = naver_poster.login_naver()
    if ok:
        print("✅ 로그인 성공 (세션이 naver_state.json에 저장됨 — 이 파일 공유 금지)")
    else:
        print("❌ 로그인 타임아웃 (300초 내 로그인 감지 실패)")


def do_draft():
    # 저장된 세션 유무를 파일만 읽어 빠르게 확인 (playwright 불필요)
    if not naver_poster.is_logged_in():
        print("⚠️ 저장된 로그인 세션이 없습니다. 먼저 'python test_post_draft.py login'을 실행하세요.")
        return
    title = "자동 임시저장 테스트 제목"
    content_lines = [
        "## 첫 번째 소제목",
        "이것은 자동 임시저장 테스트 본문 첫 줄이다.",
        "이것은 **굵게** 표시하려던 두 번째 줄이다.",
    ]
    print("더미 글을 네이버 블로그에 임시저장합니다...")
    ok = naver_poster.post_draft(
        title=title,
        content_lines=content_lines,
        image_paths=[],
        hashtags="#테스트 #자동저장",
        on_log=_log,
    )
    print("✅ 임시저장 완료" if ok else "❌ 실패")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("login", "draft"):
        print("사용법: python test_post_draft.py [login|draft]")
        return
    if sys.argv[1] == "login":
        do_login()
    else:
        do_draft()


if __name__ == "__main__":
    main()
