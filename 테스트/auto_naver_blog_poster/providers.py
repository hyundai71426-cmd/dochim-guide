import time

import requests
from anthropic import Anthropic, APIStatusError, APIConnectionError

PROVIDER_LABELS = {
    "claude": "Claude (Anthropic)",
    "gemini": "Gemini (Google)",
    "openai": "ChatGPT (OpenAI)",
    "ollama": "Ollama (로컬)",
}

# 공급자별로 사용 가능한 모델 이름을 확인할 수 있는 공식 문서 페이지.
# 모델 목록 API가 공급자/프록시마다 응답 형식이 달라 자동 조회가 불안정하므로,
# 설정 탭에서는 모델명을 직접 입력받고 이 링크로 참고하도록 안내한다.
PROVIDER_MODEL_PAGES = {
    "claude": "https://docs.anthropic.com/en/docs/about-claude/models/overview",
    "gemini": "https://ai.google.dev/gemini-api/docs/models",
    "openai": "https://platform.openai.com/docs/models",
    "ollama": "https://ollama.com/library",
}


def chat(provider, api_key, base_url, model, prompt, max_tokens=4000, retries=3, on_retry=None):
    """공급자에 상관없이 프롬프트를 보내고 텍스트 응답을 반환. 일시적 오류는 재시도."""
    base_url = base_url.rstrip("/")
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            return _chat_once(provider, api_key, base_url, model, prompt, max_tokens)
        except (APIStatusError, APIConnectionError, requests.exceptions.RequestException) as e:
            last_err = e
            if attempt == retries:
                raise
            wait = 5 * attempt
            if on_retry:
                on_retry(f"⚠️ API 오류 발생 (시도 {attempt}/{retries}), {wait}초 후 재시도... ({e})")
            time.sleep(wait)

    raise last_err


def _chat_once(provider, api_key, base_url, model, prompt, max_tokens):
    if provider == "claude":
        client = Anthropic(base_url=base_url, api_key=api_key, timeout=110.0, max_retries=0)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in response.content if getattr(b, "type", "") == "text")

    if provider == "openai":
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        resp = requests.post(
            f"{base_url}/v1/chat/completions", headers=headers, json=body, timeout=110
        )
        resp.raise_for_status()
        data = resp.json()
        # choices가 비어 있거나 message가 없는 경우 원인을 알 수 있게 명확한 오류를 낸다.
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"OpenAI 응답에 choices 없음 (응답: {data})")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if content is None:
            finish_reason = choices[0].get("finish_reason")
            raise RuntimeError(f"OpenAI 응답에 본문 없음 (finish_reason={finish_reason}, 응답: {data})")
        return content

    if provider == "gemini":
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        resp = requests.post(
            f"{base_url}/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            json=body,
            timeout=110,
        )
        resp.raise_for_status()
        data = resp.json()
        # candidates/parts가 없으면(안전필터 차단 등) finishReason·promptFeedback을 담아 명확히 알린다.
        candidates = data.get("candidates") or []
        if not candidates:
            feedback = data.get("promptFeedback")
            raise RuntimeError(f"Gemini 응답에 candidates 없음 (promptFeedback={feedback})")
        candidate = candidates[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        texts = [p["text"] for p in parts if "text" in p]
        if not texts:
            finish_reason = candidate.get("finishReason")
            feedback = data.get("promptFeedback")
            detail = f"finishReason={finish_reason}"
            if feedback is not None:
                detail += f", promptFeedback={feedback}"
            raise RuntimeError(f"Gemini 응답에 본문 없음 ({detail})")
        # 여러 part로 나뉘어 오는 경우 text들을 합쳐서 반환한다.
        return "".join(texts)

    if provider == "ollama":
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        resp = requests.post(f"{base_url}/api/chat", json=body, timeout=110)
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    raise ValueError(f"알 수 없는 공급자: {provider}")
