# 🏛️ 도심복합개발 실전 지식 포털 (Full-Stack & Cloudflare Ready)

> **공공도심복합사업 및 민간도심복합개발 실전 지식 플랫폼**  
> 프론트엔드/백엔드 분리 아키텍처, 800px 가독성 리더, HTML 카드뉴스 엔진, 실무 Q&A 시스템, Cloudflare Pages 무비용 호스팅, 구글 애드센스(Google AdSense) 승인 필수 인프라 완비

---

## 📂 프로젝트 구조

```text
├── frontend/                     # [프론트엔드] Cloudflare Pages 배포용 정적 웹
│   ├── index.html                # 메인 HTML (SEO 메타, JSON-LD, AdSense 코드 슬롯)
│   ├── css/
│   │   └── style.css             # 800px 최적화, H2/H3 서식, Q&A 섹션, 애드센스 슬롯
│   ├── js/
│   │   ├── app.js                # SPA 라우터, H2/H3/H4 파서, Q&A 렌더러
│   │   ├── api.js                # 백엔드 API 클라이언트 & 오프라인 폴백
│   │   ├── articles_data.js      # 정적 데이터 모듈 ('---' 완전 제거 & Q&A 3+ 탑재)
│   │   └── graph.js              # 인터랙티브 지식 그래프 시각화
│   ├── robots.txt                # 검색엔진 및 AdSense 크롤러 규약
│   └── sitemap.xml               # 전체 XML 사이트맵
│
├── backend/                      # [백엔드] Express REST API 및 데이터베이스
│   ├── data/
│   │   ├── articles.json         # 전체 아티클 마스터 데이터
│   │   └── categories.json       # 카테고리 메타데이터
│   ├── routes/
│   │   ├── articles.js           # GET /api/articles, GET /api/articles/:id, POST /api/articles
│   │   └── contact.js            # POST /api/contact
│   └── server.js                 # Node.js / Express 서버 엔트리포인트
│
├── functions/                    # [Cloudflare Serverless Functions]
│   └── api/
│       └── [[path]].js           # Cloudflare Pages 엣지 서버리스 API
│
├── wrangler.toml                 # Cloudflare 배포 설정
└── package.json                  # 풀스택 의존성 및 스크립트
```

---

## 🚀 1. 로컬 환경 실행 방법 (Node.js)

```bash
# 1. 의존성 설치 (최초 1회)
npm install

# 2. 풀스택 서버 실행
npm start
```
* 브라우저에서 `http://localhost:3000`으로 접속하시면 즉시 모든 기능이 동작합니다.

---

## ☁️ 2. 클라우드플레어(Cloudflare Pages) 배포 가이드 (무료)

### 방법 A. Cloudflare 웹 대시보드에서 직접 업로드 (가장 쉬움, 1분 완성)
1. [Cloudflare 대시보드](https://dash.cloudflare.com/)에 로그인합니다.
2. 왼쪽 메뉴에서 **Workers & Pages** ➔ **Create application** ➔ **Pages** 탭 ➔ **Upload assets**를 클릭합니다.
3. 프로젝트 이름(예: `urban-complex-guide`)을 입력합니다.
4. **`frontend` 폴더** 전체를 드래그 앤 드롭으로 업로드합니다.
5. **Deploy site**를 누르면 즉시 `https://urban-complex-guide.pages.dev` 주소로 전 세계에 배포됩니다!

### 방법 B. Wrangler CLI로 터미널 배포
```bash
npx wrangler pages deploy frontend --project-name=urban-complex-guide
```

---

## 🌐 3. 커스텀 도메인 연결 방법
1. Cloudflare Pages 프로젝트 대시보드에서 **Custom domains** 탭을 클릭합니다.
2. **Set up a custom domain** 버튼을 누르고 보유하신 도메인(예: `your-domain.com`)을 입력합니다.
3. 안내에 따라 DNS 레코드(CNAME)를 연결하면 **무료 SSL 보안 인증서(HTTPS)**가 자동으로 활성화됩니다.

---

## 💰 4. 구글 애드센스(Google AdSense) 승인 가이드

본 프로젝트는 구글 애드센스 심사 통과를 위한 모든 요건을 100% 갖추고 있습니다:
1. **고품질 전문 콘텐츠 & 실무 Q&A**: 각 편당 1,000~1,500자의 깊이 있는 법률/실무 지식과 3개 이상의 핵심 Q&A 탑재.
2. **필수 4대 정책 페이지 구축**:
   - `About Us` (소개): E-E-A-T 전문성 입증
   - `Privacy Policy` (개인정보처리방침): Google DART 쿠키 및 맞춤 광고 규정 완비
   - `Terms of Service` (이용약관): 법률/투자 면책조항
   - `Contact Us` (문의하기): 실시간 문의 폼 및 공식 이메일
3. **SEO & 크롤링**: `sitemap.xml` 및 `robots.txt` 완비.

### 애드센스 신청 절차:
1. 커스텀 도메인 연결 후 [Google Search Console](https://search.google.com/search-console)에 사이트를 등록하고 `https://your-domain.com/sitemap.xml`을 제출합니다.
2. [Google AdSense](https://www.google.com/adsense/)에 로그인하여 **사이트 추가**를 진행합니다.
3. 발급받은 애드센스 코드(`ca-pub-XXXXXXXX`)를 `frontend/index.html`의 46번째 줄 주석을 해제하고 붙여넣습니다.
4. **심사 요청**을 누르고 승인을 기다립니다 (통상 1~7일 소요).

---

## 📄 라이선스
MIT License.
