// 사이드패널: 저장소(chrome.storage.local)에 누적된 제목/링크 목록을 렌더링

const listEl = document.getElementById('list');
const emptyStateEl = document.getElementById('empty-state');

function logNoOf(url) {
  return Number(url.match(/logNo=(\d+)/)?.[1] ?? 0);
}

function render(posts) {
  const items = Object.values(posts).sort((a, b) => logNoOf(b.url) - logNoOf(a.url));

  if (items.length === 0) {
    listEl.innerHTML = '';
    emptyStateEl.textContent = '아직 저장된 글이 없습니다. 네이버 블로그 카테고리 목록을 열어보세요.';
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

    const deleteBtn = document.createElement('button');
    deleteBtn.textContent = '✕';
    deleteBtn.className = 'delete';
    deleteBtn.title = '목록에서 삭제';
    deleteBtn.addEventListener('click', () => deleteItem(item.url));

    li.appendChild(titleSpan);
    li.appendChild(copyBtn);
    li.appendChild(deleteBtn);
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

function isExtensionContextValid() {
  return typeof chrome !== 'undefined' && !!chrome.runtime?.id;
}

function showContextInvalidatedNotice() {
  listEl.innerHTML = '';
  emptyStateEl.textContent = '확장 프로그램이 업데이트됐습니다. 이 패널을 닫았다가 다시 열어주세요.';
  emptyStateEl.style.display = 'block';
}

function deleteItem(url) {
  if (!isExtensionContextValid()) {
    showContextInvalidatedNotice();
    return;
  }
  chrome.storage.local.get({ posts: {} }, ({ posts }) => {
    if (!isExtensionContextValid()) {
      showContextInvalidatedNotice();
      return;
    }
    delete posts[url];
    chrome.storage.local.set({ posts });
  });
}

if (!isExtensionContextValid()) {
  showContextInvalidatedNotice();
} else {
  chrome.storage.local.get({ posts: {} }, ({ posts }) => render(posts));

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'local' || !changes.posts) return;
    render(changes.posts.newValue ?? {});
  });
}
