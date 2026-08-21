# 🏛️ dochim.kr 작업 진행 및 변경 이력 (PROGRESS.md)

## 📅 2026-08-21 (금)

### 🎯 핵심 목표
- **dochim.kr 구글 애드센스 '가치 없는 콘텐츠 (Low-value content)' 거절 사유 정밀 분석 및 완전 해결**
- **50개 전체 아티클 순차적(Sequential) SSG 정적 렌더링 엔진 구축 및 Cloudflare Pages 배포 완료**

---

### 🚨 1. 애드센스 거절 원인 정밀 분석 (Root Cause)
1. **[치명적 버그] SSG 빌드 스크립트의 선택자 불일치로 인한 '0글자 HTML' 배포**:
   - `frontend/index.html`의 태그는 `<main id="mainContainer">`였으나, `scripts/build.js`에서는 `<main id="app">`을 검색하여 치환 실패.
   - 결과적으로 배포된 50개 아티클 페이지의 본문이 완전히 비어있어(`<!-- Rendered dynamically by app.js -->`), 구글 크롤러(Mediapartners-Google)에게 본문 글자 수 0인 '내용 없는 사이트'로 판정됨.
2. **[필수 정책 페이지 정적 파일 부재]**:
   - `/about`, `/privacy`, `/terms`, `/contact`가 독립된 정적 HTML 파일로 존재하지 않고 빈 SPA fallback으로 서빙됨.
3. **[구글 애드센스 공식 스크립트 미활성화]**:
   - `index.html` 내 애드센스 `<script>` 태그가 주석 처리되어 있고 더미 ID(`ca-pub-XXXXXXXX`) 상태였음.
4. **[사이트맵(sitemap.xml) 누락]**:
   - 4대 필수 정책 페이지가 사이트맵에 등록되지 않음.

---

### 🛠️ 2. 금일 작업 내역 (병렬 처리 엄격 금지 원칙 준수)

#### 1) SSG 정적 빌드 엔진 전면 개편 (`scripts/build.js`)
- **순차적(Sequential) 처리**: 병렬 처리를 금지하고 `VOL.01`부터 `VOL.50`까지 차례대로 한 편씩 정적 HTML 빌드.
- **풍부한 시맨틱 HTML 주입**:
  - `<h1>` 아티클 제목 & 브레드크럼 네비게이션
  - 3초 핵심 요약 박스 (Executive Summary)
  - 카드뉴스 배너
  - 마크다운 본문 파싱 (`<h2>`, `<h3>`, `<p>`, `<ul>`, `<blockquote>`, 테이블, 인포박스 등 1,500~2,500자)
  - 3개 이상의 핵심 실전 Q&A 아코디언 섹션
  - **E-E-A-T 전문가 검증 저자 프로필 박스** (현대공인중개사사무소 대표 백명건)
  - 이전/다음 글 네비게이션 및 연관 아티클 3종 추천 카드
- **구조화 데이터(JSON-LD) 개별 주입**:
  - `NewsArticle` (저자, 발행처, 발행일, 수정일) & `BreadcrumbList` 스키마 정적 주입.

#### 2) 4대 필수 정책 페이지 독립 정적 생성
- `frontend/about/index.html` : E-E-A-T 전문성 및 공인중개사사무소 자격 정보
- `frontend/privacy/index.html` : 개인정보처리방침 및 Google DART 쿠키/맞춤광고 규정
- `frontend/terms/index.html` : 이용약관 및 법률/투자 면책 고지
- `frontend/contact/index.html` : 실시간 문의 폼 및 대표 연락처

#### 3) 메인 페이지 (`frontend/index.html`) 정적 피드 사전 렌더링
- 메인 페이지에 Hero, 통계 바, 카테고리 탭, **50개 전체 아티클 카드 정적 링크(`<a href="/article/slug">`)**를 미리 렌더링하여 크롤러가 첫 진입 시 사이트 전체 지식망을 즉시 수집 가능하도록 개선.

#### 4) CSS 디자인 시스템 확장 (`frontend/css/style.css`)
- `.author-profile-box` (E-E-A-T 전문가 프로필 카드) 스타일 추가
- `.breadcrumb-nav` (브레드크럼 네비게이션) 스타일 추가

#### 5) 구글 애드센스 공식 연동 코드 활성화
- 실제 계정 ID(`ca-pub-8197670104893130`)를 적용한 공식 스크립트 활성화.

#### 6) 사이트맵 & robots.txt 최신화
- `sitemap.xml`에 총 55개 URL(메인 + 4개 정책 + 50개 아티클) 자동 등록.
- `robots.txt` 표준 규약 완비.

#### 7) Cloudflare Pages 배포 및 GitHub 푸시
- `wrangler.toml` 프로젝트명을 `dochim-guide`로 동기화.
- Wrangler CLI를 통해 Cloudflare Pages 배포 완료 (`https://c577ba38.dochim-guide.pages.dev`).
- GitHub 원격 저장소(`hyundai71426-cmd/dochim-guide`)에 커밋 및 푸시 완료 (`83af61c`).
- 라이브 도메인([https://dochim.kr/](https://dochim.kr/)) 정상 서비스 확인.

---

### 📊 3. 검증 결과 요약

| 점검 항목 | 이전 상태 (거절 원인) | 현재 라이브 상태 (개편 후) | 상태 |
| :--- | :--- | :--- | :---: |
| **50개 아티클 정적 HTML** | `0글자` (빈 껍데기) | **1,500~2,500자 완전한 시맨틱 텍스트** | ✅ 통과 |
| **4대 정책 페이지** | 독립 파일 부재 | `/about`, `/privacy`, `/terms`, `/contact` 정적 파일 완비 | ✅ 통과 |
| **E-E-A-T 저자 프로필** | 없음 | 공인중개사 대표 자격 정보 박스 탑재 | ✅ 통과 |
| **구글 애드센스 스크립트** | 주석 처리 (더미 ID) | 정식 활성화 (`ca-pub-8197670104893130`) | ✅ 통과 |
| **XML 사이트맵** | 정책 페이지 누락 | 55개 전체 URL 등록 완비 | ✅ 통과 |
| **Cloudflare 라이브 배포** | 이전 빌드 | 최신 SSG 빌드 100% 라이브 반영 | ✅ 통과 |

---

### 🚀 4. 애드센스 재심사 진행 절차 (Next Steps)
1. **Google Search Console**: `https://dochim.kr/sitemap.xml` 재제출 완료 권장.
2. **Google AdSense 대시보드**: `dochim.kr` 사이트 **[검토 요청]** 버튼 클릭.
