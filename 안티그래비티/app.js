/**
 * 도심복합개발 지식 포털 메인 애플리케이션 (app.js)
 * SPA 라우터, H2/H3/H4 정밀 파서, Q&A 3+ 렌더러, 애드센스 슬롯 관리, 필수 정책 페이지
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
    isAdmin: Boolean((sessionStorage.getItem('ADMIN_KEY') || localStorage.getItem('ADMIN_KEY')) === 'urban2026!')
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

  // ==========================================
  // 1. 초기화 & 데이터 로드
  // ==========================================
  async function init() {
    applyTheme(state.theme);
    updateAdminUI();
    bindGlobalEvents();

    // Load initial data from API or Static DB
    state.categories = window.CATEGORIES_DB || [];
    state.audiences = window.TARGET_AUDIENCES_DB || [];
    state.articles = await window.ApiClient.getArticles();

    // Listen to hash change
    window.addEventListener('hashchange', handleRouting);
    handleRouting();
  }

  // ==========================================
  // 2. SPA 라우팅 시스템
  // ==========================================
  async function handleRouting() {
    const hash = window.location.hash || '#home';
    window.scrollTo({ top: 0, behavior: 'instant' });

    // Highlight nav link
    elements.navLinks.forEach(link => {
      const href = link.getAttribute('href');
      link.classList.toggle('active', href === hash);
    });

    if (hash === '#home' || hash === '') {
      renderHomeView();
    } else if (hash.startsWith('#article/')) {
      const articleId = hash.replace('#article/', '');
      await renderArticleView(articleId);
    } else if (hash === '#about') {
      renderAboutView();
    } else if (hash === '#privacy') {
      renderPrivacyView();
    } else if (hash === '#terms') {
      renderTermsView();
    } else if (hash === '#contact') {
      renderContactView();
    } else {
      renderHomeView();
    }
  }

  // ==========================================
  // 3. 애드센스 슬롯 생성 헬퍼
  // ==========================================
  function createAdSenseSlot(slotType) {
    return `
      <div class="adsense-slot-container" data-slot="${slotType}">
        <span class="adsense-badge">ADVERTISEMENT / 스폰서</span>
        <div class="adsense-placeholder">
          <!-- 구글 애드센스 승인 후 광고 코드가 렌더링되는 영역입니다 -->
          <span>💡 구글 애드센스 반응형 광고 슬롯 (${slotType})</span>
        </div>
      </div>
    `;
  }

  // ==========================================
  // 4. 홈 피드 뷰 렌더링
  // ==========================================
  function renderHomeView() {
    let filtered = state.articles;

    if (state.currentCategory !== 'all') {
      filtered = filtered.filter(a => a.categoryId === state.currentCategory);
    }
    if (state.currentAudience !== '전체') {
      filtered = filtered.filter(a => a.targetAudience && a.targetAudience.includes(state.currentAudience));
    }
    if (state.searchQuery) {
      const q = state.searchQuery.toLowerCase();
      filtered = filtered.filter(a =>
        a.title.toLowerCase().includes(q) ||
        a.summary.toLowerCase().includes(q) ||
        (a.tags && a.tags.some(t => t.toLowerCase().includes(q)))
      );
    }

    const categoriesHtml = `
      <button class="filter-btn ${state.currentCategory === 'all' ? 'active' : ''}" data-cat="all">전체 (${state.articles.length})</button>
      ${state.categories.map(c => `
        <button class="filter-btn ${state.currentCategory === c.id ? 'active' : ''}" data-cat="${c.id}">
          ${c.title}
        </button>
      `).join('')}
    `;

    const cardsHtml = filtered.map(art => `
      <a href="#article/${art.id}" class="article-card">
        <div class="card-top">
          <span class="card-vol">VOL.${String(art.order).padStart(2, '0')} · ${(art.category || '').split('.')[0]}</span>
          <span class="card-time">⏱️ ${art.readingTime || '4분'} 읽기</span>
        </div>
        <h3 class="card-title">${art.title}</h3>
        <p class="card-summary">${art.easySummary || art.summary}</p>
        <div class="card-bottom">
          <div class="card-tags">
            ${(art.tags || []).map(t => `<span class="tag-badge">#${t}</span>`).join('')}
          </div>
          <span class="card-links-count">🔗 연계 글 ${(art.relatedPostIds || []).length}편</span>
        </div>
      </a>
    `).join('');

    elements.mainContainer.innerHTML = `
      <section class="hero-section">
        <span class="hero-tag">🏛️ 도심복합개발 실전 지식 포털</span>
        <h1 class="hero-title">도심복합개발 완벽 정복 백과사전</h1>
        <p class="hero-subtitle">
          기초 개념부터 세제 혜택, 사업성 분석, 갈등 해결, 투자 전략까지<br>
          유기적인 지식망으로 쉽고 명쾌하게 마스터하세요.
        </p>

        <div class="search-container">
          <span class="search-icon">🔍</span>
          <input type="text" id="searchInput" class="search-input" placeholder="궁금한 키워드를 검색해 보세요 (예: 역세권, 분담금, 용적률, 1+1, 세제)" value="${state.searchQuery}">
        </div>

        <div class="filter-tabs" id="filterTabs">
          ${categoriesHtml}
        </div>
      </section>

      ${createAdSenseSlot('상단 메인 배너')}

      <section class="articles-feed">
        ${filtered.length > 0 ? cardsHtml : `
          <div style="text-align: center; padding: 4rem 1rem; color: var(--text-muted);">
            <p style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.5rem;">검색 결과가 없습니다.</p>
            <p style="font-size: 0.9rem;">다른 검색어나 필터를 선택해 보세요.</p>
          </div>
        `}
      </section>

      ${createAdSenseSlot('하단 피드 배너')}
    `;

    // Search & Filter event bindings
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
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
  // 5. 글 상세 뷰 렌더링 (H2/H3/H4 파서 & Q&A 섹션 탑재)
  // ==========================================
  async function renderArticleView(articleId) {
    const article = await window.ApiClient.getArticleById(articleId);

    if (!article) {
      elements.mainContainer.innerHTML = `
        <div class="policy-container" style="text-align: center;">
          <h2>요청하신 글을 찾을 수 없습니다.</h2>
          <p style="margin-top: 1rem;"><a href="#home" class="btn-submit" style="display:inline-block; text-decoration:none;">홈으로 돌아가기</a></p>
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

    const cardNewsThemeClass = `card-news-theme-${article.categoryId || 'part-1'}`;

    const cardNewsHtml = `
      <div class="card-news-banner ${cardNewsThemeClass}">
        <span class="card-news-tagline">${cardNewsData.tagline}</span>
        <h2 class="card-news-highlight">${cardNewsData.highlightText}</h2>
        <div class="card-news-grid">
          ${cardNewsData.items.map(item => `
            <div class="card-news-item">
              <div class="item-icon">${item.icon}</div>
              <h4 class="item-title">${item.title}</h4>
              <p class="item-desc">${item.desc}</p>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    // Markdown Parser: H2, H3, H4, lists, quotes, bold
    let formattedContent = article.content || '';
    formattedContent = formattedContent.replace(/---/g, '');

    const lines = formattedContent.split('\n');
    let inList = false;
    let bodyHtml = '';

    for (let line of lines) {
      line = line.trim();
      if (!line) {
        if (inList) { bodyHtml += '</ul>'; inList = false; }
        continue;
      }

      if (line.startsWith('## ')) {
        if (inList) { bodyHtml += '</ul>'; inList = false; }
        bodyHtml += `<h2>${line.replace('## ', '')}</h2>`;
      } else if (line.startsWith('# ')) {
        if (inList) { bodyHtml += '</ul>'; inList = false; }
        bodyHtml += `<h2>${line.replace('# ', '')}</h2>`;
      } else if (line.startsWith('### ')) {
        if (inList) { bodyHtml += '</ul>'; inList = false; }
        bodyHtml += `<h3>${line.replace('### ', '')}</h3>`;
      } else if (line.startsWith('#### ')) {
        if (inList) { bodyHtml += '</ul>'; inList = false; }
        bodyHtml += `<h4>${line.replace('#### ', '')}</h4>`;
      } else if (line.startsWith('* ') || line.startsWith('- ')) {
        if (!inList) { bodyHtml += '<ul>'; inList = true; }
        const itemText = line.substring(2).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        bodyHtml += `<li>${itemText}</li>`;
      } else if (line.startsWith('> ')) {
        if (inList) { bodyHtml += '</ul>'; inList = false; }
        bodyHtml += `<blockquote>${line.substring(2)}</blockquote>`;
      } else {
        if (inList) { bodyHtml += '</ul>'; inList = false; }
        const parsedText = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        bodyHtml += `<p>${parsedText}</p>`;
      }
    }
    if (inList) bodyHtml += '</ul>';

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
          <div class="qna-tag">💬 FAQ & 실무 가이드</div>
          <h3 class="qna-title">이 주제에 대해 자주 묻는 핵심 Q&A</h3>
        </div>
        <div class="qna-list">
          ${qnaList.map(item => `
            <div class="qna-item">
              <div class="qna-q">${item.q}</div>
              <div class="qna-a">${item.a}</div>
            </div>
          `).join('')}
        </div>
      </section>
    `;

    // Related articles grid
    const relatedCardsHtml = (article.relatedArticles || []).map(rel => `
      <a href="#article/${rel.id}" class="related-card">
        <div>
          <div class="rel-vol">VOL.${String(rel.order).padStart(2, '0')}</div>
          <div class="rel-title">${rel.title}</div>
        </div>
        <div class="rel-summary">${(rel.easySummary || rel.summary || '').substring(0, 50)}…</div>
      </a>
    `).join('');

    elements.mainContainer.innerHTML = `
      <article class="reader-container">
        <div class="reader-nav" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
          <button class="btn-back" onclick="window.location.hash='#home'">← 전체 목록으로</button>
          <button class="btn-header" id="btnOpenEditArticle" style="font-size: 0.85rem; padding: 0.45rem 0.9rem; background: var(--bg-card); border: 1px solid var(--border-color); cursor: pointer; display: ${state.isAdmin ? 'inline-flex' : 'none'}; align-items: center; gap: 0.35rem;">
            <span>✏️</span> 이 글 수정하기
          </button>
        </div>

        <header class="reader-header">
          <div class="reader-meta-top">
            <span class="reader-category-badge">${article.category}</span>
            <span class="reader-vol">VOL.${String(article.order).padStart(2, '0')}</span>
          </div>
          <h1 class="reader-title">${article.title}</h1>
          <div class="reader-info-bar">
            <span>⏱️ ${article.readingTime || '4분'} 완성</span>
            <span>👥 추천 대상: ${(article.targetAudience || ['전체']).join(', ')}</span>
          </div>
        </header>

        <div class="reader-summary-box">
          <div class="summary-title">⚡ 3초 핵심 요약</div>
          <div class="summary-text">${article.easySummary || article.summary}</div>
        </div>

        ${cardNewsHtml}

        ${createAdSenseSlot('본문 상단 배너')}

        <div class="reader-body">
          ${bodyHtml}
        </div>

        ${qnaHtml}

        ${createAdSenseSlot('본문 중간 반응형 배너')}

        <section class="story-bridge-section">
          <div class="bridge-header">
            <div class="bridge-tag">🔗 꼬리에 꼬리를 무는 연계 지식</div>
            <h3 class="bridge-title">지금 읽은 내용과 바로 이어지는 추천 글</h3>
            <p class="bridge-desc">${article.bridgeStory || '이 글과 밀접하게 연관된 핵심 포인트를 함께 읽고 지식망을 완성하세요.'}</p>
          </div>
          <div class="related-grid">
            ${relatedCardsHtml}
          </div>
        </section>

        ${createAdSenseSlot('하단 매칭형 배너')}
      </article>
    `;

    // Bind Edit Button
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
  // 6. 애드센스 필수 페이지: About Us (소개)
  // ==========================================
  function renderAboutView() {
    elements.mainContainer.innerHTML = `
      <section class="policy-container">
        <header class="policy-header">
          <h1 class="policy-title">About Us · 도심복합개발 지식 포털 소개</h1>
          <p class="policy-date">최종 업데이트: 2026년 8월</p>
        </header>

        <div class="policy-content">
          <h2>1. 설립 취지와 목표 (E-E-A-T)</h2>
          <p>
            본 포털은 복잡하고 난해한 대한민국의 <strong>도심 공공주택 복합사업(공공주택 특별법)</strong> 및 <strong>민간 도심 복합개발(도심 복합개발 지원에 관한 법률)</strong>에 관한 정책, 법률, 세무, 사업성 분석 정보를 투명하고 알기 쉽게 제공하기 위해 개설된 전문 지식 아카이브입니다.
          </p>

          <h2>2. 전문성과 신뢰성</h2>
          <p>
            부동산 정비사업은 수많은 법적 쟁점과 토지소유자, 세입자, 상가영업권자 간의 이해관계가 얽혀 있습니다. 본 포털은 국토교통부 고시, LH·SH 공공기관 실무 가이드라인, 대법원 판례 및 세무 전문가 검증 데이터를 바탕으로 <strong>체계적인 지식 맵</strong>을 구축하였습니다.
          </p>

          <div class="policy-callout">
            <strong>💡 포털의 3대 핵심 원칙</strong>
            <ul>
              <li><strong>Fact-Based:</strong> 법령 조항 및 실제 행정 기준에 입각한 정확한 정보 제공</li>
              <li><strong>User-Centric:</strong> 전문 용어를 일상 언어로 쉽게 풀어낸 높은 가독성</li>
              <li><strong>Interconnected:</strong> 단편적 지식이 아닌 유기적 연계를 통한 입체적 이해 지원</li>
            </ul>
          </div>

          <h2>3. 운영 및 콘텐츠 업데이트</h2>
          <p>
            정부의 부동산 대책과 법령 개정 사항을 지속적으로 모니터링하여 최신성 높은 정보를 업데이트하고 있습니다. 오류 제보나 연구 협업 문의는 언제든지 <a href="#contact" style="color: var(--brand-primary); font-weight:700;">문의하기</a>를 이용해 주시기 바랍니다.
          </p>
        </div>
      </section>
      ${createAdSenseSlot('About 페이지 하단 슬롯')}
    `;
  }

  // ==========================================
  // 7. 애드센스 필수 페이지: Privacy Policy (개인정보처리방침)
  // ==========================================
  function renderPrivacyView() {
    elements.mainContainer.innerHTML = `
      <section class="policy-container">
        <header class="policy-header">
          <h1 class="policy-title">Privacy Policy · 개인정보처리방침</h1>
          <p class="policy-date">시행일자: 2026년 8월 1일</p>
        </header>

        <div class="policy-content">
          <p>
            도심복합개발 지식 포털(이하 "사이트")은 이용자의 개인정보를 중요시하며, 「개인정보 보호법」 및 Google AdSense 정책을 준수하고 있습니다.
          </p>

          <h2>1. 수집하는 개인정보 항목 및 수집 방법</h2>
          <p>
            본 사이트는 일반적인 열람 시 별도의 회원가입 없이 모든 콘텐츠를 이용할 수 있습니다. 단, '문의하기(Contact Us)' 폼을 이용할 때 아래 정보가 수집됩니다.
          </p>
          <ul>
            <li><strong>수집 항목:</strong> 이름(닉네임), 이메일 주소, 문의 내용</li>
            <li><strong>수집 목적:</strong> 문의 사항에 대한 사실 확인 및 답변 회신</li>
            <li><strong>보유 기간:</strong> 문의 처리 완료 후 1년간 보관 후 지체 없이 파기</li>
          </ul>

          <h2>2. 쿠키(Cookie) 및 웹 비콘 사용 안내 (Google AdSense 준수)</h2>
          <p>
            본 사이트는 제3자 광고 사업자(Google 포함)를 통해 사용자가 본 사이트 또는 다른 웹사이트를 방문한 기록을 바탕으로 맞춤형 광고를 게재합니다.
          </p>
          <ul>
            <li>Google은 <strong>DoubleClick DART 쿠키</strong>를 사용하여 인터넷 방문 기록에 따른 광고를 사용자에게 게재합니다.</li>
            <li>사용자는 <a href="https://adssettings.google.com" target="_blank" rel="noopener noreferrer" style="color: var(--brand-primary); font-weight:700;">Google 광고 설정</a>을 방문하여 개인 맞춤 광고 설정을 해제(Opt-out)할 수 있습니다.</li>
            <li>또한 웹 브라우저의 옵션 설정을 통해 모든 쿠키를 거부하거나 쿠키 저장 시 알림을 받도록 설정할 수 있습니다.</li>
          </ul>

          <h2>3. 개인정보의 제3자 제공 및 위탁</h2>
          <p>
            본 사이트는 이용자의 개인정보를 원칙적으로 외부에 제공하지 않으며, 법령의 규정에 의거하거나 수사 목적으로 법령에 정해진 절차와 방법에 따라 요구가 있는 경우에만 제공합니다.
          </p>

          <h2>4. 개인정보 보호책임자 및 담당 부서</h2>
          <p>
            개인정보 처리 및 보안과 관련한 문의사항은 아래 연락처로 문의해 주시기 바랍니다.
          </p>
          <ul>
            <li><strong>책임자:</strong> 도심복합개발 포털 개인정보 관리팀</li>
            <li><strong>이메일:</strong> contact@urban-complex-guide.com</li>
          </ul>
        </div>
      </section>
      ${createAdSenseSlot('Privacy 페이지 하단 슬롯')}
    `;
  }

  // ==========================================
  // 8. 애드센스 필수 페이지: Terms of Service (이용약관 및 면책조항)
  // ==========================================
  function renderTermsView() {
    elements.mainContainer.innerHTML = `
      <section class="policy-container">
        <header class="policy-header">
          <h1 class="policy-title">Terms of Service · 이용약관 및 법적 면책조항</h1>
          <p class="policy-date">시행일자: 2026년 8월 1일</p>
        </header>

        <div class="policy-content">
          <h2>1. 목적</h2>
          <p>
            본 약관은 도심복합개발 지식 포털이 제공하는 모든 정보 서비스의 이용 조건 및 절차, 이용자와 사이트 간의 권리, 의무 및 책임사항을 규정함을 목적으로 합니다.
          </p>

          <h2>2. 법적 면책조항 (Disclaimer - 중요)</h2>
          <div class="policy-callout">
            <strong>⚠️ 투자 및 법률 자문 면책 고지</strong><br>
            본 사이트에서 제공하는 모든 연재 아티클, 법률 분석, 계산 예시, 후보지 정보 등은 부동산 제도에 대한 <strong>일반적인 정보 제공 및 학술적 연구 목적</strong>으로 작성된 것입니다. 이는 특정 부동산 매매 권유, 투자 자문, 공식 법률 또는 세무 감정 의견을 대신할 수 없습니다. 모든 최종 의사결정은 관할 지자체 고시 및 전문 세무사·변호사의 자문을 받으시기 바랍니다.
          </div>

          <h2>3. 저작권 및 지식재산권</h2>
          <p>
            본 사이트에 게재된 텍스트, HTML 카드뉴스, 그래픽, 지식 그래프 시각화 엔진의 모든 저작권은 사이트 운영팀에 귀속됩니다. 사전 동의 없는 무단 전재, 크롤링, 상업적 재배포를 금지합니다.
          </p>

          <h2>4. 약관의 변경</h2>
          <p>
            본 약관은 관련 법령 및 서비스 운영 방침에 따라 변경될 수 있으며, 개정 시 본 페이지를 통해 공지합니다.
          </p>
        </div>
      </section>
      ${createAdSenseSlot('Terms 페이지 하단 슬롯')}
    `;
  }

  // ==========================================
  // 9. 애드센스 필수 페이지: Contact Us (문의하기)
  // ==========================================
  function renderContactView() {
    elements.mainContainer.innerHTML = `
      <section class="policy-container">
        <header class="policy-header">
          <h1 class="policy-title">Contact Us · 문의하기 & 피드백</h1>
          <p class="policy-date">도심복합개발 포털 운영팀과의 소통 채널입니다.</p>
        </header>

        <div class="policy-content">
          <p>
            콘텐츠에 대한 추가 문의, 후보지 데이터 정정 요청, 비즈니스 제휴 및 칼럼 기고 문의는 아래 양식을 작성해 주시면 담당자가 확인 후 24시간 이내에 회신해 드립니다.
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
              <textarea id="contactMsg" class="form-textarea" placeholder="자세한 문의 내용이나 피드백을 남겨주세요." required></textarea>
            </div>

            <button type="submit" class="btn-submit">문의 전송하기</button>
          </form>

          <div id="contactStatus" style="margin-top: 1rem; font-weight:700; display:none;"></div>

          <div class="policy-callout" style="margin-top: 2rem;">
            <strong>📬 공식 연락처 안내</strong>
            <ul>
              <li><strong>공식 이메일:</strong> contact@urban-complex-guide.com</li>
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
        contactStatus.style.color = 'var(--brand-primary)';
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

        // 지연 렌더링(모달 레이아웃 계산 후 캔버스 사이즈 맞춤)
        setTimeout(() => {
          if (!graphInstance) {
            graphInstance = new window.KnowledgeGraph(
              'graphCanvas',
              state.articles,
              state.categories,
              (articleId) => {
                elements.graphModal.classList.remove('active');
                if (graphInstance) graphInstance.hideTooltip();
                window.location.hash = `#article/${articleId}`;
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

    // 모달 배경 클릭 시 닫기
    if (elements.graphModal) {
      elements.graphModal.addEventListener('click', (e) => {
        if (e.target === elements.graphModal) {
          elements.graphModal.classList.remove('active');
          if (graphInstance) graphInstance.hideTooltip();
        }
      });
    }

    // 지식 그래프 컨트롤 (리셋, 줌인, 줌아웃, 검색, 카테고리 필터)
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

        // Try API
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
            window.location.hash = `#article/${data.data.id}`;
            return;
          }
        } catch (_) {}

        // Local fallback
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
        window.location.hash = `#article/${customArt.id}`;
      });
    }

    // Edit Article Modal Event Handlers
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

    // Admin Authentication Handlers
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
            if (state.currentArticle && window.location.hash.startsWith('#article/')) {
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
          alert('✅ 관리자 인증 완료!\n이제 상단 글쓰기 및 본문 수정 기능이 활성화되었습니다.');
          if (state.currentArticle && window.location.hash.startsWith('#article/')) {
            renderArticleView(state.currentArticle.id);
          }
        } else {
          if (elements.adminLoginError) elements.adminLoginError.style.display = 'block';
        }
      });
    }

    // Shortcut: Ctrl + Shift + A to open Admin Modal
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
        elements.btnAdminToggle.innerHTML = '🔓 관리자 종료';
        elements.btnAdminToggle.title = '관리자 세션 종료(로그아웃)';
        elements.btnAdminToggle.style.borderColor = '#10B981';
        elements.btnAdminToggle.style.color = '#10B981';
      } else {
        elements.btnAdminToggle.innerHTML = '🔒 관리자';
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
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('THEME', theme);
    if (elements.themeToggleBtn) {
      elements.themeToggleBtn.textContent = theme === 'light' ? '🌙 다크모드' : '☀️ 라이트모드';
    }
  }

  // Start app
  document.addEventListener('DOMContentLoaded', init);
})();
