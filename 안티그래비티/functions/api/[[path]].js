/**
 * Cloudflare Pages Functions - Catch-all Serverless API
 * Supports /api/articles, /api/articles/:id, /api/contact, /api/health
 */

import articlesData from '../../backend/data/articles.json';
import categoriesData from '../../backend/data/categories.json';

export async function onRequest(context) {
  const { request, params } = context;
  const url = new URL(request.url);
  const pathSegments = params.path || [];
  const pathname = pathSegments.join('/');

  // CORS Headers
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json; charset=utf-8'
  };

  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  // 1. Health check
  if (pathname === 'health') {
    return new Response(JSON.stringify({ status: 'ok', serverless: 'cloudflare-pages' }), { headers: corsHeaders });
  }

  // 2. GET /api/articles/meta
  if (pathname === 'articles/meta') {
    return new Response(JSON.stringify({ success: true, data: categoriesData }), { headers: corsHeaders });
  }

  // 3. GET /api/articles/:id
  if (pathSegments[0] === 'articles' && pathSegments.length === 2) {
    const id = pathSegments[1];
    const article = articlesData.find(a => a.id === id || a.slug === id);
    if (!article) {
      return new Response(JSON.stringify({ success: false, message: 'Article not found' }), { status: 404, headers: corsHeaders });
    }
    const related = (article.relatedPostIds || [])
      .map(relId => articlesData.find(a => a.id === relId))
      .filter(Boolean);

    return new Response(JSON.stringify({ success: true, data: { ...article, relatedArticles: related } }), { headers: corsHeaders });
  }

  // 4. GET /api/articles (with query filter)
  if (pathname === 'articles' || pathname === '') {
    const category = url.searchParams.get('category');
    const persona = url.searchParams.get('persona');
    const q = url.searchParams.get('q');

    let list = [...articlesData];

    if (category && category !== 'all') {
      list = list.filter(a => a.categoryId === category);
    }
    if (persona && persona !== '전체') {
      list = list.filter(a => a.targetAudience && a.targetAudience.includes(persona));
    }
    if (q) {
      const query = q.toLowerCase().trim();
      list = list.filter(a =>
        a.title.toLowerCase().includes(query) ||
        a.summary.toLowerCase().includes(query) ||
        (a.easySummary && a.easySummary.toLowerCase().includes(query)) ||
        (a.tags && a.tags.some(t => t.toLowerCase().includes(query)))
      );
    }

    return new Response(JSON.stringify({ success: true, total: list.length, data: list }), { headers: corsHeaders });
  }

  // 5. POST /api/contact
  if (pathname === 'contact' && request.method === 'POST') {
    try {
      const body = await request.json();
      const { name, email, subject, message } = body;
      if (!name || !email || !message) {
        return new Response(JSON.stringify({ success: false, message: '모든 필수 항목을 입력해 주세요.' }), { status: 400, headers: corsHeaders });
      }
      return new Response(JSON.stringify({ success: true, message: '문의가 성공적으로 접수되었습니다.' }), { headers: corsHeaders });
    } catch (e) {
      return new Response(JSON.stringify({ success: false, message: '잘못된 요청 형식입니다.' }), { status: 400, headers: corsHeaders });
    }
  }

  return new Response(JSON.stringify({ success: false, message: 'Endpoint not found' }), { status: 404, headers: corsHeaders });
}
