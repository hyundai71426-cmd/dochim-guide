const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');

const dataFilePath = path.join(__dirname, '../data/articles.json');
const categoriesFilePath = path.join(__dirname, '../data/categories.json');

// Helper to read articles
function getArticles() {
  try {
    const raw = fs.readFileSync(dataFilePath, 'utf8');
    return JSON.parse(raw);
  } catch (e) {
    console.error('Error reading articles.json:', e);
    return [];
  }
}

// Admin Password (환경변수 또는 기본 관리자 암호)
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'urban2026!';

function requireAdmin(req, res, next) {
  const authHeader = req.headers['authorization'] || req.headers['x-admin-key'];
  const bodyKey = req.body && req.body.adminKey;
  
  if (
    authHeader === `Bearer ${ADMIN_PASSWORD}` || 
    authHeader === ADMIN_PASSWORD || 
    bodyKey === ADMIN_PASSWORD
  ) {
    return next();
  }
  
  return res.status(401).json({
    success: false,
    message: '관리자 인증이 필요합니다. (비밀번호 불일치)'
  });
}

/**
 * GET /api/articles
 * Query params: category, persona, q (search query)
 */
router.get('/', (req, res) => {
  const { category, persona, q } = req.query;
  let articles = getArticles();

  if (category && category !== 'all') {
    articles = articles.filter(a => a.categoryId === category);
  }

  if (persona && persona !== '전체') {
    articles = articles.filter(a => a.targetAudience && a.targetAudience.includes(persona));
  }

  if (q) {
    const query = q.toLowerCase().trim();
    articles = articles.filter(a =>
      a.title.toLowerCase().includes(query) ||
      a.summary.toLowerCase().includes(query) ||
      (a.easySummary && a.easySummary.toLowerCase().includes(query)) ||
      (a.tags && a.tags.some(t => t.toLowerCase().includes(query)))
    );
  }

  res.json({
    success: true,
    total: articles.length,
    data: articles
  });
});

/**
 * GET /api/articles/meta
 * Returns categories and target audience options
 */
router.get('/meta', (req, res) => {
  const meta = getCategoriesData();
  res.json({
    success: true,
    data: meta
  });
});

/**
 * GET /api/articles/:id
 */
router.get('/:id', (req, res) => {
  const { id } = req.params;
  const articles = getArticles();
  const article = articles.find(a => a.id === id || a.slug === id);

  if (!article) {
    return res.status(404).json({
      success: false,
      message: 'Article not found'
    });
  }

  // Find related articles objects
  const related = (article.relatedPostIds || [])
    .map(relId => articles.find(a => a.id === relId))
    .filter(Boolean);

  res.json({
    success: true,
    data: {
      ...article,
      relatedArticles: related
    }
  });
});

/**
 * POST /api/articles (신규 연재 글 추가 - 관리자 전용)
 */
router.post('/', requireAdmin, (req, res) => {
  const { title, summary, category, categoryId, tags, content, relatedPostIds, targetAudience } = req.body;

  if (!title || !content) {
    return res.status(400).json({
      success: false,
      message: 'Title and content are required.'
    });
  }

  const articles = getArticles();
  const nextOrder = articles.length + 1;
  const newId = `post-${String(nextOrder).padStart(2, '0')}`;

  const newArticle = {
    id: newId,
    slug: `post-${nextOrder}-custom`,
    order: nextOrder,
    category: category || 'PART 1. 개념과 제도 도입 배경',
    categoryId: categoryId || 'part-1',
    title,
    summary: summary || title,
    easySummary: summary || title,
    targetAudience: targetAudience || ['전체', '토지소유자'],
    tags: tags || ['도심복합', '신규연재'],
    readingTime: '4분',
    cardNews: {
      tagline: `VOL.${String(nextOrder).padStart(2, '0')} 핵심 요점 브리핑`,
      highlightText: title.substring(0, 30),
      items: [
        { icon: '💡', title: '신규 분석', desc: summary ? summary.substring(0, 45) + '…' : title },
        { icon: '⏱️', title: '소요 시간', desc: '4분 완성 마스터' },
        { icon: '🚀', title: '지식망 편입', desc: `${(relatedPostIds || []).length}개의 기존 연재 글 연결` }
      ]
    },
    infographic: {
      type: 'checklist',
      title: '신규 연재 핵심 요약',
      items: [title, summary || '신규 등록된 핵심 분석']
    },
    content,
    bridgeStory: '새롭게 추가된 글과 연결된 기존 50편의 지식을 함께 읽어보세요.',
    relatedPostIds: relatedPostIds && relatedPostIds.length >= 3 ? relatedPostIds : ['post-01', 'post-06', 'post-14']
  };

  articles.push(newArticle);
  fs.writeFileSync(dataFilePath, JSON.stringify(articles, null, 2), 'utf8');

  // Sync to frontend
  try {
    const frontendDataPath = path.join(__dirname, '../../frontend/js/articles_data.js');
    const rootDataPath = path.join(__dirname, '../../articles_data.js');
    const jsContent = `window.ARTICLES_DB = ${JSON.stringify(articles, null, 2)};\n`;
    if (fs.existsSync(frontendDataPath)) fs.writeFileSync(frontendDataPath, jsContent, 'utf8');
    if (fs.existsSync(rootDataPath)) fs.writeFileSync(rootDataPath, jsContent, 'utf8');
  } catch (_) {}

  res.status(201).json({
    success: true,
    message: 'Article published successfully.',
    data: newArticle
  });
});

/**
 * PUT /api/articles/:id (기존 글 수정 - 관리자 전용)
 */
router.put('/:id', requireAdmin, (req, res) => {
  const { id } = req.params;
  const { title, summary, easySummary, category, categoryId, tags, content, qna, bridgeStory, targetAudience } = req.body;

  const articles = getArticles();
  const index = articles.findIndex(a => a.id === id);

  if (index === -1) {
    return res.status(404).json({
      success: false,
      message: 'Article not found.'
    });
  }

  const existing = articles[index];

  articles[index] = {
    ...existing,
    title: title || existing.title,
    summary: summary || existing.summary,
    easySummary: easySummary || summary || existing.easySummary,
    category: category || existing.category,
    categoryId: categoryId || existing.categoryId,
    tags: tags || existing.tags,
    content: content || existing.content,
    qna: qna || existing.qna,
    bridgeStory: bridgeStory || existing.bridgeStory,
    targetAudience: targetAudience || existing.targetAudience,
    cardNews: {
      ...existing.cardNews,
      highlightText: (title || existing.title).substring(0, 30),
      items: [
        { icon: '💡', title: '핵심 포인트', desc: (easySummary || summary || existing.summary).substring(0, 45) + '…' },
        { icon: '⏱️', title: '읽는 시간', desc: existing.readingTime || '4분' },
        { icon: '🔗', title: '연계 학습', desc: `${(existing.relatedPostIds || []).length}편의 연계 지식` }
      ]
    }
  };

  // 1. Save to backend/data/articles.json
  fs.writeFileSync(dataFilePath, JSON.stringify(articles, null, 2), 'utf8');

  // 2. Sync to frontend/js/articles_data.js for static export
  try {
    const frontendDataPath = path.join(__dirname, '../../frontend/js/articles_data.js');
    const rootDataPath = path.join(__dirname, '../../articles_data.js');
    const jsContent = `window.ARTICLES_DB = ${JSON.stringify(articles, null, 2)};\n`;
    if (fs.existsSync(frontendDataPath)) {
      fs.writeFileSync(frontendDataPath, jsContent, 'utf8');
    }
    if (fs.existsSync(rootDataPath)) {
      fs.writeFileSync(rootDataPath, jsContent, 'utf8');
    }
  } catch (err) {
    console.error('Failed to sync articles_data.js:', err);
  }

  res.json({
    success: true,
    message: '글이 성공적으로 수정되었습니다.',
    data: articles[index]
  });
});

/**
 * DELETE /api/articles/:id (글 삭제 - 관리자 전용)
 */
router.delete('/:id', requireAdmin, (req, res) => {
  const { id } = req.params;
  let articles = getArticles();
  const index = articles.findIndex(a => a.id === id);

  if (index === -1) {
    return res.status(404).json({
      success: false,
      message: 'Article not found.'
    });
  }

  const deleted = articles.splice(index, 1);
  fs.writeFileSync(dataFilePath, JSON.stringify(articles, null, 2), 'utf8');

  res.json({
    success: true,
    message: '글이 삭제되었습니다.',
    data: deleted[0]
  });
});

module.exports = router;
