"""
PostgreSQL DB 연결 설정 관리 모듈
football_service_log DB 전용 연결 설정
"""

import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

# ─────────────────────────────────────────────
# DB 연결 정보
# ─────────────────────────────────────────────
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "woore-fsfz-2-virginia-primary.cfe98cqvmxvk.us-east-1.rds.amazonaws.com"),
    "port": int(os.environ.get("DB_PORT", 61354)),
    "user": os.environ.get("DB_USER", "postadmin"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "dbname": os.environ.get("DB_NAME", "football_service_log"),
    "connect_timeout": 10,
    "options": "-c statement_timeout=30000",  # 30초 쿼리 타임아웃
}

# 뷰어에서 조회 가능한 테이블 목록
LOG_TABLES = [
    "jcl_de_friends",
    "jcl_de_match_end",
    "jcl_de_match_end_user_stats",
    "jcl_de_match_play_detail",
    "jcl_de_match_start",
    "jcl_de_matching_end",
    "jcl_de_matching_start",
]

# 공통 시간 컬럼 (날짜 범위 검색 기준)
LOG_TIME_COLUMN = "log_time"

# 페이지당 기본 행 수

DEFAULT_PAGE_SIZE = 100


def get_connection():
    """새 DB 연결을 반환합니다."""
    return psycopg2.connect(**DB_CONFIG)


@contextmanager
def get_db_cursor(cursor_factory=psycopg2.extras.RealDictCursor):
    """
    컨텍스트 매니저로 DB 커서를 제공합니다.
    RealDictCursor를 기본으로 사용해 컬럼명이 키인 dict 형태로 결과를 반환합니다.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=cursor_factory)
        yield cursor
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def test_connection() -> tuple[bool, str]:
    """DB 연결을 테스트하고 (성공여부, 메시지) 를 반환합니다."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()
        return True, f"연결 성공: {version['version'][:60]}..."
    except Exception as e:
        return False, f"연결 실패: {str(e)}"


def get_table_columns(table_name: str) -> list[dict]:
    """
    테이블의 컬럼 정보(name, data_type)를 반환합니다.
    """
    sql = """
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """
    with get_db_cursor() as cursor:
        cursor.execute(sql, (table_name,))
        return [dict(r) for r in cursor.fetchall()]


def fetch_logs(
    table_name: str,
    start_dt: str,
    end_dt: str,
    filters: list | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    로그 데이터를 조회합니다.

    Args:
        table_name: 조회할 테이블명
        start_dt:   시작 일시 문자열 (e.g. '2026-03-24 00:00:00')
        end_dt:     종료 일시 문자열 (e.g. '2026-03-25 23:59:59')
        filters:    [{"column": str, "operator": str, "value": str}, ...]
        limit:      페이지 크기
        offset:     오프셋

    Returns:
        (rows, total_count)
    """
    if table_name not in LOG_TABLES:
        raise ValueError(f"허용되지 않은 테이블입니다: {table_name}")

    params: list = [start_dt, end_dt]
    where_clauses = [
        f"{LOG_TIME_COLUMN} >= %s",
        f"{LOG_TIME_COLUMN} <= %s",
    ]

    # 추가 필터 조건 생성
    if filters:
        for f in filters:
            col = f.get("column", "")
            op = f.get("operator", "=")
            val = f.get("value", "")

            if not col or val == "":
                continue

            if op == "LIKE":
                where_clauses.append(f'"{col}"::text ILIKE %s')
                params.append(f"%{val}%")
            elif op in ("=", "!=", ">", ">=", "<", "<="):
                where_clauses.append(f'"{col}"::text {op} %s')
                params.append(str(val))

    where_sql = " AND ".join(where_clauses)

    count_sql = f'SELECT COUNT(*) AS cnt FROM "{table_name}" WHERE {where_sql}'
    data_sql = (
        f'SELECT * FROM "{table_name}" WHERE {where_sql} '
        f"ORDER BY {LOG_TIME_COLUMN} DESC "
        f"LIMIT %s OFFSET %s"
    )

    with get_db_cursor() as cursor:
        cursor.execute(count_sql, params)
        total = cursor.fetchone()["cnt"]

        cursor.execute(data_sql, params + [limit, offset])
        rows = cursor.fetchall()

    return [dict(r) for r in rows], total
