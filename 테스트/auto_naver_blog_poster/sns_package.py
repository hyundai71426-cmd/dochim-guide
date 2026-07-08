"""SNS 패키지 생성 모듈 (PyQt5·네트워크 무의존, 표준 라이브러리만 사용).

블로그 글 1편으로부터 카드뉴스 세트(표지/본문/CTA)의 HTML과
스레드/인스타 공용 본문·해시태그를 만들기 위한 순수 함수 모음이다.

- 실제 LLM 호출은 호출자(main.py의 BlogGeneratorThread)가 담당한다.
  이 모듈은 프롬프트 문자열 생성(build_sns_prompt)과 응답 파싱(parse_sns_package),
  그리고 고정 HTML/CSS 템플릿 렌더링(render_*)만 책임진다.
- 디자인·문구 규칙의 근거는 CARD_NEWS_GUIDE.md 참고.
"""

import html
import hashlib


# ── 색 테마 3종 (CARD_NEWS_GUIDE §3: 카드 1장에 색 2~3개만) ──
# 각 테마는 배경/본문 텍스트/포인트/보조(진행표시 등) 4색으로 구성한다.
THEMES = [
    # 1) 라이트 크림 배경 + 딥네이비 텍스트 + 오렌지 포인트
    {"bg": "#faf6ee", "text": "#1f2a44", "accent": "#f2762e", "sub": "#9aa0ad"},
    # 2) 딥네이비 배경 + 화이트 텍스트 + 옐로 포인트
    {"bg": "#16203a", "text": "#f5f7fb", "accent": "#ffcf3f", "sub": "#7f8aa6"},
    # 3) 화이트 배경 + 차콜 텍스트 + 블루 포인트
    {"bg": "#ffffff", "text": "#22262e", "accent": "#2f6bff", "sub": "#a2a8b4"},
]

# 카드뉴스 크기(1:1). CARD_NEWS_GUIDE §3에 따라 1080×1080 고정.
CARD_SIZE = 1080

# 네이버 클립(세로 숏폼)용 카드 크기(9:16).
CLIP_SIZE = (1080, 1920)

# LLM 출력 마커
_M_COVER = "===COVER==="
_M_CARD = "===CARD==="
_M_LAST = "===LAST==="
_M_SNS = "===SNS==="
_M_CLIP = "===CLIP==="
_M_HASHTAGS = "===HASHTAGS==="

# 공용 SNS 본문 권장 한도(자). 초과 시 호출자가 경고만 남긴다.
SNS_TEXT_LIMIT = 500

# 네이버 클립 설명 권장 한도(자, 공백 포함). 초과 시 호출자가 경고만 남긴다.
CLIP_TEXT_LIMIT = 300


def _escape_and_mark(raw_text, accent_color):
    """사용자 텍스트를 안전하게 HTML로 변환한다.

    순서가 중요하다: 먼저 리터럴 백슬래시+n("\\n" 두 글자, LLM이 실제 개행 대신 이스케이프
    시퀀스를 문자 그대로 출력하는 경우가 있어 이를 실제 개행으로 정규화)을 실제 개행으로
    바꾼 뒤, html.escape로 전체를 이스케이프하고, `**...**` 강조 마크만 accent 색 span으로
    치환하고, 마지막에 개행을 <br>로 바꾼다.
    (escape를 먼저 하므로 <script> 같은 입력은 그대로 이스케이프되어 안전하다.)
    """
    # LLM 응답에 실제 개행 문자 대신 "\n"이라는 두 글자(백슬래시+n)가 그대로 섞여 나오는
    # 경우가 있다(카드뉴스 표지 프롬프트가 "줄바꿈(\n)을 넣어"라고 지시하기 때문). 이걸 미리
    # 실제 개행으로 정규화하지 않으면 화면에 "\n" 글자가 그대로 노출된다.
    normalized = raw_text.replace("\\n", "\n")
    escaped = html.escape(normalized)
    # **강조** → accent 색 span. escape 이후이므로 별표는 그대로 남아 있다.
    result = []
    i = 0
    while i < len(escaped):
        if escaped[i:i + 2] == "**":
            end = escaped.find("**", i + 2)
            if end != -1:
                inner = escaped[i + 2:end]
                result.append(
                    f'<span style="color:{accent_color};">{inner}</span>'
                )
                i = end + 2
                continue
        result.append(escaped[i])
        i += 1
    marked = "".join(result)
    # 줄바꿈은 <br>로 반영
    return marked.replace("\n", "<br>")


def _resolve_size(size):
    """size=(w, h) 튜플을 (width, height)로 정규화한다. None이면 기본 정사각 카드."""
    if size is None:
        return CARD_SIZE, CARD_SIZE
    return size[0], size[1]


def _page_head(size=None):
    """모든 카드 공통 <head> — Noto Sans KR 구글 폰트 link + body 리셋.

    size=(width, height) 미지정 시 기본 정사각(1080×1080)."""
    width, height = _resolve_size(size)
    return (
        '<head>'
        '<meta charset="utf-8">'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?'
        'family=Noto+Sans+KR:wght@400;700;900&display=swap" rel="stylesheet">'
        '<style>'
        '* { margin:0; padding:0; box-sizing:border-box; }'
        f'body {{ margin:0; padding:0; width:{width}px; height:{height}px; '
        "font-family:'Noto Sans KR', sans-serif; }"
        '</style>'
        '</head>'
    )


def render_cover(cover_text, theme, size=None):
    """표지 카드 HTML(기본 1080×1080, size=(w,h)로 세로형 등 오버라이드 가능).

    후킹 문구를 크고 굵게 중앙 배치. 입력의 \n 줄바꿈을 그대로 반영하고,
    `**단어**`는 accent 색으로 강조한다. 배경은 단순(단색 + 은은한 장식원)."""
    body_html = _escape_and_mark(cover_text, theme["accent"])
    return (
        '<!doctype html><html>' + _page_head(size) +
        f'<body style="background:{theme["bg"]};">'
        # 은은한 장식 요소(모서리의 큰 반투명 원) — 배경은 단순하게 유지
        f'<div style="position:absolute; top:-160px; right:-160px; '
        f'width:460px; height:460px; border-radius:50%; '
        f'background:{theme["accent"]}; opacity:0.10;"></div>'
        f'<div style="position:absolute; bottom:-200px; left:-160px; '
        f'width:420px; height:420px; border-radius:50%; '
        f'background:{theme["accent"]}; opacity:0.07;"></div>'
        # 중앙 문구 영역 — 여백 넉넉히
        f'<div style="width:100%; height:100%; display:flex; '
        f'align-items:center; justify-content:center; padding:120px 100px; '
        f'position:relative; z-index:1;">'
        f'<div style="color:{theme["text"]}; font-weight:900; '
        f'font-size:96px; line-height:1.28; text-align:center; '
        f'word-break:keep-all;">{body_html}</div>'
        '</div>'
        '</body></html>'
    )


def render_content(idx, total, card_title, card_body, theme, size=None):
    """본문 카드 HTML(기본 1080×1080, size=(w,h)로 오버라이드 가능).

    상단에 진행 표시 "idx/total"(sub 색), 제목(굵게, accent 강조 가능),
    본문(text 색). 중앙 정렬, 여백 충분."""
    progress = f"{idx}/{total}"
    title_html = _escape_and_mark(card_title, theme["accent"])
    body_html = _escape_and_mark(card_body, theme["accent"])
    return (
        '<!doctype html><html>' + _page_head(size) +
        f'<body style="background:{theme["bg"]};">'
        f'<div style="width:100%; height:100%; display:flex; '
        f'flex-direction:column; align-items:center; justify-content:center; '
        f'padding:120px 110px; text-align:center; word-break:keep-all;">'
        # 진행 표시
        f'<div style="color:{theme["sub"]}; font-size:36px; '
        f'font-weight:700; letter-spacing:2px; margin-bottom:48px;">{progress}</div>'
        # 제목
        f'<div style="color:{theme["text"]}; font-size:76px; '
        f'font-weight:900; line-height:1.3; margin-bottom:44px;">{title_html}</div>'
        # 본문
        f'<div style="color:{theme["text"]}; font-size:46px; '
        f'font-weight:400; line-height:1.55; opacity:0.9;">{body_html}</div>'
        '</div>'
        '</body></html>'
    )


def render_last(summary, cta, theme, size=None):
    """마지막(CTA) 카드 HTML(기본 1080×1080, size=(w,h)로 오버라이드 가능).

    요약 1줄 + CTA 문구 강조 + 하단에 블로그 유도 문구."""
    summary_html = _escape_and_mark(summary, theme["accent"])
    cta_html = _escape_and_mark(cta, theme["accent"])
    return (
        '<!doctype html><html>' + _page_head(size) +
        f'<body style="background:{theme["bg"]};">'
        f'<div style="position:absolute; bottom:-180px; right:-140px; '
        f'width:420px; height:420px; border-radius:50%; '
        f'background:{theme["accent"]}; opacity:0.08;"></div>'
        f'<div style="width:100%; height:100%; display:flex; '
        f'flex-direction:column; align-items:center; justify-content:center; '
        f'padding:120px 110px; text-align:center; word-break:keep-all; '
        f'position:relative; z-index:1;">'
        # 요약 1줄
        f'<div style="color:{theme["text"]}; font-size:52px; '
        f'font-weight:700; line-height:1.5; margin-bottom:60px;">{summary_html}</div>'
        # CTA 강조 박스
        f'<div style="color:{theme["bg"]}; background:{theme["accent"]}; '
        f'font-size:56px; font-weight:900; line-height:1.35; '
        f'padding:36px 56px; border-radius:28px;">{cta_html}</div>'
        # 하단 블로그 유도
        f'<div style="color:{theme["sub"]}; font-size:38px; '
        f'font-weight:700; margin-top:72px;">자세한 내용은 블로그에</div>'
        '</div>'
        '</body></html>'
    )


def build_sns_prompt(blog_text, blog_title):
    """LLM에 보낼 SNS 패키지 생성 프롬프트 문자열을 만든다.

    문구 규칙은 CARD_NEWS_GUIDE.md의 공식(구체적 이득·숫자·타깃 등)을 반영한다.
    반드시 지정된 마커 형식으로만 출력하도록 강하게 지시한다."""
    return f"""당신은 블로그 글 한 편을 인스타/스레드용 카드뉴스와 SNS 글로 재구성하는 SNS 콘텐츠 에디터입니다.
아래 블로그 글을 바탕으로, 지정된 형식에 맞춰 SNS 패키지를 작성하세요.

[블로그 제목]
{blog_title}

[블로그 본문]
{blog_text}

[표지 문구 규칙]
- 8단어 이내의 후킹 문구. 추상 표현 금지, 낚시 금지.
- 구체적 이득 + 숫자 + 타깃을 우선 반영하세요. (예: "알바생을 위한 노동법 7가지")
- 표지에 개수를 쓰면(예: "꿀팁 3가지") 반드시 실제 본문 카드 장수와 일치시키세요.
- 강조할 단어 1~2개를 **단어** 형태로 표시하세요.
- 두세 단어 단위로 줄바꿈(\\n)을 넣어 한 번에 인식되게 하세요.

[본문 카드 규칙]
- 카드 4~8장. 카드 1장 = 메시지 1개. 여러 내용을 욱여넣지 마세요.
- 제목은 20자 이내, 내용은 50자 내외.
- 블로그 소제목(H2)을 그대로 요약하지 말고, 독자에게 유용한 단위로 재구성하세요.

[마지막 카드 규칙]
- 핵심 요약 1줄 + 저장 유도 CTA(예: "저장해두고 필요할 때 보세요").

[SNS 본문 규칙]
- 스레드/인스타에 공용으로 쓸 하나의 글. 반드시 500자 이내.
- 후킹 첫 줄 + 핵심 요약 + "블로그에 전문" 마무리 구조.
- 해시태그는 넣지 마세요(별도 섹션에서 출력).

[클립 설명 규칙]
- 네이버 클립(숏폼 영상) 설명란에 넣을 글. 반드시 300자 이내(공백 포함).
- 글의 핵심 내용이 요약되어 있어야 합니다.
- 첫 문장은 후킹, 마지막은 "블로그에 전문이 있다"는 마무리로 끝내세요.
- 해시태그·이모지 남발은 금지합니다.

[해시태그 규칙]
- 인스타용 해시태그 10개 내외. # 기호로 공백 구분.

[출력 형식 - 아래 마커를 그대로 사용]
{_M_COVER}
(표지 문구)
{_M_CARD}
제목: (카드 제목)
내용: (카드 내용)
{_M_CARD}
(카드 반복)
{_M_LAST}
요약: (핵심 요약 1줄)
CTA: (저장 유도 문구)
{_M_SNS}
(스레드/인스타 공용 본문)
{_M_CLIP}
(네이버 클립 설명 - 300자 이내)
{_M_HASHTAGS}
#태그1 #태그2 ...

[절대 금지]
- 위 출력 형식 이외의 어떠한 텍스트도 출력하지 마세요.
"""


def _strip_label(line, *labels):
    """줄 앞에 붙은 라벨(예: "제목:", "요약:")을 있으면 떼고 값만 반환한다."""
    stripped = line.strip()
    for label in labels:
        if stripped.startswith(label):
            return stripped[len(label):].strip()
    return stripped


def _parse_card(block):
    """하나의 카드 블록 텍스트에서 제목/내용을 뽑는다.

    "제목:"/"내용:" 라벨 유무를 모두 방어한다. 라벨이 없으면
    첫 줄을 제목, 나머지를 내용으로 본다."""
    lines = [ln for ln in block.split("\n") if ln.strip()]
    if not lines:
        return None
    title = ""
    body_parts = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("제목:"):
            title = _strip_label(s, "제목:")
        elif s.startswith("내용:"):
            body_parts.append(_strip_label(s, "내용:"))
        else:
            # 라벨이 없는 줄: 제목이 아직 없으면 제목으로, 있으면 내용으로 취급
            if not title:
                title = s
            else:
                body_parts.append(s)
    body = " ".join(body_parts).strip()
    if not title and not body:
        return None
    return {"title": title, "body": body}


def parse_sns_package(raw):
    """LLM 응답(raw)을 마커 기준으로 파싱해 dict로 반환한다.

    반환: {"cover", "cards"[{"title","body"}...], "summary", "cta",
           "sns_text", "clip_text", "hashtags"}
    마커가 누락되면 해당 필드는 빈 값/빈 리스트로 둔다(판단은 호출자 몫).
    cover가 비어 있으면 그대로 빈 문자열을 반환한다."""
    result = {
        "cover": "",
        "cards": [],
        "summary": "",
        "cta": "",
        "sns_text": "",
        "clip_text": "",
        "hashtags": "",
    }
    if not raw:
        return result

    text = raw.replace("\r\n", "\n")

    # ── COVER: ===COVER=== 이후 ~ 다음 마커 전까지 ──
    cover_idx = text.find(_M_COVER)
    if cover_idx != -1:
        after = text[cover_idx + len(_M_COVER):]
        # 다음 마커 위치(가장 먼저 나오는 것)까지 잘라낸다
        cut = _first_marker_pos(after, [_M_CARD, _M_LAST, _M_SNS, _M_CLIP, _M_HASHTAGS])
        result["cover"] = after[:cut].strip() if cut is not None else after.strip()

    # ── CARDS: 각 ===CARD=== 블록 ──
    # LAST/SNS/HASHTAGS가 시작되기 전까지의 영역에서만 카드를 찾는다.
    cards_region = text
    region_end = _first_marker_pos(text, [_M_LAST, _M_SNS, _M_CLIP, _M_HASHTAGS])
    if region_end is not None:
        cards_region = text[:region_end]
    card_chunks = cards_region.split(_M_CARD)
    # 첫 조각은 COVER 영역이므로 버리고 이후만 카드로 취급
    for chunk in card_chunks[1:]:
        card = _parse_card(chunk)
        if card is not None:
            result["cards"].append(card)

    # ── LAST: 요약/CTA ──
    last_idx = text.find(_M_LAST)
    if last_idx != -1:
        after = text[last_idx + len(_M_LAST):]
        cut = _first_marker_pos(after, [_M_SNS, _M_CLIP, _M_HASHTAGS])
        last_block = after[:cut] if cut is not None else after
        for ln in last_block.split("\n"):
            s = ln.strip()
            if not s:
                continue
            if s.startswith("요약:"):
                result["summary"] = _strip_label(s, "요약:")
            elif s.startswith("CTA:"):
                result["cta"] = _strip_label(s, "CTA:")
            elif not result["summary"]:
                # 라벨 없는 첫 줄은 요약으로 방어
                result["summary"] = s
            elif not result["cta"]:
                result["cta"] = s

    # ── SNS: 공용 본문 ──
    sns_idx = text.find(_M_SNS)
    if sns_idx != -1:
        after = text[sns_idx + len(_M_SNS):]
        cut = _first_marker_pos(after, [_M_CLIP, _M_HASHTAGS])
        result["sns_text"] = (after[:cut] if cut is not None else after).strip()

    # ── CLIP: 네이버 클립 설명 ──
    clip_idx = text.find(_M_CLIP)
    if clip_idx != -1:
        after = text[clip_idx + len(_M_CLIP):]
        cut = _first_marker_pos(after, [_M_HASHTAGS])
        result["clip_text"] = (after[:cut] if cut is not None else after).strip()

    # ── HASHTAGS ──
    tag_idx = text.find(_M_HASHTAGS)
    if tag_idx != -1:
        result["hashtags"] = text[tag_idx + len(_M_HASHTAGS):].strip()

    return result


def _first_marker_pos(text, markers):
    """text에서 주어진 마커들 중 가장 먼저 등장하는 위치를 반환(없으면 None)."""
    positions = [text.find(m) for m in markers]
    positions = [p for p in positions if p != -1]
    return min(positions) if positions else None


def pick_theme(seed_text):
    """제목 문자열 해시로 THEMES 중 하나를 결정한다.

    같은 글(같은 seed_text)은 항상 같은 테마를 받는다(재현성)."""
    digest = hashlib.md5((seed_text or "").encode("utf-8")).hexdigest()
    return THEMES[int(digest, 16) % len(THEMES)]
