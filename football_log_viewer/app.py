"""
Football Service Log Viewer
Streamlit 기반 PostgreSQL 로그 뷰어
"""

import json
import math
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import db_config as db

# ─────────────────────────────────────────────
# 페이지 기본 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Football Log Viewer",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("⚽ Football Service Log Viewer")
st.markdown("---")


# ─────────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────────
def is_json_like(value) -> bool:
    """값이 dict/list 이거나 JSON 문자열인지 확인합니다."""
    if isinstance(value, (dict, list)):
        return True
    if isinstance(value, str):
        stripped = value.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        ):
            try:
                json.loads(stripped)
                return True
            except (json.JSONDecodeError, ValueError):
                pass
    return False


def parse_json(value):
    """dict/list면 그대로, 문자열이면 파싱해서 반환합니다."""
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def format_cell(value) -> str:
    """데이터프레임 셀 표시용으로 값을 문자열로 변환합니다."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


@st.cache_data(ttl=300, show_spinner=False)
def load_columns(table_name: str):
    """테이블 컬럼 목록을 캐싱해서 반환합니다."""
    return db.get_table_columns(table_name)


def run_query(table, start_dt, end_dt, filters, page, page_size):
    """DB 조회를 실행하고 결과를 반환합니다."""
    offset = (page - 1) * page_size
    return db.fetch_logs(
        table_name=table,
        start_dt=start_dt,
        end_dt=end_dt,
        filters=filters,
        limit=page_size,
        offset=offset,
    )


# ─────────────────────────────────────────────
# 사이드바 – 검색 조건
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 검색 조건")

    # 1) 테이블 선택
    selected_table = st.selectbox(
        "테이블 선택",
        db.LOG_TABLES,
        help="조회할 로그 테이블을 선택하세요.",
    )

    st.markdown("---")

    # 2) 날짜 범위 선택 (기본값: 어제 ~ 오늘)
    st.subheader("📅 날짜 범위 (log_time)")
    today = date.today()
    yesterday = today - timedelta(days=1)

    col_s, col_e = st.columns(2)
    with col_s:
        start_date = st.date_input("시작일", value=yesterday, key="start_date")
    with col_e:
        end_date = st.date_input("종료일", value=today, key="end_date")

    col_st, col_et = st.columns(2)
    with col_st:
        start_time = st.time_input("시작 시각", value=datetime.strptime("00:00", "%H:%M").time(), key="start_time")
    with col_et:
        end_time = st.time_input("종료 시각", value=datetime.strptime("23:59", "%H:%M").time(), key="end_time")

    start_dt = datetime.combine(start_date, start_time).strftime("%Y-%m-%d %H:%M:%S")
    end_dt = datetime.combine(end_date, end_time).strftime("%Y-%m-%d %H:%M:%S")

    st.caption(f"검색 범위: `{start_dt}` ~ `{end_dt}`")

    st.markdown("---")

    # 3) 컬럼 필터
    st.subheader("🎛️ 컬럼 필터")

    try:
        columns_info = load_columns(selected_table)
        col_names = [c["column_name"] for c in columns_info]
    except Exception as e:
        st.error(f"컬럼 로드 실패: {e}")
        columns_info = []
        col_names = []

    # 최대 3개 필터 지원
    filters = []
    for idx in range(1, 4):
        with st.expander(f"필터 {idx}", expanded=(idx == 1)):
            f_col = st.selectbox(
                "컬럼",
                ["(선택 안 함)"] + col_names,
                key=f"f_col_{idx}",
            )
            f_op = st.selectbox(
                "연산자",
                ["=", "!=", "LIKE", ">", ">=", "<", "<="],
                key=f"f_op_{idx}",
            )
            f_val = st.text_input("값", key=f"f_val_{idx}", placeholder="필터 값 입력")

            if f_col != "(선택 안 함)" and f_val:
                filters.append({"column": f_col, "operator": f_op, "value": f_val})

    st.markdown("---")

    # 4) 페이지 크기
    st.subheader("📄 페이지 설정")
    page_size = st.selectbox("페이지당 행 수", [50, 100, 200, 500], index=1)

    # 5) 조회 버튼
    search_btn = st.button("🔍 조회", type="primary", use_container_width=True)

    st.markdown("---")

    # 6) DB 연결 테스트
    if st.button("🔌 DB 연결 테스트", use_container_width=True):
        ok, msg = db.test_connection()
        if ok:
            st.success(msg)
        else:
            st.error(msg)


# ─────────────────────────────────────────────
# 메인 영역
# ─────────────────────────────────────────────

# 세션 상태 초기화
if "rows" not in st.session_state:
    st.session_state.rows = []
if "total" not in st.session_state:
    st.session_state.total = 0
if "current_page" not in st.session_state:
    st.session_state.current_page = 1
if "last_query" not in st.session_state:
    st.session_state.last_query = {}

# 조회 버튼 클릭 시 1페이지부터 다시 조회
if search_btn:
    st.session_state.current_page = 1
    st.session_state.last_query = {
        "table": selected_table,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "filters": filters,
        "page_size": page_size,
    }
    try:
        with st.spinner("조회 중..."):
            rows, total = run_query(
                selected_table, start_dt, end_dt, filters,
                page=1, page_size=page_size,
            )
        st.session_state.rows = rows
        st.session_state.total = total
    except Exception as e:
        st.error(f"조회 오류: {e}")

# 결과 표시
q = st.session_state.last_query
rows = st.session_state.rows
total = st.session_state.total

if q:
    # 요약 정보
    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.metric("테이블", q["table"])
    col_info2.metric("전체 건수", f"{total:,}")
    col_info3.metric("현재 페이지", f"{st.session_state.current_page} / {max(1, math.ceil(total / q['page_size']))}")

    if total == 0:
        st.info("조회된 데이터가 없습니다.")
    elif rows:
        # ── 탭: 테이블 뷰 / JSON 뷰 ──────────────────────────────
        tab_table, tab_json, tab_schema = st.tabs(["📋 테이블 뷰", "🗂️ JSON 뷰", "📐 스키마 정보"])

        # 컬럼 정보 (JSON 여부 판단에 사용)
        try:
            col_info = load_columns(q["table"])
            json_col_types = {"json", "jsonb"}
            db_json_cols = {
                c["column_name"]
                for c in col_info
                if c["data_type"] in json_col_types or c["udt_name"] in json_col_types
            }
        except Exception:
            db_json_cols = set()

        # 런타임에도 JSON 같은 값이면 JSON 컬럼으로 간주
        runtime_json_cols = set()
        for row in rows[:5]:  # 앞 5개 샘플로 판단
            for k, v in row.items():
                if is_json_like(v):
                    runtime_json_cols.add(k)
        json_cols = db_json_cols | runtime_json_cols

        # ── 탭 1: 테이블 뷰 ──────────────────────────────────────
        with tab_table:
            # JSON 컬럼은 문자열로 변환해서 표시
            display_rows = []
            for row in rows:
                display_row = {}
                for k, v in row.items():
                    display_row[k] = format_cell(v)
                display_rows.append(display_row)

            df = pd.DataFrame(display_rows)
            if not df.empty:
                st.caption("💡 행을 클릭하면 아래에 상세 내용이 펼쳐집니다.")
                event = st.dataframe(
                    df,
                    use_container_width=True,
                    height=500,
                    selection_mode="single-row",
                    on_select="rerun",
                    key="table_df",
                )

                # 선택된 행 아코디언
                selected_indices = event.selection.rows if event.selection.rows else []
                if selected_indices:
                    selected_idx = selected_indices[0]
                    selected_row = rows[selected_idx]

                    with st.expander(f"📄 행 {selected_idx + 1} 상세 보기", expanded=True):
                        # 일반 컬럼
                        normal_data = [
                            {"컬럼": k, "값": format_cell(v)}
                            for k, v in selected_row.items()
                            if k not in json_cols
                        ]
                        if normal_data:
                            st.markdown("**일반 컬럼**")
                            st.table(pd.DataFrame(normal_data))

                        # JSON/Array 컬럼
                        for col in sorted(json_cols):
                            val = selected_row.get(col)
                            if val is None:
                                continue
                            st.markdown(f"**`{col}`** *(JSON/Array)*")
                            st.json(parse_json(val))

                # CSV 다운로드
                csv = df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "📥 CSV 다운로드",
                    data=csv,
                    file_name=f"{q['table']}_{q['start_dt'][:10]}_{q['end_dt'][:10]}.csv",
                    mime="text/csv",
                )

        # ── 탭 2: JSON 뷰 ────────────────────────────────────────
        with tab_json:
            if not json_cols:
                st.info("이 테이블에는 JSON 컬럼이 없습니다.")
            else:
                st.caption(f"JSON 컬럼: `{'`, `'.join(sorted(json_cols))}`")

                # 행 선택 슬라이더
                row_idx = st.slider(
                    "행 선택",
                    min_value=1,
                    max_value=len(rows),
                    value=1,
                    key="json_row_slider",
                )
                selected_row = rows[row_idx - 1]

                # log_time 등 기본 정보 표시
                log_time_val = selected_row.get(db.LOG_TIME_COLUMN, "N/A")
                st.markdown(f"**log_time:** `{log_time_val}`  |  **행 번호 (현재 페이지):** `{row_idx}`")
                st.markdown("---")

                # JSON 컬럼 별로 표시
                has_json = False
                for col in sorted(json_cols):
                    val = selected_row.get(col)
                    if val is None:
                        continue
                    has_json = True
                    with st.expander(f"📄 `{col}`", expanded=True):
                        parsed = parse_json(val)
                        st.json(parsed)

                # 비-JSON 컬럼도 expander로
                with st.expander("📋 전체 행 데이터 (원본)", expanded=False):
                    non_json = {
                        k: format_cell(v)
                        for k, v in selected_row.items()
                        if k not in json_cols
                    }
                    if non_json:
                        st.table(pd.DataFrame(non_json.items(), columns=["컬럼", "값"]))

                if not has_json:
                    st.info("선택한 행에는 JSON 데이터가 없습니다.")

        # ── 탭 3: 스키마 정보 ────────────────────────────────────
        with tab_schema:
            try:
                schema_rows = load_columns(q["table"])
                schema_df = pd.DataFrame(schema_rows)
                # JSON 여부 컬럼 추가
                schema_df["is_json"] = schema_df["column_name"].apply(
                    lambda c: "✅" if c in json_cols else ""
                )
                st.dataframe(schema_df, use_container_width=True)
            except Exception as e:
                st.error(f"스키마 조회 실패: {e}")

        # ── 페이지네이션 ─────────────────────────────────────────
        st.markdown("---")
        total_pages = max(1, math.ceil(total / q["page_size"]))
        col_prev, col_page, col_next = st.columns([1, 3, 1])

        with col_prev:
            if st.button("◀ 이전", disabled=(st.session_state.current_page <= 1)):
                st.session_state.current_page -= 1
                rows, total = run_query(
                    q["table"], q["start_dt"], q["end_dt"], q["filters"],
                    page=st.session_state.current_page, page_size=q["page_size"],
                )
                st.session_state.rows = rows
                st.session_state.total = total
                st.rerun()

        with col_page:
            new_page = st.number_input(
                "페이지",
                min_value=1,
                max_value=total_pages,
                value=st.session_state.current_page,
                step=1,
                key="page_input",
                label_visibility="collapsed",
            )
            if new_page != st.session_state.current_page:
                st.session_state.current_page = new_page
                rows, total = run_query(
                    q["table"], q["start_dt"], q["end_dt"], q["filters"],
                    page=new_page, page_size=q["page_size"],
                )
                st.session_state.rows = rows
                st.session_state.total = total
                st.rerun()
            st.caption(f"총 {total_pages} 페이지")

        with col_next:
            if st.button("다음 ▶", disabled=(st.session_state.current_page >= total_pages)):
                st.session_state.current_page += 1
                rows, total = run_query(
                    q["table"], q["start_dt"], q["end_dt"], q["filters"],
                    page=st.session_state.current_page, page_size=q["page_size"],
                )
                st.session_state.rows = rows
                st.session_state.total = total
                st.rerun()

else:
    # 초기 화면
    st.info("👈 왼쪽 사이드바에서 테이블과 날짜 범위를 선택한 후 **조회** 버튼을 누르세요.")

    st.markdown("### 📋 조회 가능한 테이블")
    for t in db.LOG_TABLES:
        st.markdown(f"- `{t}`")

    st.markdown("### 🎯 사용법")
    st.markdown("""
1. **테이블 선택** – 조회할 로그 테이블을 선택합니다.
2. **날짜 범위** – `log_time` 기준으로 기간을 설정합니다 (기본: 어제 ~ 오늘).
3. **컬럼 필터** – 특정 컬럼 값으로 필터를 추가할 수 있습니다 (최대 3개).
4. **조회** 버튼을 클릭합니다.
5. **테이블 뷰** 탭에서 행을 클릭하면 아코디언으로 상세 내용(일반 컬럼 + JSON 컬럼)을 확인할 수 있습니다.
6. CSV 다운로드 기능을 제공합니다.
    """)
