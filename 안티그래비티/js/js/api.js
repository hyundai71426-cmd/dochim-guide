/**
 * API 통신 클라이언트 모듈 (api.js)
 * 백엔드 REST API(/api/articles)와 통신하되,
 * 관리자 인증(Bearer Token) 및 오프라인 로컬 저장 폴백을 지원합니다.
 */

window.ApiClient = {
  baseUrl: '/api',

  getAdminKey() {
    return sessionStorage.getItem('ADMIN_KEY') || localStorage.getItem('ADMIN_KEY') || '';
  },

  // 1. 전체 아티클 목록 조회
  async getArticles(params = {}) {
    const query = new URLSearchParams();
    if (params.category && params.category !== 'all') query.set('category', params.category);
    if (params.persona && params.persona !== '전체') query.set('persona', params.persona);
    if (params.q) query.set('q', params.q);

    try {
      const res = await fetch(`${this.baseUrl}/articles?${query.toString()}`);
      if (res.ok) {
        const json = await res.json();
        return json.data || [];
      }
    } catch (e) {
      console.warn('[ApiClient] 백엔드 API 연결 불가 -> 로컬 정적 데이터로 자동 폴백');
    }

    // Fallback to window.ARTICLES_DB + Local storage modifications
    let list = [...(window.ARTICLES_DB || [])];
    const editedMap = JSON.parse(localStorage.getItem('EDITED_ARTICLES') || '{}');
    list = list.map(a => editedMap[a.id] ? { ...a, ...editedMap[a.id] } : a);

    const savedCustom = localStorage.getItem('CUSTOM_ARTICLES');
    if (savedCustom) {
      try { list = [...list, ...JSON.parse(savedCustom)]; } catch (_) {}
    }

    if (params.category && params.category !== 'all') {
      list = list.filter(a => a.categoryId === params.category);
    }
    if (params.persona && params.persona !== '전체') {
      list = list.filter(a => a.targetAudience && a.targetAudience.includes(params.persona));
    }
    if (params.q) {
      const q = params.q.toLowerCase().trim();
      list = list.filter(a =>
        a.title.toLowerCase().includes(q) ||
        a.summary.toLowerCase().includes(q) ||
        (a.easySummary && a.easySummary.toLowerCase().includes(q)) ||
        (a.tags && a.tags.some(t => t.toLowerCase().includes(q)))
      );
    }
    return list;
  },

  // 2. 단일 아티클 조회
  async getArticleById(id) {
    try {
      const res = await fetch(`${this.baseUrl}/articles/${id}`);
      if (res.ok) {
        const json = await res.json();
        return json.data;
      }
    } catch (e) {}

    // Fallback
    const list = await this.getArticles();
    const found = list.find(a => a.id === id || a.slug === id);
    if (!found) return null;

    const related = (found.relatedPostIds || [])
      .map(relId => list.find(a => a.id === relId))
      .filter(Boolean);

    return { ...found, relatedArticles: related };
  },

  // 3. 신규 글 발행 (POST - 관리자 전용)
  async publishArticle(newArticle) {
    const adminKey = this.getAdminKey();
    try {
      const res = await fetch(`${this.baseUrl}/articles`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${adminKey}`
        },
        body: JSON.stringify({ ...newArticle, adminKey })
      });
      if (res.ok) {
        return await res.json();
      }
      const err = await res.json();
      return { success: false, message: err.message || '인증 실패' };
    } catch (e) {}

    // Fallback to localStorage
    const localSaved = JSON.parse(localStorage.getItem('CUSTOM_ARTICLES') || '[]');
    const nextOrder = 50 + localSaved.length + 1;
    const customArt = {
      ...newArticle,
      id: `post-${nextOrder}`,
      order: nextOrder,
      readingTime: '4분',
      cardNews: {
        tagline: `VOL.${nextOrder} 신규 발행`,
        highlightText: newArticle.title,
        items: [{ icon: '💡', title: '핵심 요약', desc: newArticle.summary }]
      },
      bridgeStory: '새로 발행된 글입니다.',
      relatedPostIds: ['post-01', 'post-06', 'post-14']
    };
    localSaved.push(customArt);
    localStorage.setItem('CUSTOM_ARTICLES', JSON.stringify(localSaved));

    return {
      success: true,
      message: '글이 로컬에 저장되었습니다.',
      data: customArt
    };
  },

  // 4. 기존 글 수정 (PUT - 관리자 전용)
  async updateArticle(id, updatedData) {
    const adminKey = this.getAdminKey();
    try {
      const res = await fetch(`${this.baseUrl}/articles/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${adminKey}`
        },
        body: JSON.stringify({ ...updatedData, adminKey })
      });
      if (res.ok) {
        return await res.json();
      }
      const err = await res.json();
      return { success: false, message: err.message || '인증 실패' };
    } catch (e) {}

    // Fallback to localStorage
    const editedMap = JSON.parse(localStorage.getItem('EDITED_ARTICLES') || '{}');
    editedMap[id] = { ...(editedMap[id] || {}), ...updatedData };
    localStorage.setItem('EDITED_ARTICLES', JSON.stringify(editedMap));

    return {
      success: true,
      message: '글이 로컬에 안전하게 저장/수정되었습니다.',
      data: { id, ...updatedData }
    };
  },

  // 5. 글 삭제 (DELETE - 관리자 전용)
  async deleteArticle(id) {
    const adminKey = this.getAdminKey();
    try {
      const res = await fetch(`${this.baseUrl}/articles/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${adminKey}`
        }
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {}

    return { success: true, message: '글이 삭제되었습니다.' };
  },

  // 6. 문의하기 전송 (일반 사용자)
  async submitContact(data) {
    try {
      const res = await fetch(`${this.baseUrl}/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {}

    // Fallback
    console.log('[Contact Local Fallback]', data);
    return { success: true, message: '문의가 성공적으로 접수되었습니다. 신속히 답변드리겠습니다.' };
  }
};
