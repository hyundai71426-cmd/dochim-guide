@echo off
cd /d "%~dp0"
title auto_blog_poster 설치

echo ============================================
echo  auto_blog_poster 설치를 시작합니다
echo ============================================
echo.

REM ── [1/5] Python 확인 ──────────────────────────
echo [1/5] Python 확인 중...
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [X] Python이 설치되어 있지 않습니다.
    echo       지금 여는 페이지에서 Python 3.13을 설치하세요.
    echo       ※ 설치 첫 화면에서 "Add python.exe to PATH" 반드시 체크!
    echo       설치가 끝나면 이 setup.bat 을 다시 실행하세요.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo   [OK] %%v 확인됨
echo.

REM ── [2/5] 파이썬 패키지 설치 ───────────────────
echo [2/5] 파이썬 패키지 설치 중... (PyQt5, playwright, edge-tts 등)
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo   [X] 패키지 설치에 실패했습니다. 인터넷 연결을 확인하고 다시 실행하세요.
    pause
    exit /b 1
)
echo   [OK] 패키지 설치 완료
echo.

REM ── [3/5] Playwright Chromium 설치 (네이버 임시저장용) ──
echo [3/5] Playwright Chromium 브라우저 설치 중... (수 분 걸릴 수 있음)
python -m playwright install chromium
if errorlevel 1 (
    echo   [주의] Chromium 설치 실패 - 네이버 자동 임시저장 기능만 안 됩니다.
    echo          나중에 직접 실행: python -m playwright install chromium
) else (
    echo   [OK] Chromium 설치 완료
)
echo.

REM ── [4/5] ffmpeg 확인 (클립 영상/TTS용) ────────
echo [4/5] ffmpeg 확인 중...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo   ffmpeg가 없어 winget으로 설치를 시도합니다...
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo   [주의] ffmpeg 자동 설치 실패 - 클립 영상 기능만 안 됩니다.
        echo          수동 설치: https://www.gyan.dev/ffmpeg/builds/ 에서 받아 PATH에 추가하세요.
    ) else (
        echo   [OK] ffmpeg 설치 완료
        echo   ※ PATH 반영을 위해 컴퓨터를 재시작하거나 로그아웃/로그인이 필요할 수 있습니다.
    )
) else (
    echo   [OK] ffmpeg 확인됨
)
echo.

REM ── [5/5] Chrome 확인 (카드뉴스 이미지 캡처용) ──
echo [5/5] Chrome 브라우저 확인 중...
set "CHROME_FOUND="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1
if defined CHROME_FOUND (
    echo   [OK] Chrome 확인됨
) else (
    echo   [주의] Chrome이 없습니다 - 썸네일/카드뉴스 이미지 캡처가 안 될 수 있습니다.
    echo          https://www.google.com/chrome/ 에서 설치하세요.
)
echo.

echo ============================================
echo  설치 완료!
echo ============================================
echo.
echo  실행 방법: run.bat 더블클릭 (또는: python main.py)
echo.
echo  처음 할 일:
echo   1. 설정 탭에서 API 키 입력 (LLM + 네이버 검색/검색광고)
echo   2. 설정 탭에서 "네이버 블로그 로그인" 한 번 실행
echo.
pause
