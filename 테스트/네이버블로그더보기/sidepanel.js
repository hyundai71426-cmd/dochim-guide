// 사이드패널: content-script가 보낸 제목/링크 목록을 받아 렌더링

const listEl = document.getElementById('list');
const emptyStateEl = document.getElementById('empty-state');

function renderList(items) {
  if (!items || items.length === 0) {
    listEl.innerHTML = '';
    emptyStateEl.textContent = '게시글이 없습니다.';
    emptyStateEl.style.display = 'block';
    return;
  }

  emptyStateEl.style.display = 'none';
  listEl.innerHTML = '';

  for (const item of items) {
    const li = document.createElement('li');

    const titleSpan = document.createElement('span');
    titleSpan.className = 'title';
    titleSpan.textContent = item.title;
    titleSpan.title = item.title;

    const copyBtn = document.createElement('button');
    copyBtn.textContent = '복사';
    copyBtn.addEventListener('click', () => copyUrl(item.url, copyBtn));

    li.appendChild(titleSpan);
    li.appendChild(copyBtn);
    listEl.appendChild(li);
  }
}

async function copyUrl(url, button) {
  const original = button.textContent;
  try {
    await navigator.clipboard.writeText(url);
    button.textContent = '복사됨';
  } catch (err) {
    console.error('클립보드 복사 실패', err);
    button.textContent = '실패';
  }
  setTimeout(() => {
    button.textContent = original;
  }, 1000);
}

async function getActiveTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab?.id;
}

chrome.runtime.onMessage.addListener(async (message, sender) => {
  if (message.type !== 'BLOG_LIST_UPDATE') return;
  const activeTabId = await getActiveTabId();
  if (sender.tab?.id !== activeTabId) return;
  renderList(message.items);
});

chrome.tabs.onActivated.addListener(({ tabId }) => {
  emptyStateEl.textContent = '네이버 블로그 카테고리 페이지를 열어주세요.';
  emptyStateEl.style.display = 'block';
  listEl.innerHTML = '';
  chrome.tabs.sendMessage(tabId, { type: 'REQUEST_LIST' }, () => {
    if (chrome.runtime.lastError) {
      // 네이버 블로그가 아닌 탭이면 content-script가 없어 에러가 나는 게 정상
    }
  });
});

(async () => {
  const activeTabId = await getActiveTabId();
  if (activeTabId != null) {
    chrome.tabs.sendMessage(activeTabId, { type: 'REQUEST_LIST' }, () => {
      if (chrome.runtime.lastError) {
        // 네이버 블로그가 아닌 탭이면 content-script가 없어 에러가 나는 게 정상
      }
    });
  }
})();
