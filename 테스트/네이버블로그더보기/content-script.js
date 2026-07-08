// 네이버 블로그 카테고리 페이지에서 게시글 제목/링크를 추출해 저장소(chrome.storage.local)에 누적

function extractList() {
  return [...document.querySelectorAll('a.link.pcol2')]
    .map((a) => ({
      title: a.querySelector('strong.title.ell')?.textContent.trim() ?? '',
      url: new URL(a.getAttribute('href'), location.href).href,
    }))
    .filter((item) => item.title && item.url);
}

function saveItems(items) {
  if (items.length === 0) return;

  chrome.storage.local.get({ posts: {} }, ({ posts }) => {
    let changed = false;
    for (const item of items) {
      if (!posts[item.url]) {
        posts[item.url] = item;
        changed = true;
      }
    }
    if (changed) chrome.storage.local.set({ posts });
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
