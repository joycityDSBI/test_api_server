# check_models.py
import os
import google.generativeai as genai
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ Error: GOOGLE_API_KEY가 환경변수에 없습니다.")
else:
    print(f"🔑 API Key 확인됨: {api_key[:5]}...")
    
    try:
        genai.configure(api_key=api_key)
        print("\n🔍 사용 가능한 모델 목록 (generateContent 지원):")
        print("-" * 60)
        
        found = False
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"✅ {m.name}")  # 이 이름을 복사해서 써야 합니다!
                found = True
        
        if not found:
            print("⚠️ 사용 가능한 텍스트 생성 모델이 없습니다.")
            
    except Exception as e:
        print(f"\n❌ API 호출 에러: {e}")