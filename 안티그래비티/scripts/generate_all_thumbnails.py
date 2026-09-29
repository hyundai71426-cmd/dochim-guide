import asyncio
import os
import sys
import json
import time

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright

# 썸네일 템플릿 생성 함수 (레퍼런스 100% 일치)
def get_thumbnail_html(bg_image_url, line1_text, highlight_text, line3_text=None):
    line3_html = f'<div class="sub-text">{line3_text}</div>' if line3_text else ''
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: "Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
            -webkit-font-smoothing: antialiased;
        }}
        body {{
            width: 1080px;
            height: 1080px;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #000000;
        }}
        .thumbnail {{
            width: 1080px;
            height: 1080px;
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            overflow: hidden;
            background-image: url('{bg_image_url}');
            background-size: cover;
            background-position: center;
        }}
        /* 어두운 무드 오버레이 & 미세 블러 */
        .overlay {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(180deg, rgba(0,0,0,0.60) 0%, rgba(0,0,0,0.78) 50%, rgba(0,0,0,0.65) 100%);
            backdrop-filter: blur(1.5px);
        }}
        
        .content {{
            position: relative;
            z-index: 10;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 92%;
            gap: 12px;
        }}
        
        /* 상단 흰색 글씨 */
        .top-text {{
            font-size: 100px;
            font-weight: 900;
            color: #ffffff;
            line-height: 1.18;
            letter-spacing: -3px;
            -webkit-text-stroke: 8px #000000;
            paint-order: stroke fill;
            text-shadow: 0 10px 25px rgba(0, 0, 0, 0.9);
            word-break: keep-all;
        }}
        
        /* 중앙 형광 네온 라임 강조 글씨 */
        .highlight-text {{
            font-size: 130px;
            font-weight: 900;
            color: #ccff00;
            line-height: 1.15;
            letter-spacing: -3px;
            -webkit-text-stroke: 10px #000000;
            paint-order: stroke fill;
            text-shadow: 0 12px 30px rgba(0, 0, 0, 0.95);
            word-break: keep-all;
        }}
        
        /* 하단 보조 흰색 글씨 */
        .sub-text {{
            font-size: 80px;
            font-weight: 900;
            color: #ffffff;
            line-height: 1.2;
            letter-spacing: -2px;
            -webkit-text-stroke: 7px #000000;
            paint-order: stroke fill;
            text-shadow: 0 10px 25px rgba(0, 0, 0, 0.9);
            margin-top: 6px;
            word-break: keep-all;
        }}
    </style>
</head>
<body>
    <div class="thumbnail">
        <div class="overlay"></div>
        <div class="content">
            <div class="top-text">{line1_text}</div>
            <div class="highlight-text">{highlight_text}</div>
            {line3_html}
        </div>
    </div>
</body>
</html>"""

# 50개 아티클 맞춤형 메타데이터
THUMBNAIL_CONFIGS = [
    {
        "order": 1,
        "id": "post-01",
        "file": "thumb_post01.png",
        "bg": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=1080&auto=format&fit=crop", # 고층 복합빌딩
        "line1": "내 땅에 맞는 최적의 사업은?",
        "highlight": "공공 vs 민간 복합개발",
        "line3": "토지 소유권 유지 & 용적률 140% 완화"
    },
    {
        "order": 2,
        "id": "post-02",
        "file": "thumb_post02.png",
        "bg": "https://images.unsplash.com/photo-1541888946425-d0fbb180c5f5?q=80&w=1080&auto=format&fit=crop", # 건설 현장 타워크레인
        "line1": "15년 재개발 인허가 혁신",
        "highlight": "3년 만에 착공 직행",
        "line3": "조합 설립 생략 + 8대 원스톱 통합심의"
    },
    {
        "order": 3,
        "id": "post-03",
        "file": "thumb_post03.png",
        "bg": "https://images.unsplash.com/photo-1519501025264-65ba15a82390?q=80&w=1080&auto=format&fit=crop", # 도심 야경 도시계획
        "line1": "내 집도 복합개발 대상일까?",
        "highlight": "역세권·준공업·저층주거",
        "line3": "3대 사업유형별 필수 지정 요건 총정리"
    },
    {
        "order": 4,
        "id": "post-04",
        "file": "thumb_post04.png",
        "bg": "https://images.unsplash.com/photo-1450133064473-71024230f91b?q=80&w=1080&auto=format&fit=crop", # 서류/동의서
        "line1": "주민 동의율 67% 넘기면 끝?",
        "highlight": "토지면적 50%의 함정",
        "line3": "알박기 방지 & 토지 면적 동의율 승리 전략"
    },
    {
        "order": 5,
        "id": "post-05",
        "file": "thumb_post05.png",
        "bg": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?q=80&w=1080&auto=format&fit=crop", # 비즈니스/심의
        "line1": "원스톱 인허가 패스트트랙",
        "highlight": "8대 심의를 1번에 통합",
        "line3": "건축·교통·환경·교육 심의 일괄 통과"
    },
    {
        "order": 6,
        "id": "post-06",
        "file": "thumb_post06.png",
        "bg": "https://images.unsplash.com/photo-1497366216548-37526070297c?q=80&w=1080&auto=format&fit=crop", # 오피스 회의실
        "line1": "총괄사업관리자 누구에게?",
        "highlight": "신탁사 vs LH 완벽 비교",
        "line3": "수수료율·공사속도·브랜드 선택권 분석"
    },
    {
        "order": 7,
        "id": "post-07",
        "file": "thumb_post07.png",
        "bg": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?q=80&w=1080&auto=format&fit=crop", # 계약서 서명
        "line1": "내 땅 등기 넘겨야 한다고?",
        "highlight": "토지 신탁 vs 공공 수용",
        "line3": "소유권 방어 & 신탁등기 안전성 팩트체크"
    },
    {
        "order": 8,
        "id": "post-08",
        "file": "thumb_post08.png",
        "bg": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?q=80&w=1080&auto=format&fit=crop", # 법원 저울
        "line1": "도심복합구역 지정 즉시",
        "highlight": "현금청산 피하는 법",
        "line3": "권리산정기준일 & 매매·증여 실전 가이드"
    },
    {
        "order": 9,
        "id": "post-09",
        "file": "thumb_post09.png",
        "bg": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?q=80&w=1080&auto=format&fit=crop", # 고급 주상복합
        "line1": "단독주택·다가구 소유자 필독",
        "highlight": "1+1 아파트 2채 분양",
        "line3": "종전자산평가액 & 전용면적 3대 요건"
    },
    {
        "order": 10,
        "id": "post-10",
        "file": "thumb_post10.png",
        "bg": "https://images.unsplash.com/photo-1513694203232-719a280e022f?q=80&w=1080&auto=format&fit=crop", # 상가 거리
        "line1": "상가주택·근생 소유자 생존권",
        "highlight": "상가 분양 & 영업보상",
        "line3": "우선공급권 자격 & 휴업손실 완벽 보상"
    },
    {
        "order": 11,
        "id": "post-11",
        "file": "thumb_post11.png",
        "bg": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?q=80&w=1080&auto=format&fit=crop", # 신축 모델하우스
        "line1": "소유주 갈등 제로 전략",
        "highlight": "단독주택 vs 빌라 가치평가",
        "line3": "대지지분·감정평가 불만 100% 해소법"
    },
    {
        "order": 12,
        "id": "post-12",
        "file": "thumb_post12.png",
        "bg": "https://images.unsplash.com/photo-1579532537598-459ecdaf39cc?q=80&w=1080&auto=format&fit=crop", # 금융 계산기
        "line1": "내 분담금 얼마나 나올까?",
        "highlight": "추정 분담금 1분 계산법",
        "line3": "종전자산평가 × 비례율 산식 완전 정복"
    },
    {
        "order": 13,
        "id": "post-13",
        "file": "thumb_post13.png",
        "bg": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=1080&auto=format&fit=crop", # 초고층 스카이라인
        "line1": "용적률 최대 140% 인센티브",
        "highlight": "준주거 용적률 700%",
        "line3": "3종주거 420% · 상한선 극대화 설계 비법"
    },
    {
        "order": 14,
        "id": "post-14",
        "file": "thumb_post14.png",
        "bg": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?q=80&w=1080&auto=format&fit=crop", # 모던 펜트하우스
        "line1": "용도지역 2단계 수직 상향",
        "highlight": "2종일반 → 준주거 종상향",
        "line3": "스카이라인 혁신 & 사업성 200% 극대화"
    },
    {
        "order": 15,
        "id": "post-15",
        "file": "thumb_post15.png",
        "bg": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?q=80&w=1080&auto=format&fit=crop", # 주택 단지
        "line1": "공공기여 기부채납 얼마나?",
        "highlight": "완화 용적률 30~50% 환원",
        "line3": "공공분양·임대주택·생활SOC 황금비율"
    },
    {
        "order": 16,
        "id": "post-16",
        "file": "thumb_post16.png",
        "bg": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?q=80&w=1080&auto=format&fit=crop", # 금융 그래프
        "line1": "일반분양 수입 극대화 비법",
        "highlight": "분양가 상한제 & HUG 보증",
        "line3": "고분양가 심사 회피 & 비례율 120% 달성"
    },
    {
        "order": 17,
        "id": "post-17",
        "file": "thumb_post17.png",
        "bg": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?q=80&w=1080&auto=format&fit=crop", # 건축 도면
        "line1": "일조권·사선제한 규제 완화",
        "highlight": "건폐율 50% 완화의 마법",
        "line3": "동간거리 축소 & 세대수 극대화 배치도"
    },
    {
        "order": 18,
        "id": "post-18",
        "file": "thumb_post18.png",
        "bg": "https://images.unsplash.com/photo-1563986768609-322da13575f3?q=80&w=1080&auto=format&fit=crop", # 금융 핀테크
        "line1": "신탁사 수수료 3%의 진실",
        "highlight": "남는 장사일까 아까울까?",
        "line3": "이자 비용 절감 vs 신탁보수 손익 계산서"
    },
    {
        "order": 19,
        "id": "post-19",
        "file": "thumb_post19.png",
        "bg": "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?q=80&w=1080&auto=format&fit=crop", # 로드맵 플래너
        "line1": "주민동의부터 입주까지 완벽 가이드",
        "highlight": "복합개발 6단계 로드맵",
        "line3": "구역지정·시행자선정·통합심의·준공 총정리"
    },
    {
        "order": 20,
        "id": "post-20",
        "file": "thumb_post20.png",
        "bg": "https://images.unsplash.com/photo-1521791136064-7986c2920216?q=80&w=1080&auto=format&fit=crop", # 악수/동의
        "line1": "1년 만에 동의율 완판 비결",
        "highlight": "동의율 67% 단기 돌파법",
        "line3": "주민설명회·비대위 설득 5단계 필승 공식"
    },
    {
        "order": 21,
        "id": "post-21",
        "file": "thumb_post21.png",
        "bg": "https://images.unsplash.com/photo-1450133064473-71024230f91b?q=80&w=1080&auto=format&fit=crop", # 계약서 검토
        "line1": "신탁계약서 도장 찍기 전 필수!",
        "highlight": "3대 독소조항 완전 박멸",
        "line3": "책임준공·신탁해지권·비용정산 안전장치"
    },
    {
        "order": 22,
        "id": "post-22",
        "file": "thumb_post22.png",
        "bg": "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?q=80&w=1080&auto=format&fit=crop", # 주식 금융 리츠
        "line1": "부동산투자회사 리츠(REITs) 개발",
        "highlight": "배당 수익 + 아파트 입주",
        "line3": "현물출자 비과세 & AMC 펀딩 구조 마스터"
    },
    {
        "order": 23,
        "id": "post-23",
        "file": "thumb_post23.png",
        "bg": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?q=80&w=1080&auto=format&fit=crop", # 1군 브랜드 아파트
        "line1": "1군 하이엔드 브랜드를 잡아라!",
        "highlight": "시공사 입찰 경쟁 비법",
        "line3": "주민대표회의 도급계약 & 공사비 협상 전략"
    },
    {
        "order": 24,
        "id": "post-24",
        "file": "thumb_post24.png",
        "bg": "https://images.unsplash.com/photo-1554224154-26032ffc0d07?q=80&w=1080&auto=format&fit=crop", # 감정평가사
        "line1": "내 부동산 가치 20% 더 받는 법",
        "highlight": "감정평가 승리 노하우",
        "line3": "감정평가사 지정권 & 이의신청 실전 대응"
    },
    {
        "order": 25,
        "id": "post-25",
        "file": "thumb_post25.png",
        "bg": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?q=80&w=1080&auto=format&fit=crop", # 서울 수도권 지도
        "line1": "서울 vs 경기도 조례 완벽 분석",
        "highlight": "지자체별 복합개발 온도차",
        "line3": "노후도·용적률 인센티브 지역별 맞춤 전략"
    },
    {
        "order": 26,
        "id": "post-26",
        "file": "thumb_post26.png",
        "bg": "https://images.unsplash.com/photo-1582407947304-fd86f028f716?q=80&w=1080&auto=format&fit=crop", # 부동산 자산
        "line1": "단독주택 vs 다세대 갈등 해결",
        "highlight": "독립정산제 권리가액 산정",
        "line3": "종전자산 공정 배분 & 분담금 잡음 제로"
    },
    {
        "order": 27,
        "id": "post-27",
        "file": "thumb_post27.png",
        "bg": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?q=80&w=1080&auto=format&fit=crop", # 소송 법률
        "line1": "반대파 매도청구 소송 완벽 방어",
        "highlight": "알박기 토지 수용 절차",
        "line3": "지구지정 후 60일 내 보상협의 3단계 해법"
    },
    {
        "order": 28,
        "id": "post-28",
        "file": "thumb_post28.png",
        "bg": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?q=80&w=1080&auto=format&fit=crop", # 회의실 조율
        "line1": "추진위가 사업을 말아먹을 때",
        "highlight": "주민 과반수 철회권 발동",
        "line3": "지구지정 취소 & 신탁사 변경 3원칙"
    },
    {
        "order": 29,
        "id": "post-29",
        "file": "thumb_post29.png",
        "bg": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?q=80&w=1080&auto=format&fit=crop", # 공사 인플레이션
        "line1": "공사비 평당 천만원 시대",
        "highlight": "공사비 증액 갈등 완벽 방어",
        "line3": "물가변동 ESC 조항 & 한국부동산원 검증"
    },
    {
        "order": 30,
        "id": "post-30",
        "file": "thumb_post30.png",
        "bg": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?q=80&w=1080&auto=format&fit=crop", # 금융 금리
        "line1": "PF 위기 속 초저금리 자금조달",
        "highlight": "HUG 보증 PF 대출 비법",
        "line3": "금리 2%p 절감 & 브릿지론 차환 전략"
    },
    {
        "order": 31,
        "id": "post-31",
        "file": "thumb_post31.png",
        "bg": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?q=80&w=1080&auto=format&fit=crop", # 세무 세금 계산서
        "line1": "세금 폭탄 완벽하게 피하는 법",
        "highlight": "양도세 이월과세 특례",
        "line3": "신탁 등기 취득세 비과세 혜택 총정리"
    },
    {
        "order": 32,
        "id": "post-32",
        "file": "thumb_post32.png",
        "bg": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?q=80&w=1080&auto=format&fit=crop", # 환승역 지하철
        "line1": "노후도 0%여도 사업 지정 가능!",
        "highlight": "성장거점형 복합개발",
        "line3": "환승역세권 500m 용적률 대폭 완화 혜택"
    },
    {
        "order": 33,
        "id": "post-33",
        "file": "thumb_post33.png",
        "bg": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?q=80&w=1080&auto=format&fit=crop", # 취득세 서류
        "line1": "새 아파트 취득세 반값 감면",
        "highlight": "지방세특례제한법 85㎡ 꿀팁",
        "line3": "원주민 50% 감면 & 다주택 중과세 회피"
    },
    {
        "order": 34,
        "id": "post-34",
        "file": "thumb_post34.png",
        "bg": "https://images.unsplash.com/photo-1450133064473-71024230f91b?q=80&w=1080&auto=format&fit=crop", # 종부세 고지서
        "line1": "신탁 맡기면 종부세 누구한테?",
        "highlight": "보유세·종부세 팩트체크",
        "line3": "위탁자 납세의무 & 공실 재산세 절세법"
    },
    {
        "order": 35,
        "id": "post-35",
        "file": "thumb_post35.png",
        "bg": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?q=80&w=1080&auto=format&fit=crop", # 이주/이사
        "line1": "내 돈 없이 이주하는 특급 비결",
        "highlight": "이주비 대출 LTV 70%",
        "line3": "무이자 지원 & 전세퇴거자금 대출 완벽 활용"
    },
    {
        "order": 36,
        "id": "post-36",
        "file": "thumb_post36.png",
        "bg": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?q=80&w=1080&auto=format&fit=crop", # 상속 증여
        "line1": "자녀 증여·상속 절세 골든타임",
        "highlight": "복합구역 지정 전 증여 전략",
        "line3": "감정가액 낮을 때 증여세 수천만원 절감"
    },
    {
        "order": 37,
        "id": "post-37",
        "file": "thumb_post37.png",
        "bg": "https://images.unsplash.com/photo-1579532537598-459ecdaf39cc?q=80&w=1080&auto=format&fit=crop", # 법인 세무
        "line1": "법인 토지 소유자 절세 노하우",
        "highlight": "법인세 추가과세 특례",
        "line3": "현물출자 과세이연 & 비영리법인 분양권"
    },
    {
        "order": 38,
        "id": "post-38",
        "file": "thumb_post38.png",
        "bg": "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?q=80&w=1080&auto=format&fit=crop", # 투자 타이밍 차트
        "line1": "도심복합 입주권 프리미엄 분석",
        "highlight": "3단계 황금 매수 타이밍",
        "line3": "지구지정·통합심의·착공 시세 상승 곡선"
    },
    {
        "order": 39,
        "id": "post-39",
        "file": "thumb_post39.png",
        "bg": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?q=80&w=1080&auto=format&fit=crop", # 1호 선도구역
        "line1": "전국 1호 선도구역 집중 분석",
        "highlight": "방학역·쌍문역 성공 요인",
        "line3": "비례율 130% 달성 비결 & 투자 교훈"
    },
    {
        "order": 40,
        "id": "post-40",
        "file": "thumb_post40.png",
        "bg": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=1080&auto=format&fit=crop", # 초고층 미래빌딩
        "line1": "용적률 1,400% 초고밀 개발",
        "highlight": "도시혁신구역(한국형 복합)",
        "line3": "입지규제최소구역 & 복합환승센터 비전"
    },
    {
        "order": 41,
        "id": "post-41",
        "file": "thumb_post41.png",
        "bg": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?q=80&w=1080&auto=format&fit=crop", # 경매/급매
        "line1": "경매·공매로 줍줍할 때 필수 확인!",
        "highlight": "물딱지 권리분석 3대 필터",
        "line3": "권리산정일 이후 소유권 취득 현금청산 주의"
    },
    {
        "order": 42,
        "id": "post-42",
        "file": "thumb_post42.png",
        "bg": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?q=80&w=1080&auto=format&fit=crop", # 청년 신혼부부 주택
        "line1": "청년·신혼부부 로또 청약 기회",
        "highlight": "도심복합 '뉴:홈' 청약 전략",
        "line3": "나눔형·선택형·일반형 100% 당첨 공략법"
    },
    {
        "order": 43,
        "id": "post-43",
        "file": "thumb_post43.png",
        "bg": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?q=80&w=1080&auto=format&fit=crop", # 1군 브랜드 펜트하우스
        "line1": "1군 대형 건설사 수주 경쟁",
        "highlight": "주요 12대 브랜드 비교",
        "line3": "아크로·디에이치·르엘 하이엔드 유치 조건"
    },
    {
        "order": 44,
        "id": "post-44",
        "file": "thumb_post44.png",
        "bg": "https://images.unsplash.com/photo-1519501025264-65ba15a82390?q=80&w=1080&auto=format&fit=crop", # 도시 정비사업 비교
        "line1": "정비사업 4대 천왕 최종 비교",
        "highlight": "도심복합 vs 신통 vs 모아타운",
        "line3": "사업 속도·용적률 완화·수익률 최종 승자는?"
    },
    {
        "order": 45,
        "id": "post-45",
        "file": "thumb_post45.png",
        "bg": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=1080&auto=format&fit=crop", # 정부 정책 국토부
        "line1": "2025~2026 정부 국토부 정책",
        "highlight": "도심복합개발 완화 총정리",
        "line3": "세제 감면 확대 & 인허가 단축 핵심 전망"
    },
    {
        "order": 46,
        "id": "post-46",
        "file": "thumb_post46.png",
        "bg": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?q=80&w=1080&auto=format&fit=crop", # 화이트존 도시공간
        "line1": "용도와 용적률 제한이 없다?",
        "highlight": "공간혁신구역 화이트존",
        "line3": "도시혁신·복합용도·도시계획시설 입체화"
    },
    {
        "order": 47,
        "id": "post-47",
        "file": "thumb_post47.png",
        "bg": "https://images.unsplash.com/photo-1506973035872-a4ec16b8e8d9?q=80&w=1080&auto=format&fit=crop", # 롯폰기힐스 글로벌도시
        "line1": "글로벌 도심 복합개발 벤치마킹",
        "highlight": "롯폰기힐스 & 허드슨야드",
        "line3": "해외 메가 프로젝트에서 배우는 성공 방정식"
    },
    {
        "order": 48,
        "id": "post-48",
        "file": "thumb_post48.png",
        "bg": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1080&auto=format&fit=crop", # 미래 스마트시티 AI UAM
        "line1": "미래형 스마트 컴팩트시티",
        "highlight": "AI · UAM · 로봇 복합단지",
        "line3": "도심항공교통 버티포트 & 탄소중립 인센티브"
    },
    {
        "order": 49,
        "id": "post-49",
        "file": "thumb_post49.png",
        "bg": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?q=80&w=1080&auto=format&fit=crop", # 지방 대도시 광역시
        "line1": "수도권을 넘어 지방 대도시로!",
        "highlight": "부산·대구·대전 복합개발",
        "line3": "지방 거점 역세권 고밀개발 유망 구역 분석"
    },
    {
        "order": 50,
        "id": "post-50",
        "file": "thumb_post50.png",
        "bg": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=1080&auto=format&fit=crop", # 완벽 가이드북
        "line1": "50편 대단원의 완결 종합본",
        "highlight": "도심복합개발 A to Z",
        "line3": "토지주 성공 10대 수칙 & 핵심 체크리스트"
    }
]

async def generate_all_thumbnails():
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "images", "thumbnails")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"==================================================")
    print(f"🎨 도심복합개발 50편 전용 고품질 썸네일 생성 엔진 시작")
    print(f"📂 저장 경로: {output_dir}")
    print(f"⚡ 원칙: 순차적 렌더링 (Sequential Rendering)")
    print(f"==================================================\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": 1080, "height": 1080},
            device_scale_factor=2 # 2160x2160 초고해상도 스크린샷
        )
        
        success_count = 0
        start_time = time.time()
        
        for idx, item in enumerate(THUMBNAIL_CONFIGS, 1):
            file_name = item["file"]
            out_file = os.path.join(output_dir, file_name)
            
            html_content = get_thumbnail_html(
                bg_image_url=item["bg"],
                line1_text=item["line1"],
                highlight_text=item["highlight"],
                line3_text=item["line3"]
            )
            
            await page.set_content(html_content, wait_until="networkidle")
            # 폰트 및 배경 이미지 렌더링 대기
            await page.wait_for_timeout(300)
            
            element = await page.query_selector(".thumbnail")
            if element:
                await element.screenshot(path=out_file, type="png")
                print(f"  [{idx:02d}/50] 렌더링 완료: {file_name} -> {item['highlight']}")
                success_count += 1
            else:
                print(f"  [ERROR] {file_name} 렌더링 실패")
        
        await browser.close()
        elapsed = time.time() - start_time
        print(f"\n==================================================")
        print(f"✅ 총 {success_count}/50개 썸네일 렌더링 완료! (소요 시간: {elapsed:.2f}초)")
        print(f"==================================================")

if __name__ == "__main__":
    asyncio.run(generate_all_thumbnails())
