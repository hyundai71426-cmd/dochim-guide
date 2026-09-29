import json
import os
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_articles_path = os.path.join(root_dir, 'backend', 'data', 'articles.json')
frontend_articles_data_path = os.path.join(root_dir, 'articles_data.js')

# 1. backend/data/articles.json 업데이트
with open(backend_articles_path, 'r', encoding='utf-8') as f:
    articles = json.load(f)

for art in articles:
    order_num = f"{art['order']:02d}"
    art['thumbnail'] = f"/images/thumbnails/thumb_post{order_num}.png"

with open(backend_articles_path, 'w', encoding='utf-8') as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"✅ backend/data/articles.json 썸네일 필드 주입 완료 ({len(articles)}개)")

# 2. articles_data.js (루트) 업데이트
js_content = f"// Auto-generated 50 Deep Masterpiece Articles Data with Thumbnails\nconst ARTICLES_DATA = {json.dumps(articles, ensure_ascii=False, indent=2)};\n\nif (typeof module !== 'undefined' && module.exports) {{\n  module.exports = ARTICLES_DATA;\n}}\n"

with open(frontend_articles_data_path, 'w', encoding='utf-8') as f:
    f.write(js_content)

print(f"✅ articles_data.js 썸네일 데이터 업데이트 완료")

# 3. frontend/js/articles_data.js 업데이트
frontend_js_articles_data_path = os.path.join(root_dir, 'frontend', 'js', 'articles_data.js')
backend_categories_path = os.path.join(root_dir, 'backend', 'data', 'categories.json')
with open(backend_categories_path, 'r', encoding='utf-8') as f:
    categories_data = json.load(f)

frontend_bundle_js = f"""window.CATEGORIES_DB = {json.dumps(categories_data.get('categories', []), ensure_ascii=False, indent=2)};
window.TARGET_AUDIENCES_DB = {json.dumps(categories_data.get('targetAudiences', []), ensure_ascii=False, indent=2)};
window.ARTICLES_DB = {json.dumps(articles, ensure_ascii=False, indent=2)};
"""

with open(frontend_js_articles_data_path, 'w', encoding='utf-8') as f:
    f.write(frontend_bundle_js)

print(f"✅ frontend/js/articles_data.js 썸네일 데이터 업데이트 완료")
