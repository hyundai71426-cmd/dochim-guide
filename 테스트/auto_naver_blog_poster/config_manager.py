import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "active_provider": "claude",
    # 네이버 검색 API 키 (최상위 "naver" 섹션). 실제 키는 config.json에 사용자가 입력한다.
    "naver": {
        "search_client_id": "",
        "search_client_secret": "",
        "searchad_customer_id": "",
        "searchad_access_license": "",
        "searchad_secret_key": "",
    },
    # 클립(세로 숏폼) 영상 생성 설정 (최상위 "video" 섹션).
    "video": {
        "bgm_path": "",
        "tts_voice": "ko-KR-SunHiNeural",
    },
    "providers": {
        "claude": {
            "api_key": "",
            "base_url": "https://api.anthropic.com",
            "model": "claude-haiku-4-5-20251001",
        },
        "gemini": {
            "api_key": "",
            "base_url": "https://generativelanguage.googleapis.com",
            "model": "gemini-2.0-flash",
        },
        "openai": {
            "api_key": "",
            "base_url": "https://api.openai.com",
            "model": "gpt-4o-mini",
        },
        "ollama": {
            "api_key": "",
            "base_url": "http://localhost:11434",
            "model": "",
        },
    },
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 새 버전에서 추가된 공급자가 기존 config.json에 없을 경우 기본값으로 보강
    for provider, defaults in DEFAULT_CONFIG["providers"].items():
        cfg.setdefault("providers", {}).setdefault(provider, dict(defaults))
    cfg.setdefault("active_provider", DEFAULT_CONFIG["active_provider"])
    # 최상위 "naver" 섹션이 없으면(구버전 config.json) 기본값(빈 문자열 5개)으로 보강
    naver = cfg.setdefault("naver", {})
    for key, default_value in DEFAULT_CONFIG["naver"].items():
        naver.setdefault(key, default_value)
    # 최상위 "video" 섹션이 없으면(구버전 config.json) 기본값으로 보강
    video = cfg.setdefault("video", {})
    for key, default_value in DEFAULT_CONFIG["video"].items():
        video.setdefault(key, default_value)
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
