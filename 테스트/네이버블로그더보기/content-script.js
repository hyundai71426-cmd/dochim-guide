// 네이버 블로그 카테고리 페이지에서 게시글 제목/링크를 추출해 저장소(chrome.storage.local)에 누적

function canonicalUrl(href) {
  const url = new URL(href, location.href);
  const blogId = url.searchParams.get('blogId');
  const logNo = url.searchParams.get('logNo');
  if (!blogId || !logNo) return url.href;
  return `https://blog.naver.com/PostView.naver?blogId=${blogId}&logNo=${logNo}`;
}

function extractList() {
  return [...document.querySelectorAll('a.link.pcol2')]
    .map((a) => ({
      title: a.querySelector('strong.title.ell')?.textContent.trim() ?? '',
      url: canonicalUrl(a.getAttribute('href')),
    }))
    .filter((item) => item.title && item.url);
}

function normalizePosts(posts) {
  const normalized = {};
  for (const post of Object.values(posts)) {
    const url = canonicalUrl(post.url);
    if (!normalized[url]) normalized[url] = { title: post.title, url };
  }
  return normalized;
}

function saveItems(items) {
  if (items.length === 0) return;

  chrome.storage.local.get({ posts: {} }, ({ posts }) => {
    const normalized = normalizePosts(posts);
    let changed = Object.keys(normalized).length !== Object.keys(posts).length;

    for (const item of items) {
      if (!normalized[item.url]) {
        normalized[item.url] = item;
        changed = true;
      }
    }
    if (changed) chrome.storage.local.set({ posts: normalized });
  });
}

const debouncedSave = (() => {
  let timer = null;
  return () => {
    clearTimeout(timer);
    timer = setTimeout(() => saveItems(extractList()), 300);
  };
})();

const observer = new MutationObserver(debouncedSave);
observer.observe(document.body, { childList: true, subtree: true });

['pushState', 'replaceState'].forEach((method) => {
  const original = history[method];
  history[method] = function (...args) {
    const result = original.apply(this, args);
    debouncedSave();
    return result;
  };
});
window.addEventListener('popstate', debouncedSave);

saveItems(extractList());
