# 네이버 블로그 카테고리 제목 목록 사이드패널 확장 프로그램 - 설계

## 배경 및 목적

네이버 블로그 포스팅 중 "함께보면 좋은 글" 링크를 걸 때, 다른 탭이나 창을 오가며 URL을 찾는 번거로움을 줄인다. 크롬 사이드패널에서 현재 보고 있는 블로그 카테고리의 게시글 제목 목록을 보여주고, 각 제목 옆 복사 버튼으로 해당 게시글 URL을 즉시 클립보드에 복사할 수 있게 한다.

## 요구사항 요약

- 사이드패널에 보여줄 목록은 사용자가 현재 보고 있는 네이버 블로그 카테고리 페이지를 파싱해서 가져온다 (별도 API 호출이나 블로그 ID 입력 없음).
- 카테고리나 페이지를 이동하면 목록이 자동으로 갱신된다.
- 복사 버튼을 누르면 게시글의 순수 URL만 클립보드에 복사된다 (제목 텍스트 없이).

## 아키텍처

```
[블로그 탭]
  outer frame (blog.naver.com/블로그ID)
    └ iframe#mainFrame (PostList.naver?blogId=...)
         └ content-script.js 주입 (all_frames: true)
                │ (제목/링크 추출, MutationObserver로 변화 감지)
                ▼ chrome.runtime.sendMessage
[사이드패널] (side_panel.html/js)
   메시지 수신 → 목록 렌더링 (제목 + 복사 버튼)
```

네이버 블로그는 최상위 페이지(outer frame)가 `iframe#mainFrame`을 통해 실제 콘텐츠(카테고리/게시글 목록)를 로드하는 구조다. 콘텐츠 스크립트는 `all_frames: true`로 주입되어 outer frame과 inner iframe 양쪽에서 실행되지만, 실제 게시글 목록(`a.link.pcol2`)이 존재하는 프레임에서만 동작한다.

## 구성 요소

| 파일 | 역할 |
|---|---|
| `manifest.json` | Manifest V3. `sidePanel`, `scripting`, `tabs` 권한 + `host_permissions: ["https://blog.naver.com/*"]` |
| `content-script.js` | 게시글 목록 추출, DOM 변화/URL 변화 감지 시 재추출 후 메시지 전송 |
| `background.js` | 서비스워커. 액션 아이콘 클릭 시 사이드패널을 열도록 `chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })` 설정 |
| `sidepanel.html` / `sidepanel.js` | 메시지 수신, 목록 렌더링, 복사 버튼 처리 |

## 실제 DOM 구조 (확인됨)

```html
<a href="/PostView.naver?blogId=0124sungmin&logNo=224340139211&categoryNo=11&parentCategoryNo=&from=thumbnailList" class="link pcol2">
  <div class="area_thumb">...</div>
  <div class="area_text">
    <strong class="title ell">주식 시장이 멈췄다? 당황스러운 서킷브레이커 뜻과 발동 기준 및 대응 방법</strong>
    ...
  </div>
</a>
```

- 게시글 한 건 = `a.link.pcol2`
- 제목 텍스트 = 그 안의 `strong.title.ell`
- `href`는 상대경로이므로 `new URL(href, location.href).href`로 절대 URL 변환 필요

## 데이터 흐름

**추출 로직 (content-script.js)**

```js
function extractList() {
  return [...document.querySelectorAll('a.link.pcol2')].map(a => ({
    title: a.querySelector('strong.title.ell')?.textContent.trim() ?? '',
    url: new URL(a.getAttribute('href'), location.href).href,
  })).filter(item => item.title && item.url);
}
```

**갱신 감지**

네이버 블로그는 카테고리 전환 시 iframe 전체를 새로고침하지 않고 `history.pushState`/`replaceState`로 URL만 바꾸며 내부 DOM을 교체하는 SPA 방식이다. 다음 두 가지를 함께 사용해 변화를 감지한다.

1. **MutationObserver** — 게시글 목록의 공통 조상(없으면 `document.body`)을 관찰. 자식 노드 변경 시 300ms 디바운스 후 재추출.
2. **history API 후킹** — `pushState`/`replaceState` 호출 시에도 재추출 트리거 (이중 안전장치).

추출 결과가 이전과 달라졌을 때만(첫 항목 url 비교 등) 다음 메시지를 전송한다.

```js
chrome.runtime.sendMessage({ type: 'BLOG_LIST_UPDATE', items });
```

**사이드패널 수신 & 렌더링**

```js
chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.type === 'BLOG_LIST_UPDATE') renderList(msg.items, sender.tab?.id);
});
```

- 각 항목: 제목 텍스트 + 복사 버튼
- 복사 버튼 클릭 → `navigator.clipboard.writeText(url)` → 버튼 텍스트를 잠깐 "복사됨"으로 표시 후 원복

**활성 탭 필터링**

사이드패널은 창 단위로 공유되므로, 다른 탭에서 온 메시지가 섞이지 않도록 `sender.tab.id`가 현재 활성 탭 id와 일치할 때만 반영한다. 탭 전환 시 `chrome.tabs.onActivated`를 감지해 새 활성 탭에 목록 재전송을 요청한다.

## 예외 상황

- 네이버 블로그가 아니거나 목록이 없는 페이지: 사이드패널에 "네이버 블로그 카테고리 페이지를 열어주세요" 안내 표시
- 게시글이 없는 빈 카테고리: "게시글이 없습니다" 표시
- 클립보드 복사 실패: 복사 버튼에 실패 표시, 콘솔 에러 로그

## 테스트 방법

1. 크롬 `chrome://extensions`에서 압축해제된 확장 프로그램으로 로드
2. 실제 네이버 블로그 카테고리 페이지 접속 → 사이드패널 열기 → 제목 목록 확인
3. 복사 버튼 클릭 → 클립보드에 정확한 URL이 담기는지 붙여넣기로 확인
4. 다른 카테고리 클릭 → 목록이 자동으로 갱신되는지 확인
5. 다른 탭으로 전환 → 사이드패널이 그 탭 기준으로 갱신되는지 확인
