from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, engine, Base, init_db, QueryLog
from pydantic import BaseModel
import time
import os
from llm_logic import load_and_merge_yamls, parse_schema_to_prompt, get_gemini_chain, create_schema_retriever, get_relevant_context
import logging
import traceback
from google.cloud import bigquery
import re
from langchain_google_vertexai import ChatVertexAI
from langchain_core.callbacks import BaseCallbackHandler

class TokenCounterCallback(BaseCallbackHandler):
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0

    def on_llm_end(self, response, **kwargs):
        """LLM 호출이 끝날 때마다 실행되어 토큰 수를 누적합니다."""
        try:
            if response.generations and len(response.generations) > 0:
                generation = response.generations[0][0]
                
                # 디버깅 로그 (필요 시 주석 처리)
                # print(f"🔍 [DEBUG] Info: {generation.generation_info}")

                usage = None
                
                # 1. 최신 LangChain 방식 (message.usage_metadata)
                if hasattr(generation, 'message') and hasattr(generation.message, 'usage_metadata'):
                    usage = generation.message.usage_metadata
                # 2. 구버전 호환 (generation_info)
                elif hasattr(generation, 'generation_info') and generation.generation_info:
                    usage = generation.generation_info.get('usage_metadata') or generation.generation_info.get('token_usage')

                if usage:
                    # ▼▼▼ [핵심 수정] Vertex AI와 일반 키를 모두 체크합니다 ▼▼▼
                    
                    # 1. Input Token (Standard vs Vertex)
                    input_val = usage.get('input_tokens') or usage.get('prompt_token_count') or 0
                    self.input_tokens += input_val
                    
                    # 2. Output Token (Standard vs Vertex)
                    # Vertex AI는 답변 토큰을 'candidates_token_count'라고 부릅니다.
                    candidates = usage.get('output_tokens') or usage.get('candidates_token_count') or 0
                    thoughts = usage.get('thoughts_token_count') or 0
                    
                    output_val = candidates + thoughts # 답변 + 생각 = 전체 출력 비용
                    
                    self.output_tokens += output_val
                    
                    # 3. Total Token
                    total_val = usage.get('total_tokens') or usage.get('total_token_count') or 0
                    self.total_tokens += total_val
                    
        except Exception as e:
            print(f"⚠️ Token counting failed: {e}")

app = FastAPI(
    title="FastAPI Server",
    description="GCP Compute Engine 기반 FastAPI 서버",
    version="1.0.0"
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    user_id: str = "anonymous"  # [추가] 기본값은 익명
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

print("🔄 Initializing Vector Store for Schema Pruning...")
try:
    schema_retriever = create_schema_retriever(full_data)
    print("✅ Schema Retriever initialized.")
except Exception as e:
    print(f"❌ Failed to init retriever: {e}")
    schema_retriever = None

# 2. 프롬프트 컨텍스트 생성 (메모리에 캐싱)
context_string = parse_schema_to_prompt(full_data)
# 3. Gemini 체인 생성
try:
    # API 키가 환경변수에 없다면 여기서 설정하거나 에러 발생
    # os.environ["GOOGLE_API_KEY"] = "your_api_key_here" 
    chain = get_gemini_chain(model_name="gemini-2.5-flash")
    print("✅ Gemini Chain initialized successfully.")
except Exception as e:
    print(f"❌ Failed to initialize Gemini Chain: {e}")
    chain = None

# 요청 데이터 모델
class QueryRequest(BaseModel):
    query: str
    execute: bool = True
    user_id: str = "anonymous" 

@app.post("/nlquery")
async def process_nl_query(request: QueryRequest, db: Session = Depends(get_db)):

    # 0. 토큰 계산기 초기화
    token_handler = TokenCounterCallback()
    
    # 1. 체인 초기화 확인
    if not chain:
         return {"success": False, "error": "Chain not initialized"}

    try:
        logger.info(f"Received query: {request.query}") # 로그 남기기

        # ▼▼▼ [핵심 수정] 동적 Context 구성 ▼▼▼
        if schema_retriever:
            # 질문과 관련된 Top-5 테이블만 가져옴
            current_context = get_relevant_context(schema_retriever, request.query)
            logger.info("🔍 Schema Pruning applied. Relevant tables selected.")
        else:
            # 실패 시 기존 방식(전체 스키마) 사용 (fallback)
            current_context = context_string

        # 2. LLM 실행
        generated_sql = chain.invoke({
            "context": current_context,
            "question": request.query
            }, 
            config={"callbacks": [token_handler]}
        )

        logger.info("SQL Generated successfully.") # 성공 로그

        # 1. 마크다운 제거
        cleaned_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
        cleaned_sql = cleaned_sql.replace("≥", ">=").replace("≤", "<=")

        # ▼▼▼ [수정된 부분] 정규표현식으로 테이블 경로 강제 교정 ▼▼▼
        
        # 설명: 
        # 1. `? : 백틱이 있을 수도 있고 없을 수도 있음
        # 2. datahub-478802 : 프로젝트 ID
        # 3. \. : 점(.)
        # 4. (\w+) : 테이블 이름 (캡처 그룹)
        # 5. `? : 끝에 백틱이 또 있을 수도 있음 (이걸 제거하는 게 핵심)
        
        pattern = r"`?datahub-478802`?\.`?datahub`?\.`?(\w+)`?"
        
        # 매칭된 부분을 "`datahub-478802`.datahub.테이블명" 형태로 싹 바꿔치기
        cleaned_sql = re.sub(pattern, r"`datahub-478802`.datahub.\1", cleaned_sql)

        print(f"▶️ [DEBUG] Final SQL to DB: {cleaned_sql}") # 최종 쿼리 확인용

        # ▼▼▼ [로직 추가] DB에 로그 저장 ▼▼▼
        try:
            log_entry = QueryLog(
                user_id=request.user_id,
                question=request.query,
                generated_sql=cleaned_sql,
                total_tokens = token_handler.total_tokens,
                input_tokens = token_handler.input_tokens,
                output_tokens = token_handler.output_tokens
            )
            db.add(log_entry)
            db.commit() # 저장 확정
            db.refresh(log_entry) # ID 등 갱신
            print(f"✅ Query logged to DB (ID: {log_entry.id})")
        except Exception as db_e:
            print(f"⚠️ Failed to save log: {db_e}")
            # 로그 저장이 실패해도 사용자에게 응답은 가도록 pass 처리하거나 에러 로깅
        # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
        
        response_data = {
            "success": True,
            "generated_sql": cleaned_sql,
            "data": [],
            "columns": [], # 👈 빈 리스트로 초기화
            "explanation": "데이터 조회 후 분석 대기 중...",
            "tokens": {} # 토큰 사용량 정보
        }

        if request.execute:
            try:
                # ▼▼▼ [수정된 부분 시작] 실제 DB 조회 로직 ▼▼▼
                print(f"▶️ [DEBUG] Executing SQL: {cleaned_sql}")  # 1. SQL 확인
                bq_client = bigquery.Client() 
                query_job = bq_client.query(cleaned_sql)
                results = query_job.result()  # 결과 대기 (RowIterator 반환)
                
                # 3. 컬럼명 추출
                columns = [field.name for field in results.schema]
                response_data["columns"] = columns
                print(f"▶️ [DEBUG] BigQuery Columns: {columns}")

                # RowIterator를 dict list로 변환
                rows = [dict(row) for row in results]
                response_data["data"] = rows
                print(f"▶️ [DEBUG] BigQuery Rows count: {len(rows)}")

                if rows:
                # 2-1. 토큰 절약을 위해 데이터 샘플링 (최대 50건만 LLM에게 전달)
                # 데이터가 너무 많으면 "이하 생략" 처리
                    print("▶️ [DEBUG] Starting LLM Analysis...") # 👈 이 로그가 찍히는지 확인 중요
                    
                    data_preview = rows[:500] 
                    data_context = str(data_preview)
                    if len(rows) > 500:
                        data_context += f"\n... (총 {len(rows)}건 중 상위 50건만 표시)"

                    # 2-2. 해석을 위한 프롬프트 구성
                    analysis_prompt = f"""
                    당신은 데이터 분석가입니다. 아래 '사용자 질문'과 '조회된 데이터'를 보고, 
                    사용자가 이해하기 쉽게 핵심 인사이트를 요약해서 답변해주세요.
                    
                    [상황 정보]
                    - 사용자 질문: {request.query}
                    - 실행된 SQL: {cleaned_sql}
                    
                    [조회된 데이터]
                    {data_context}
                    
                    [지침]
                    1. 데이터가 비어있지 않다면, 구체적인 수치를 인용해서 답변하세요. (예: "총 135명입니다.")
                    2. 데이터가 날짜별 추세라면, 증가/감소 추세를 언급하세요.
                    3. SQL 문법 설명보다는 '데이터 결과' 자체에 집중해서 비즈니스 관점으로 답변하세요.
                    4. 한국어로 정중하게 답변하세요.
                    """

                    # 2-3. LLM 호출 (기존 chain 객체의 llm 모델을 재사용하거나, chain.invoke 사용)
                    # 만약 기존 'chain'이 PromptTemplate에 묶여 있다면, 
                    # 여기서 단순히 llm 모델 객체(ChatGoogleGenerativeAI 등)를 직접 호출하는 게 편합니다.
                    # 편의상 기존 chain.llm 을 사용한다고 가정합니다.
                        
                    logger.info("Generating explanation using LLM...")
                        
                    try:
                        # 1. 분석을 위한 LLM 모델을 별도로 정의 (확실한 호출을 위해)
                        # (SQL 생성에 썼던 모델과 같은 모델을 씁니다)
                        # API KEY는 이미 환경변수에 있다고 가정합니다.
                        analysis_llm = ChatVertexAI(model="gemini-2.5-flash", temperature=0)
                        
                        # 2. invoke 호출
                        analysis_response = analysis_llm.invoke(
                            analysis_prompt,
                            config={"callbacks": [token_handler]}
                        )
                        
                        explanation_text = analysis_response.content
                        response_data["explanation"] = explanation_text
                        print(f"✅ Explanation Generated: {explanation_text[:50]}...")
                        
                    except Exception as llm_e:
                        # 분석 단계에서 에러가 나더라도, 표 데이터는 보여줘야 하므로 에러만 찍고 넘어감
                        print(f"🚨 [ERROR] LLM Analysis Failed: {llm_e}")
                        print(traceback.format_exc()) # 상세 에러 출력
                        response_data["explanation"] = f"AI 분석 중 오류 발생: {str(llm_e)}"

                else:
                    print("▶️ [DEBUG] No rows found. Skipping analysis.")
                    response_data["explanation"] = "조건에 맞는 데이터가 없습니다 (0건)."
                
            except Exception as execution_error:
                print(f"🚨 [ERROR] BigQuery Execution Failed: {execution_error}")
                print(traceback.format_exc())
                response_data["data"] = []
                response_data["db_error"] = str(execution_error)

        # ▼▼▼ [핵심 추가] 4. 최종 토큰 값을 DB 로그에 업데이트 ▼▼▼
        try:
            # log_entry 객체는 이미 세션에 연결되어 있으므로 값만 바꾸고 commit하면 UPDATE 됨
            log_entry.input_tokens = token_handler.input_tokens
            log_entry.output_tokens = token_handler.output_tokens
            log_entry.total_tokens = token_handler.total_tokens
            
            db.commit() # DB에 최종 반영
            print(f"✅ Log updated with tokens: Total {token_handler.total_tokens}")
            
        except Exception as update_e:
            print(f"⚠️ Failed to update token logs: {update_e}")

        # 5. 응답에도 토큰 정보 포함
        response_data["tokens"] = {
            "input": token_handler.input_tokens,
            "output": token_handler.output_tokens,
            "total": token_handler.total_tokens
        }

        return response_data

    except Exception as e:
        # 3. 에러 발생 시 상세 정보 캡처
        error_msg = str(e)
        error_trace = traceback.format_exc() # 에러의 상세 위치를 문자열로 가져옴
        
        logger.error(f"Error processing query: {error_msg}")
        logger.error(error_trace) # 서버 콘솔에도 출력

        return {
            "success": False, 
            "error": error_msg,     # 간단한 에러 메시지
            "traceback": error_trace # 상세 스택 트레이스 (프론트엔드로 전송)
        }
    
@app.get("/logs")
def get_query_logs(limit: int = 10, db: Session = Depends(get_db)):
    """최신 쿼리 로그 N개를 조회합니다."""
    logs = db.query(QueryLog).order_by(QueryLog.id.desc()).limit(limit).all()
    return logs