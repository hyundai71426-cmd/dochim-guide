/**
 * 도심복합개발 지식 포털 메인 애플리케이션 (app.js)
 * Stitch Alexandria & Urban Composite 테마 적용
 * SPA 라우터, H2/H3/H4 정밀 파서, 3초 요약 엔진, Q&A 3+ 렌더러, 지식망 시각화 연동
 */

(function () {
  'use strict';

  // 상태 관리
  const state = {
    articles: [],
    categories: [],
    audiences: [],
    currentCategory: 'all',
    currentAudience: '전체',
    searchQuery: '',
    currentArticle: null,
    theme: localStorage.getItem('THEME') || 'light',
    isAdmin: btoa(sessionStorage.getItem('ADMIN_KEY') || localStorage.getItem('ADMIN_KEY') || '') === 'dXJiYW4yMDI2IQ=='
  };

  // DOM 캐시
  const elements = {
    mainContainer: document.getElementById('mainContainer'),
    progressBar: document.getElementById('readingProgress'),
    themeToggleBtn: document.getElementById('themeToggleBtn'),
    graphModal: document.getElementById('graphModal'),
    btnOpenGraph: document.getElementById('btnOpenGraph'),
    btnCloseGraph: document.getElementById('btnCloseGraph'),
    publishModal: document.getElementById('publishModal'),
    btnOpenPublish: document.getElementById('btnOpenPublish'),
    btnClosePublish: document.getElementById('btnClosePublish'),
    publishForm: document.getElementById('publishForm'),
    btnResetGraph: document.getElementById('btnResetGraph'),
    navLinks: document.querySelectorAll('.nav-link'),
    btnAdminToggle: document.getElementById('btnAdminToggle'),
    footerAdminBtn: document.getElementById('footerAdminBtn'),
    adminModal: document.getElementById('adminModal'),
    btnCloseAdmin: document.getElementById('btnCloseAdmin'),
    adminLoginForm: document.getElementById('adminLoginForm'),
    adminPasswordInput: document.getElementById('adminPasswordInput'),
    adminLoginError: document.getElementById('adminLoginError')
  };

  let graphInstance = null;

  // 전역 카테고리 필터링 헬퍼 (푸터 등에서 호출 가능)
  window.filterCategory = function (catId) {
    state.currentCategory = catId;
    if (window.location.pathname !== '/') {
      navigateTo('/');
    } else {
      renderHomeView();
    }
  };

  // ==========================================
  // 1. 초기화 & 데이터 로드
  // ==========================================
  async function init() {
    applyTheme(state.theme);
    updateAdminUI();
    bindGlobalEvents();

    // 초기 데이터 로드 (API 또는 정적 DB)
    state.categories = window.CATEGORIES_DB || [];
    state.audiences = window.TARGET_AUDIENCES_DB || [];
    state.articles = await window.ApiClient.getArticles();

    // Popstate 이벤트 리스너
    window.addEventListener('popstate', handleRouting);

    // SPA 링크 클릭 인터셉터
    document.body.addEventListener('click', e => {
      const link = e.target.closest('a');
      if (link && link.getAttribute('href') && link.getAttribute('href').startsWith('/')) {
        const href = link.getAttribute('href');
        // XML 사이트맵 및 파일 링크는 제외
        if (href.endsWith('.xml') || href.endsWith('.txt')) return;
        
        e.preventDefault();
        navigateTo(href);
      }
    });

    handleRouting();
  }

  // ==========================================
  // 2. SPA 라우팅 시스템
  // ==========================================
  function navigateTo(path) {
    window.history.pushState({}, '', path);
    handleRouting();
  }
  window.navigateTo = navigateTo;

  async function handleRouting() {
    const path = window.location.pathname;
    window.scrollTo({ top: 0, behavior: 'instant' });

    // 네비게이션 링크 활성화 표시
    elements.navLinks.forEach(link => {
      const href = link.getAttribute('href');
      link.classList.toggle('active', href === path || (path === '/' && href === '/'));
    });

    if (path === '/' || path === '') {
      renderHomeView();
    } else if (path.startsWith('/article/')) {
      const articleId = path.replace('/article/', '');
      await renderArticleView(articleId);
    } else if (path === '/about') {
      renderAboutView();
    } else if (path === '/privacy') {
      renderPrivacyView();
    } else if (path === '/terms') {
      renderTermsView();
    } else if (path === '/contact') {
      renderContactView();
    } else {
      renderHomeView();
    }
  }

  // ==========================================
  // 3. 마크다운 및 텍스트 파서 유틸리티
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

    // 1. 코드블록 -> 정보 상자(Infobox) 렌더링
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
    let listType = ''; // 'ul' or 'ol'
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

      // Table line
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

      // Blockquote line
      if (/^>\s*/.test(line)) {
        flushList();
        inQuote = true;
        quoteLines.push(line.replace(/^>\s*/, ''));
        continue;
      } else {
        flushQuote();
      }

      if (!line) {
        flushList();
        continue;
      }

      if (/^<div[\s\S]*<\/div>$/.test(line)) {
        flushList();
        result += line;
      } else if (/^####\s+/.test(line)) {
        flushList();
        result += `<h4>${parseInlineMarkdown(line.replace(/^####\s+/, ''))}</h4>`;
      } else if (/^###\s+/.test(line)) {
        flushList();
        result += `<h3><span style="display:inline-block; width:4px; height:18px; border-radius:2px; background:var(--color-accent); margin-right:0.4rem;"></span>${parseInlineMarkdown(line.replace(/^###\s+/, ''))}</h3>`;
      } else if (/^##\s+/.test(line)) {
        flushList();
        result += `<h2>${parseInlineMarkdown(line.replace(/^##\s+/, ''))}</h2>`;
      } else if (/^#\s+/.test(line)) {
        flushList();
        result += `<h1>${parseInlineMarkdown(line.replace(/^#\s+/, ''))}</h1>`;
      } else if (/^[-*]\s+/.test(line)) {
        if (!inList || listType !== 'ul') {
          flushList();
          result += '<ul>';
          inList = true;
          listType = 'ul';
        }
        result += `<li>${parseInlineMarkdown(line.replace(/^[-*]\s+/, ''))}</li>`;
      } else if (/^\d+\.\s+/.test(line)) {
        if (!inList || listType !== 'ol') {
          flushList();
          result += '<ol>';
          inList = true;
          listType = 'ol';
        }
        result += `<li>${parseInlineMarkdown(line.replace(/^\d+\.\s+/, ''))}</li>`;
      } else {
        flushList();
        result += `<p>${parseInlineMarkdown(line)}</p>`;
      }
    }

    flushList();
    flushQuote();
    flushTable();

    return result;
  }

  // ==========================================
  // 3-1. 애드센스 슬롯 생성 헬퍼
  // ==========================================
  function createAdSenseSlot(slotType) {
    // 실서비스 뷰에서는 군더더기 박스를 노출하지 않습니다.
    return '';
  }

  // ==========================================
  // 4. 홈 뷰 렌더링 (Stitch Dochim Home Refined)
  // ==========================================
  function renderHomeView() {
    let filtered = state.articles;

    if (state.currentCategory !== 'all') {
      filtered = filtered.filter(a => a.categoryId === state.currentCategory);
    }
    if (state.searchQuery) {
      const q = state.searchQuery.toLowerCase();
      filtered = filtered.filter(a =>
        a.title.toLowerCase().includes(q) ||
        (a.summary && a.summary.toLowerCase().includes(q)) ||
        (a.easySummary && a.easySummary.toLowerCase().includes(q)) ||
        (a.tags && a.tags.some(t => t.toLowerCase().includes(q)))
      );
    }

    const categoriesHtml = `
      <button class="filter-btn ${state.currentCategory === 'all' ? 'active' : ''}" data-cat="all">
        전체 지식망 <span class="filter-count">(${state.articles.length})</span>
      </button>
      ${state.categories.map(c => `
        <button class="filter-btn ${state.currentCategory === c.id ? 'active' : ''}" data-cat="${c.id}">
          ${c.name}
        </button>
      `).join('')}
    `;

    const cardsHtml = filtered.map(art => `
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

    elements.mainContainer.innerHTML = `
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
          <input type="text" id="searchInput" class="search-input" placeholder="궁금한 키워드를 검색하세요 (예: 역세권, 분담금, 용적률, 1+1, 세제)" value="${state.searchQuery}">
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

      ${createAdSenseSlot('상단 메인 배너')}

      <!-- Articles Card Feed -->
      <section class="articles-feed">
        ${filtered.length > 0 ? cardsHtml : `
          <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem; background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-lg);">
            <p style="font-size: 1.2rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.5rem;">검색 결과가 없습니다.</p>
            <p style="font-size: 0.9rem; color: var(--text-muted);">다른 검색어나 상단 카테고리 필터를 선택해 보세요.</p>
            <button class="btn-header" style="margin-top: 1rem;" onclick="window.filterCategory('all')">전체 목록 보기</button>
          </div>
        `}
      </section>

      ${createAdSenseSlot('하단 피드 배너')}
    `;

    // 이벤트 바인딩
    const searchInput = document.getElementById('searchInput');
    const searchClearBtn = document.getElementById('searchClearBtn');

    if (searchInput) {
      if (searchClearBtn) {
        searchClearBtn.style.display = state.searchQuery ? 'block' : 'none';
        searchClearBtn.addEventListener('click', () => {
          state.searchQuery = '';
          renderHomeView();
        });
      }

      searchInput.addEventListener('input', (e) => {
        state.searchQuery = e.target.value;
        renderHomeView();
        const newSearch = document.getElementById('searchInput');
        if (newSearch) {
          newSearch.focus();
          newSearch.setSelectionRange(state.searchQuery.length, state.searchQuery.length);
        }
      });
    }

    // 퀵 태그 클릭
    document.querySelectorAll('.quick-tag').forEach(tag => {
      tag.addEventListener('click', () => {
        state.searchQuery = tag.dataset.kw;
        renderHomeView();
      });
    });

    const filterTabs = document.getElementById('filterTabs');
    if (filterTabs) {
      filterTabs.addEventListener('click', (e) => {
        const btn = e.target.closest('.filter-btn');
        if (btn) {
          state.currentCategory = btn.dataset.cat;
          renderHomeView();
        }
      });
    }
  }

  // ==========================================
  // 5. 글 상세 뷰 렌더링 (Stitch Article Detail Refined)
  // ==========================================
  async function renderArticleView(articleId) {
    const article = await window.ApiClient.getArticleById(articleId);

    if (!article) {
      elements.mainContainer.innerHTML = `
        <div class="policy-container" style="text-align: center;">
          <h2 class="policy-title">요청하신 아티클을 찾을 수 없습니다.</h2>
          <p class="policy-desc" style="margin-top: 1rem;">주소가 잘못되었거나 삭제된 글입니다.</p>
          <p style="margin-top: 1.5rem;"><a href="/" class="btn-submit" style="display:inline-block; text-decoration:none;">메인 포털로 돌아가기</a></p>
        </div>
      `;
      return;
    }

    state.currentArticle = article;

    // Card News HTML
    const cardNewsData = article.cardNews || {
      tagline: `VOL.${String(article.order).padStart(2, '0')} 핵심 요점`,
      highlightText: article.title,
      items: [
        { icon: '💡', title: '핵심 포인트', desc: article.summary },
        { icon: '⏱️', title: '읽는 시간', desc: '4분 완성' },
        { icon: '🔗', title: '연계 학습', desc: `${(article.relatedPostIds || []).length}편의 연계 지식` }
      ]
    };

    const cardNewsHtml = `
      <div class="card-news-banner">
        <div class="card-news-header">
          <span class="card-news-tagline">${cardNewsData.tagline}</span>
          <h2 class="card-news-highlight">${cardNewsData.highlightText}</h2>
        </div>
        <div class="card-news-grid">
          ${cardNewsData.items.map((item) => `
            <div class="card-news-item">
              <div class="item-icon">${item.icon}</div>
              <h4 class="item-title">${parseInlineMarkdown(item.title)}</h4>
              <p class="item-desc">${parseInlineMarkdown(item.desc)}</p>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    // Markdown Parser
    const bodyHtml = parseMarkdownToHtml(article.content || '');

    // Q&A HTML rendering
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

    // 이전/다음 글 찾기
    const allArts = state.articles;
    const currentIndex = allArts.findIndex(a => a.id === article.id || a.slug === article.slug);
    const prevArticle = currentIndex > 0 ? allArts[currentIndex - 1] : null;
    const nextArticle = currentIndex >= 0 && currentIndex < allArts.length - 1 ? allArts[currentIndex + 1] : null;

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

    // 연관 아티클 카드
    const relatedCardsHtml = (article.relatedArticles || []).map(rel => `
      <a href="/article/${rel.slug || rel.id}" class="related-card">
        <div class="rel-vol">VOL.${String(rel.order).padStart(2, '0')}</div>
        <div class="rel-title">${rel.title}</div>
        <div class="rel-summary">${parseInlineMarkdown((rel.easySummary || rel.summary || '').substring(0, 48))}…</div>
      </a>
    `).join('');

    elements.mainContainer.innerHTML = `
      <div class="reader-layout">
        <article class="reader-container">
          <!-- 상단 네비게이션 & 관리자 수정 버튼 -->
          <div class="reader-nav">
            <button class="btn-back" onclick="navigateTo('/')">
              <span class="material-symbols-outlined icon-sm">arrow_back</span>
              전체 연재 목록으로
            </button>
            <button class="btn-header" id="btnOpenEditArticle" style="display: ${state.isAdmin ? 'inline-flex' : 'none'};">
              <span class="material-symbols-outlined icon-sm">edit</span>
              이 글 수정하기
            </button>
          </div>

          <!-- 아티클 헤더 -->
          <header class="reader-header">
            <nav class="breadcrumb-nav" aria-label="Breadcrumb">
              <a href="/">홈</a>
              <span class="breadcrumb-separator">/</span>
              <a href="/" onclick="window.filterCategory && window.filterCategory('${article.categoryId}')">${article.category}</a>
              <span class="breadcrumb-separator">/</span>
              <span style="color: var(--text-primary); font-weight:700;">VOL.${String(article.order).padStart(2, '0')}</span>
            </nav>
            <div class="reader-meta-top">
              <span class="reader-category-badge">${article.category}</span>
              <span class="reader-vol">VOL.${String(article.order).padStart(2, '0')}</span>
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

          ${createAdSenseSlot('본문 상단 배너')}

          <!-- 본문 마크다운 -->
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

          ${createAdSenseSlot('본문 중간 반응형 배너')}

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

          ${createAdSenseSlot('하단 매칭형 배너')}
        </article>
      </div>
    `;

    // 글 수정 버튼 바인딩
    const btnOpenEdit = document.getElementById('btnOpenEditArticle');
    if (btnOpenEdit) {
      btnOpenEdit.addEventListener('click', () => {
        openEditModal(article);
      });
    }
  }

  function openEditModal(article) {
    const editModal = document.getElementById('editModal');
    if (!editModal) return;

    document.getElementById('editPostId').value = article.id;
    document.getElementById('editPostTitle').value = article.title || '';
    document.getElementById('editPostCategory').value = article.category || 'PART 1. 개념과 제도 도입 배경';
    document.getElementById('editPostSummary').value = article.easySummary || article.summary || '';
    document.getElementById('editPostTags').value = (article.tags || []).join(', ');
    document.getElementById('editPostContent').value = article.content || '';

    editModal.classList.add('active');
  }

  // ==========================================
  // 6. 정책 페이지: About Us (소개)
  // ==========================================
  function renderAboutView() {
    elements.mainContainer.innerHTML = `
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

          <h3>3. 운영 주체</h3>
          <div style="background: var(--bg-surface-low); border: 1.5px solid var(--border-color); border-radius: var(--radius-md); padding: 1.2rem 1.5rem; margin: 1.2rem 0;">
            <strong style="color: var(--color-primary); font-size: 1.05rem;">🏢 현대공인중개사사무소</strong>
            <ul style="margin: 0.6rem 0 0 1.2rem; line-height: 1.8;">
              <li><strong>대표:</strong> 백명건</li>
              <li><strong>주소:</strong> 서울특별시 서초구 반포동 714-26 1층</li>
              <li><strong>등록번호:</strong> 11650-2016-00300</li>
              <li><strong>대표번호:</strong> 02-3446-2361 &nbsp;|&nbsp; <strong>팩스:</strong> 02-3446-2711</li>
            </ul>
          </div>

          <h3>4. 콘텐츠 업데이트 안내</h3>
          <p>
            정부의 부동산 대책과 법령 개정 사항을 지속적으로 모니터링하여 최신 정보를 업데이트하고 있습니다. 오류 제보나 추가 문의는 언제든지 <a href="/contact" style="color: var(--color-secondary); font-weight:700;">문의하기</a>를 이용해 주시기 바랍니다.
          </p>
        </div>
      </section>
      ${createAdSenseSlot('About 페이지 하단 슬롯')}
    `;
  }

  // ==========================================
  // 7. 정책 페이지: Privacy Policy (개인정보처리방침)
  // ==========================================
  function renderPrivacyView() {
    elements.mainContainer.innerHTML = `
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
            <li>Google은 <strong>DoubleClick DART 쿠키</strong>를 사용하여 인터넷 방문 기록에 따른 광고를 사용자에게 게재합니다.</li>
            <li>사용자는 <a href="https://adssettings.google.com" target="_blank" rel="noopener noreferrer" style="color: var(--color-secondary); font-weight:700;">Google 광고 설정</a>을 방문하여 개인 맞춤 광고 설정을 해제(Opt-out)할 수 있습니다.</li>
            <li>또한 웹 브라우저의 옵션 설정을 통해 모든 쿠키를 거부하거나 쿠키 저장 시 알림을 받도록 설정할 수 있습니다.</li>
          </ul>

          <h3>3. 개인정보 보호책임자</h3>
          <p>
            현대공인중개사사무소 (대표: 백명건 / 서울특별시 서초구 반포동 714-26 1층 / 02-3446-2361)
          </p>
        </div>
      </section>
      ${createAdSenseSlot('Privacy 페이지 하단 슬롯')}
    `;
  }

  // ==========================================
  // 8. 정책 페이지: Terms of Service (이용약관 및 면책조항)
  // ==========================================
  function renderTermsView() {
    elements.mainContainer.innerHTML = `
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
            본 사이트에 게재된 텍스트, HTML 카드뉴스, 그래픽, 지식 그래프 시각화 엔진의 모든 저작권은 사이트 운영팀에 귀속됩니다. 사전 동의 없는 무단 전재, 크롤링, 상업적 재배포를 금지합니다.
          </p>
        </div>
      </section>
      ${createAdSenseSlot('Terms 페이지 하단 슬롯')}
    `;
  }

  // ==========================================
  // 9. 정책 페이지: Contact Us (문의하기)
  // ==========================================
  function renderContactView() {
    elements.mainContainer.innerHTML = `
      <section class="policy-container">
        <header class="policy-header">
          <h1 class="policy-title">Contact Us · 문의하기 & 피드백</h1>
          <p class="policy-desc">도심복합개발 포털 연구팀과의 소통 채널입니다.</p>
        </header>

        <div class="policy-content">
          <p>
            콘텐츠에 대한 추가 문의, 후보지 데이터 정정 요청, 비즈니스 제휴 및 칼럼 기고 문의는 아래 양식을 작성해 주시면 담당자가 확인 후 신속하게 회신해 드립니다.
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

          <div id="contactStatus" style="margin-top: 1rem; font-weight:700; display:none;"></div>

          <div style="margin-top: 2rem; background: var(--bg-surface-low); border: 1.5px solid var(--border-color); border-radius: var(--radius-md); padding: 1.2rem 1.5rem;">
            <strong style="color: var(--color-primary); font-size: 1.05rem;">📬 공식 연락처 안내</strong>
            <ul style="margin: 0.5rem 0 0 1.2rem; line-height: 1.8;">
              <li><strong>상호:</strong> 현대공인중개사사무소</li>
              <li><strong>대표:</strong> 백명건 &nbsp;|&nbsp; <strong>등록번호:</strong> 11650-2016-00300</li>
              <li><strong>주소:</strong> 서울특별시 서초구 반포동 714-26 1층</li>
              <li><strong>대표번호:</strong> 02-3446-2361 &nbsp;|&nbsp; <strong>팩스:</strong> 02-3446-2711</li>
              <li><strong>운영 시간:</strong> 평일 09:30 ~ 18:00 (주말 및 공휴일 제외)</li>
            </ul>
          </div>
        </div>
      </section>
      ${createAdSenseSlot('Contact 페이지 하단 슬롯')}
    `;

    const contactForm = document.getElementById('contactPageForm');
    const contactStatus = document.getElementById('contactStatus');
    if (contactForm) {
      contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = {
          name: document.getElementById('contactName').value,
          email: document.getElementById('contactEmail').value,
          subject: document.getElementById('contactSubject').value,
          message: document.getElementById('contactMsg').value
        };

        contactStatus.style.display = 'block';
        contactStatus.style.color = 'var(--color-secondary)';
        contactStatus.textContent = '문의를 전송하는 중입니다...';

        const result = await window.ApiClient.submitContact(data);
        if (result.success) {
          contactStatus.style.color = '#10B981';
          contactStatus.textContent = '✅ ' + result.message;
          contactForm.reset();
        } else {
          contactStatus.style.color = '#EF4444';
          contactStatus.textContent = '❌ ' + (result.message || '전송 실패');
        }
      });
    }
  }

  // ==========================================
  // 10. 글로벌 이벤트 & 모달 관리
  // ==========================================
  function bindGlobalEvents() {
    // Theme Toggle
    if (elements.themeToggleBtn) {
      elements.themeToggleBtn.addEventListener('click', () => {
        const nextTheme = state.theme === 'light' ? 'dark' : 'light';
        applyTheme(nextTheme);
      });
    }

    // Scroll progress bar
    window.addEventListener('scroll', () => {
      const winScroll = document.documentElement.scrollTop || document.body.scrollTop;
      const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      const scrolled = height > 0 ? (winScroll / height) * 100 : 0;
      if (elements.progressBar) {
        elements.progressBar.style.width = `${scrolled}%`;
      }
    });

    // Knowledge Graph Modal
    if (elements.btnOpenGraph && elements.graphModal) {
      elements.btnOpenGraph.addEventListener('click', async () => {
        elements.graphModal.classList.add('active');

        if (!state.articles || state.articles.length === 0) {
          state.articles = await window.ApiClient.getArticles();
        }

        setTimeout(() => {
          if (!graphInstance) {
            graphInstance = new window.KnowledgeGraph(
              'graphCanvas',
              state.articles,
              state.categories,
              (articleId) => {
                elements.graphModal.classList.remove('active');
                if (graphInstance) graphInstance.hideTooltip();
                navigateTo(`/article/${articleId}`);
              }
            );
          } else {
            graphInstance.setArticles(state.articles, state.categories);
            graphInstance.resize();
            graphInstance.resetView();
          }
        }, 50);
      });
    }

    if (elements.btnCloseGraph && elements.graphModal) {
      elements.btnCloseGraph.addEventListener('click', () => {
        elements.graphModal.classList.remove('active');
        if (graphInstance) graphInstance.hideTooltip();
      });
    }

    if (elements.graphModal) {
      elements.graphModal.addEventListener('click', (e) => {
        if (e.target === elements.graphModal) {
          elements.graphModal.classList.remove('active');
          if (graphInstance) graphInstance.hideTooltip();
        }
      });
    }

    // 지식 그래프 툴 컨트롤
    const btnResetGraph = document.getElementById('btnResetGraph');
    if (btnResetGraph) {
      btnResetGraph.addEventListener('click', () => {
        if (graphInstance) graphInstance.resetView();
      });
    }

    const btnZoomInGraph = document.getElementById('btnZoomInGraph');
    if (btnZoomInGraph) {
      btnZoomInGraph.addEventListener('click', () => {
        if (graphInstance) graphInstance.zoomIn();
      });
    }

    const btnZoomOutGraph = document.getElementById('btnZoomOutGraph');
    if (btnZoomOutGraph) {
      btnZoomOutGraph.addEventListener('click', () => {
        if (graphInstance) graphInstance.zoomOut();
      });
    }

    const graphSearchInput = document.getElementById('graphSearchInput');
    if (graphSearchInput) {
      graphSearchInput.addEventListener('input', (e) => {
        if (graphInstance) graphInstance.searchNode(e.target.value);
      });
    }

    const graphCatFilters = document.getElementById('graphCatFilters');
    if (graphCatFilters) {
      graphCatFilters.addEventListener('click', (e) => {
        const btn = e.target.closest('.graph-filter-btn');
        if (btn) {
          graphCatFilters.querySelectorAll('.graph-filter-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          if (graphInstance) graphInstance.focusCategory(btn.dataset.cat);
        }
      });
    }

    // Publish Post Modal
    if (elements.btnOpenPublish && elements.publishModal) {
      elements.btnOpenPublish.addEventListener('click', () => {
        elements.publishModal.classList.add('active');
      });
    }

    if (elements.btnClosePublish && elements.publishModal) {
      elements.btnClosePublish.addEventListener('click', () => {
        elements.publishModal.classList.remove('active');
      });
    }

    if (elements.publishForm) {
      elements.publishForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = document.getElementById('newPostTitle').value;
        const category = document.getElementById('newPostCategory').value;
        const summary = document.getElementById('newPostSummary').value;
        const content = document.getElementById('newPostContent').value;
        const tags = document.getElementById('newPostTags').value.split(',').map(t => t.trim()).filter(Boolean);

        const newPost = {
          title,
          category,
          categoryId: 'part-1',
          summary,
          easySummary: summary,
          content,
          tags,
          targetAudience: ['전체', '토지소유자'],
          qna: [
            { q: "Q1. 이 글의 핵심 실무 포인트는 무엇인가요?", a: summary },
            { q: "Q2. 토지소유자가 가장 주의해야 할 사항은?", a: "사업 추진 일정 및 동의율 요건을 면밀히 확인해야 합니다." },
            { q: "Q3. 추가 자문은 어디서 받을 수 있나요?", a: "사이트의 문의하기 폼을 통해 전문 연구팀과 상담할 수 있습니다." }
          ]
        };

        try {
          const res = await fetch('/api/articles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newPost)
          });
          if (res.ok) {
            const data = await res.json();
            alert('글이 성공적으로 발행되었습니다!');
            elements.publishModal.classList.remove('active');
            elements.publishForm.reset();
            state.articles = await window.ApiClient.getArticles();
            navigateTo(`/article/${data.data.slug || data.data.id}`);
            return;
          }
        } catch (_) {}

        // 로컬 스토리지 폴백
        const localSaved = JSON.parse(localStorage.getItem('CUSTOM_ARTICLES') || '[]');
        const nextOrder = state.articles.length + 1;
        const customArt = {
          ...newPost,
          id: `post-${nextOrder}`,
          order: nextOrder,
          readingTime: '4분',
          cardNews: {
            tagline: `VOL.${nextOrder} 신규 발행`,
            highlightText: title,
            items: [{ icon: '💡', title: '핵심 요약', desc: summary }]
          },
          bridgeStory: '새로 발행된 글입니다.',
          relatedPostIds: ['post-01', 'post-06', 'post-14']
        };
        localSaved.push(customArt);
        localStorage.setItem('CUSTOM_ARTICLES', JSON.stringify(localSaved));

        alert('글이 로컬에 저장되어 발행되었습니다!');
        elements.publishModal.classList.remove('active');
        elements.publishForm.reset();
        state.articles = await window.ApiClient.getArticles();
        navigateTo(`/article/${customArt.slug || customArt.id}`);
      });
    }

    // CMS 수정 모달
    const editModal = document.getElementById('editModal');
    const btnCloseEdit = document.getElementById('btnCloseEdit');
    const btnCancelEdit = document.getElementById('btnCancelEdit');
    const editForm = document.getElementById('editForm');

    if (btnCloseEdit && editModal) {
      btnCloseEdit.addEventListener('click', () => editModal.classList.remove('active'));
    }
    if (btnCancelEdit && editModal) {
      btnCancelEdit.addEventListener('click', () => editModal.classList.remove('active'));
    }

    if (editForm) {
      editForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('editPostId').value;
        const title = document.getElementById('editPostTitle').value;
        const categorySelect = document.getElementById('editPostCategory');
        const category = categorySelect.value;
        const categoryId = categorySelect.options[categorySelect.selectedIndex]?.dataset?.cat || 'part-1';
        const summary = document.getElementById('editPostSummary').value;
        const content = document.getElementById('editPostContent').value;
        const tags = document.getElementById('editPostTags').value.split(',').map(t => t.trim()).filter(Boolean);

        const updatedData = {
          title,
          category,
          categoryId,
          summary,
          easySummary: summary,
          content,
          tags
        };

        const res = await window.ApiClient.updateArticle(id, updatedData);
        if (res && res.success) {
          alert('글이 성공적으로 수정되었습니다!');
          editModal.classList.remove('active');
          state.articles = await window.ApiClient.getArticles();
          renderArticleView(id);
        } else {
          alert('수정에 실패했습니다. 다시 시도해 주세요.');
        }
      });
    }

    // Admin 관리자 모달
    function openAdminModal() {
      if (elements.adminModal) {
        if (elements.adminLoginError) elements.adminLoginError.style.display = 'none';
        if (elements.adminPasswordInput) elements.adminPasswordInput.value = '';
        elements.adminModal.classList.add('active');
        if (elements.adminPasswordInput) elements.adminPasswordInput.focus();
      }
    }

    if (elements.btnAdminToggle) {
      elements.btnAdminToggle.addEventListener('click', () => {
        if (state.isAdmin) {
          if (confirm('관리자 세션을 종료하고 일반 방문자 모드로 전환하시겠습니까?')) {
            state.isAdmin = false;
            sessionStorage.removeItem('ADMIN_KEY');
            localStorage.removeItem('ADMIN_KEY');
            updateAdminUI();
            if (state.currentArticle && window.location.pathname.startsWith('/article/')) {
              renderArticleView(state.currentArticle.id);
            }
            alert('관리자 모드가 해제되었습니다.');
          }
        } else {
          openAdminModal();
        }
      });
    }

    if (elements.footerAdminBtn) {
      elements.footerAdminBtn.addEventListener('click', () => {
        if (!state.isAdmin) openAdminModal();
        else alert('이미 관리자 권한으로 로그인되어 있습니다.');
      });
    }

    if (elements.btnCloseAdmin && elements.adminModal) {
      elements.btnCloseAdmin.addEventListener('click', () => {
        elements.adminModal.classList.remove('active');
      });
    }

    if (elements.adminLoginForm) {
      elements.adminLoginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const pwd = (elements.adminPasswordInput.value || '').trim();
        if (pwd === 'urban2026!') {
          state.isAdmin = true;
          sessionStorage.setItem('ADMIN_KEY', 'urban2026!');
          localStorage.setItem('ADMIN_KEY', 'urban2026!');
          updateAdminUI();
          elements.adminModal.classList.remove('active');
          alert('✅ 관리자 인증 완료!\n이제 상단 글쓰기 및 본문 실시간 CMS 수정 기능이 활성화되었습니다.');
          if (state.currentArticle && window.location.pathname.startsWith('/article/')) {
            renderArticleView(state.currentArticle.id);
          }
        } else {
          if (elements.adminLoginError) elements.adminLoginError.style.display = 'block';
        }
      });
    }

    // 단축키: Ctrl + Shift + A 관리자 모달
    window.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.shiftKey && (e.key === 'A' || e.key === 'a')) {
        e.preventDefault();
        if (!state.isAdmin) openAdminModal();
        else alert('현재 관리자 모드 활성 상태입니다.');
      }
    });
  }

  function updateAdminUI() {
    if (elements.btnOpenPublish) {
      elements.btnOpenPublish.style.display = state.isAdmin ? 'inline-flex' : 'none';
    }
    if (elements.btnAdminToggle) {
      if (state.isAdmin) {
        elements.btnAdminToggle.innerHTML = '<span class="material-symbols-outlined icon-sm">lock_open</span><span>관리자 종료</span>';
        elements.btnAdminToggle.title = '관리자 세션 종료(로그아웃)';
        elements.btnAdminToggle.style.borderColor = 'var(--color-accent)';
        elements.btnAdminToggle.style.color = 'var(--color-accent-hover)';
      } else {
        elements.btnAdminToggle.innerHTML = '<span class="material-symbols-outlined icon-sm">lock</span><span>관리자</span>';
        elements.btnAdminToggle.title = '관리자 모드 로그인';
        elements.btnAdminToggle.style.borderColor = '';
        elements.btnAdminToggle.style.color = '';
      }
    }
    const editBtn = document.getElementById('btnOpenEditArticle');
    if (editBtn) {
      editBtn.style.display = state.isAdmin ? 'inline-flex' : 'none';
    }
  }

  function applyTheme(theme) {
    state.theme = theme;
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(`theme-${theme}`);
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('THEME', theme);

    const themeIcon = document.getElementById('themeIcon');
    if (themeIcon) {
      themeIcon.textContent = theme === 'light' ? 'dark_mode' : 'light_mode';
    }
  }

  // 앱 시작
  document.addEventListener('DOMContentLoaded', init);
})();
