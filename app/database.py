from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime # [수정] 타입 임포트 추가
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func # [수정] 시간 함수 임포트 추가
from config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------------------------------------------------------
# [추가됨] 1. 자연어 쿼리 로그 테이블 모델 정의
# ---------------------------------------------------------
class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=False)       # 사용자 ID
    question = Column(Text, nullable=False)             # 사용자의 질문
    generated_sql = Column(Text, nullable=True)         # 생성된 SQL
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # 생성 일시
    input_tokens = Column(Integer, nullable=True)     # 입력 토큰 수
    output_tokens = Column(Integer, nullable=True)    # 출력 토큰 수    
    total_tokens = Column(Integer, nullable=True)     # 총 토큰 수

# ---------------------------------------------------------
# [추가됨] 2. 테이블 생성 함수 (main.py 시작 시 호출용)
# ---------------------------------------------------------
def init_db():
    # 정의된 모든 모델(Base를 상속받은 클래스)의 테이블을 DB에 생성합니다.
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()