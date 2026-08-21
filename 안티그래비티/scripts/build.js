const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const articlesPath = path.join(rootDir, 'backend', 'data', 'articles.json');
const categoriesPath = path.join(rootDir, 'backend', 'data', 'categories.json');
const indexPath = path.join(rootDir, 'frontend', 'index.html');
const frontendDir = path.join(rootDir, 'frontend');

const articles = JSON.parse(fs.readFileSync(articlesPath, 'utf8'));
const categoriesData = JSON.parse(fs.readFileSync(categoriesPath, 'utf8'));
const categories = categoriesData.categories;
const templateHtml = fs.readFileSync(indexPath, 'utf8');

const baseUrl = 'https://dochim.kr';
const today = new Date().toISOString().split('T')[0];

console.log('====================================================');
console.log('🏛️  도심복합개발 실전 지식 포털 SSG 빌드 엔진 시작');
console.log('⚡  원칙: 병렬 처리 금지! 순차적(Sequential) 렌더링');
console.log(`📚  총 연재 아티클 수: ${articles.length}편`);
console.log('====================================================\n');

// ==========================================
// 1. 마크다운 파서 유틸리티
// ==========================================
function parseInlineMarkdown(text) {
  if (!text) return '';
  return String(text)
    .replace(/\$\\rightarrow\$/g, '→')
    .replace(/\\rightarrow/g, '→')
    .replace(/\$\\ge\$/g, '≥')
    .replace(/\\ge/g, '≥')
    .replace(/\$\\le\$/g, '≤')
    .replace(/\\le/g, '≤')
    .replace(/\$\\times\$/g, '×')
    .replace(/\\times/g, '×')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/(?<!\*)\*([^\*\n]+?)\*(?!\*)/g, '<em>$1</em>')
    .replace(/`([^`\n]+)`/g, '<code style="padding: 0.15rem 0.45rem; background: var(--color-accent-subtle); color: var(--color-accent-hover); border-radius: 4px; font-weight: 700; font-size: 0.85em;">$1</code>');
}

function parseMarkdownToHtml(content) {
  if (!content) return '';
  let formatted = content.replace(/\r\n/g, '\n').replace(/---/g, '');

  // 코드블록 -> 정보 상자(Infobox)
  formatted = formatted.replace(/```([\s\S]*?)```/g, (match, inner) => {
    const innerLines = inner.trim().split('\n');
    const cardBody = innerLines.map(l => {
      let line = l.trim();
      if (!line) return '';
      if (line.startsWith('[') && line.endsWith(']')) {
        return `<div style="font-weight: 800; color: var(--color-primary); font-size: 1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem;"><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--color-accent);"></span>${line.slice(1, -1)}</div>`;
      }
      return `<div style="margin: 0.25rem 0; color: var(--text-secondary); line-height: 1.7; font-weight: 500;">${parseInlineMarkdown(line)}</div>`;
    }).filter(Boolean).join('');

    return `<div style="margin: 1.8rem 0; padding: 1.5rem; background: linear-gradient(135deg, var(--bg-surface-low) 0%, var(--bg-surface) 100%); border: 1.5px solid var(--border-color); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm);">${cardBody}</div>`;
  });

  const lines = formatted.split('\n');
  let inList = false;
  let listType = '';
  let inTable = false;
  let tableHtml = '';
  let inQuote = false;
  let quoteLines = [];
  let result = '';

  function flushList() {
    if (inList) {
      result += `</${listType}>`;
      inList = false;
      listType = '';
    }
  }

  function flushQuote() {
    if (inQuote) {
      const quoteContent = quoteLines.map(ql => `<div style="margin: 0.25rem 0; line-height: 1.7;">${parseInlineMarkdown(ql)}</div>`).join('');
      result += `<blockquote>${quoteContent}</blockquote>`;
      inQuote = false;
      quoteLines = [];
    }
  }

  function flushTable() {
    if (inTable) {
      tableHtml += '</tbody></table></div>';
      result += tableHtml;
      inTable = false;
      tableHtml = '';
    }
  }

  for (let rawLine of lines) {
    const line = rawLine.trim();

    if (line.startsWith('|') && line.endsWith('|')) {
      flushList();
      flushQuote();
      if (!inTable) {
        inTable = true;
        tableHtml = '<div style="overflow-x: auto; margin: 1.8rem 0; border-radius: var(--radius-md); border: 1px solid var(--border-color);"><table style="width:100%; border-collapse: collapse; text-align: left;"><thead>';
      }
      const cells = line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1).map(c => c.trim());
      if (cells.some(c => c.includes('---'))) {
        tableHtml += '</thead><tbody>';
      } else if (!tableHtml.includes('<tbody')) {
        tableHtml += '<tr>' + cells.map(c => `<th>${parseInlineMarkdown(c)}</th>`).join('') + '</tr>';
      } else {
        tableHtml += '<tr>' + cells.map(c => `<td>${parseInlineMarkdown(c)}</td>`).join('') + '</tr>';
      }
      continue;
    } else {
      flushTable();
    }

    if (line.startsWith('#### ')) {
      flushList();
      flushQuote();
      result += `<h4>${parseInlineMarkdown(line.slice(5))}</h4>`;
      continue;
    }

    if (line.startsWith('### ')) {
      flushList();
      flushQuote();
      result += `<h3>${parseInlineMarkdown(line.slice(4))}</h3>`;
      continue;
    }

    if (line.startsWith('## ')) {
      flushList();
      flushQuote();
      result += `<h2>${parseInlineMarkdown(line.slice(3))}</h2>`;
      continue;
    }

    if (line.startsWith('# ')) {
      flushList();
      flushQuote();
      result += `<h1>${parseInlineMarkdown(line.slice(2))}</h1>`;
      continue;
    }

    if (line.startsWith('>')) {
      flushList();
      inQuote = true;
      quoteLines.push(line.replace(/^>\s*/, ''));
      continue;
    } else {
      flushQuote();
    }

    if (line.startsWith('* ') || line.startsWith('- ') || line.startsWith('• ')) {
      flushQuote();
      if (!inList || listType !== 'ul') {
        flushList();
        inList = true;
        listType = 'ul';
        result += '<ul>';
      }
      const itemContent = line.replace(/^[\*\-•]\s*/, '');
      result += `<li>${parseInlineMarkdown(itemContent)}</li>`;
      continue;
    }

    if (/^\d+\.\s/.test(line)) {
      flushQuote();
      if (!inList || listType !== 'ol') {
        flushList();
        inList = true;
        listType = 'ol';
        result += '<ol>';
      }
      const itemContent = line.replace(/^\d+\.\s*/, '');
      result += `<li>${parseInlineMarkdown(itemContent)}</li>`;
      continue;
    }

    flushList();

    if (line.length > 0) {
      result += `<p>${parseInlineMarkdown(line)}</p>`;
    }
  }

  flushList();
  flushQuote();
  flushTable();

  return result;
}

// ==========================================
// 2. 50개 아티클 정적 HTML 순차적 생성 (1편부터 50편까지 차례대로 실행)
// ==========================================
console.log('▶ [1단계] 50개 아티클 상세 페이지 순차적 SSG 생성 시작...\n');

for (let i = 0; i < articles.length; i++) {
  const article = articles[i];
  const orderNum = String(article.order).padStart(2, '0');
  console.log(`  [${orderNum}/50] VOL.${orderNum} 처리 중: "${article.title}"...`);

  const dirPath = path.join(frontendDir, 'article', article.slug);
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }

  const plainDesc = (article.easySummary || article.summary || '').replace(/[`*#>]/g, '').substring(0, 160).trim();
  const fullUrl = `${baseUrl}/article/${article.slug}`;

  // 이전/다음 글 계산
  const prevArticle = i > 0 ? articles[i - 1] : null;
  const nextArticle = i < articles.length - 1 ? articles[i + 1] : null;

  const navButtonsHtml = `
    <div class="article-nav-buttons">
      ${prevArticle ? `
        <a href="/article/${prevArticle.slug || prevArticle.id}" class="btn-nav-card">
          <span class="btn-nav-label">← 이전 연재 (VOL.${String(prevArticle.order).padStart(2, '0')})</span>
          <span class="btn-nav-title">${prevArticle.title}</span>
        </a>
      ` : '<div></div>'}
      ${nextArticle ? `
        <a href="/article/${nextArticle.slug || nextArticle.id}" class="btn-nav-card" style="text-align: right; align-items: flex-end;">
          <span class="btn-nav-label">다음 연재 (VOL.${String(nextArticle.order).padStart(2, '0')}) →</span>
          <span class="btn-nav-title">${nextArticle.title}</span>
        </a>
      ` : '<div></div>'}
    </div>
  `;

  // 카드뉴스 HTML
  const cardNewsData = article.cardNews || {
    tagline: `VOL.${orderNum} 핵심 요점`,
    highlightText: article.title,
    items: [
      { icon: '💡', title: '핵심 포인트', desc: article.summary },
      { icon: '⏱️', title: '읽는 시간', desc: '4분 완성' },
      { icon: '🔗', title: '연계 학습', desc: '3편의 연계 지식' }
    ]
  };

  const cardNewsHtml = `
    <div class="card-news-banner">
      <div class="card-news-header">
        <span class="card-news-tagline">${cardNewsData.tagline}</span>
        <h2 class="card-news-highlight">${cardNewsData.highlightText}</h2>
      </div>
      <div class="card-news-grid">
        ${(cardNewsData.items || []).map(item => `
          <div class="card-news-item">
            <div class="item-icon">${item.icon}</div>
            <h4 class="item-title">${parseInlineMarkdown(item.title)}</h4>
            <p class="item-desc">${parseInlineMarkdown(item.desc)}</p>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  // 본문 HTML
  const bodyHtml = parseMarkdownToHtml(article.content || '');

  // Q&A HTML
  const qnaList = article.qna || [
    {
      q: "Q1. 도심복합개발의 핵심 장점은 무엇인가요?",
      a: "조합 설립 절차를 생략하고 공공/신탁사가 직접 시행하여 인허가 기간을 10년 이상에서 3~5년으로 획기적으로 단축하며, 법적 상한 용적률의 140%까지 혜택을 부여합니다."
    },
    {
      q: "Q2. 토지소유자의 분담금 부담은 어떻게 줄어드나요?",
      a: "용적률 완화 및 종상향으로 확보된 일반분양 물량 수익을 통해 토지소유자의 분담금을 기존 재개발 대비 10~30% 낮춰줍니다."
    },
    {
      q: "Q3. 시공사 선정 권한은 누구에게 있나요?",
      a: "토지소유자로 구성된 주민대표회의에서 주민 투표를 통해 1군 대형 건설사 브랜드를 직접 결정합니다."
    }
  ];

  const qnaHtml = `
    <section class="reader-qna-section">
      <div class="qna-header">
        <div class="qna-tag">💬 실전 FAQ & 자문 가이드</div>
        <h3 class="qna-title">이 주제에 대해 자주 묻는 핵심 질문 (Q&A)</h3>
      </div>
      <div class="qna-list">
        ${qnaList.map(item => `
          <div class="qna-item">
            <div class="qna-q">${parseInlineMarkdown(item.q)}</div>
            <div class="qna-a">${parseInlineMarkdown(item.a)}</div>
          </div>
        `).join('')}
      </div>
    </section>
  `;

  // 연관 글 카드
  const relIds = article.relatedPostIds || [];
  const relatedArticles = articles.filter(a => relIds.includes(a.id)).slice(0, 3);
  const fallbackRelated = relatedArticles.length > 0 ? relatedArticles : articles.filter(a => a.id !== article.id).slice(0, 3);

  const relatedCardsHtml = fallbackRelated.map(rel => `
    <a href="/article/${rel.slug || rel.id}" class="related-card">
      <div class="rel-vol">VOL.${String(rel.order).padStart(2, '0')}</div>
      <div class="rel-title">${rel.title}</div>
      <div class="rel-summary">${parseInlineMarkdown((rel.easySummary || rel.summary || '').substring(0, 48))}…</div>
    </a>
  `).join('');

  // 100% 완전한 기사 리더 HTML 조립
  const articleReaderHtml = `
    <div class="reader-layout">
      <article class="reader-container">
        <!-- 상단 네비게이션 -->
        <div class="reader-nav">
          <a href="/" class="btn-back">
            <span class="material-symbols-outlined icon-sm">arrow_back</span>
            전체 연재 목록으로
          </a>
        </div>

        <!-- 아티클 헤더 -->
        <header class="reader-header">
          <nav class="breadcrumb-nav" aria-label="Breadcrumb">
            <a href="/">홈</a>
            <span class="breadcrumb-separator">/</span>
            <a href="/">${article.category}</a>
            <span class="breadcrumb-separator">/</span>
            <span style="color: var(--text-primary); font-weight:700;">VOL.${orderNum}</span>
          </nav>
          <div class="reader-meta-top">
            <span class="reader-category-badge">${article.category}</span>
            <span class="reader-vol">VOL.${orderNum}</span>
          </div>
          <h1 class="reader-title">${article.title}</h1>
          <div class="reader-meta-bottom">
            <span class="reader-author">🏛️ 도심복합개발 실전 연구팀 (검증 전문가: 백명건 대표)</span>
            <span>⏱️ ${article.readingTime || '4분'} 완독 &nbsp;|&nbsp; 👥 추천: ${(article.targetAudience || ['전체']).join(', ')}</span>
          </div>
        </header>

        <!-- 3초 핵심 요약 박스 (Executive Summary) -->
        <div class="executive-summary-box">
          <div class="summary-header">
            <span class="material-symbols-outlined icon-sm">bolt</span>
            3초 핵심 요약 (Executive Summary)
          </div>
          <div class="summary-text">
            ${
              (article.easySummary || article.summary || '')
                .split('\n')
                .filter(line => line.trim())
                .map(line => `<div style="margin: 0.35rem 0;">${parseInlineMarkdown(line.trim())}</div>`)
                .join('')
            }
          </div>
        </div>

        <!-- 카드뉴스 시각화 배너 -->
        ${cardNewsHtml}

        <!-- 본문 마크다운 (시맨틱 HTML) -->
        <div class="reader-body">
          ${bodyHtml}
        </div>

        <!-- 실무 Q&A 섹션 -->
        ${qnaHtml}

        <!-- E-E-A-T 저자 프로필 박스 -->
        <div class="author-profile-box">
          <div class="author-avatar">🏛️</div>
          <div class="author-info">
            <div class="author-badge">
              <span class="material-symbols-outlined icon-sm" style="font-size:0.9rem;">verified</span>
              전문가 검증 칼럼 (E-E-A-T)
            </div>
            <div class="author-name">
              현대공인중개사사무소 · 도심복합개발 연구팀
            </div>
            <div class="author-desc">
              공공도심복합사업 및 민간도심복합개발법 실전 정책·법률·사업성 분석 전문. 서울시 및 수도권 주요 정비사업 구역의 권리분석 및 세제 컨설팅을 제공합니다.
            </div>
            <div class="author-meta">
              <span>📍 서울특별시 서초구 반포동 714-26 1층</span>
              <span>대표: 백명건 (등록번호: 11650-2016-00300)</span>
              <span>문의: 02-3446-2361</span>
            </div>
          </div>
        </div>

        <!-- 이전/다음 글 네비게이션 -->
        ${navButtonsHtml}

        <!-- 연계 지식 추천 섹션 -->
        <section class="related-section">
          <div class="qna-tag">🔗 꼬리를 무는 연계 지식</div>
          <h3 class="related-title">함께 읽으면 지식망이 완성되는 추천 연재</h3>
          <div class="related-grid">
            ${relatedCardsHtml}
          </div>
        </section>
      </article>
    </div>
  `;

  // JSON-LD 구조화 데이터 (Article & BreadcrumbList)
  const jsonLdData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "NewsArticle",
        "headline": article.title,
        "description": plainDesc,
        "url": fullUrl,
        "inLanguage": "ko-KR",
        "datePublished": "2026-08-01T09:00:00+09:00",
        "dateModified": `${today}T09:00:00+09:00`,
        "author": {
          "@type": "Person",
          "name": "백명건",
          "jobTitle": "대표 공인중개사",
          "worksFor": {
            "@type": "RealEstateAgent",
            "name": "현대공인중개사사무소",
            "telephone": "02-3446-2361",
            "address": {
              "@type": "PostalAddress",
              "streetAddress": "반포동 714-26 1층",
              "addressLocality": "서초구",
              "addressRegion": "서울특별시",
              "addressCountry": "KR"
            }
          }
        },
        "publisher": {
          "@type": "Organization",
          "name": "도심복합개발 지식 포털",
          "url": baseUrl,
          "logo": {
            "@type": "ImageObject",
            "url": `${baseUrl}/favicon.ico`
          }
        },
        "mainEntityOfPage": {
          "@type": "WebPage",
          "@id": fullUrl
        }
      },
      {
        "@type": "BreadcrumbList",
        "itemListElement": [
          {
            "@type": "ListItem",
            "position": 1,
            "name": "홈",
            "item": baseUrl
          },
          {
            "@type": "ListItem",
            "position": 2,
            "name": article.category,
            "item": `${baseUrl}/#${article.categoryId}`
          },
          {
            "@type": "ListItem",
            "position": 3,
            "name": article.title,
            "item": fullUrl
          }
        ]
      }
    ]
  };

  let pageHtml = templateHtml;

  // 1. Meta Tags 교체
  pageHtml = pageHtml.replace(/<title>.*?<\/title>/, `<title>${article.title} · 도심복합개발 백과사전</title>`);
  pageHtml = pageHtml.replace(/<meta name="title" content=".*?">/, `<meta name="title" content="${article.title}">`);
  pageHtml = pageHtml.replace(/<meta name="description" content=".*?">/, `<meta name="description" content="${plainDesc}">`);
  pageHtml = pageHtml.replace(/<meta property="og:title" content=".*?">/, `<meta property="og:title" content="${article.title}">`);
  pageHtml = pageHtml.replace(/<meta property="og:description" content=".*?">/, `<meta property="og:description" content="${plainDesc}">`);
  pageHtml = pageHtml.replace(/<meta property="og:url" content=".*?">/, `<meta property="og:url" content="${fullUrl}">`);
  pageHtml = pageHtml.replace(/<meta property="twitter:title" content=".*?">/, `<meta property="twitter:title" content="${article.title}">`);
  pageHtml = pageHtml.replace(/<meta property="twitter:description" content=".*?">/, `<meta property="twitter:description" content="${plainDesc}">`);

  // 2. JSON-LD 주입
  pageHtml = pageHtml.replace(
    /<script type="application\/ld\+json">[\s\S]*?<\/script>/,
    `<script type="application/ld+json">\n${JSON.stringify(jsonLdData, null, 2)}\n  </script>`
  );

  // 3. 본문 정적 HTML 주입 (<main class="main-wrapper" id="mainContainer">)
  pageHtml = pageHtml.replace(
    /<main class="main-wrapper" id="mainContainer">[\s\S]*?<\/main>/,
    `<main class="main-wrapper" id="mainContainer">\n${articleReaderHtml}\n  </main>`
  );

  fs.writeFileSync(path.join(dirPath, 'index.html'), pageHtml, 'utf8');
  console.log(`  └─ ✅ [${orderNum}/50] ${article.slug}/index.html 저장 완료 (정적 본문 크기: ${articleReaderHtml.length} bytes)`);
}

console.log('\n✅ 50개 전체 아티클 순차적 생성 완료!\n');

// ==========================================
// 3. 4대 정책 페이지 (About, Privacy, Terms, Contact) 정적 생성
// ==========================================
console.log('▶ [2단계] 필수 4대 정책 페이지 정적 SSG 생성 시작...\n');

// A. About Us
const aboutDir = path.join(frontendDir, 'about');
if (!fs.existsSync(aboutDir)) fs.mkdirSync(aboutDir, { recursive: true });

const aboutContent = `
  <section class="policy-container">
    <header class="policy-header">
      <h1 class="policy-title">About Us · 도심복합개발 지식 포털 소개</h1>
      <p class="policy-desc">대한민국 공공·민간 도심복합사업 표준 실전 지식 아카이브</p>
    </header>

    <div class="policy-content">
      <h3>1. 설립 취지와 목표 (E-E-A-T)</h3>
      <p>
        본 포털은 복잡하고 난해한 대한민국의 <strong>도심 공공주택 복합사업(공공주택 특별법)</strong> 및 <strong>민간 도심 복합개발(도심 복합개발 지원에 관한 법률)</strong>에 관한 정책, 법률, 세무, 사업성 분석 정보를 투명하고 알기 쉽게 제공하기 위해 개설된 전문 지식 아카이브입니다.
      </p>

      <h3>2. 전문성과 신뢰성</h3>
      <p>
        부동산 정비사업은 수많은 법적 쟁점과 토지소유자, 세입자, 상가영업권자 간의 이해관계가 얽혀 있습니다. 본 포털은 국토교통부 고시, LH·SH 공공기관 실무 가이드라인, 대법원 판례 및 세무 전문가 검증 데이터를 바탕으로 <strong>체계적인 지식 맵</strong>을 구축하였습니다.
      </p>

      <blockquote style="margin: 1.5rem 0;">
        <strong>💡 포털의 3대 핵심 원칙</strong><br>
        • <strong>Fact-Based:</strong> 법령 조항 및 실제 행정 기준에 입각한 정확한 정보 제공<br>
        • <strong>User-Centric:</strong> 전문 용어를 일상 언어로 쉽게 풀어낸 높은 가독성<br>
        • <strong>Interconnected:</strong> 단편적 지식이 아닌 유기적 연계를 통한 입체적 이해 지원
      </blockquote>

      <h3>3. 운영 주체 및 자격 정보</h3>
      <div style="background: var(--bg-surface-low); border: 1.5px solid var(--border-color); border-radius: var(--radius-md); padding: 1.2rem 1.5rem; margin: 1.2rem 0;">
        <strong style="color: var(--color-primary); font-size: 1.05rem;">🏢 현대공인중개사사무소</strong>
        <ul style="margin: 0.6rem 0 0 1.2rem; line-height: 1.8;">
          <li><strong>대표 공인중개사:</strong> 백명건</li>
          <li><strong>주소:</strong> 서울특별시 서초구 반포동 714-26 1층</li>
          <li><strong>등록번호:</strong> 11650-2016-00300</li>
          <li><strong>대표번호:</strong> 02-3446-2361 &nbsp;|&nbsp; <strong>팩스:</strong> 02-3446-2711</li>
          <li><strong>전문 분야:</strong> 공공도심복합사업, 민간도심복합개발법, 정비사업 권리분석 및 세무 자문</li>
        </ul>
      </div>

      <h3>4. 콘텐츠 업데이트 안내</h3>
      <p>
        정부의 부동산 대책과 법령 개정 사항을 지속적으로 모니터링하여 최신 정보를 업데이트하고 있습니다. 오류 제보나 추가 문의는 언제든지 <a href="/contact" style="color: var(--color-secondary); font-weight:700;">문의하기</a>를 이용해 주시기 바랍니다.
      </p>
    </div>
  </section>
`;

let aboutHtml = templateHtml
  .replace(/<title>.*?<\/title>/, `<title>About Us · 도심복합개발 지식 포털 소개</title>`)
  .replace(/<meta name="title" content=".*?">/, `<meta name="title" content="About Us · 도심복합개발 지식 포털 소개">`)
  .replace(/<meta name="description" content=".*?">/, `<meta name="description" content="도심복합개발 실전 지식 포털 설립 취지, E-E-A-T 전문성 및 운영팀 소개">`)
  .replace(/<meta property="og:url" content=".*?">/, `<meta property="og:url" content="${baseUrl}/about">`)
  .replace(/<main class="main-wrapper" id="mainContainer">[\s\S]*?<\/main>/, `<main class="main-wrapper" id="mainContainer">\n${aboutContent}\n  </main>`);

fs.writeFileSync(path.join(aboutDir, 'index.html'), aboutHtml, 'utf8');
console.log('  ├─ ✅ /about/index.html 생성 완료');

// B. Privacy Policy
const privacyDir = path.join(frontendDir, 'privacy');
if (!fs.existsSync(privacyDir)) fs.mkdirSync(privacyDir, { recursive: true });

const privacyContent = `
  <section class="policy-container">
    <header class="policy-header">
      <h1 class="policy-title">Privacy Policy · 개인정보처리방침</h1>
      <p class="policy-desc">시행일자: 2026년 8월 1일</p>
    </header>

    <div class="policy-content">
      <p>
        도심복합개발 지식 포털(이하 "사이트")은 이용자의 개인정보를 중요시하며, 「개인정보 보호법」 및 Google AdSense 정책을 준수하고 있습니다.
      </p>

      <h3>1. 수집하는 개인정보 항목 및 수집 방법</h3>
      <p>
        본 사이트는 일반적인 열람 시 별도의 회원가입 없이 모든 콘텐츠를 이용할 수 있습니다. 단, '문의하기(Contact Us)' 폼을 이용할 때 아래 정보가 수집됩니다.
      </p>
      <ul>
        <li><strong>수집 항목:</strong> 이름(닉네임), 이메일 주소, 문의 내용</li>
        <li><strong>수집 목적:</strong> 문의 사항에 대한 사실 확인 및 답변 회신</li>
        <li><strong>보유 기간:</strong> 문의 처리 완료 후 1년간 보관 후 지체 없이 파기</li>
      </ul>

      <h3>2. 쿠키(Cookie) 및 웹 비콘 사용 안내 (Google AdSense 준수)</h3>
      <p>
        본 사이트는 제3자 광고 사업자(Google 포함)를 통해 사용자가 본 사이트 또는 다른 웹사이트를 방문한 기록을 바탕으로 맞춤형 광고를 게재합니다.
      </p>
      <ul>
        <li>Google은 <strong>DoubleClick DART 쿠키</strong>를 사용하여 사용자의 인터넷 방문 기록에 따른 광고를 게재합니다.</li>
        <li>사용자는 <a href="https://adssettings.google.com" target="_blank" rel="noopener noreferrer" style="color: var(--color-secondary); font-weight:700;">Google 광고 설정</a>을 방문하여 맞춤 광고 게재에 사용되는 DART 쿠키를 사용 중지(Opt-out)할 수 있습니다.</li>
        <li>또한 사용자는 웹 브라우저의 옵션 설정을 통해 쿠키 허용 여부를 언제든지 변경할 수 있습니다.</li>
      </ul>

      <h3>3. 개인정보 보호책임자</h3>
      <p>
        현대공인중개사사무소 (대표: 백명건 / 서울특별시 서초구 반포동 714-26 1층 / 연락처: 02-3446-2361)
      </p>
    </div>
  </section>
`;

let privacyHtml = templateHtml
  .replace(/<title>.*?<\/title>/, `<title>개인정보처리방침 (Privacy Policy) · 도심복합개발 지식 포털</title>`)
  .replace(/<meta name="title" content=".*?">/, `<meta name="title" content="개인정보처리방침 (Privacy Policy) · 도심복합개발 지식 포털">`)
  .replace(/<meta name="description" content=".*?">/, `<meta name="description" content="도심복합개발 포털의 개인정보 보호 정책, Google AdSense 쿠키 규정 안내">`)
  .replace(/<meta property="og:url" content=".*?">/, `<meta property="og:url" content="${baseUrl}/privacy">`)
  .replace(/<main class="main-wrapper" id="mainContainer">[\s\S]*?<\/main>/, `<main class="main-wrapper" id="mainContainer">\n${privacyContent}\n  </main>`);

fs.writeFileSync(path.join(privacyDir, 'index.html'), privacyHtml, 'utf8');
console.log('  ├─ ✅ /privacy/index.html 생성 완료');

// C. Terms of Service
const termsDir = path.join(frontendDir, 'terms');
if (!fs.existsSync(termsDir)) fs.mkdirSync(termsDir, { recursive: true });

const termsContent = `
  <section class="policy-container">
    <header class="policy-header">
      <h1 class="policy-title">Terms of Service · 이용약관 및 법적 면책조항</h1>
      <p class="policy-desc">시행일자: 2026년 8월 1일</p>
    </header>

    <div class="policy-content">
      <h3>1. 목적</h3>
      <p>
        본 약관은 도심복합개발 지식 포털이 제공하는 모든 정보 서비스의 이용 조건 및 절차, 이용자와 사이트 간의 권리, 의무 및 책임사항을 규정함을 목적으로 합니다.
      </p>

      <h3>2. 법적 면책조항 (Disclaimer - 중요)</h3>
      <blockquote style="margin: 1.5rem 0;">
        <strong>⚠️ 투자 및 법률 자문 면책 고지</strong><br>
        본 사이트에서 제공하는 모든 연재 아티클, 법률 분석, 계산 예시, 후보지 정보 등은 부동산 제도에 대한 <strong>일반적인 정보 제공 및 학술적 연구 목적</strong>으로 작성된 것입니다. 이는 특정 부동산 매매 권유, 투자 자문, 공식 법률 또는 세무 감정 의견을 대신할 수 없습니다. 모든 최종 의사결정은 관할 지자체 고시 및 전문 세무사·변호사의 자문을 받으시기 바랍니다.
      </blockquote>

      <h3>3. 저작권 및 지식재산권</h3>
      <p>
        본 사이트에 게재된 텍스트, HTML 카드뉴스, 그래픽, 지식 그래프 시각화 엔진의 모든 저작권은 사이트 운영팀에 귀속됩니다. 사전 서면 동의 없는 무단 전재, 크롤링, 상업적 재배포를 금지합니다.
      </p>
    </div>
  </section>
`;

let termsHtml = templateHtml
  .replace(/<title>.*?<\/title>/, `<title>이용약관 및 면책조항 (Terms of Service) · 도심복합개발 포털</title>`)
  .replace(/<meta name="title" content=".*?">/, `<meta name="title" content="이용약관 및 면책조항 (Terms of Service) · 도심복합개발 포털">`)
  .replace(/<meta name="description" content=".*?">/, `<meta name="description" content="도심복합개발 지식 포털 서비스 이용약관 및 투자/법률 면책조항">`)
  .replace(/<meta property="og:url" content=".*?">/, `<meta property="og:url" content="${baseUrl}/terms">`)
  .replace(/<main class="main-wrapper" id="mainContainer">[\s\S]*?<\/main>/, `<main class="main-wrapper" id="mainContainer">\n${termsContent}\n  </main>`);

fs.writeFileSync(path.join(termsDir, 'index.html'), termsHtml, 'utf8');
console.log('  ├─ ✅ /terms/index.html 생성 완료');

// D. Contact Us
const contactDir = path.join(frontendDir, 'contact');
if (!fs.existsSync(contactDir)) fs.mkdirSync(contactDir, { recursive: true });

const contactContent = `
  <section class="policy-container">
    <header class="policy-header">
      <h1 class="policy-title">Contact Us · 문의하기 & 자문 요청</h1>
      <p class="policy-desc">도심복합개발 포털 연구팀 및 전문가 소통 채널입니다.</p>
    </header>

    <div class="policy-content">
      <p>
        콘텐츠에 대한 추가 질의, 후보지 데이터 정정 요청, 비즈니스 제휴 및 칼럼 기고 문의는 아래 양식을 작성해 주시면 담당자가 확인 후 신속하게 회신해 드립니다.
      </p>

      <form id="contactPageForm" class="contact-form">
        <div class="form-group">
          <label class="form-label" for="contactName">이름 (또는 닉네임) *</label>
          <input type="text" id="contactName" class="form-input" placeholder="홍길동" required>
        </div>

        <div class="form-group">
          <label class="form-label" for="contactEmail">이메일 주소 *</label>
          <input type="email" id="contactEmail" class="form-input" placeholder="example@domain.com" required>
        </div>

        <div class="form-group">
          <label class="form-label" for="contactSubject">문의 제목</label>
          <input type="text" id="contactSubject" class="form-input" placeholder="문의하시는 핵심 주제를 입력해 주세요">
        </div>

        <div class="form-group">
          <label class="form-label" for="contactMsg">문의 내용 *</label>
          <textarea id="contactMsg" class="form-textarea" style="min-height: 140px;" placeholder="자세한 문의 내용이나 피드백을 남겨주세요." required></textarea>
        </div>

        <button type="submit" class="btn-submit">문의 전송하기</button>
      </form>

      <div style="margin-top: 2rem; background: var(--bg-surface-low); border: 1.5px solid var(--border-color); border-radius: var(--radius-md); padding: 1.2rem 1.5rem;">
        <strong style="color: var(--color-primary);">📞 연구팀 직통 연락처</strong>
        <p style="margin: 0.5rem 0 0; font-size: 0.88rem; color: var(--text-secondary);">
          • 사무소: 현대공인중개사사무소 (대표: 백명건)<br>
          • 대표전화: 02-3446-2361 &nbsp;|&nbsp; 팩스: 02-3446-2711<br>
          • 주소: 서울특별시 서초구 반포동 714-26 1층
        </p>
      </div>
    </div>
  </section>
`;

let contactHtml = templateHtml
  .replace(/<title>.*?<\/title>/, `<title>문의하기 (Contact Us) · 도심복합개발 지식 포털</title>`)
  .replace(/<meta name="title" content=".*?">/, `<meta name="title" content="문의하기 (Contact Us) · 도심복합개발 지식 포털">`)
  .replace(/<meta name="description" content=".*?">/, `<meta name="description" content="도심복합개발 실전 연구팀 및 현대공인중개사사무소 문의 채널">`)
  .replace(/<meta property="og:url" content=".*?">/, `<meta property="og:url" content="${baseUrl}/contact">`)
  .replace(/<main class="main-wrapper" id="mainContainer">[\s\S]*?<\/main>/, `<main class="main-wrapper" id="mainContainer">\n${contactContent}\n  </main>`);

fs.writeFileSync(path.join(contactDir, 'index.html'), contactHtml, 'utf8');
console.log('  └─ ✅ /contact/index.html 생성 완료\n');

// ==========================================
// 4. 메인 인덱스 페이지 (`frontend/index.html`) 정적 사전 렌더링
// ==========================================
console.log('▶ [3단계] 메인 페이지 (/) 정적 피드 사전 렌더링 시작...\n');

const categoriesHtml = `
  <button class="filter-btn active" data-cat="all">
    전체 지식망 <span class="filter-count">(${articles.length})</span>
  </button>
  ${categories.map(c => `
    <button class="filter-btn" data-cat="${c.id}">
      ${c.name}
    </button>
  `).join('')}
`;

const cardsHtml = articles.map(art => `
  <a href="/article/${art.slug || art.id}" class="article-card">
    <div>
      <div class="card-top">
        <span class="card-vol">VOL.${String(art.order).padStart(2, '0')} · ${(art.category || '').split('.')[0]}</span>
        <span class="card-time">⏱️ ${art.readingTime || '4분'} 읽기</span>
      </div>
      <h3 class="card-title">${art.title}</h3>
      <p class="card-summary">${parseInlineMarkdown(art.easySummary || art.summary)}</p>
    </div>
    <div class="card-bottom">
      <div class="card-tags">
        ${(art.tags || []).slice(0, 3).map(t => `<span class="tag-badge">#${t}</span>`).join('')}
      </div>
      <span class="card-read-action">
        바로 읽기
        <span class="material-symbols-outlined icon-sm">arrow_forward</span>
      </span>
    </div>
  </a>
`).join('');

const homeMainHtml = `
  <!-- Editorial Hero Section -->
  <section class="hero-section">
    <span class="hero-tag">
      <span class="material-symbols-outlined icon-sm">verified</span>
      국토교통부 공공·민간 도심복합개발 실전 백과사전
    </span>
    <h1 class="hero-title">도심복합개발 완벽 정복 백과사전</h1>
    <p class="hero-subtitle">
      기초 개념부터 역세권·준공업·저층주거 지정기준, 사업성 분석, 140% 용적률 상향, 세제 감면, 실무 Q&A까지<br>
      유기적인 지식망으로 쉽고 명쾌하게 마스터하세요.
    </p>

    <!-- Search Bar -->
    <div class="search-container">
      <span class="material-symbols-outlined search-icon">search</span>
      <input type="text" id="searchInput" class="search-input" placeholder="궁금한 키워드를 검색하세요 (예: 역세권, 분담금, 용적률, 1+1, 세제)">
      <button class="search-clear-btn" id="searchClearBtn" title="검색어 지우기">&times;</button>
    </div>

    <!-- Quick Keyword Chips -->
    <div class="quick-keywords">
      <span class="quick-label">추천 키워드:</span>
      <span class="quick-tag" data-kw="역세권">#역세권 고밀개발</span>
      <span class="quick-tag" data-kw="용적률">#140% 용적률</span>
      <span class="quick-tag" data-kw="현물선납">#현물선납 세제특례</span>
      <span class="quick-tag" data-kw="동의율">#토지주 동의율</span>
      <span class="quick-tag" data-kw="1+1">#1+1 우선공급</span>
      <span class="quick-tag" data-kw="상가">#상가영업보상</span>
    </div>

    <!-- Key Status Statistics Grid -->
    <div class="hero-stats-grid">
      <div class="stat-item">
        <div class="stat-val">50부작</div>
        <div class="stat-label">실전 전문 연재 완비</div>
      </div>
      <div class="stat-item">
        <div class="stat-val">8대 영역</div>
        <div class="stat-label">체계적 지식 아카이브</div>
      </div>
      <div class="stat-item">
        <div class="stat-val">최대 140%</div>
        <div class="stat-label">법적 상한 용적률 완화</div>
      </div>
      <div class="stat-item">
        <div class="stat-val">100% 실전</div>
        <div class="stat-label">3초 요약 & Q&A 탑재</div>
      </div>
    </div>
  </section>

  <!-- Category Filter Tabs -->
  <div class="filter-tabs-wrapper">
    <div class="filter-tabs" id="filterTabs">
      ${categoriesHtml}
    </div>
  </div>

  <!-- Articles Card Feed (50개 전체 아티클 정적 렌더링) -->
  <section class="articles-feed">
    ${cardsHtml}
  </section>
`;

let finalIndexHtml = templateHtml.replace(
  /<main class="main-wrapper" id="mainContainer">[\s\S]*?<\/main>/,
  `<main class="main-wrapper" id="mainContainer">\n${homeMainHtml}\n  </main>`
);

fs.writeFileSync(indexPath, finalIndexHtml, 'utf8');
console.log(`  └─ ✅ frontend/index.html 메인 50개 카드 정적 렌더링 완료 (${cardsHtml.length} bytes)\n`);

// ==========================================
// 5. 사이트맵(sitemap.xml) 생성 (55개 전체 URL)
// ==========================================
console.log('▶ [4단계] 전체 XML 사이트맵(sitemap.xml) 생성 시작...\n');

let sitemapXml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n`;

// 1) 메인
sitemapXml += `  <url>\n    <loc>${baseUrl}/</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>\n`;

// 2) 4대 정책 페이지
sitemapXml += `  <url>\n    <loc>${baseUrl}/about</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.8</priority>\n  </url>\n`;
sitemapXml += `  <url>\n    <loc>${baseUrl}/privacy</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.8</priority>\n  </url>\n`;
sitemapXml += `  <url>\n    <loc>${baseUrl}/terms</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.8</priority>\n  </url>\n`;
sitemapXml += `  <url>\n    <loc>${baseUrl}/contact</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.8</priority>\n  </url>\n`;

// 3) 50개 아티클
articles.forEach(art => {
  sitemapXml += `  <url>\n    <loc>${baseUrl}/article/${art.slug}</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.9</priority>\n  </url>\n`;
});

sitemapXml += `</urlset>`;
fs.writeFileSync(path.join(frontendDir, 'sitemap.xml'), sitemapXml, 'utf8');
console.log(`  └─ ✅ sitemap.xml 생성 완료 (총 55개 URL 등록)\n`);

// ==========================================
// 6. Robots.txt 생성
// ==========================================
console.log('▶ [5단계] robots.txt 생성 시작...\n');

const robotsTxt = `User-agent: *
Allow: /
Disallow: /backend/

Sitemap: ${baseUrl}/sitemap.xml
`;
fs.writeFileSync(path.join(frontendDir, 'robots.txt'), robotsTxt, 'utf8');
console.log(`  └─ ✅ robots.txt 생성 완료\n`);

console.log('====================================================');
console.log('🎉  SSG 빌드 완벽 성공! 모든 정적 HTML & SEO 배포 준비 완료');
console.log('====================================================');

