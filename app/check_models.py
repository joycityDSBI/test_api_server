from google.cloud import aiplatform

def list_vertex_models():
    aiplatform.init(project="datahub-478802", location="us-central1")
    
    print("🔍 Vertex AI Model Garden (Foundation Models):")
    # Vertex AI의 모델 리스트를 가져오는 로직은 SDK 버전마다 다르지만,
    # 가장 확실한 건 'gemini-1.5-flash'를 직접 호출해보는 것입니다.
    
    try:
        from langchain_google_vertexai import ChatVertexAI
        
        # 테스트할 모델 리스트
        candidates = [
            "gemini-1.5-flash",
            "gemini-2.5-flash",
            "gemini-3.0-flash",
            "gemini-3-flash-preview"
        ]
        
        for model in candidates:
            print(f"\nTesting connection to: {model} ...")
            try:
                llm = ChatVertexAI(model_name=model)
                res = llm.invoke("Hi")
                print(f"✅ {model}: Available! (Response: {res.content})")
            except Exception as e:
                print(f"❌ {model}: Not Available ({str(e)[:50]}...)")
                
    except Exception as e:
        print(e)

if __name__ == "__main__":
    list_vertex_models()