from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, engine, Base
from pydantic import BaseModel
import time
import os
from app.knowledge_graph.llm_logic import load_and_merge_yamls, parse_schema_to_prompt, get_gemini_chain

app = FastAPI(
    title="FastAPI Server",
    description="GCP Compute Engine 기반 FastAPI 서버",
    version="1.0.0"
)

@app.on_event("startup")
def startup():
    max_retries = 30
    retry_interval = 2
    
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            print("✅ Database connection successful!")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⏳ Waiting for database... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_interval)
            else:
                print(f"❌ Failed to connect to database after {max_retries} attempts")
                raise e

@app.get("/")
def root():
    return {"message": "FastAPI 서버 정상 동작 중", "status": "ok"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}

@app.get("/integer/{value}")
def read_item(value: int):
    return {"input": value, "result": value / 2}

# BigQuery 엔드포인트
from bigquery_service import bq_service

class QueryRequest(BaseModel):
    query: str
    max_results: int = 100

@app.post("/bigquery/query")
def run_bigquery_query(request: QueryRequest):
    """BigQuery 쿼리 실행"""
    try:
        result = bq_service.run_query(request.query, request.max_results)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

@app.get("/bigquery/table/{dataset_id}/{table_id}")
def get_table_info(dataset_id: str, table_id: str):
    """테이블 정보 조회"""
    try:
        result = bq_service.get_table_schema(dataset_id, table_id)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

# 자연어 질의 변환 엔드포인트
class NLQueryRequest(BaseModel):
    query: str
    execute: bool = True

# --- [초기화] 서버 시작 시 한 번만 실행 ---
# 1. YAML 로드
SCHEMA_DIR = "./knowledge_graph"  # YAML 파일들이 있는 폴더 경로
full_data = load_and_merge_yamls(SCHEMA_DIR)

# 2. 프롬프트 컨텍스트 생성 (메모리에 캐싱)
context_string = parse_schema_to_prompt(full_data)
# 3. Gemini 체인 생성
try:
    # API 키가 환경변수에 없다면 여기서 설정하거나 에러 발생
    # os.environ["GOOGLE_API_KEY"] = "your_api_key_here" 
    chain = get_gemini_chain(model_name="gemini-1.5-pro")
    print("✅ Gemini Chain initialized successfully.")
except Exception as e:
    print(f"❌ Failed to initialize Gemini Chain: {e}")
    chain = None

# 요청 데이터 모델
class QueryRequest(BaseModel):
    query: str
    execute: bool = True

@app.post("/nlquery")
async def process_nl_query(request: QueryRequest):
    if not chain:
        raise HTTPException(status_code=500, detail="LLM Chain is not initialized.")

    try:
        # 1. LLM 실행 (context와 질문 주입)
        generated_sql = chain.invoke({
            "context": context_string,
            "question": request.query
        })
        
        # 2. 결과 전처리 (가끔 마크다운이 붙어나올 경우 제거)
        cleaned_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
        
        response_data = {
            "success": True,
            "generated_sql": cleaned_sql,
            "data": [],
            "explanation": "Generated based on YAML schema."
        }

        # 3. (옵션) 실제 DB 조회 로직
        if request.execute:
            # 여기에 실제 BigQuery 연동 코드를 넣으시면 됩니다.
            # 지금은 테스트용 더미 데이터 반환
            response_data["data"] = [
                {"game": "Dummy Game", "login_count": 1234, "date": "2024-05-20"}
            ]

        return response_data

    except Exception as e:
        return {"success": False, "error": str(e)}