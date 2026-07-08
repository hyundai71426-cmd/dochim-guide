# 컨텍스트 노트

## 결정 사항

- 목록 소스: 별도 API 호출 없이 사용자가 현재 보고 있는 페이지를 파싱 (사용자가 컴맹이라 설정 단계를 최소화하고 싶어함).
- 갱신 방식: 자동 갱신 (수동 새로고침 버튼 없음). 네이버 블로그가 SPA라 MutationObserver + history 후킹 이중 감지 필요.
- 복사 내용: 순수 URL만 (제목 텍스트 없이). 스마트에디터에 붙여넣으면 네이버가 자동으로 링크 미리보기 카드로 변환해줌.

## 실제 확인된 DOM 구조 (사용자가 제공한 HTML 발췌 기반)

- outer frame: `blog.naver.com/블로그ID` → `<iframe id="mainFrame" src="/PostList.naver?blogId=...">`
- 게시글 한 건: `<a class="link pcol2" href="/PostView.naver?blogId=...&logNo=...">`
- 제목: 그 안의 `<strong class="title ell">`
- href는 상대경로 → `new URL(href, location.href)`로 절대 URL 변환 필요

## 리스크/미검증 사항

- MutationObserver 관찰 대상을 `document.body` 전체로 잡음 (더 좁은 컨테이너 셀렉터를 못 구했음). 성능 이슈 있으면 추후 좁힐 것.
- 실제 브라우저 수동 테스트는 사용자가 진행 (에이전트가 직접 크롬 확장 프로그램을 로드해서 테스트할 수 없음).
