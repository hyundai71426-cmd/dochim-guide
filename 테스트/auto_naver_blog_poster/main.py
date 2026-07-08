import sys
import os
import re
import time
import webbrowser
import requests
from bs4 import BeautifulSoup

# PyQt5 wheel 배포판에 qt.conf가 빠져 있으면(백신 격리, 불완전 설치 등) Qt가 플러그인 폴더
# 위치를 스스로 못 찾아 "Could not find the Qt platform plugin windows" 오류로 앱이 아예 안 뜬다.
# 하드코딩된 절대경로 없이, 실제 설치된 PyQt5 패키지 위치를 기준으로 플러그인 폴더를 찾아
# QApplication 생성 전에 환경변수로 알려줘서 이 문제를 자동으로 우회한다.
try:
    import PyQt5
    _qt_plugin_path = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins", "platforms")
    if os.path.isdir(_qt_plugin_path):
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", _qt_plugin_path)
except ImportError:
    pass

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTextEdit, QPushButton, QLabel, QProgressBar, QTabWidget, QComboBox,
    QCheckBox, QLineEdit, QDialog, QListWidget, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QRadioButton, QButtonGroup
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QColor
from html2image import Html2Image

import config_manager
import providers
import textutils
import naver_keywords
import sns_package
import video_maker
import tts_maker


class BlogGeneratorThread(QThread):
    progress_signal = pyqtSignal(str)
    progress_value = pyqtSignal(int)
    finished_signal = pyqtSignal(str, str)
    error_signal = pyqtSignal(str)

    def __init__(self, titles, provider_cfg, make_thumbnail, make_images, naver_cfg=None,
                 make_sns=True, make_clip=True, video_cfg=None, make_tts=True, title_mode="home"):
        super().__init__()
        self.titles = titles
        self.provider_cfg = provider_cfg
        self.make_thumbnail = make_thumbnail
        self.make_images = make_images
        # "home"(홈판용 클릭유도형) | "info"(정보전달용 SEO형) - 제목 규칙·본문 톤/분량·
        # 크롤링 개수를 이 값에 따라 분기한다.
        self.title_mode = title_mode
        # SNS 패키지(카드뉴스+공용 본문) 생성 여부. 글 생성 완료 직전에 수행한다.
        self.make_sns = make_sns
        # 네이버 클립(세로 숏폼) 슬라이드쇼 영상 생성 여부. make_sns가 켜져 있을 때만 의미 있다.
        self.make_clip = make_clip
        # 클립에 TTS 나레이션 삽입 여부. make_clip이 켜져 있을 때만 의미 있다.
        self.make_tts = make_tts
        # 클립 설정(config.json의 "video" 섹션). bgm_path 등. 없으면 빈 dict.
        self.video_cfg = video_cfg or {}
        # 네이버 검색 API 키(config.json의 "naver" 섹션). 없으면 빈 dict로 두고 search_naver에서 방어.
        self.naver_cfg = naver_cfg or {}
        self.output_dir = self.make_job_dir(titles)
        self.hti = Html2Image(size=(800, 450), output_path=self.output_dir)
        # 네이버 자동 임시저장에 필요한 산출물(제목/본문/해시태그/이미지 경로)을 담을 자리.
        # run() 완료 직전에 채워지며, MainWindow가 on_finished에서 복사해 사용한다.
        self.last_post_data = None

    def make_job_dir(self, titles):
        """작업마다 독립된 폴더를 만들어 그 안에 preview.html과 이미지 파일들을 저장한다."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        results_root = os.path.join(base_dir, "results")
        os.makedirs(results_root, exist_ok=True)

        title_lines = self.clean_title_lines(titles)
        first_line = title_lines[0] if title_lines else "블로그"
        safe_name = re.sub(r'[\\/*?:"<>|]', '', first_line).strip()
        safe_name = re.sub(r'\s+', '_', safe_name)[:30]
        # Windows는 폴더/파일명이 마침표·공백으로 끝나는 것을 허용하지 않고 자동으로 잘라내므로,
        # (예: "...논란.." → "...논란") 여기서 미리 제거하지 않으면 os.makedirs로 만든 실제 폴더명과
        # 파이썬이 들고 있는 경로 문자열이 어긋나 이후 파일 열기에서 FileNotFoundError가 발생한다.
        safe_name = safe_name.rstrip('. ') or "블로그"

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        job_dir = os.path.join(results_root, f"{timestamp}_{safe_name}")
        os.makedirs(job_dir, exist_ok=True)
        return job_dir

    def log(self, msg):
        """진행 메시지를 UI(진행 로그 패널)로 보내는 동시에 작업 폴더의 log.txt에도 남긴다.
        네이버 크롤링이 실제로 몇 건을 가져왔는지 등을 나중에도 확인할 수 있게 하기 위함."""
        self.progress_signal.emit(msg)
        try:
            with open(os.path.join(self.output_dir, "log.txt"), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    def call_api(self, prompt, max_tokens=4000, retries=3):
        """선택된 공급자(Claude/Gemini/ChatGPT/Ollama)로 API 호출 (일시적 오류는 재시도)"""
        return providers.chat(
            provider=self.provider_cfg["provider"],
            api_key=self.provider_cfg["api_key"],
            base_url=self.provider_cfg["base_url"],
            model=self.provider_cfg["model"],
            prompt=prompt,
            max_tokens=max_tokens,
            retries=retries,
            on_retry=self.log,
        )

    def clean_title_lines(self, raw_titles):
        """붙여넣은 제목 목록에서 순번만 있는 줄을 걸러낸다 (textutils 위임 래퍼)."""
        return textutils.clean_title_lines(raw_titles)

    def extract_main_keyword(self, title_lines):
        """제목들에서 공통 핵심 개념어를 뽑아 검색어로 조합한다 (textutils 위임 래퍼)."""
        return textutils.extract_main_keyword(title_lines)

    def extract_headings(self, text):
        """마크다운에서 H2 소제목만 추출한다 (textutils 위임 래퍼)."""
        return textutils.extract_headings(text)

    def capture_html(self, html_code, filename, size=None):
        """HTML 코드를 이미지 파일로 캡처. size 미지정 시 기본 카드 크기(800x450) 사용."""
        temp_path = os.path.join(self.output_dir, f"_temp_{filename}.html")
        out_path = os.path.join(self.output_dir, filename)
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(html_code)
            kwargs = {"html_file": temp_path, "save_as": filename}
            if size:
                kwargs["size"] = size
            self.hti.screenshot(**kwargs)
            return out_path
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def search_naver(self, query, search_type="blog", display=5):
        """네이버 검색 API 호출 (blog 또는 news). 키는 config.json의 "naver" 섹션에서 읽는다."""
        client_id = self.naver_cfg.get("search_client_id", "")
        client_secret = self.naver_cfg.get("search_client_secret", "")
        if not client_id or not client_secret:
            self.log("⚠️ 네이버 검색 API 키가 config.json에 없습니다")
            return ""
        url = f"https://openapi.naver.com/v1/search/{search_type}.json"
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret
        }
        params = {"query": query, "display": display, "sort": "sim"}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=5)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            self.log(f"📰 네이버 {search_type} 검색: '{query}' 요청(display={display}) → {len(items)}건 응답 수신")
            results = []
            for i, item in enumerate(items, 1):
                # HTML 태그 제거
                title = re.sub(r'<[^>]+>', '', item.get('title', ''))
                desc  = re.sub(r'<[^>]+>', '', item.get('description', ''))
                self.log(f"  [{i}/{len(items)}] {title}")
                results.append(f"- {title}: {desc}")
            return "\n".join(results)
        except Exception as e:
            self.log(f"❌ 네이버 {search_type} 검색 오류: {e}")
            return f"(검색 오류: {e})"

    def crawl_naver_blogs(self, query, count=3):
        """네이버 모바일 통합검색에서 실제 상위노출 중인 블로그 글을 찾아 본문을 크롤링.
        오픈API의 '관련도순' 결과와 달리 실제 검색 화면 노출 순서를 반영한다."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; SM-S911N) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
            )
        }
        try:
            resp = requests.get(
                "https://m.search.naver.com/search.naver",
                headers=headers, params={"query": query}, timeout=5
            )
            resp.raise_for_status()
            # 블로그ID/글번호 형태(실제 포스트)만 매칭. 프로필/홈 링크(글번호 없음)는 제외.
            found_urls = re.findall(
                r'href="(https?://(?:m\.)?blog\.naver\.com/[^/"]+/\d+)(?:[?"])',
                resp.text
            )

            seen = set()
            blog_urls = []
            for u in found_urls:
                base = u.split('?')[0].replace("://blog.naver.com", "://m.blog.naver.com")
                if base in seen:
                    continue
                seen.add(base)
                blog_urls.append(base)
                if len(blog_urls) >= count:
                    break

            self.log(
                f"📝 네이버 블로그 검색: '{query}' → 후보 URL {len(found_urls)}개 중 "
                f"중복 제거 후 상위 {len(blog_urls)}개(목표 {count}개) 크롤링 시도"
            )

            results = []
            for i, url in enumerate(blog_urls, 1):
                try:
                    time.sleep(0.5)
                    page = requests.get(url, headers=headers, timeout=5)
                    page.raise_for_status()
                    page.encoding = page.apparent_encoding
                    soup = BeautifulSoup(page.text, "html.parser")
                    content = (
                        soup.select_one("div.se-main-container")
                        or soup.select_one("div#viewTypeSelector")
                        or soup.select_one("div.post_ct")
                    )
                    if not content:
                        self.log(f"  [{i}/{len(blog_urls)}] {url} → 본문 영역 없음, 스킵")
                        continue
                    text = content.get_text(separator="\n", strip=True)
                    self.log(f"  [{i}/{len(blog_urls)}] {url} → 크롤링 성공 ({len(text)}자)")
                    results.append(f"[참고 블로그 원문 - {url}]\n{text[:1200]}")
                except Exception as e:
                    self.log(f"  [{i}/{len(blog_urls)}] {url} → 크롤링 실패: {e}")
                    continue

            self.log(f"📝 네이버 블로그 크롤링 완료: {len(results)}/{len(blog_urls)}개 본문 확보")

            if not results:
                return "(상위노출 블로그 크롤링 결과 없음)"
            return "\n\n".join(results)
        except Exception as e:
            self.log(f"❌ 블로그 크롤링 오류: {e}")
            return f"(블로그 크롤링 오류: {e})"

    def run(self):
        try:
            is_info_mode = self.title_mode == "info"
            # 정보전달용은 경험 관점 오버레이 단계가 빠지므로 총 단계 수가 하나 적다
            # (홈판용: 분석→크롤링→초안→경험→윤문→이미지 6단계 / 정보전달용: 분석→크롤링→초안→윤문→이미지 5단계).
            total_steps = 5 if is_info_mode else 6
            step_draft, step_experience = 3, 4
            step_proofread = 4 if is_info_mode else 5
            step_image = 5 if is_info_mode else 6

            title_lines = self.clean_title_lines(self.titles)
            cleaned_titles = "\n".join(title_lines) if title_lines else self.titles.strip()
            # 파이썬 빈도 기반 추출 결과 - Step 0 LLM 분석이 실패했을 때의 폴백으로만 쓰인다.
            fallback_keyword = self.extract_main_keyword(title_lines) if title_lines else cleaned_titles.split('\n')[0]

            # ── STEP 0: 메인키워드 · 논조 · 소제목 개요 분석 (LLM) ──────
            self.log(f"Step 1/{total_steps} : 메인키워드·논조·소제목 분석 중...")
            self.progress_value.emit(5)

            prompt_keyword_analysis = f"""
아래는 블로그 글감으로 붙여넣은 참고 제목들입니다. 이 제목들을 분석해서 다음 3가지를 결정하세요.

참고 제목들:
{cleaned_titles}

[분석 기준]
1. 메인키워드: 이 제목들 전체를 관통하는 핵심 검색 키워드 문구(예: "대장암 초기증상"). 여러 단어로
   구성돼도 좋지만, 실제 사람들이 네이버에 검색할 법한 자연스러운 붙여쓰기 구(句) 형태로만 뽑고
   3단어를 넘지 않게 하세요.
2. 논조/타겟독자: 제목들의 공통된 톤(정보성/후기성/경고성 등)과 타겟 독자층을 한 문장으로.
3. 소제목 개요: 이 주제로 글을 쓸 때 독자가 검색 의도상 궁금해할 순서대로 소제목(H2) 후보를
   3~6개, 짧은 구 형태로 나열.

[출력 형식 - 반드시 이 마커만 사용]
===KEYWORD===
(메인키워드 한 줄)
===TONE===
(논조/타겟독자 한 줄)
===OUTLINE===
- 소제목 후보1
- 소제목 후보2

[절대 금지]
- 위 출력 형식 이외의 어떠한 말도 출력하지 마세요.
"""
            raw_analysis = self.call_api(prompt_keyword_analysis, max_tokens=500)
            analysis = textutils.parse_keyword_analysis(raw_analysis, fallback_keyword=fallback_keyword)
            main_keyword = analysis["keyword"] or fallback_keyword
            tone_guide = analysis["tone"]
            outline_guide = analysis["outline"]

            if main_keyword == fallback_keyword and not tone_guide and not outline_guide:
                self.log(f"⚠️ 키워드 분석 응답 파싱 실패 - 기존 빈도 기반 방식으로 폴백: '{main_keyword}'")
            else:
                self.log(f"Step 1/{total_steps} 완료 - 메인키워드: '{main_keyword}' / 논조: {tone_guide or '(분석 없음)'}")
                if outline_guide:
                    self.log(f"  추천 소제목 개요: {' / '.join(outline_guide)}")

            # ── STEP 1: 네이버 블로그 & 뉴스 검색 (사실관계 조사) ──────
            self.log(f"Step 2/{total_steps} : '{main_keyword}' 키워드로 네이버 상위노출 블로그 & 뉴스 검색 중...")
            self.progress_value.emit(10)
            # 정보전달용은 연관 키워드를 검색 자료에서 직접 뽑아 써야 하므로 블로그 크롤링 개수를 늘린다.
            blog_count = 5 if is_info_mode else 3
            blog_results = self.crawl_naver_blogs(main_keyword, count=blog_count)
            news_results = self.search_naver(main_keyword, "news", display=5)

            search_context = f"""
[네이버 실제 상위노출 블로그 {blog_count}개 - 원문 발췌]
{blog_results}

[네이버 뉴스 검색 결과 - 최신 5개 요약]
{news_results}
"""

            # ── STEP 2: 정보 초안 작성 (경험 없이 사실/구조에만 집중) ──
            self.log(f"Step {step_draft}/{total_steps} : 정보 초안 작성 중...")
            self.progress_value.emit(20)

            outline_text = "\n".join(f"- {h}" for h in outline_guide) if outline_guide else "(없음 - 검색 자료로 직접 구성)"

            if is_info_mode:
                title_rule_block = f"""[제목 규칙 - 반드시 지킬 것]
- 제목 맨 앞에 메인키워드 "{main_keyword}"를 그대로 배치하세요(다른 단어를 앞에 붙이지 마세요).
- 그 뒤에 위 [사실관계 참고 자료]에서 실제로 등장하는 연관어를 1~2개 자연스럽게 이어 붙여 검색
  유입에 도움이 되는 제목을 만드세요. 억지로 끼워 맞추지 말고 실제 자료에 등장하는 표현만 쓰세요."""
                extra_writing_rules = """- 문장은 ~습니다/~해요 체의 존댓말로 작성하세요.
- 어려운 전문용어는 풀어서, 어린이도 이해할 수 있을 만큼 쉬운 단어로 설명하세요.
- 모바일 화면에서 읽기 편하도록 한 문장이 너무 길어지지 않게 적당히 끊어서 작성하세요.
- 전체 본문 분량은 공백 포함 2500~5000자 내외로, 정보가 풍부하되 과하지 않게 작성하세요."""
                length_rule = "- 전체 본문 분량은 공백 포함 2500~5000자 내외로 유지하세요."
            else:
                title_rule_block = f"""[제목 규칙 - 반드시 지킬 것]
- 아래 4가지 홈판(네이버 메인 노출)용 후킹 패턴 중, 이 글감에 가장 잘 어울리는 것을 하나만 골라
  제목을 쓰세요.
  ① 의외의 반전으로 호기심을 자극하는 유형
  ② 손해·실패를 피하고 싶은 심리를 자극하는 유형
  ③ 내돈내산·경험담처럼 현실감이 느껴지는 유형
  ④ 가성비·효율을 극대화한 리스트형
- 제목에는 메인키워드 "{main_keyword}"를 중간에 다른 단어를 끼워 넣지 말고 하나로 붙여서 그대로
  포함하세요. 예를 들어 메인키워드가 "대장암 초기증상"이면 제목에 "대장암 초기증상"이 통째로
  들어가야 하며, "대장암 이럴 때 초기증상"처럼 사이에 다른 말을 끼워 쪼개면 안 됩니다."""
                extra_writing_rules = ""
                length_rule = "- 전체 본문 분량은 공백 포함 2000~2500자 내외로 유지하세요."

            prompt_draft = f"""
당신은 독자 중심 정보성 블로그 콘텐츠를 쓰는 전문 에디터입니다.
이 단계에서는 경험담이나 개인적 문체를 넣지 마세요. 정보의 정확성, 충실도, 논리적 구조에만 집중하세요.
(개인적 경험/문체는 다음 단계에서 별도로 입혀집니다.)

[핵심 원칙 - 가장 중요]
이 글은 "제가 이런 걸 써봤으니 읽어주세요"가 아니라, 독자가 이 주제를 검색한 이유(궁금한 점, 해결하고 싶은 문제)에서 출발해서 써야 합니다.
- 도입부는 필자 소개나 인사말이 아니라, 독자의 궁금증·고민을 짚어주는 데서 시작하세요.
- 소제목 순서는 독자가 검색했을 때 자연스럽게 궁금해할 순서(개념 → 대안/비교 → 시작 방법 → 주의할 점 등)를 따르세요.
- 결론은 "저는 이렇게 할 겁니다"가 아니라 독자가 지금 당장 뭘 하면 되는지로 마무리하세요.

참고 블로그 제목들 (글감):
{cleaned_titles}

[사전 분석 결과 - 참고용]
- 메인키워드: {main_keyword}
- 논조/타겟독자: {tone_guide or '(제목들에서 직접 판단하세요)'}
- 추천 소제목 개요(개수·표현은 자유롭게 조정 가능):
{outline_text}

[사실관계 참고 자료 - 네이버 실시간 검색 결과]
{search_context}
위 자료의 사실관계는 절대 왜곡하지 말고, 정확한 정보만 활용하세요.

[작성 규칙]
- 위 논조/타겟독자 분석을 반영하세요.
- 소제목(##) 개수는 고정하지 마세요. 검색 자료 중 독자에게 중요한 내용이 많으면 늘리고, 아니면 줄이세요. 개수보다 술술 읽히는 흐름이 우선입니다.
- 대안/선택지가 여러 개면 장단점을 나열하고, 독자 상황별로("예산이 부족하다면 A, 품질이 중요하다면 B") 다르게 추천하세요.
- 가격/스펙/일정처럼 항목별로 값을 비교·정리하는 내용은 문장으로 풀어쓰지 말고 마크다운 표(| 항목 | 값 |
  형식, 첫 행은 헤더, 둘째 행은 |---|---| 구분선)로 정리하세요. 표는 정보가 실제로 표 형태에 맞을 때만
  쓰고 억지로 만들지 마세요.
- 검색 노출만을 위한 억지 키워드 반복이나 문맥에 안 맞는 키워드 삽입은 절대 금지합니다.
{length_rule}
- 마크다운 형식(## 소제목, ### 세부제목, **굵게** 등)을 사용하세요.
{extra_writing_rules}
- 블로그 본문 작성 완료 후 반드시 ===HASHTAGS=== 구분자를 넣고,
  그 아래에 네이버 블로그용 한국어 해시태그를 정확히 30개 # 기호로 공백 구분하여 출력하세요.

{title_rule_block}

[출력 형식]
(독자의 클릭을 이끌 후킹형 블로그 제목, 한 줄. 메인키워드 "{main_keyword}" 통째 포함 필수)
===TITLE_END===
(블로그 본문)
===HASHTAGS===
#해시태그1 #해시태그2 ... (총 30개)

[절대 금지]
- 위 출력 형식 이외의 어떠한 말도 출력하지 마세요.
- "원하시면 ~해드릴게요", "추가로 ~도 생성할 수 있습니다" 같은 AI 제안 문구 완전 금지.
"""
            # 정보전달용은 목표 분량이 최대 5000자(~7000토큰)라 기존 5000으로는 잘릴 수 있어 상향한다.
            raw_draft = self.call_api(prompt_draft, max_tokens=7000 if is_info_mode else 5000)

            # 제목 분리
            if '===TITLE_END===' in raw_draft:
                title_part, rest_draft = raw_draft.split('===TITLE_END===', 1)
                blog_title = title_part.strip()
            else:
                blog_title = ""
                rest_draft = raw_draft

            # 본문과 해시태그 분리
            if '===HASHTAGS===' in rest_draft:
                parts = rest_draft.split('===HASHTAGS===')
                draft_text = parts[0].strip()
                hashtags = parts[1].strip()
            else:
                draft_text = rest_draft.strip()
                hashtags = ""

            # 해시태그 개수 확인 (요청은 30개). 재요청은 하지 않고 경고 로그만 남긴다.
            hashtag_count = hashtags.count('#')
            if hashtag_count != 30:
                self.log(f"⚠️ 해시태그 {hashtag_count}개 생성됨 (요청 30개)")

            # 제목 규칙 검증 - 실패 시 제목만 최대 2회 재요청.
            # (사용자 결정: 검증 실패 시 재시도. 본문/해시태그까지 통째로 재생성하면 비싸고 느리므로
            # 제목만 짧게 다시 요청하는 별도의 소형 API 호출로 처리한다.)
            # 홈판용: 메인키워드가 끊기지 않고 "포함"되면 통과. 정보전달용: 메인키워드로 "시작"해야 통과.
            if is_info_mode:
                title_ok = lambda t: textutils.title_starts_with_keyword(t, main_keyword)
                title_violation_desc = f"메인키워드 '{main_keyword}'로 시작하지 않음"
                fix_title_instruction = (
                    f'메인키워드 "{main_keyword}"가 제목 맨 앞에 그대로 와야 합니다.\n\n'
                    f"이 제목을 규칙에 맞게 다시 작성하세요. 제목 맨 앞에 "
                    f'"{main_keyword}"를 그대로 배치하고, 뒤에 자연스러운 연관어를 이어 붙이세요.'
                )
            else:
                title_ok = lambda t: textutils.title_contains_keyword(t, main_keyword)
                title_violation_desc = f"메인키워드 '{main_keyword}'가 끊기지 않고 포함되지 않음"
                fix_title_instruction = (
                    f'메인키워드 "{main_keyword}"가 중간에 다른 단어 없이 하나로 붙어서 정확히 그대로 '
                    f"포함되어야 합니다.\n\n이 제목을 규칙에 맞게 다시 작성하세요. 독자의 클릭을 이끄는 "
                    f'후킹형 문구는 유지하되, "{main_keyword}"는 반드시 끊기지 않고 통째로 들어가게 하세요.'
                )

            MAX_TITLE_RETRIES = 2
            title_retry_count = 0
            while not title_ok(blog_title) and title_retry_count < MAX_TITLE_RETRIES:
                title_retry_count += 1
                self.log(
                    f"⚠️ 제목 규칙 위반: {title_violation_desc} "
                    f"(시도 {title_retry_count}/{MAX_TITLE_RETRIES}) - 제목 재생성 중... 현재 제목: '{blog_title}'"
                )
                prompt_fix_title = f"""
아래 블로그 제목은 규칙을 어겼습니다. {fix_title_instruction}

기존 제목: {blog_title}

[출력 형식]
(수정된 제목 한 줄만 출력하세요. 다른 말은 하지 마세요.)
"""
                fixed_title = self.call_api(prompt_fix_title, max_tokens=200).strip()
                if fixed_title:
                    blog_title = fixed_title

            if title_ok(blog_title):
                if title_retry_count:
                    self.log(f"✅ 제목 재시도 성공 ({title_retry_count}회 만에 규칙 충족): '{blog_title}'")
            else:
                self.log(f"⚠️ {MAX_TITLE_RETRIES}회 재시도 후에도 규칙 위반({title_violation_desc}) - 그대로 진행: '{blog_title}'")

            self.log(f"Step {step_draft}/{total_steps} 완료 - 정보 초안 글자수: {len(draft_text)}자")

            if is_info_mode:
                # ── 정보전달용: 경험 관점 오버레이 단계를 생략하고 곧장 존댓말 윤문으로 넘어간다 ──
                experience_text = draft_text
            else:
                # ── STEP 3: 경험 관점 입히기 (완성된 정보 위에 결만 덧입힘) ──
                self.log(f"Step {step_experience}/{total_steps} : 경험 관점 입히는 중...")
                self.progress_value.emit(35)

                prompt_experience = f"""
아래는 사실관계 확인이 끝난 블로그 정보 초안입니다. 이 초안의 실제 내용과 분위기를 보고,
아래 5가지 경험 서술 방식 중 이 글에 가장 자연스러운 것 '하나'를 골라 경험/개인 관점의 결을 입히세요.

[경험 서술 방식 - 하나만 선택]
1. 정보 탐색 과정 자체를 경험으로 (며칠간 비교·조사한 과정을 공유)
2. 타인의 경험을 재해석 (커뮤니티/후기를 모아 분석해서 정리)
3. 초보자 관점의 시행착오 공유 (헤맨 과정과 그 결론)
4. TPO를 극도로 세분화한 가정 (특정 상황의 독자에 맞춘 시뮬레이션)
5. 실행 계획/버킷리스트 형태 (앞으로 할 일을 구체적으로 공유)

[반드시 지킬 것]
- 아래 초안에 있는 사실, 수치, 비교 내용은 절대 삭제·왜곡하지 마세요. 그대로 유지한 채 위에 경험의 결만 얹으세요.
- 도입부와 결론에 선택한 경험 관점을 반영해 사람 냄새가 나게 고치세요.
- 각 소제목(##) 시작 부분에 자연스럽게 1~2문장 정도의 경험/개인 관점 문장을 추가하세요. 문단마다 기계적으로 반복하지 말고 강약을 조절하세요.
- 마크다운 구조(##, ###, **굵게** 등)와 소제목 문구는 그대로 유지하세요.
- 없는 경험을 과장되게 지어내 진위 논란이 생길 표현(예: 구체적 금액/날짜/장소를 사실인 것처럼 단정)은 피하고, "~해봤다", "~찾아봤다" 정도의 톤을 유지하세요.
- 경험 문장은 "추가"하는 것이지 기존 문장을 "대체"하는 게 아닙니다. 초안의 문장·정보량을 요약하거나 줄이지 말고, 원문 분량 이상으로 늘어나야 정상입니다.
- 모든 소제목(##) 구간에 최소 1문장 이상 경험/개인 관점 문장이 반드시 들어가야 한다. 하나도 빠뜨리지 마라.
- 같은 문형을 두 번 이상 반복 금지. 특히 '~인 줄 알았는데' 같은 반전 화법은 글 전체에서 최대 1회만 사용.
- 최소 한 곳에는 구체적인 탐색 디테일(비교해 본 대안 개수, 찾아본 기간, 참고한 후기 수 등)을 포함하라. 단, 사실로 단정할 수 없는 구체적 금액/날짜는 여전히 금지.

[절대 금지]
- 블로그 본문 이외의 어떠한 말도 출력하지 마세요.
- 경험 관점이 입혀진 본문 전체만 출력하세요. 그 외 아무것도 출력하지 마세요.

[정보 초안]
{draft_text}
"""
                experience_text = self.call_api(prompt_experience, max_tokens=5000)
                self.log(f"Step {step_experience}/{total_steps} 완료 - 경험 관점 입힌 후 글자수: {len(experience_text)}자")

            # ── STEP 4: 윤문 (홈판용: im-not-ai / 정보전달용: 존댓말 유지) ──
            self.log(f"Step {step_proofread}/{total_steps} : 윤문 중...")
            self.progress_value.emit(50)

            if is_info_mode:
                prompt_proofread = f"""
당신은 대한민국 최고 수준의 한국어 편집자(Copyeditor)이자 윤문 전문가입니다.
아래 블로그 초안에서 무미건조한 'AI 스타일 한글 티'를 완전히 지우고, 사람이 정성스럽게 직접 쓴 듯
자연스러운 문장으로 다듬으세요.

[기존 톤 유지]
- ~습니다/~요 체의 존댓말을 그대로 유지하세요. 반말체로 바꾸지 마세요.
- 어려운 전문용어는 풀어서, 어린이도 이해할 수 있을 만큼 쉬운 단어로 설명하는 톤을 유지하세요.
- 모바일 화면에서 읽기 편하도록 한 문장이 너무 길어지지 않게 적당히 끊어진 상태를 유지하세요.

[번역투 제거]
- "~에 대해(서)", "~를 통해/통하여" 남발 금지 → 목적격 조사나 "~로/해서/함으로써"로 우회 교체
- "~에 있어(서)", "~라는 점에서", "~와 관련하여", "~에 기반하여/바탕으로" 금지 → "~에서", "~해서/이유로" 등으로 교체
- "가지고 있다"(소유 직역) → "~이 있다/강하다" 등 형용사형으로 교체
- 이중 피동 "~되어진다", "~지게 된다" 전체 수정 → 능동 표현 또는 단일 피동으로("판단되어진다" → "판단됩니다/판단합니다")
- 행위자 피동 "~에 의해" → 행위자를 주어로 능동 복구
- "그/그녀/그것/그들" 같은 영어 대명사 직역 전량 삭제 (한국어는 대명사 생략이 자연스러움)

[AI 특유 상투구 제거]
- "결론적으로", "요약하면", "종합하면", "정리하자면" → 모두 삭제(문단 흐름으로 자연스럽게 종결)
- "시사하는 바가 크다", "주목할 만하다", "매우 중요하다", "반드시 기억해야 한다" → 삭제 또는 평이하게 치환
- 과장 어휘("혁신적인", "획기적인", "전례 없는", "압도적", "폭발적", "파격적" 등) → 삭제하고 구체적 팩트로 환원

[가독성/리듬 개선]
- "첫째, 둘째, 셋째" 로봇식 나열 금지 → 산문으로 녹이거나 "우선/다음으로/마지막으로" 등으로 변주
- 문두 접속사("또한", "따라서", "즉", "나아가", "아울러") 남발 금지(80% 이상 삭제)

[절대 지킬 것]
- 문장이나 문단을 삭제·요약해서 분량을 줄이지 마세요. 원문에 있는 정보, 수치, 사례는 하나도 빠짐없이
  그대로 담되 말투와 표현만 자연스럽게 다듬으세요. 결과물 글자수는 원문과 비슷하거나 더 길어야 합니다.
- 소제목(##, ###) 마크다운 형식은 반드시 유지하세요.
- 원문에 있는 핵심 수치, 날짜, 고유명사는 단 한 글자도 바꾸지 마세요. 없는 사실을 추가하지 마세요.
- 마크다운 표(| ... |)가 있다면 격자 구조를 그대로 유지하고 셀 안 텍스트만 다듬으세요.

[절대 금지]
- 블로그 본문 이외의 어떠한 말도 출력하지 마세요.
- 윤문된 본문만 출력하세요. 코드블록이나 다른 설명 없이 최종 텍스트만 출력하세요.

[블로그 초안]
{experience_text}
"""
            else:
                prompt_proofread = f"""
당신은 대한민국 최고 수준의 한국어 편집자(Copyeditor)이자 윤문 전문가입니다.
아래 블로그 초안에서 무미건조한 'AI 스타일 한글 티'를 완전히 지우고, 사람이 정성스럽게 직접 경험하고 쓴 듯 자연스러운 문장으로 다듬으세요.

[기존 톤 유지]
- ~습니다/~요 체 대신 ~다/~했다 형식의 담백한 커뮤니티 찐후기 평어체를 유지하세요.

[번역투 제거]
- "~에 대해(서)", "~를 통해/통하여" 남발 금지 → 목적격 조사나 "~로/해서/함으로써"로 우회 교체
- "~에 있어(서)", "~라는 점에서", "~와 관련하여", "~에 기반하여/바탕으로" 금지 → "~에서", "~해서/이유로" 등으로 교체
- "가지고 있다"(소유 직역) → "~이 있다/강하다" 등 형용사형으로 교체
- 이중 피동 "~되어진다", "~지게 된다" 전체 수정 → 능동 표현 또는 단일 피동으로("판단되어진다" → "판단된다/판단한다")
- 행위자 피동 "~에 의해" → 행위자를 주어로 능동 복구
- "~할 수 있다", "~을 위해" 과다 사용 지양
- "그/그녀/그것/그들" 같은 영어 대명사 직역 전량 삭제 (한국어는 대명사 생략이 자연스러움)

[AI 특유 상투구 제거]
- "결론적으로", "요약하면", "종합하면", "정리하자면" → 모두 삭제(문단 흐름으로 자연스럽게 종결)
- "시사하는 바가 크다", "주목할 만하다", "매우 중요하다", "반드시 기억해야 한다" → 삭제 또는 평이하게 치환
- 과장 어휘("혁신적인", "획기적인", "전례 없는", "압도적", "폭발적", "파격적" 등) → 삭제하고 구체적 팩트로 환원
- "지금이야말로 ~할 때입니다" 같은 억지 결말 표현 금지

[가독성/리듬 개선]
- "첫째, 둘째, 셋째" 로봇식 나열 금지 → 산문으로 녹이거나 "우선/다음으로/마지막으로" 등으로 변주
- 연결어미(-고/-며/-지만/-면서/-아서/-어서 등) 직후 불필요한 쉼표 제거
- 문두 접속사("또한", "따라서", "즉", "나아가", "아울러") 남발 금지(80% 이상 삭제)
- 진행형 "~고 있다" 남발 제거 → 단순 현재/과거 시제로 환원
- 같은 종결어미("~다")가 한 문단 안에서 4회 이상 연속 반복되지 않도록 변주

[절대 지킬 것]
- 문장이나 문단을 삭제·요약해서 분량을 줄이지 마세요. 원문에 있는 정보, 수치, 사례는 하나도 빠짐없이 그대로 담되 말투와 표현만 자연스럽게 다듬으세요. 결과물 글자수는 원문과 비슷하거나 더 길어야 합니다.
- 소제목(##, ###) 마크다운 형식은 반드시 유지하세요.
- 원문에 있는 핵심 수치, 날짜, 고유명사는 단 한 글자도 바꾸지 마세요. 없는 사실을 추가하지 마세요.
- 마크다운 표(| ... |)가 있다면 격자 구조를 그대로 유지하고 셀 안 텍스트만 다듬으세요.

[절대 금지]
- 블로그 본문 이외의 어떠한 말도 출력하지 마세요.
- 윤문된 본문만 출력하세요. 코드블록이나 다른 설명 없이 최종 텍스트만 출력하세요.

[블로그 초안]
{experience_text}
"""
            final_text = self.call_api(prompt_proofread, max_tokens=7000 if is_info_mode else 5000)
            self.log(f"Step {step_proofread}/{total_steps} 완료 - 최종 윤문 후 글자수: {len(final_text)}자 (윤문 전 대비 {len(final_text) - len(experience_text):+d}자)")

            # ── 이미지 HTML 생성 및 캡처 (체크박스로 on/off) ──
            headings = self.extract_headings(final_text)
            thumbnail_file = None
            heading_files = [None] * len(headings)

            jobs = []
            if self.make_thumbnail:
                jobs.append(("thumbnail", 0, blog_title if blog_title else "블로그 대표 이미지"))
            if self.make_images:
                for i, h in enumerate(headings):
                    jobs.append(("heading", i, h))

            if jobs:
                self.progress_value.emit(60)
                # 카드를 한 번에 몰아서 요청하면 생성량이 많아져 프록시 타임아웃(524) 위험이 커지므로
                # 항목별로 나누어 호출한다.
                for j, (kind, idx, target) in enumerate(jobs):
                    self.log(
                        f"Step {step_image}/{total_steps} : 이미지 HTML 생성 중... ({j + 1}/{len(jobs)}) [{kind}]"
                    )
                    self.progress_value.emit(60 + int(25 * (j + 1) / len(jobs)))

                    if kind == "thumbnail":
                        role_desc = f"블로그 전체를 대표하는 썸네일 카드. 아래는 이 글의 제목이며, 제목 문구를 그대로 노출하기보다 핵심 키워드를 강조해 시선을 끄는 대표 이미지로 디자인하세요.\n제목: {target}"
                        card_size_rule = "- 카드는 width:1080px, height:1080px 고정 (1:1 정사각형)"
                    else:
                        role_desc = f"블로그 소제목 '{target}' 구간에 들어갈 카드. 이 소제목 내용을 압축해서 보여주세요."
                        card_size_rule = "- 카드는 width:800px, height:450px 고정"

                    prompt_image = f"""
아래 항목에 대해 세련된 인포그래픽 HTML/CSS 카드를 생성하세요.
HTML 카드는 반드시 ```html ... ``` 코드 블록 하나로만 감싸서 출력하세요.

생성할 항목:
{role_desc}

[디자인 규칙]
{card_size_rule}
- body margin:0, padding:0 설정
- 모던하고 세련된 그라데이션 배경 사용
- 항목 내용을 텍스트로 크게 표시
- 폰트는 구글 Noto Sans KR 사용

[절대 금지]
- ```html ... ``` 코드 블록 이외의 텍스트 출력 금지
- "썸네일", "소제목 이미지" 같은 메타 표현을 카드에 그대로 쓰지 마세요. 실제 내용만 표시하세요.
"""
                    image_raw = self.call_api(prompt_image, max_tokens=2500)
                    match = re.search(r'```html\s*(.*?)\s*```', image_raw, re.DOTALL)
                    if not match:
                        self.log(
                            f"⚠️ 카드 HTML 생성 실패 [{kind}] '{target}': "
                            f"응답에서 html 코드 블록을 찾지 못함 (응답 {len(image_raw)}자)"
                        )
                        continue

                    # 개별 카드 캡처 실패가 전체 작업을 중단시키지 않도록 try/except로 감싼다.
                    try:
                        if kind == "thumbnail":
                            self.capture_html(match.group(1), "thumbnail.png", size=(1080, 1080))
                            thumbnail_file = "thumbnail.png"
                        else:
                            fname = f"image_{idx + 1}.png"
                            self.capture_html(match.group(1), fname)
                            heading_files[idx] = fname
                    except Exception as e:
                        self.log(f"⚠️ 카드 캡처 실패 [{kind}] '{target}': {e}")
                        continue
            else:
                self.log(f"Step {step_image}/{total_steps} : 이미지 생성 건너뜀 (체크박스 미선택)")

            self.log("이미지 캡처 및 해시태그 처리 완료")
            self.progress_value.emit(90)

            # ── 네이버 스마트에디터 붙여넣기용 HTML 포맷팅 ────
            formatted_html = self.format_for_naver(final_text, thumbnail_file, heading_files, hashtags, blog_title)

            preview_html = self.build_preview_html(formatted_html)
            preview_path = os.path.join(self.output_dir, "preview.html")
            with open(preview_path, "w", encoding="utf-8") as f:
                f.write(preview_html)

            # ── SNS 패키지 생성(카드뉴스 세트 + 스레드/인스타 공용 본문) ──
            # 실패해도 블로그 결과에는 영향이 없도록 전체를 try/except로 감싼다.
            if self.make_sns:
                try:
                    self.log("SNS 패키지 생성 중... (카드뉴스+공용 본문)")
                    self.progress_value.emit(92)

                    prompt = sns_package.build_sns_prompt(final_text, blog_title)
                    raw = self.call_api(prompt, max_tokens=2500)
                    data = sns_package.parse_sns_package(raw)

                    # 표지 문구가 없거나 본문 카드가 2장 미만이면 품질 미달로 보고 건너뛴다.
                    if not data["cover"] or len(data["cards"]) < 2:
                        self.log(
                            f"⚠️ SNS 패키지 건너뜀 (표지 {'있음' if data['cover'] else '없음'}, "
                            f"카드 {len(data['cards'])}장 - 최소 2장 필요)"
                        )
                    else:
                        theme = sns_package.pick_theme(blog_title)
                        total = len(data["cards"])

                        # 표지 캡처
                        try:
                            self.capture_html(
                                sns_package.render_cover(data["cover"], theme),
                                "sns_cover.png", size=(1080, 1080)
                            )
                        except Exception as e:
                            self.log(f"⚠️ SNS 표지 캡처 실패: {e}")

                        # 본문 카드 캡처 (진행 표시는 1부터)
                        for i, card in enumerate(data["cards"], 1):
                            try:
                                self.capture_html(
                                    sns_package.render_content(
                                        i, total, card["title"], card["body"], theme
                                    ),
                                    f"sns_card_{i}.png", size=(1080, 1080)
                                )
                            except Exception as e:
                                self.log(f"⚠️ SNS 카드 {i} 캡처 실패: {e}")

                        # 마지막(CTA) 카드 캡처
                        try:
                            self.capture_html(
                                sns_package.render_last(
                                    data["summary"], data["cta"], theme
                                ),
                                "sns_last.png", size=(1080, 1080)
                            )
                        except Exception as e:
                            self.log(f"⚠️ SNS 마지막 카드 캡처 실패: {e}")

                        # 공용 본문/해시태그 텍스트 저장
                        sns_text = data["sns_text"]
                        if len(sns_text) > sns_package.SNS_TEXT_LIMIT:
                            self.log(
                                f"⚠️ SNS 본문 {len(sns_text)}자 "
                                f"(권장 {sns_package.SNS_TEXT_LIMIT}자 초과, 자르지 않음)"
                            )
                        with open(os.path.join(self.output_dir, "sns_threads.txt"),
                                  "w", encoding="utf-8") as f:
                            f.write(sns_text)

                        # 네이버 클립 설명 저장(해시태그 미포함). 누락 시 SNS 본문으로 폴백.
                        clip_text = data["clip_text"].strip()
                        if not clip_text:
                            clip_text = sns_text
                            self.log("⚠️ 클립 설명 누락 → SNS 본문으로 대체")
                        if len(clip_text) > sns_package.CLIP_TEXT_LIMIT:
                            self.log(
                                f"⚠️ 클립 설명 {len(clip_text)}자 "
                                f"(권장 {sns_package.CLIP_TEXT_LIMIT}자 초과, 자르지 않음)"
                            )
                        with open(os.path.join(self.output_dir, "sns_clip.txt"),
                                  "w", encoding="utf-8") as f:
                            f.write(clip_text)

                        with open(os.path.join(self.output_dir, "sns_instagram.txt"),
                                  "w", encoding="utf-8") as f:
                            f.write(sns_text + "\n\n" + data["hashtags"])

                        self.log(
                            f"SNS 패키지 완료: 카드 {total}장 + 본문 {len(sns_text)}자 "
                            f"+ 클립 설명 {len(clip_text)}자"
                        )

                        # ── 네이버 클립(세로 숏폼) 슬라이드쇼 영상 생성 ──
                        # 세로형(1080×1920) 카드를 추가 캡처한 뒤 ffmpeg로 mp4를 만든다.
                        # 실패해도 블로그/SNS 패키지 결과에는 영향이 없도록 별도 try/except로 감싼다.
                        if self.make_clip:
                            try:
                                self.log("🎬 클립 영상용 세로형 카드 캡처 중...")
                                self.progress_value.emit(95)
                                clip_size = sns_package.CLIP_SIZE  # (1080, 1920)
                                slides = []

                                # 표지(세로)
                                cover_v = self.capture_html(
                                    sns_package.render_cover(
                                        data["cover"], theme, size=clip_size
                                    ),
                                    "sns_v_cover.png", size=clip_size
                                )
                                slides.append(
                                    (cover_v, video_maker.DEFAULT_DURATIONS["cover"])
                                )

                                # 본문 카드(세로)
                                for i, card in enumerate(data["cards"], 1):
                                    card_v = self.capture_html(
                                        sns_package.render_content(
                                            i, total, card["title"], card["body"],
                                            theme, size=clip_size
                                        ),
                                        f"sns_v_card_{i}.png", size=clip_size
                                    )
                                    slides.append(
                                        (card_v, video_maker.DEFAULT_DURATIONS["content"])
                                    )

                                # 마지막(CTA) 카드(세로)
                                last_v = self.capture_html(
                                    sns_package.render_last(
                                        data["summary"], data["cta"],
                                        theme, size=clip_size
                                    ),
                                    "sns_v_last.png", size=clip_size
                                )
                                slides.append(
                                    (last_v, video_maker.DEFAULT_DURATIONS["last"])
                                )

                                bgm_path = (self.video_cfg.get("bgm_path", "") or "").strip()
                                if bgm_path and not os.path.exists(bgm_path):
                                    self.log(f"⚠️ 설정된 BGM 파일이 없어 무음으로 진행: {bgm_path}")
                                    bgm_path = ""

                                # ── TTS 나레이션 합성(선택) ──
                                # 실패해도 나레이션 없이 기존 방식으로 클립을 만들도록 별도 try/except로 감싼다.
                                narrations = None
                                has_narr = False
                                if self.make_tts:
                                    try:
                                        # 슬라이드별 나레이션 텍스트: 표지 / 카드 / 마지막.
                                        narr_texts = [tts_maker.clean_narration(data["cover"])]
                                        for card in data["cards"]:
                                            narr_texts.append(
                                                tts_maker.clean_narration(
                                                    f"{card['title']}. {card['body']}"
                                                )
                                            )
                                        narr_texts.append(
                                            tts_maker.clean_narration(
                                                f"{data['summary']}. {data['cta']}"
                                            )
                                        )
                                        voice = (self.video_cfg.get("tts_voice", "")
                                                 or tts_maker.DEFAULT_VOICE).strip()

                                        self.log(f"🔊 TTS 나레이션 합성 중... (목소리: {voice})")
                                        tts_names = (
                                            ["tts_cover.mp3"]
                                            + [f"tts_card_{i}.mp3" for i in range(1, total + 1)]
                                            + ["tts_last.mp3"]
                                        )
                                        tts_durs = []
                                        for text, name in zip(narr_texts, tts_names):
                                            mp3_path = os.path.join(self.output_dir, name)
                                            tts_maker.synthesize(text, mp3_path, voice=voice)
                                            tts_durs.append(
                                                tts_maker.probe_duration(mp3_path)
                                            )

                                        # 타이밍 헬퍼로 슬라이드 길이·나레이션 시작 시각 재계산.
                                        entries = [
                                            (png, dur, tdur)
                                            for (png, dur), tdur in zip(slides, tts_durs)
                                        ]
                                        new_slides, starts = video_maker.plan_narrated_slides(
                                            entries, video_maker.XFADE_DURATION
                                        )
                                        slides = new_slides
                                        narrations = [
                                            (os.path.join(self.output_dir, name), start)
                                            for name, start in zip(tts_names, starts)
                                        ]
                                        has_narr = True
                                        self.log(f"🔊 나레이션 {len(narrations)}개 합성 완료")
                                    except Exception as e:
                                        self.log(
                                            f"⚠️ TTS 나레이션 실패 → 나레이션 없이 진행: {e}"
                                        )
                                        narrations = None
                                        has_narr = False

                                out_path = os.path.join(self.output_dir, "sns_clip.mp4")
                                video_maker.make_clip(
                                    slides, out_path,
                                    bgm_path=bgm_path or None,
                                    on_log=self.log,
                                    narrations=narrations,
                                )
                                clip_dur = video_maker.total_duration(
                                    slides, video_maker.XFADE_DURATION
                                )
                                audio_desc = []
                                if has_narr:
                                    audio_desc.append("나레이션")
                                audio_desc.append("BGM" if bgm_path else "무음")
                                self.log(
                                    f"🎬 클립 영상 완료: sns_clip.mp4 "
                                    f"(약 {clip_dur:.1f}초, {'+'.join(audio_desc)})"
                                )
                            except Exception as e:
                                self.log(
                                    f"⚠️ 클립 영상 생성 실패(블로그/SNS 결과에는 영향 없음): {e}"
                                )
                except Exception as e:
                    self.log(f"⚠️ SNS 패키지 생성 실패(블로그 결과에는 영향 없음): {e}")

            # ── 네이버 자동 임시저장용 산출물 보관 ──
            # 이미지 파일명(썸네일 + 소제목 카드)을 절대경로로 변환해 모은다.
            image_paths = []
            if thumbnail_file:
                image_paths.append(os.path.join(self.output_dir, thumbnail_file))
            for hf in heading_files:
                if hf:
                    image_paths.append(os.path.join(self.output_dir, hf))
            self.last_post_data = {
                "title": blog_title,
                # 마크다운 원문을 라인 리스트로 넘긴다(naver_poster에서 서식 기호 제거).
                "content_lines": final_text.split("\n"),
                "hashtags": hashtags,
                "image_paths": image_paths,
            }

            self.progress_value.emit(100)
            self.finished_signal.emit(formatted_html, preview_path)

        except Exception as e:
            import traceback
            self.error_signal.emit(f"{str(e)}\n\n{traceback.format_exc()}")

    def format_for_naver(self, text, thumbnail_file, heading_files, hashtags, title=""):
        """마크다운을 네이버 복붙용 HTML로 변환한다 (textutils 위임 래퍼)."""
        return textutils.format_for_naver(text, thumbnail_file, heading_files, hashtags, title)

    def build_preview_html(self, body_html):
        """브라우저 복사용 완전한 HTML 문서를 만든다 (textutils 위임 래퍼)."""
        return textutils.build_preview_html(body_html)


class KeywordAnalysisThread(QThread):
    """시드 키워드로 연관 키워드+검색량을 조회하고(1차), 상위 키워드의 블로그 문서수를
    순차 조회해 황금점수를 계산하는(2차) 워커 스레드."""

    # 1차: 연관 키워드+검색량 리스트 (문서수/점수는 아직 없음)
    keywords_ready = pyqtSignal(list)
    # 2차: 키워드별 문서수/황금점수/등급 (keyword, blog_docs, ratio, grade)
    doc_count_ready = pyqtSignal(str, int, float, str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    # 문서수 조회는 검색량 상위 N개에만 수행(호출량/시간 절약)
    MAX_DOC_LOOKUP = 60

    def __init__(self, naver_cfg, seed):
        super().__init__()
        self.naver_cfg = naver_cfg or {}
        self.seed = seed

    def run(self):
        try:
            # 검색광고 API 키 5개 중 하나라도 비어 있으면 즉시 안내하고 중단한다.
            searchad_keys = [
                "searchad_customer_id", "searchad_access_license", "searchad_secret_key",
            ]
            search_keys = ["search_client_id", "search_client_secret"]
            if any(not self.naver_cfg.get(k) for k in searchad_keys + search_keys):
                self.error_signal.emit("⚠️ 설정 탭에서 네이버 검색광고 API 키를 입력하세요")
                return

            # ── 1차: 연관 키워드 + 월간 검색량 조회 ──
            keywords = naver_keywords.fetch_related_keywords(self.naver_cfg, self.seed)
            self.keywords_ready.emit(keywords)

            # ── 2차: 검색량 상위 MAX_DOC_LOOKUP개에 대해서만 블로그 문서수 조회 ──
            top_keywords = sorted(keywords, key=lambda k: k["total"], reverse=True)[:self.MAX_DOC_LOOKUP]
            for item in top_keywords:
                keyword = item["keyword"]
                # 한 건의 일시적 실패(429 등)가 나머지 전체 조회를 중단시키지 않도록
                # 키워드 단위로 방어하고 실패 건은 건너뛴다.
                try:
                    blog_docs = naver_keywords.fetch_blog_doc_count(self.naver_cfg, keyword)
                except Exception:
                    time.sleep(0.15)
                    continue
                ratio, grade = naver_keywords.golden_score(item["total"], blog_docs)
                self.doc_count_ready.emit(keyword, blog_docs, ratio, grade)
                # 검색 API 호출 간격을 살짝 두어 과도한 연속 호출을 피한다.
                time.sleep(0.15)

            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


class NaverLoginThread(QThread):
    """네이버 로그인 창을 띄워 사용자가 직접 로그인하게 하는 워커 스레드.

    playwright import는 지연 import로 처리해 미설치 환경에서도 앱이 뜨게 한다.
    import 실패 시 error_signal로 'IMPORT' 센티널을 보낸다."""

    finished_signal = pyqtSignal(bool)  # 로그인 성공 여부
    error_signal = pyqtSignal(str)

    def run(self):
        try:
            import naver_poster  # 지연 import (playwright 미설치 대비)
        except ImportError:
            self.error_signal.emit("IMPORT")
            return
        try:
            ok = naver_poster.login_naver()
            self.finished_signal.emit(ok)
        except Exception as e:
            self.error_signal.emit(str(e))


class NaverPostThread(QThread):
    """생성된 글+이미지를 네이버 블로그에 자동으로 임시저장하는 워커 스레드.

    QThread(메인 스레드가 아님) 안에서 playwright sync API를 쓰는 것은 문제없다.
    import 실패 시 error_signal로 'IMPORT' 센티널을 보낸다."""

    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, post_data):
        super().__init__()
        self.post_data = post_data

    def run(self):
        try:
            import naver_poster  # 지연 import (playwright 미설치 대비)
        except ImportError:
            self.error_signal.emit("IMPORT")
            return
        try:
            naver_poster.post_draft(
                title=self.post_data.get("title", ""),
                content_lines=self.post_data.get("content_lines", []),
                image_paths=self.post_data.get("image_paths", []),
                hashtags=self.post_data.get("hashtags", ""),
                on_log=self.progress_signal.emit,
            )
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


class AddTaskDialog(QDialog):
    """실행 중인 작업이 있어도 다음 글감을 미리 입력해 예약 큐에 추가하기 위한 다이얼로그."""

    def __init__(self, parent=None, default_thumbnail=True, default_images=True,
                 default_sns=True, default_clip=True, default_tts=True, default_title_mode="home"):
        super().__init__(parent)
        self.setWindowTitle("➕ 새 작업 예약 추가")
        self.resize(520, 440)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(QLabel("📋 참고 블로그 제목 입력 (여러 줄 붙여넣기)"))

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText(
            "예시:\n클로드 코드로 1인 창업하기\n코딩 없이 앱 만드는 법\n비전공자 개발 도전기"
        )
        layout.addWidget(self.input_text)

        title_mode_layout = QHBoxLayout()
        title_mode_layout.addWidget(QLabel("제목 작성 모드:"))
        self.radio_home = QRadioButton("🏠 홈판용 (클릭 유도형)")
        self.radio_info = QRadioButton("📖 정보 전달용 (SEO형)")
        if default_title_mode == "info":
            self.radio_info.setChecked(True)
        else:
            self.radio_home.setChecked(True)
        self.title_mode_group = QButtonGroup(self)
        self.title_mode_group.addButton(self.radio_home)
        self.title_mode_group.addButton(self.radio_info)
        title_mode_layout.addWidget(self.radio_home)
        title_mode_layout.addWidget(self.radio_info)
        title_mode_layout.addStretch()
        layout.addLayout(title_mode_layout)

        option_layout = QHBoxLayout()
        self.chk_thumbnail = QCheckBox("썸네일 이미지 만들기")
        self.chk_thumbnail.setChecked(default_thumbnail)
        self.chk_images = QCheckBox("본문 소제목 이미지 만들기")
        self.chk_images.setChecked(default_images)
        self.chk_sns = QCheckBox("SNS 패키지 만들기 (카드뉴스+스레드/인스타 글)")
        self.chk_sns.setChecked(default_sns)
        self.chk_clip = QCheckBox("🎬 클립 영상 만들기 (네이버 클립용 세로 영상)")
        self.chk_clip.setChecked(default_clip)
        self.chk_clip.setEnabled(default_sns)
        self.chk_tts = QCheckBox("🔊 TTS 나레이션")
        self.chk_tts.setChecked(default_tts)
        self.chk_tts.setEnabled(default_sns and default_clip)

        def _sync_enabled(*_):
            # SNS를 끄면 클립·나레이션 모두 의미가 없고, 클립을 끄면 나레이션이 의미가 없다.
            self.chk_clip.setEnabled(self.chk_sns.isChecked())
            self.chk_tts.setEnabled(self.chk_sns.isChecked() and self.chk_clip.isChecked())

        self.chk_sns.stateChanged.connect(_sync_enabled)
        self.chk_clip.stateChanged.connect(_sync_enabled)
        option_layout.addWidget(self.chk_thumbnail)
        option_layout.addWidget(self.chk_images)
        option_layout.addWidget(self.chk_sns)
        option_layout.addWidget(self.chk_clip)
        option_layout.addWidget(self.chk_tts)
        option_layout.addStretch()
        layout.addLayout(option_layout)

        btn_row = QHBoxLayout()
        self.btn_ok = QPushButton("✅ 확인 (예약 추가)")
        self.btn_cancel = QPushButton("취소")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_ok)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def get_data(self):
        return {
            "titles": self.input_text.toPlainText().strip(),
            "title_mode": "home" if self.radio_home.isChecked() else "info",
            "make_thumbnail": self.chk_thumbnail.isChecked(),
            "make_images": self.chk_images.isChecked(),
            "make_sns": self.chk_sns.isChecked(),
            "make_clip": self.chk_sns.isChecked() and self.chk_clip.isChecked(),
            "make_tts": (self.chk_sns.isChecked() and self.chk_clip.isChecked()
                         and self.chk_tts.isChecked()),
        }


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.provider_keys = ["claude", "gemini", "openai", "ollama"]
        # 네이버 로그인 워커. MainWindow가 main_window 속성을 주입해 임시저장 스레드와의
        # 동시 실행 여부를 교차 확인한다.
        self.naver_login_thread = None
        self.main_window = None
        cfg = config_manager.load_config()
        self.pending = {k: dict(v) for k, v in cfg["providers"].items()}
        self.current_provider = cfg.get("active_provider", "claude")

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        self.combo_provider = QComboBox()
        self.combo_provider.addItems([providers.PROVIDER_LABELS[k] for k in self.provider_keys])
        form.addRow("AI 공급자", self.combo_provider)

        key_row = QHBoxLayout()
        self.input_key = QLineEdit()
        self.input_key.setEchoMode(QLineEdit.Password)
        self.input_key.setPlaceholderText("API 키 (Ollama는 비워두세요)")
        self.chk_show_key = QCheckBox("표시")
        self.chk_show_key.toggled.connect(
            lambda on: self.input_key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        )
        key_row.addWidget(self.input_key)
        key_row.addWidget(self.chk_show_key)
        key_widget = QWidget()
        key_widget.setLayout(key_row)
        form.addRow("API 키", key_widget)

        self.input_base_url = QLineEdit()
        self.input_base_url.setPlaceholderText("예: https://api.anthropic.com")
        form.addRow("Base URL", self.input_base_url)

        model_row = QHBoxLayout()
        self.input_model = QLineEdit()
        self.input_model.setPlaceholderText("모델 이름을 직접 입력하세요 (예: claude-sonnet-4-5-20250929)")
        self.btn_model_link = QPushButton("🔗 모델 목록 보기")
        self.btn_model_link.clicked.connect(self.on_open_model_page)
        model_row.addWidget(self.input_model, stretch=1)
        model_row.addWidget(self.btn_model_link)
        model_widget = QWidget()
        model_widget.setLayout(model_row)
        form.addRow("모델", model_widget)

        layout.addLayout(form)

        # ── 네이버 API 키 구획 (검색 API 2개 + 검색광고 API 3개) ──
        naver_cfg = cfg.get("naver", {})
        lbl_naver = QLabel("🔑 네이버 API (키워드 분석용)")
        lbl_naver.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 8px;")
        layout.addWidget(lbl_naver)

        naver_form = QFormLayout()
        naver_form.setSpacing(10)

        self.input_naver_search_id = QLineEdit()
        self.input_naver_search_id.setText(naver_cfg.get("search_client_id", ""))
        naver_form.addRow("검색 Client ID", self.input_naver_search_id)

        self.input_naver_search_secret = QLineEdit()
        self.input_naver_search_secret.setEchoMode(QLineEdit.Password)
        self.input_naver_search_secret.setText(naver_cfg.get("search_client_secret", ""))
        naver_form.addRow("검색 Client Secret", self.input_naver_search_secret)

        self.input_naver_customer_id = QLineEdit()
        self.input_naver_customer_id.setText(naver_cfg.get("searchad_customer_id", ""))
        naver_form.addRow("검색광고 Customer ID", self.input_naver_customer_id)

        self.input_naver_access_license = QLineEdit()
        self.input_naver_access_license.setText(naver_cfg.get("searchad_access_license", ""))
        naver_form.addRow("검색광고 액세스 라이선스", self.input_naver_access_license)

        self.input_naver_secret_key = QLineEdit()
        self.input_naver_secret_key.setEchoMode(QLineEdit.Password)
        self.input_naver_secret_key.setText(naver_cfg.get("searchad_secret_key", ""))
        naver_form.addRow("검색광고 비밀키", self.input_naver_secret_key)

        layout.addLayout(naver_form)

        # Secret/비밀키 두 필드를 하나의 체크박스로 함께 표시/숨김 토글
        self.chk_show_naver = QCheckBox("네이버 Secret/비밀키 표시")
        self.chk_show_naver.toggled.connect(self.on_toggle_naver_secret)
        layout.addWidget(self.chk_show_naver)

        # ── 클립(세로 숏폼) 영상 BGM 구획 ──
        video_cfg = cfg.get("video", {})
        lbl_video = QLabel("🎬 클립 영상 BGM (선택, 비우면 무음)")
        lbl_video.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 8px;")
        layout.addWidget(lbl_video)

        bgm_row = QHBoxLayout()
        self.input_bgm_path = QLineEdit()
        self.input_bgm_path.setPlaceholderText("배경음악 파일 경로 (*.mp3 *.m4a *.wav)")
        self.input_bgm_path.setText(video_cfg.get("bgm_path", ""))
        self.btn_browse_bgm = QPushButton("📂 찾아보기")
        self.btn_browse_bgm.clicked.connect(self.on_browse_bgm)
        bgm_row.addWidget(self.input_bgm_path, stretch=1)
        bgm_row.addWidget(self.btn_browse_bgm)
        bgm_widget = QWidget()
        bgm_widget.setLayout(bgm_row)
        layout.addWidget(bgm_widget)

        # ── TTS 나레이션 목소리 선택 ──
        lbl_voice = QLabel("🔊 TTS 나레이션 목소리")
        lbl_voice.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 8px;")
        layout.addWidget(lbl_voice)

        self.combo_tts_voice = QComboBox()
        self.combo_tts_voice.setEditable(True)
        for voice_id, label in tts_maker.VOICES:
            self.combo_tts_voice.addItem(f"{label} — {voice_id}", voice_id)
        cur_voice = (video_cfg.get("tts_voice", "") or tts_maker.DEFAULT_VOICE).strip()
        # 저장된 목소리가 목록에 있으면 해당 항목을 선택, 없으면 편집란에 직접 표기.
        idx = self.combo_tts_voice.findData(cur_voice)
        if idx >= 0:
            self.combo_tts_voice.setCurrentIndex(idx)
        else:
            self.combo_tts_voice.setEditText(cur_voice)
        layout.addWidget(self.combo_tts_voice)

        self.btn_save = QPushButton("💾 설정 저장")
        self.btn_save.setMinimumHeight(40)
        self.btn_save.clicked.connect(self.on_save)
        layout.addWidget(self.btn_save)

        # ── 네이버 블로그 로그인 구획 (자동 임시저장 세션 확보용) ──
        lbl_naver_login = QLabel("🔐 네이버 블로그 자동 임시저장")
        lbl_naver_login.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 8px;")
        layout.addWidget(lbl_naver_login)

        self.btn_naver_login = QPushButton("🔐 네이버 블로그 로그인")
        self.btn_naver_login.setMinimumHeight(40)
        self.btn_naver_login.clicked.connect(self.on_naver_login)
        layout.addWidget(self.btn_naver_login)

        self.lbl_naver_login_status = QLabel(
            "로그인 버튼을 누르면 브라우저 창이 열립니다. 직접 로그인하면 세션이 저장됩니다."
        )
        layout.addWidget(self.lbl_naver_login_status)

        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)
        layout.addStretch()

        self.setLayout(layout)

        # currentIndexChanged는 필드가 준비된 뒤 연결해야 초기화 중 오동작하지 않음
        self.combo_provider.setCurrentIndex(self.provider_keys.index(self.current_provider))
        self.load_provider_fields(self.current_provider)
        self.combo_provider.currentIndexChanged.connect(self.on_provider_changed)

    def stash_current_fields(self):
        # 마크다운 이스케이프(\_)가 포함된 텍스트를 복사해 붙여넣으면 키에 백슬래시가
        # 섞여 "API key not valid" 오류가 나므로, 저장 시점에 제거한다.
        api_key = self.input_key.text().strip().replace("\\", "")
        self.pending[self.current_provider] = {
            "api_key": api_key,
            "base_url": self.input_base_url.text().strip(),
            "model": self.input_model.text().strip(),
        }

    def load_provider_fields(self, provider_key):
        p = self.pending.get(provider_key, {})
        self.input_key.setText(p.get("api_key", ""))
        self.input_base_url.setText(p.get("base_url", ""))
        self.input_model.setText(p.get("model", ""))
        self.btn_model_link.setText(f"🔗 {providers.PROVIDER_LABELS[provider_key]} 모델 목록 보기")
        self.lbl_status.setText("")

    def on_provider_changed(self, index):
        self.stash_current_fields()
        self.current_provider = self.provider_keys[index]
        self.load_provider_fields(self.current_provider)

    def on_open_model_page(self):
        url = providers.PROVIDER_MODEL_PAGES.get(self.current_provider)
        if url:
            webbrowser.open(url)

    def on_browse_bgm(self):
        """BGM 파일 선택 다이얼로그. 선택 시 경로 입력란에 채운다."""
        start_dir = os.path.dirname(self.input_bgm_path.text().strip()) or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "배경음악 파일 선택", start_dir,
            "오디오 파일 (*.mp3 *.m4a *.wav);;모든 파일 (*.*)"
        )
        if path:
            self.input_bgm_path.setText(path)

    def on_toggle_naver_secret(self, on):
        """네이버 Secret Client Secret / 검색광고 비밀키 두 필드의 표시 여부를 함께 토글한다."""
        mode = QLineEdit.Normal if on else QLineEdit.Password
        self.input_naver_search_secret.setEchoMode(mode)
        self.input_naver_secret_key.setEchoMode(mode)

    def _resolve_tts_voice(self):
        """편집 가능한 목소리 콤보에서 실제 voice_id를 뽑는다.
        - 목록 항목을 고른 경우: currentData(voice_id) 사용.
        - "label — voice_id" 형태를 직접 입력한 경우: 마지막 조각 사용.
        - 순수 voice_id를 직접 입력한 경우: 그대로 사용."""
        text = self.combo_tts_voice.currentText().strip()
        data = self.combo_tts_voice.currentData()
        if data and text.endswith(data):
            return data
        if " — " in text:
            return text.split(" — ")[-1].strip() or tts_maker.DEFAULT_VOICE
        return text or tts_maker.DEFAULT_VOICE

    def on_save(self):
        self.stash_current_fields()
        # 기존 config.json을 기반으로 갱신해야 "naver" 섹션(검색·검색광고 API 키) 등
        # 이 탭에서 다루지 않는 설정이 저장 시 유실되지 않는다.
        cfg = config_manager.load_config()
        cfg["active_provider"] = self.current_provider
        cfg["providers"] = self.pending
        # 네이버 API 키 5개를 naver 섹션에 반영. 마크다운 이스케이프로 섞인 백슬래시는 제거한다.
        naver = cfg.setdefault("naver", {})
        naver["search_client_id"] = self.input_naver_search_id.text().strip().replace("\\", "")
        naver["search_client_secret"] = self.input_naver_search_secret.text().strip().replace("\\", "")
        naver["searchad_customer_id"] = self.input_naver_customer_id.text().strip().replace("\\", "")
        naver["searchad_access_license"] = self.input_naver_access_license.text().strip().replace("\\", "")
        naver["searchad_secret_key"] = self.input_naver_secret_key.text().strip().replace("\\", "")
        # 클립 영상 BGM 경로를 video 섹션에 반영(다른 섹션 유실 방지 위해 load 기반 갱신).
        video = cfg.setdefault("video", {})
        video["bgm_path"] = self.input_bgm_path.text().strip()
        video["tts_voice"] = self._resolve_tts_voice()
        config_manager.save_config(cfg)
        self.lbl_status.setText("✅ 설정 저장 완료")

    def on_naver_login(self):
        """네이버 로그인 창을 띄운다. 임시저장 스레드가 돌고 있으면 시작을 거부한다."""
        if self.naver_login_thread is not None and self.naver_login_thread.isRunning():
            return
        # 임시저장 스레드와 동시에 돌지 않도록 교차 확인.
        mw = self.main_window
        if mw is not None and getattr(mw, "naver_post_thread", None) is not None \
                and mw.naver_post_thread.isRunning():
            self.lbl_naver_login_status.setText("⚠️ 네이버 임시저장이 진행 중입니다. 완료 후 다시 시도하세요.")
            return

        self.btn_naver_login.setEnabled(False)
        self.lbl_naver_login_status.setText("🔐 브라우저 창에서 직접 로그인하세요... (최대 300초 대기)")
        self.naver_login_thread = NaverLoginThread()
        self.naver_login_thread.finished_signal.connect(self.on_naver_login_finished)
        self.naver_login_thread.error_signal.connect(self.on_naver_login_error)
        self.naver_login_thread.finished.connect(lambda: self.btn_naver_login.setEnabled(True))
        self.naver_login_thread.start()

    def on_naver_login_finished(self, ok):
        if ok:
            self.lbl_naver_login_status.setText("✅ 네이버 로그인 성공 (세션이 저장되었습니다).")
            # 로그인을 기다리며 대기열에 쌓인 임시저장이 있으면 이어서 처리한다.
            if self.main_window is not None:
                self.main_window.drain_post_queue()
        else:
            self.lbl_naver_login_status.setText("⏱️ 로그인 타임아웃 (300초 내 로그인 감지 실패).")

    def on_naver_login_error(self, msg):
        if msg == "IMPORT":
            self.lbl_naver_login_status.setText(
                "⚠️ pip install playwright 후 python -m playwright install chromium 필요"
            )
            return
        self.lbl_naver_login_status.setText(f"❌ 로그인 오류: {msg[:120]}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🚀 Auto Blog Poster v3 (멀티 프로바이더)")
        self.resize(1200, 780)
        self.setStyleSheet("""
            QMainWindow { background-color: #f4f5fa; }
            QWidget { background-color: #f4f5fa; color: #2b2d42; font-family: 'Malgun Gothic'; }
            QTextEdit {
                background-color: #ffffff; color: #2b2d42;
                border: 1px solid #d7dae6; border-radius: 8px;
                padding: 10px; font-size: 13px;
            }
            QLineEdit, QComboBox {
                background-color: #ffffff; color: #2b2d42;
                border: 1px solid #d7dae6; border-radius: 6px;
                padding: 6px 8px; font-size: 13px;
            }
            QCheckBox { font-size: 13px; }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5b8def, stop:1 #9b7cf6);
                color: #ffffff; border: none; border-radius: 8px;
                font-size: 15px; font-weight: bold; padding: 12px 20px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4a7bdb, stop:1 #8a6be8); }
            QPushButton:disabled { background: #d7dae6; color: #9599ad; }
            QLabel { color: #3a6b3a; font-size: 13px; }
            QProgressBar {
                background-color: #e4e6f0; border: none; border-radius: 6px; height: 12px;
                color: #2b2d42;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5b8def, stop:1 #9b7cf6);
                border-radius: 6px;
            }
            QTabWidget::pane { border: 1px solid #d7dae6; border-radius: 8px; background: #ffffff; }
            QTabBar::tab {
                background: #e4e6f0; color: #2b2d42; padding: 10px 18px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px;
            }
            QTabBar::tab:selected { background: #ffffff; color: #4a7bdb; font-weight: bold; }
        """)

        self._preview_path = None
        self._log_path = None
        self._output_dir = None
        self.thread = None
        self.job_queue = []

        self.keyword_thread = None

        # 네이버 자동 임시저장용 상태.
        self.naver_post_thread = None
        self._last_post_data = None
        # 포스팅 대기열: 예약 큐로 여러 글이 연속 생성될 때, 임시저장 스레드가 도는 중에
        # 완성된 글이 유실되지 않도록 여기에 쌓아 순서대로 처리한다.
        self.post_queue = []

        self.settings_tab = SettingsTab()
        # SettingsTab이 임시저장 스레드와의 동시 실행을 교차 확인할 수 있게 참조를 주입한다.
        self.settings_tab.main_window = self

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_generate_tab(), "✍️ 글 작성")
        self.tabs.addTab(self.build_keyword_tab(), "🔑 키워드 분석")
        self.tabs.addTab(self.settings_tab, "⚙️ 설정")
        self.setCentralWidget(self.tabs)

    def build_generate_tab(self):
        main_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 라벨
        label_layout = QHBoxLayout()
        lbl_input = QLabel("📋 참고 블로그 제목 입력 (여러 줄 붙여넣기)")
        lbl_output = QLabel("📄 HTML 소스 (참고/백업용 - 붙여넣기는 아래 미리보기 버튼 사용)")
        label_layout.addWidget(lbl_input)
        label_layout.addWidget(lbl_output)
        layout.addLayout(label_layout)

        # 텍스트 영역
        text_layout = QHBoxLayout()
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("예시:\n클로드 코드로 1인 창업하기\n코딩 없이 앱 만드는 법\n비전공자 개발 도전기")
        self.output_text = QTextEdit()
        self.output_text.setPlaceholderText(
            "완료 후 '🌐 브라우저에서 미리보기 열기' 버튼을 눌러,\n"
            "실제 렌더링된 화면에서 전체 선택(Ctrl+A) → 복사(Ctrl+C) 후\n"
            "네이버 블로그 스마트에디터원에 붙여넣으세요.\n(이 영역은 HTML 소스 참고용입니다.)"
        )
        self.output_text.setReadOnly(True)
        text_layout.addWidget(self.input_text)
        text_layout.addWidget(self.output_text)
        layout.addLayout(text_layout)

        # 제목 작성 모드 (홈판용 클릭유도형 / 정보전달용 SEO형) - 상호배타
        title_mode_layout = QHBoxLayout()
        title_mode_layout.addWidget(QLabel("제목 작성 모드:"))
        self.radio_home = QRadioButton("🏠 홈판용 (클릭 유도형)")
        self.radio_home.setChecked(True)
        self.radio_info = QRadioButton("📖 정보 전달용 (SEO형)")
        self.title_mode_group = QButtonGroup(self)
        self.title_mode_group.addButton(self.radio_home)
        self.title_mode_group.addButton(self.radio_info)
        title_mode_layout.addWidget(self.radio_home)
        title_mode_layout.addWidget(self.radio_info)
        title_mode_layout.addStretch()
        layout.addLayout(title_mode_layout)

        # 이미지 생성 옵션
        option_layout = QHBoxLayout()
        self.chk_thumbnail = QCheckBox("썸네일 이미지 만들기")
        self.chk_thumbnail.setChecked(True)
        self.chk_images = QCheckBox("본문 소제목 이미지 만들기")
        self.chk_images.setChecked(True)
        self.chk_auto_post = QCheckBox("생성 완료 후 자동으로 네이버 임시저장")
        self.chk_auto_post.setChecked(True)
        self.chk_sns = QCheckBox("SNS 패키지 만들기 (카드뉴스+스레드/인스타 글)")
        self.chk_sns.setChecked(True)
        self.chk_clip = QCheckBox("🎬 클립 영상 만들기 (네이버 클립용 세로 영상)")
        self.chk_clip.setChecked(True)
        self.chk_tts = QCheckBox("🔊 TTS 나레이션")
        self.chk_tts.setChecked(True)
        # SNS 패키지를 만들지 않으면 클립 영상도 만들 수 없으므로 함께 비활성화한다.
        # 클립을 만들지 않으면 나레이션도 의미가 없으므로 함께 비활성화한다.
        self.chk_sns.stateChanged.connect(self._sync_clip_enabled)
        self.chk_clip.stateChanged.connect(self._sync_clip_enabled)
        option_layout.addWidget(self.chk_thumbnail)
        option_layout.addWidget(self.chk_images)
        option_layout.addWidget(self.chk_auto_post)
        option_layout.addWidget(self.chk_sns)
        option_layout.addWidget(self.chk_clip)
        option_layout.addWidget(self.chk_tts)
        option_layout.addStretch()
        layout.addLayout(option_layout)

        # 컨트롤 영역
        control_layout = QHBoxLayout()
        self.btn_run = QPushButton("✍️  글 작성 + 이미지 생성 + 해시태그 자동 실행")
        self.btn_run.setMinimumHeight(50)
        self.btn_run.clicked.connect(self.start_generation)
        self.btn_add_task = QPushButton("➕ 새 작업 예약 추가")
        self.btn_add_task.setMinimumHeight(50)
        self.btn_add_task.clicked.connect(self.on_add_task)
        self.btn_preview = QPushButton("🌐 브라우저에서 미리보기 열기 (복사용)")
        self.btn_preview.setMinimumHeight(50)
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(self.open_preview)
        self.btn_open_log = QPushButton("📄 로그 파일 열기")
        self.btn_open_log.setMinimumHeight(50)
        self.btn_open_log.setEnabled(False)
        self.btn_open_log.clicked.connect(self.open_log_file)
        self.btn_open_folder = QPushButton("📂 결과 폴더 열기")
        self.btn_open_folder.setMinimumHeight(50)
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        self.btn_post_draft = QPushButton("📤 네이버 임시저장")
        self.btn_post_draft.setMinimumHeight(50)
        self.btn_post_draft.setEnabled(False)  # 글 생성 완료(on_finished) 후 활성화
        self.btn_post_draft.clicked.connect(self.on_post_draft)
        control_layout.addWidget(self.btn_run)
        control_layout.addWidget(self.btn_add_task)
        control_layout.addWidget(self.btn_preview)
        control_layout.addWidget(self.btn_open_log)
        control_layout.addWidget(self.btn_open_folder)
        control_layout.addWidget(self.btn_post_draft)
        layout.addLayout(control_layout)

        # 예약 작업 목록
        layout.addWidget(QLabel("🗂️ 예약된 작업 목록 (현재 작업이 끝나면 순서대로 자동 실행)"))
        queue_row = QHBoxLayout()
        self.list_queue = QListWidget()
        self.list_queue.setMaximumHeight(90)
        queue_row.addWidget(self.list_queue, stretch=1)
        self.btn_remove_task = QPushButton("🗑️ 선택 삭제")
        self.btn_remove_task.clicked.connect(self.on_remove_task)
        queue_row.addWidget(self.btn_remove_task)
        layout.addLayout(queue_row)

        # 진행 표시
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("대기 중... 제목을 입력하고 버튼을 눌러주세요.")
        layout.addWidget(self.lbl_status)

        # 실행 로그 (네이버 블로그/뉴스 검색이 실제 몇 건 처리됐는지 등 상세 진행 내역)
        layout.addWidget(QLabel("🪵 실행 로그 (블로그·뉴스 검색 등 실제 처리 건수 확인)"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(160)
        self.log_view.setStyleSheet(
            "font-family: Consolas, 'Malgun Gothic', monospace; font-size: 12px;"
        )
        layout.addWidget(self.log_view)

        main_widget.setLayout(layout)
        return main_widget

    # ── 키워드 분석 탭 컬럼 정의 ──
    KW_COLS = ["키워드", "월간 검색량(합계)", "PC", "모바일", "블로그 문서수", "황금점수", "등급", "광고경쟁"]

    def build_keyword_tab(self):
        """🔑 키워드 분석 탭: 시드 입력 → 연관 키워드/검색량/문서수/황금점수 테이블."""
        main_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 상단: 시드 입력 + 분석 시작
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("🌱 시드 키워드"))
        self.kw_seed_input = QLineEdit()
        self.kw_seed_input.setPlaceholderText("예: 감자 보관법")
        self.kw_seed_input.returnPressed.connect(self.start_keyword_analysis)
        self.btn_kw_analyze = QPushButton("🔍 분석 시작")
        self.btn_kw_analyze.clicked.connect(self.start_keyword_analysis)
        top_row.addWidget(self.kw_seed_input, stretch=1)
        top_row.addWidget(self.btn_kw_analyze)
        layout.addLayout(top_row)

        # 중앙: 결과 테이블
        self.kw_table = QTableWidget()
        self.kw_table.setColumnCount(len(self.KW_COLS))
        self.kw_table.setHorizontalHeaderLabels(self.KW_COLS)
        self.kw_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.kw_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.kw_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.kw_table.setSortingEnabled(True)
        header = self.kw_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, len(self.KW_COLS)):
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        layout.addWidget(self.kw_table, stretch=1)

        # 하단: 상태 라벨 + 글쓰기 버튼
        bottom_row = QHBoxLayout()
        self.lbl_kw_status = QLabel("시드 키워드를 입력하고 '분석 시작'을 눌러주세요.")
        self.btn_kw_to_write = QPushButton("✍️ 이 키워드로 글 쓰기")
        self.btn_kw_to_write.clicked.connect(self.on_keyword_to_write)
        bottom_row.addWidget(self.lbl_kw_status, stretch=1)
        bottom_row.addWidget(self.btn_kw_to_write)
        layout.addLayout(bottom_row)

        main_widget.setLayout(layout)
        return main_widget

    def start_keyword_analysis(self):
        """시드 키워드로 KeywordAnalysisThread를 시작한다."""
        if self.keyword_thread is not None and self.keyword_thread.isRunning():
            return
        seed = self.kw_seed_input.text().strip()
        if not seed:
            self.lbl_kw_status.setText("⚠️ 시드 키워드를 입력해주세요.")
            return

        cfg = config_manager.load_config()
        naver_cfg = cfg.get("naver", {})

        # 테이블 초기화 (정렬 일시 해제 후 재활성화하지 않고 갱신 뒤 다시 켠다)
        self.kw_table.setSortingEnabled(False)
        self.kw_table.setRowCount(0)
        self.kw_table.setSortingEnabled(True)

        self.btn_kw_analyze.setEnabled(False)
        # 조회 대상 상위 개수(2차 진행 표시용). 실제 개수는 keywords_ready에서 확정.
        self._kw_doc_total = 0
        self._kw_doc_done = 0
        self._kw_result_count = 0
        self.lbl_kw_status.setText(f"🔍 '{seed}' 연관 키워드 조회 중...")

        self.keyword_thread = KeywordAnalysisThread(naver_cfg, seed)
        self.keyword_thread.keywords_ready.connect(self.on_keywords_ready)
        self.keyword_thread.doc_count_ready.connect(self.on_doc_count_ready)
        self.keyword_thread.finished_signal.connect(self.on_keyword_finished)
        self.keyword_thread.error_signal.connect(self.on_keyword_error)
        # 스레드가 완전히 종료되면 버튼을 다시 활성화한다.
        self.keyword_thread.finished.connect(lambda: self.btn_kw_analyze.setEnabled(True))
        self.keyword_thread.start()

    def _make_num_item(self, value):
        """숫자 정렬이 되도록 DisplayRole에 실제 숫자값을 넣은 셀을 만든다."""
        item = QTableWidgetItem()
        item.setData(Qt.DisplayRole, value)
        return item

    def on_keywords_ready(self, keywords):
        """1차: 연관 키워드+검색량을 테이블에 표시(문서수/점수/등급은 '…')."""
        self._kw_result_count = len(keywords)
        # 문서수 조회 대상은 검색량 상위 MAX_DOC_LOOKUP개
        self._kw_doc_total = min(len(keywords), KeywordAnalysisThread.MAX_DOC_LOOKUP)

        # 행 갱신 중에는 정렬을 꺼서 행이 꼬이지 않게 한다.
        self.kw_table.setSortingEnabled(False)
        self.kw_table.setRowCount(len(keywords))
        for row, item in enumerate(keywords):
            self.kw_table.setItem(row, 0, QTableWidgetItem(item["keyword"]))
            self.kw_table.setItem(row, 1, self._make_num_item(item["total"]))
            self.kw_table.setItem(row, 2, self._make_num_item(item["pc"]))
            self.kw_table.setItem(row, 3, self._make_num_item(item["mobile"]))
            # 문서수/점수/등급은 조회 전이라 "…"
            self.kw_table.setItem(row, 4, QTableWidgetItem("…"))
            self.kw_table.setItem(row, 5, QTableWidgetItem("…"))
            self.kw_table.setItem(row, 6, QTableWidgetItem("…"))
            self.kw_table.setItem(row, 7, QTableWidgetItem(item["comp_idx"]))
        self.kw_table.setSortingEnabled(True)

        self.lbl_kw_status.setText(
            f"연관 키워드 {len(keywords)}개 수신. 블로그 문서수 조회 중... 0/{self._kw_doc_total}"
        )

    def on_doc_count_ready(self, keyword, blog_docs, ratio, grade):
        """2차: 특정 키워드 행을 찾아 문서수/황금점수/등급을 갱신한다."""
        self._kw_doc_done += 1
        self.kw_table.setSortingEnabled(False)
        # 0번 컬럼(키워드)이 일치하는 행을 찾아 갱신 (정렬돼도 안전)
        for row in range(self.kw_table.rowCount()):
            cell = self.kw_table.item(row, 0)
            if cell is not None and cell.text() == keyword:
                self.kw_table.setItem(row, 4, self._make_num_item(blog_docs))
                self.kw_table.setItem(row, 5, self._make_num_item(round(ratio, 2)))
                grade_item = QTableWidgetItem(grade)
                grade_item.setBackground(self._grade_color(grade))
                self.kw_table.setItem(row, 6, grade_item)
                break
        self.kw_table.setSortingEnabled(True)

        self.lbl_kw_status.setText(
            f"블로그 문서수 조회 중... {self._kw_doc_done}/{self._kw_doc_total}"
        )

    def _grade_color(self, grade):
        """등급별 배경색: A=초록/B=주황/C=회색."""
        if grade == "A":
            return QColor("#c8f0c8")
        if grade == "B":
            return QColor("#ffe0a3")
        return QColor("#e0e0e0")

    def on_keyword_finished(self):
        self.lbl_kw_status.setText(
            f"✅ 완료: {self._kw_result_count}개 키워드, 문서수 조회 {self._kw_doc_done}개"
        )

    def on_keyword_error(self, msg):
        self.btn_kw_analyze.setEnabled(True)
        self.lbl_kw_status.setText(f"❌ {msg}")

    def on_keyword_to_write(self):
        """선택된 행의 키워드를 글 작성 탭 input_text에 넣고 그 탭으로 이동한다."""
        row = self.kw_table.currentRow()
        if row < 0:
            self.lbl_kw_status.setText("⚠️ 먼저 표에서 키워드 행을 선택해주세요.")
            return
        cell = self.kw_table.item(row, 0)
        if cell is None:
            self.lbl_kw_status.setText("⚠️ 먼저 표에서 키워드 행을 선택해주세요.")
            return
        keyword = cell.text()
        self.input_text.setPlainText(keyword)
        self.tabs.setCurrentIndex(0)

    def _sync_clip_enabled(self, *args):
        """SNS/클립 체크 상태에 따라 하위 옵션 체크박스 활성/비활성을 맞춘다.
        SNS를 끄면 클립도, 클립을 끄면 나레이션도 의미가 없으므로 비활성화(회색)한다."""
        self.chk_clip.setEnabled(self.chk_sns.isChecked())
        self.chk_tts.setEnabled(self.chk_sns.isChecked() and self.chk_clip.isChecked())

    def get_title_mode(self):
        return "home" if self.radio_home.isChecked() else "info"

    def start_generation(self):
        titles = self.input_text.toPlainText().strip()
        if not titles:
            self.lbl_status.setText("⚠️ 오류: 블로그 제목을 입력해주세요.")
            return

        job = {
            "titles": titles,
            "title_mode": self.get_title_mode(),
            "make_thumbnail": self.chk_thumbnail.isChecked(),
            "make_images": self.chk_images.isChecked(),
            "make_sns": self.chk_sns.isChecked(),
            "make_clip": self.chk_sns.isChecked() and self.chk_clip.isChecked(),
            "make_tts": (self.chk_sns.isChecked() and self.chk_clip.isChecked()
                         and self.chk_tts.isChecked()),
        }
        self.job_queue.append(job)
        self.refresh_queue_list()
        self.try_start_next_job()

    def on_add_task(self):
        """실행 중에도 다음 글감을 입력받아 예약 큐에 추가. '확인'을 누르면 예약 작업으로 등록된다."""
        dlg = AddTaskDialog(self, self.chk_thumbnail.isChecked(), self.chk_images.isChecked(),
                            self.chk_sns.isChecked(), self.chk_clip.isChecked(),
                            self.chk_tts.isChecked(), self.get_title_mode())
        if dlg.exec_() != QDialog.Accepted:
            return

        data = dlg.get_data()
        if not data["titles"]:
            self.lbl_status.setText("⚠️ 예약 작업 추가 실패: 제목을 입력해주세요.")
            return

        self.job_queue.append(data)
        self.refresh_queue_list()
        if self.thread is not None and self.thread.isRunning():
            self.lbl_status.setText(f"📌 예약 작업이 추가되었습니다. (대기 중 {len(self.job_queue)}개)")
        else:
            self.try_start_next_job()

    def refresh_queue_list(self):
        self.list_queue.clear()
        for i, job in enumerate(self.job_queue, 1):
            first_line = job["titles"].split("\n")[0]
            self.list_queue.addItem(f"{i}. {first_line}")

    def on_remove_task(self):
        row = self.list_queue.currentRow()
        if row >= 0:
            del self.job_queue[row]
            self.refresh_queue_list()

    def try_start_next_job(self):
        """현재 실행 중인 작업이 없고 큐에 대기 중인 작업이 있으면 다음 작업을 이어서 시작한다.
        스레드가 완전히 종료된 뒤(QThread 내장 finished 콜백)에서만 호출되므로 레이스가 없다."""
        if self.thread is not None and self.thread.isRunning():
            return
        if not self.job_queue:
            # 큐가 비었으면 다음 실행을 위해 '글 작성' 버튼을 반드시 다시 활성화한다.
            self.btn_run.setEnabled(True)
            return

        job = self.job_queue.pop(0)
        self.refresh_queue_list()
        if not self.run_job(job):
            # 설정 미비 등으로 시작하지 못했으면 작업을 잃지 않도록 큐 맨 앞에 되돌려 놓고,
            # 버튼이 영구 비활성 상태로 남지 않도록 반드시 다시 활성화한다(실패 사유는 상태 라벨에 남음).
            self.job_queue.insert(0, job)
            self.refresh_queue_list()
            self.btn_run.setEnabled(True)

    def run_job(self, job):
        cfg = config_manager.load_config()
        provider = cfg.get("active_provider", "claude")
        settings = cfg.get("providers", {}).get(provider, {})
        provider_cfg = {
            "provider": provider,
            "api_key": settings.get("api_key", ""),
            "base_url": settings.get("base_url", ""),
            "model": settings.get("model", ""),
        }
        if provider != "ollama" and not provider_cfg["api_key"]:
            self.lbl_status.setText("⚠️ '⚙️ 설정' 탭에서 API 키를 입력하고 저장해주세요.")
            return False
        if not provider_cfg["model"]:
            self.lbl_status.setText("⚠️ '⚙️ 설정' 탭에서 모델을 선택하고 저장해주세요.")
            return False

        self.btn_run.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.output_text.clear()
        self.log_view.clear()
        self.progress_bar.setValue(0)
        self._preview_path = None

        # 네이버 검색 API 키는 config.json의 "naver" 섹션에서 스레드로 전달한다.
        naver_cfg = cfg.get("naver", {})
        # 클립 영상 설정(BGM 경로 등)은 config.json의 "video" 섹션에서 전달한다.
        video_cfg = cfg.get("video", {})
        make_sns = job.get("make_sns", True)
        make_clip = make_sns and job.get("make_clip", True)
        make_tts = make_clip and job.get("make_tts", True)
        self.thread = BlogGeneratorThread(
            job["titles"], provider_cfg, job["make_thumbnail"], job["make_images"], naver_cfg,
            make_sns, make_clip, video_cfg, make_tts, job.get("title_mode", "home")
        )
        self._output_dir = self.thread.output_dir
        self._log_path = os.path.join(self.thread.output_dir, "log.txt")
        self.btn_open_log.setEnabled(True)
        self.btn_open_folder.setEnabled(True)
        self.thread.progress_signal.connect(self.lbl_status.setText)
        self.thread.progress_signal.connect(self.append_log)
        self.thread.progress_value.connect(self.progress_bar.setValue)
        self.thread.finished_signal.connect(self.on_finished)
        self.thread.error_signal.connect(self.on_error)
        # 결과 표시(on_finished/on_error)와 별개로, 스레드가 "완전히 종료"된 뒤에만 큐를 재개한다.
        # finished_signal/error_signal 수신 시점에는 워커 스레드가 아직 isRunning()일 수 있어
        # try_start_next_job이 조기 반환하는 레이스가 있었으므로, QThread 내장 finished에 연결한다.
        self.thread.finished.connect(self.on_thread_finished)
        self.thread.start()
        return True

    def append_log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.log_view.append(f"[{timestamp}] {msg}")
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def open_log_file(self):
        if self._log_path and os.path.exists(self._log_path):
            file_url = 'file:///' + os.path.abspath(self._log_path).replace('\\', '/')
            webbrowser.open(file_url)
        else:
            self.lbl_status.setText("⚠️ 로그 파일을 찾을 수 없습니다. 아직 로그가 기록되지 않았을 수 있습니다.")

    def on_finished(self, html_result, preview_path):
        """작업 성공 결과 표시만 담당한다. 큐 재개는 on_thread_finished에서만 처리한다."""
        self.output_text.setPlainText(html_result)
        self._preview_path = preview_path
        self.btn_preview.setEnabled(True)
        # 네이버 자동 임시저장에 쓸 산출물을 워커에서 복사해 두고 버튼을 활성화한다.
        self._last_post_data = getattr(self.thread, "last_post_data", None)
        if self._last_post_data:
            self.btn_post_draft.setEnabled(True)
        if self.job_queue:
            self.lbl_status.setText(f"✅ 작업 완료! 예약된 다음 작업을 이어서 시작합니다. (남은 {len(self.job_queue)}개)")
        else:
            self.lbl_status.setText("✅ 완료! '브라우저에서 미리보기 열기'를 눌러 서식 그대로 복사해 네이버 블로그에 붙여넣으세요.")
        # 자동 임시저장: 체크되어 있으면 완성된 글을 곧바로(또는 대기열로) 임시저장한다.
        if self._last_post_data and self.chk_auto_post.isChecked():
            self.lbl_status.setText("📤 자동 임시저장 시작...")
            self.request_post_draft(self._last_post_data)

    def on_error(self, err_msg):
        """작업 오류 결과 표시만 담당한다. 큐 재개는 on_thread_finished에서만 처리한다."""
        self.lbl_status.setText(f"❌ 오류 발생: {err_msg[:120]}")
        self.output_text.setPlainText(f"[오류 상세]\n{err_msg}")

    def on_thread_finished(self):
        """워커 스레드가 완전히 종료된 뒤 호출되는 콜백. 여기서만 큐를 재개해
        finished_signal/error_signal 수신 시점의 isRunning() 레이스를 피한다."""
        self.try_start_next_job()

    def _is_naver_login_running(self):
        """설정 탭의 네이버 로그인 스레드가 실행 중인지 확인한다(동시 실행 금지용)."""
        login_thread = getattr(self.settings_tab, "naver_login_thread", None)
        return login_thread is not None and login_thread.isRunning()

    def on_post_draft(self):
        """수동 '📤 네이버 임시저장' 버튼 — 자동 임시저장과 같은 대기열 경로를 탄다."""
        if self._last_post_data is None:
            self.lbl_status.setText("⚠️ 먼저 글을 생성해주세요.")
            return
        self.request_post_draft(self._last_post_data)

    def request_post_draft(self, post_data):
        """임시저장 요청 공통 경로(수동 버튼/자동 완료 모두 여기로).

        임시저장 스레드가 이미 실행 중이면 유실 방지를 위해 post_queue에 쌓고,
        아니면 즉시 시작한다."""
        if self.naver_post_thread is not None and self.naver_post_thread.isRunning():
            self.post_queue.append(post_data)
            self.lbl_status.setText(f"📌 임시저장 대기열에 추가됨 ({len(self.post_queue)}개 대기)")
            return
        if self._is_naver_login_running():
            # 로그인과 동시 실행 금지 — 대기열에 넣어 두면 로그인 완료 후 처리된다.
            self.post_queue.append(post_data)
            self.lbl_status.setText(
                f"📌 네이버 로그인 진행 중 — 임시저장 대기열에 추가됨 ({len(self.post_queue)}개 대기)"
            )
            return
        self._start_post_thread(post_data)

    def _start_post_thread(self, post_data):
        """NaverPostThread를 실제로 시작한다. 완전 종료 시 대기열을 이어서 처리한다."""
        self.btn_post_draft.setEnabled(False)
        self.lbl_status.setText("📤 네이버 임시저장을 시작합니다...")
        self.naver_post_thread = NaverPostThread(post_data)
        self.naver_post_thread.progress_signal.connect(self.append_log)
        self.naver_post_thread.progress_signal.connect(self.lbl_status.setText)
        self.naver_post_thread.finished_signal.connect(self.on_post_draft_finished)
        self.naver_post_thread.error_signal.connect(self.on_post_draft_error)
        # QThread가 완전히 종료된 뒤에만 대기열을 재개한다(isRunning 레이스 방지).
        self.naver_post_thread.finished.connect(self.on_post_thread_finished)
        self.naver_post_thread.start()

    def on_post_thread_finished(self):
        """임시저장 스레드가 완전히 종료된 뒤: 대기열에 남은 글을 이어서 임시저장한다."""
        self.drain_post_queue()
        if not (self.naver_post_thread is not None and self.naver_post_thread.isRunning()):
            # 대기열이 비어 더 시작할 게 없으면 수동 버튼을 다시 활성화한다.
            self.btn_post_draft.setEnabled(self._last_post_data is not None)

    def drain_post_queue(self):
        """대기열의 다음 임시저장을 시작한다(스레드/로그인 미실행일 때만).
        설정 탭 로그인 완료 후에도 호출되어 로그인 대기 중 쌓인 글을 처리한다."""
        if not self.post_queue:
            return
        if self.naver_post_thread is not None and self.naver_post_thread.isRunning():
            return
        if self._is_naver_login_running():
            return
        self._start_post_thread(self.post_queue.pop(0))

    def on_post_draft_finished(self):
        self.lbl_status.setText("✅ 네이버 임시저장 완료! 에디터에서 검토 후 직접 발행하세요.")

    def on_post_draft_error(self, msg):
        if msg == "IMPORT":
            self.lbl_status.setText(
                "⚠️ pip install playwright 후 python -m playwright install chromium 필요"
            )
            return
        if "로그인이 필요합니다" in msg:
            self.lbl_status.setText("⚠️ 설정 탭에서 네이버 로그인을 먼저 해주세요")
            return
        self.lbl_status.setText(f"❌ 임시저장 실패: {msg[:120]}")

    def open_preview(self):
        if self._preview_path and os.path.exists(self._preview_path):
            file_url = 'file:///' + os.path.abspath(self._preview_path).replace('\\', '/')
            webbrowser.open(file_url)
        else:
            self.lbl_status.setText("⚠️ 미리보기 파일을 찾을 수 없습니다. 먼저 글을 생성해주세요.")

    def open_output_folder(self):
        """현재/직전 작업의 결과 폴더를 탐색기로 연다."""
        if self._output_dir and os.path.isdir(self._output_dir):
            os.startfile(self._output_dir)
        else:
            self.lbl_status.setText("⚠️ 결과 폴더를 찾을 수 없습니다. 먼저 글을 생성해주세요.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
