// 네이버 블로그 카테고리 페이지에서 게시글 제목/링크를 추출해 사이드패널로 전송

let lastSentKey = null;
let currentCategoryKey = null;
const itemsMap = new Map();

function extractList() {
  return [...document.querySelectorAll('a.link.pcol2')]
    .map((a) => ({
      title: a.querySelector('strong.title.ell')?.textContent.trim() ?? '',
      url: new URL(a.getAttribute('href'), location.href).href,
    }))
    .filter((item) => item.title && item.url);
}

function listKey(items) {
  return items.map((i) => i.url).join('|');
}

function getCategoryKey() {
  const params = new URLSearchParams(location.search);
  return `${params.get('blogId') ?? ''}::${params.get('categoryNo') ?? ''}::${location.pathname}`;
}

function sendListIfChanged() {
  // 네이버 블로그 목록은 가상 스크롤이라 화면에 보이는 글만 DOM에 존재한다.
  // 그래서 지금 보이는 것만 쓰지 않고, 한 번이라도 보인 글은 누적해서 기억한다.
  const categoryKey = getCategoryKey();
  if (categoryKey !== currentCategoryKey) {
    currentCategoryKey = categoryKey;
    itemsMap.clear();
  }

  for (const item of extractList()) {
    itemsMap.set(item.url, item);
  }

  if (itemsMap.size === 0) return;

  const items = [...itemsMap.values()];
  const key = listKey(items);
  if (key === lastSentKey) return;

  lastSentKey = key;
  chrome.runtime.sendMessage({ type: 'BLOG_LIST_UPDATE', items });
}

const debouncedSend = (() => {
  let timer = null;
  return () => {
    clearTimeout(timer);
    timer = setTimeout(sendListIfChanged, 300);
  };
})();

const observer = new MutationObserver(debouncedSend);
observer.observe(document.body, { childList: true, subtree: true });

['pushState', 'replaceState'].forEach((method) => {
  const original = history[method];
  history[method] = function (...args) {
    const result = original.apply(this, args);
    debouncedSend();
    return result;
  };
});
window.addEventListener('popstate', debouncedSend);

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'REQUEST_LIST') {
    lastSentKey = null;
    sendListIfChanged();
  }
});

sendListIfChanged();
