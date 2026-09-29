import os
import sys
import json
from PIL import Image

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_thumb_dir = os.path.join(root_dir, 'frontend', 'images', 'thumbnails')
root_thumb_dir = os.path.join(root_dir, 'images', 'thumbnails')

os.makedirs(frontend_thumb_dir, exist_ok=True)
os.makedirs(root_thumb_dir, exist_ok=True)

backend_articles_path = os.path.join(root_dir, 'backend', 'data', 'articles.json')
frontend_js_articles_data_path = os.path.join(root_dir, 'frontend', 'js', 'articles_data.js')
root_articles_data_path = os.path.join(root_dir, 'articles_data.js')
backend_categories_path = os.path.join(root_dir, 'backend', 'data', 'categories.json')

with open(backend_articles_path, 'r', encoding='utf-8') as f:
    articles = json.load(f)

print(f"==================================================")
print(f"🖼️  썸네일 모바일/웹 초경량 고화질 WebP 리사이징 (800x800)")
print(f"총 아티클 수: {len(articles)}편")
print(f"==================================================\n")

converted_count = 0

for art in articles:
    order_num = f"{art['order']:02d}"
    png_name = f"thumb_post{order_num}.png"
    webp_name = f"thumb_post{order_num}.webp"
    
    png_path = os.path.join(frontend_thumb_dir, png_name)
    webp_frontend_path = os.path.join(frontend_thumb_dir, webp_name)
    webp_root_path = os.path.join(root_thumb_dir, webp_name)
    
    # 1. 800x800 리사이즈 및 WebP 고품질 변환
    if os.path.exists(png_path):
        with Image.open(png_path) as img:
            # RGB 변환
            rgb_img = img.convert('RGB')
            # 800x800 고품질 리샘플링 (모바일 2.5x 레티나 최적)
            resized_img = rgb_img.resize((800, 800), Image.Resampling.LANCZOS)
            # quality=88 로 압축 최적화 (텍스트 가독성 완벽 유지 + 30~50KB 용량)
            resized_img.save(webp_frontend_path, 'WEBP', quality=88, method=6)
            resized_img.save(webp_root_path, 'WEBP', quality=88, method=6)
            
        png_size = os.path.getsize(png_path) / 1024
        webp_size = os.path.getsize(webp_frontend_path) / 1024
        print(f"  [{order_num}/50] 800x800 WebP: {webp_name} ({png_size:.0f}KB -> {webp_size:.0f}KB, {((png_size-webp_size)/png_size*100):.1f}% 절감)")
        converted_count += 1
    else:
        print(f"  [WARN] PNG 파일을 찾을 수 없음: {png_path}")

    # 2. 고품질 SEO 맞춤형 알트태그(ALT) 생성
    alt_text = f"VOL.{order_num} {art['title']} - {art.get('category', '')} | 도심복합개발 백과사전 썸네일 인포그래픽"
    art['thumbnail'] = f"/images/thumbnails/{webp_name}"
    art['alt'] = alt_text

# 3. 데이터베이스 저장
with open(backend_articles_path, 'w', encoding='utf-8') as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

js_content = f"// Auto-generated 50 Deep Masterpiece Articles Data with WebP Thumbnails & ALT Tags\nconst ARTICLES_DATA = {json.dumps(articles, ensure_ascii=False, indent=2)};\n\nif (typeof module !== 'undefined' && module.exports) {{\n  module.exports = ARTICLES_DATA;\n}}\n"
with open(root_articles_data_path, 'w', encoding='utf-8') as f:
    f.write(js_content)

with open(backend_categories_path, 'r', encoding='utf-8') as f:
    categories_data = json.load(f)

frontend_bundle_js = f"""window.CATEGORIES_DB = {json.dumps(categories_data.get('categories', []), ensure_ascii=False, indent=2)};
window.TARGET_AUDIENCES_DB = {json.dumps(categories_data.get('targetAudiences', []), ensure_ascii=False, indent=2)};
window.ARTICLES_DB = {json.dumps(articles, ensure_ascii=False, indent=2)};
"""
with open(frontend_js_articles_data_path, 'w', encoding='utf-8') as f:
    f.write(frontend_bundle_js)

root_js_dir = os.path.join(root_dir, 'js')
os.makedirs(root_js_dir, exist_ok=True)
with open(os.path.join(root_js_dir, 'articles_data.js'), 'w', encoding='utf-8') as f:
    f.write(frontend_bundle_js)

print(f"\n🎉 800x800 초경량 WebP 변환 및 최적화 완료 ({converted_count}개 파일)!")
