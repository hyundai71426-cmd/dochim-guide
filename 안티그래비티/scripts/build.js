const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const articlesPath = path.join(rootDir, 'backend', 'data', 'articles.json');
const indexPath = path.join(rootDir, 'frontend', 'index.html');
const frontendDir = path.join(rootDir, 'frontend');

const articles = JSON.parse(fs.readFileSync(articlesPath, 'utf8'));
const indexHtml = fs.readFileSync(indexPath, 'utf8');

const baseUrl = 'https://dochim.kr';
const today = new Date().toISOString().split('T')[0];

console.log('Starting SSG build for Cloudflare Pages...');

// 1. Generate Static HTML files
articles.forEach(article => {
  const dirPath = path.join(frontendDir, 'article', article.slug);
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }

  // Generate plain text content for crawlers
  const plainText = article.content.replace(/[`*#>]/g, '').substring(0, 300) + '...';
  const desc = article.cardNews && article.cardNews[0] ? article.cardNews[0].desc : plainText;

  let newHtml = indexHtml;

  // Replace Meta Tags
  newHtml = newHtml.replace(/<title>.*?<\/title>/, `<title>${article.title} - 도심복합개발 백과사전</title>`);
  newHtml = newHtml.replace(/<meta name="title" content=".*?">/, `<meta name="title" content="${article.title}">`);
  newHtml = newHtml.replace(/<meta name="description" content=".*?">/, `<meta name="description" content="${desc}">`);
  
  newHtml = newHtml.replace(/<meta property="og:title" content=".*?">/, `<meta property="og:title" content="${article.title}">`);
  newHtml = newHtml.replace(/<meta property="og:description" content=".*?">/, `<meta property="og:description" content="${desc}">`);
  newHtml = newHtml.replace(/<meta property="og:url" content=".*?">/, `<meta property="og:url" content="${baseUrl}/article/${article.slug}">`);
  
  newHtml = newHtml.replace(/<meta property="twitter:title" content=".*?">/, `<meta property="twitter:title" content="${article.title}">`);
  newHtml = newHtml.replace(/<meta property="twitter:description" content=".*?">/, `<meta property="twitter:description" content="${desc}">`);

  // Inject Crawler HTML into <main id="app">
  const crawlerHtml = `
    <article style="padding: 2rem;">
      <h1>${article.title}</h1>
      <p>${desc}</p>
      <div>${article.content.replace(/\n/g, '<br>')}</div>
    </article>
  `;
  newHtml = newHtml.replace(/<main id="app".*?>/, `<main id="app" class="pb-24 max-w-4xl mx-auto mt-20 relative">\n${crawlerHtml}`);

  fs.writeFileSync(path.join(dirPath, 'index.html'), newHtml, 'utf8');
});

// 2. Generate Sitemap
let sitemapXml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n`;
sitemapXml += `  <url>\n    <loc>${baseUrl}/</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>\n`;

articles.forEach(art => {
  sitemapXml += `  <url>\n    <loc>${baseUrl}/article/${art.slug}</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.9</priority>\n  </url>\n`;
});
sitemapXml += `</urlset>`;
fs.writeFileSync(path.join(frontendDir, 'sitemap.xml'), sitemapXml, 'utf8');

// 3. Generate Robots.txt
const robotsTxt = `User-agent: *\nAllow: /\nDisallow: /backend/\n\nSitemap: ${baseUrl}/sitemap.xml\n`;
fs.writeFileSync(path.join(frontendDir, 'robots.txt'), robotsTxt, 'utf8');

console.log(`✅ SSG Build Complete! Generated ${articles.length} HTML files, sitemap.xml, robots.txt`);
