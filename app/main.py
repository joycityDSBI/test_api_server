from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, engine, Base
import time
from bigquery_service import bq_service
from pydantic import BaseModel

app = FastAPI(
    title="FastAPI Server",
    description="GCP Compute Engine 기반 FastAPI 서버",
    version="1.0.0"
)

@app.on_event("startup")
def startup():
    # MySQL이 준비될 때까지 재시도
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

class QueryRequest(BaseModel):
    query: str
    max_results: int = 100

@app.post("/bigquery/query")
def run_bigquery_query(request: QueryRequest):
    """BigQuery 쿼리 실행"""
    result = bq_service.run_query(request.query, request.max_results)
    return result

@app.get("/bigquery/table/{dataset_id}/{table_id}")
def get_table_info(dataset_id: str, table_id: str):
    """테이블 정보 조회"""
    result = bq_service.get_table_schema(dataset_id, table_id)
    return result