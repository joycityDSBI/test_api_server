from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, engine, Base
from pydantic import BaseModel
import time
import os

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

# Natural Language Query 엔드포인트
kg_available = os.path.exists("knowledge_graph/schema.yml")

if kg_available:
    try:
        from knowledge_graph.parser import KnowledgeGraphParser
        from knowledge_graph.query_generator import QueryGenerator
        
        kg_parser = KnowledgeGraphParser()
        query_gen = QueryGenerator(kg_parser)
        
        print("✅ Knowledge Graph initialized successfully!")
    except Exception as e:
        print(f"⚠️ Knowledge Graph initialization failed: {str(e)}")
        kg_available = False

class NLQueryRequest(BaseModel):
    query: str
    execute: bool = True

@app.post("/nlquery")
def natural_language_query(request: NLQueryRequest):
    """자연어 쿼리를 SQL로 변환하고 실행"""
    
    if not kg_available:
        return {
            "success": False,
            "error": "Knowledge Graph가 초기화되지 않았습니다."
        }
    
    try:
        # 1. 키워드 추출
        keywords = kg_parser.extract_keywords(request.query)
        
        # 2. SQL 쿼리 생성
        query_result = query_gen.generate_sql(keywords)
        
        if not query_result.get("success"):
            return query_result
        
        # 3. 쿼리 실행 (옵션)
        if request.execute:
            sql_query = query_result["sql"]
            bq_result = bq_service.run_query(sql_query, max_results=100)
            
            return {
                "success": True,
                "keywords": keywords,
                "generated_sql": sql_query,
                "explanation": query_result.get("explanation"),
                "debug": query_result.get("debug"),
                "query_result": bq_result
            }
        else:
            return {
                "success": True,
                "keywords": keywords,
                "generated_sql": query_result["sql"],
                "explanation": query_result.get("explanation"),
                "debug": query_result.get("debug")
            }
            
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": f"자연어 쿼리 처리 실패: {str(e)}",
            "traceback": traceback.format_exc()
        }