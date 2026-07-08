"""순수 텍스트 처리 함수 모음 (PyQt5 등 UI 의존성 없음).

main.py의 BlogGeneratorThread에서 쓰던 텍스트 변환 로직을 UI와 분리해 여기로 옮겼다.
이 모듈은 표준 라이브러리만 사용하므로 PyQt5 없이 단독으로 import·테스트할 수 있다."""

import os
import re
from collections import Counter


def clean_title_lines(raw_titles):
    """붙여넣은 제목 목록에서 순번만 있는 줄(1, 2, 12. 등)을 걸러내 실제 제목 줄만 남긴다."""
    lines = [l.strip() for l in raw_titles.strip().split('\n')]
    return [l for l in lines if l and not re.fullmatch(r'\d+[.)]?', l)]


def extract_main_keyword(title_lines):
    """제목들 사이에 공통으로 가장 많이 등장하는 핵심 개념어 1~2개를 추출해 검색어로 조합한다.
    맨 첫 줄이 안내 문구/헤더일 수 있으므로 '첫 줄 = 키워드'로 가정하지 않고
    전체 줄에서 빈도 기반으로 뽑아야 엉뚱한 주제로 검색하는 것을 막을 수 있다.

    '보관'/'보관법'/'보관방법'/'보관하는'처럼 같은 개념의 파생어가 철자만 갈려 표가
    쪼개지면, 정작 제목들의 진짜 주제(예: '감자 보관법')인데도 그중 하나('감자')만 득표해
    지나치게 뭉뚱그려진 키워드로 뽑히는 문제가 있었다. 공통 접두어(2글자 이상)를 공유하는
    토큰들을 같은 개념 그룹으로 묶어 합산한 뒤, 상위 두 개념을 조합해 검색어로 쓴다."""
    counter = Counter()
    for line in title_lines:
        tokens = set(re.findall(r'[가-힣A-Za-z0-9]{2,}', line))
        counter.update(tokens)
    if not counter:
        return title_lines[0] if title_lines else ""

    # 공통 접두어가 2글자 이상인 토큰들을 같은 개념 그룹으로 합산한다
    # (예: 보관/보관법/보관방법/보관하는 → 공통 접두어 '보관'로 통합).
    # 득표가 많은 토큰부터 그룹 기준으로 삼아야 그 뒤에 나오는 변형들이 안정적으로 모인다.
    groups = {}
    for token, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
        matched_stem = next(
            (stem for stem in groups if len(os.path.commonprefix([token, stem])) >= 2),
            None,
        )
        if matched_stem is None:
            groups[token] = count
        else:
            merged_count = groups.pop(matched_stem) + count
            common = os.path.commonprefix([token, matched_stem])
            groups[common] = merged_count

    ranked = sorted(groups.items(), key=lambda kv: -kv[1])
    top_terms = [term for term, count in ranked if count >= 2][:2]

    if len(top_terms) >= 2:
        # 득표순이 아니라 제목에 등장하는 순서로 배열해야 "감자 보관"처럼 자연스럽게 읽힌다.
        remaining = set(top_terms)
        order_index = {}
        for line in title_lines:
            for tok in re.findall(r'[가-힣A-Za-z0-9]{2,}', line):
                for term in list(remaining):
                    if tok.startswith(term) or term.startswith(tok):
                        order_index[term] = len(order_index)
                        remaining.discard(term)
            if not remaining:
                break
        top_terms.sort(key=lambda t: order_index.get(t, 999))

    if top_terms:
        return " ".join(top_terms)
    return title_lines[0] if title_lines else ""


def title_contains_keyword(title, keyword):
    """제목에 메인키워드가 중간에 다른 말이 끼어들지 않고 하나로 붙어서 포함되어 있는지 확인.

    메인키워드가 '대장암 초기증상'처럼 여러 단어로 되어 있어도, 공백 유무 차이(예: '대장암  초기증상',
    '대장암초기증상')는 허용하되 '대장암 이럴 때 초기증상'처럼 사이에 다른 단어가 끼어들면 위반으로
    판단한다. 공백을 전부 제거한 뒤 부분 문자열로 포함되는지만 확인하면 이 두 경우를 정확히 구분할 수 있다."""
    if not keyword or not keyword.strip():
        return True
    normalized_keyword = re.sub(r'\s+', '', keyword)
    normalized_title = re.sub(r'\s+', '', title)
    return normalized_keyword in normalized_title


def title_starts_with_keyword(title, keyword):
    """제목이 메인키워드로 '시작'하는지 확인 (정보 전달용 제목 규칙 검증).

    title_contains_keyword와 동일하게 공백 유무 차이는 허용하되(정규화 후 비교), 포함 위치가
    아니라 맨 앞에 오는지까지 확인한다는 점이 다르다."""
    if not keyword or not keyword.strip():
        return True
    normalized_keyword = re.sub(r'\s+', '', keyword)
    normalized_title = re.sub(r'\s+', '', title)
    return normalized_title.startswith(normalized_keyword)


def parse_keyword_analysis(raw_text, fallback_keyword=""):
    """글감(참고 제목들) 분석 LLM 응답(===KEYWORD===/===TONE===/===OUTLINE=== 마커 형식)을 파싱.

    마커가 없거나 파싱에 실패하면 조용히 실패하지 않고 fallback_keyword(기존 빈도 기반
    extract_main_keyword 결과)로 안전하게 폴백한다 — API 응답 포맷이 흔들려도 파이프라인이
    죽지 않아야 하기 때문."""
    result = {"keyword": fallback_keyword, "tone": "", "outline": []}
    try:
        if '===KEYWORD===' not in raw_text or '===TONE===' not in raw_text:
            return result

        after_keyword = raw_text.split('===KEYWORD===', 1)[1]
        keyword_part, after_keyword = after_keyword.split('===TONE===', 1)
        keyword_candidate = keyword_part.strip()
        if keyword_candidate:
            result["keyword"] = keyword_candidate

        if '===OUTLINE===' in after_keyword:
            tone_part, outline_part = after_keyword.split('===OUTLINE===', 1)
            result["tone"] = tone_part.strip()
            result["outline"] = [
                re.sub(r'^[-*]\s*', '', line).strip()
                for line in outline_part.strip().split('\n')
                if line.strip()
            ]
        else:
            result["tone"] = after_keyword.strip()
    except Exception:
        pass
    return result


def extract_headings(text):
    """마크다운 텍스트에서 H2 소제목만 추출 (본문 이미지는 H2 단락당 1개만 생성)"""
    headings = re.findall(r'^#{2}\s+(.+)$', text, re.MULTILINE)
    return headings


def _is_table_row(line):
    """'| a | b |' 형태의 마크다운 표 행인지 확인 (최소 파이프 1개 포함)."""
    return '|' in line.strip()


def _is_table_separator(line):
    """'|---|---|' / '| :--- | ---: |' 같은 헤더 구분선인지 확인."""
    stripped = line.strip()
    return bool(stripped) and bool(re.fullmatch(r'[\s|:-]+', stripped)) and '-' in stripped


def _split_table_row(line):
    """표 행 문자열을 셀 텍스트 리스트로 분리한다(앞뒤 파이프는 있어도 없어도 됨)."""
    stripped = line.strip()
    if stripped.startswith('|'):
        stripped = stripped[1:]
    if stripped.endswith('|'):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split('|')]


def _render_table(header_cells, body_rows):
    """마크다운 표를 네이버 에디터 붙여넣기용 실제 <table> HTML로 렌더링.
    외부 스타일시트는 복사 시 함께 전달되지 않으므로 셀마다 inline style을 직접 붙인다."""
    th_style = 'border:1px solid #ddd;padding:8px 10px;background:#f5f5f5;font-weight:bold;text-align:left;'
    td_style = 'border:1px solid #ddd;padding:8px 10px;text-align:left;'
    rows_html = ['<tr>' + ''.join(f'<th style="{th_style}">{c}</th>' for c in header_cells) + '</tr>']
    for row in body_rows:
        rows_html.append('<tr>' + ''.join(f'<td style="{td_style}">{c}</td>' for c in row) + '</tr>')
    return (
        '<table style="border-collapse:collapse;width:100%;margin:12px 0;">'
        + ''.join(rows_html) + '</table>'
    )


def format_for_naver(text, thumbnail_file, heading_files, hashtags, title=""):
    """
    윤문된 마크다운 텍스트를 네이버 스마트에디터 복붙용 HTML로 변환.
    소제목(##) 바로 뒤에 해당 이미지를 실제로 삽입한다(브라우저 미리보기에서
    렌더링된 화면을 그대로 복사해 붙여넣는 방식이므로 플레이스홀더가 아닌 실제 <img> 사용).
    연속된 '- '/'* ' 리스트 라인들은 <ul>...</ul>로 묶는다.
    '| a | b |' 형태의 마크다운 표는 실제 <table>로 변환한다(그냥 <p>로 찍으면
    붙여넣었을 때 표 구조가 깨지고 파이프 기호만 텍스트로 남는 문제가 있었다).
    """
    lines = text.split('\n')
    html_lines = []
    heading_idx = 0  # 소제목별 이미지 인덱스 (0부터: heading_files[0] ~)
    in_list = False  # 현재 연속 리스트(<ul>)를 여는 중인지 추적

    def close_list():
        """리스트가 아닌 요소를 만나면 열려 있던 <ul>을 먼저 닫는다."""
        nonlocal in_list
        if in_list:
            html_lines.append('</ul>')
            in_list = False

    def bold(s):
        return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', s)

    if title:
        html_lines.append(f'<h1>{title}</h1>')

    if thumbnail_file:
        html_lines.append(
            f'<img src="{thumbnail_file}" alt="썸네일" '
            f'style="max-width:100%;border-radius:8px;margin-bottom:16px;" />'
        )

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            close_list()
            html_lines.append('<br>')
            i += 1
            continue

        # 표 감지: 현재 줄이 파이프 행이고, 바로 다음 줄이 구분선(|---|---|)이면 표 시작.
        if _is_table_row(stripped) and i + 1 < n and _is_table_separator(lines[i + 1]):
            close_list()
            header_cells = [bold(c) for c in _split_table_row(stripped)]
            i += 2  # 헤더 행 + 구분선 소비
            body_rows = []
            while i < n and _is_table_row(lines[i].strip()) and lines[i].strip():
                body_rows.append([bold(c) for c in _split_table_row(lines[i])])
                i += 1
            html_lines.append(_render_table(header_cells, body_rows))
            continue

        # ** 볼드 마크다운을 모든 라인 유형에 우선 적용
        stripped = bold(stripped)

        if stripped.startswith('### '):
            close_list()
            html_lines.append(f'<h3>{stripped[4:]}</h3>')
            # H3는 이미지 없음 (본문 이미지는 H2 단락당 1개만 생성)
        elif stripped.startswith('## '):
            close_list()
            html_lines.append(f'<h2>{stripped[3:]}</h2>')
            img_file = heading_files[heading_idx] if heading_idx < len(heading_files) else None
            heading_idx += 1
            if img_file:
                html_lines.append(
                    f'<img src="{img_file}" alt="소제목 이미지" '
                    f'style="max-width:100%;border-radius:8px;margin:12px 0;" />'
                )
        elif stripped.startswith('# '):
            close_list()
            html_lines.append(f'<h1>{stripped[2:]}</h1>')
        elif stripped.startswith('- ') or stripped.startswith('* '):
            # 연속된 리스트 라인은 하나의 <ul>로 감싼다.
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            html_lines.append(f'<li>{stripped[2:]}</li>')
        else:
            close_list()
            html_lines.append(f'<p>{stripped}</p>')

        i += 1

    # 본문 끝에서 리스트가 아직 열려 있으면 닫는다.
    close_list()

    # 해시태그 섹션 추가
    clean_hashtags = hashtags.strip()
    html_lines.append('<br>')
    html_lines.append(
        f'<p style="background:#f5f5f5;padding:16px;border-radius:8px;'
        f'font-size:14px;color:#555;line-height:2;">{clean_hashtags}</p>'
    )

    return "\n".join(html_lines)


def build_preview_html(body_html):
    """브라우저에서 열어 Ctrl+A/C로 그대로 복사할 수 있는 완전한 HTML 문서 생성."""
    # 안내 배너: user-select:none으로 지정해 Ctrl+A 전체 선택·복사 시 선택 범위에서 제외되도록 한다
    # (배너 문구가 네이버 에디터에 같이 붙는 것을 막기 위함).
    notice_banner = (
        '<div style="background:#fff3cd;border:1px solid #ffe08a;color:#7a5b00;'
        'padding:14px 18px;border-radius:8px;margin-bottom:24px;font-size:14px;'
        'font-weight:bold;line-height:1.6;user-select:none;-webkit-user-select:none;">'
        '⚠️ 아래 이미지들은 복사해도 네이버 에디터에 붙지 않습니다. '
        '글을 붙여넣은 뒤, 결과 폴더의 PNG 파일을 에디터로 드래그해서 넣어주세요.'
        '</div>'
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>블로그 미리보기 (여기서 전체 선택 후 복사하세요)</title>
<style>
  body {{ font-family: 'Malgun Gothic', 'Noto Sans KR', sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px 60px; line-height: 1.8; color: #222; }}
  h1 {{ font-size: 26px; margin: 0 0 20px; }}
  h2 {{ font-size: 20px; margin-top: 32px; border-left: 4px solid #4a90d9; padding-left: 10px; }}
  h3 {{ font-size: 17px; margin-top: 20px; }}
  img {{ display: block; max-width: 100%; height: auto; }}
  li {{ margin-left: 20px; }}
  p {{ margin: 10px 0; }}
</style>
</head>
<body>
{notice_banner}
{body_html}
</body>
</html>"""
