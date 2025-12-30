import streamlit as st
import requests
import json
import pandas as pd

# 페이지 설정
st.set_page_config(
    page_title="FastAPI 테스트",
    page_icon="🚀",
    layout="wide"
)

# API 서버 URL
API_URL = "http://fastapi-app:8000"

# 제목
st.title("🚀 FastAPI 서버 테스트")
st.markdown("---")

# 탭 생성
tab1, tab2, tab3, tab4 = st.tabs(["📝 텍스트 입력", "🔢 정수 연산", "🔍 BigQuery", "📊 서버 상태"])

# 탭 1: 기본 텍스트 입력
with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📝 입력")
        
        endpoint = st.selectbox(
            "API 엔드포인트",
            ["/", "/health"],
            key="text_endpoint"
        )
        
        user_input = st.text_input(
            "데이터 입력",
            placeholder="여기에 데이터를 입력하세요...",
            key="text_input"
        )
        
        if st.button("🚀 전송", type="primary", key="text_submit"):
            if user_input:
                try:
                    response = requests.get(
                        f"{API_URL}{endpoint}",
                        params={"data": user_input}
                    )
                    
                    st.session_state.text_response = response.json()
                    st.session_state.text_status_code = response.status_code
                    st.success("✅ 요청 성공!")
                    
                except Exception as e:
                    st.error(f"❌ 오류 발생: {str(e)}")
            else:
                st.warning("⚠️ 데이터를 입력해주세요!")
    
    with col2:
        st.subheader("📤 응답")
        
        if 'text_response' in st.session_state:
            st.json(st.session_state.text_response)
            
            if st.session_state.text_status_code == 200:
                st.success(f"Status Code: {st.session_state.text_status_code}")
            else:
                st.error(f"Status Code: {st.session_state.text_status_code}")
        else:
            st.info("👈 왼쪽에서 데이터를 입력하고 전송 버튼을 눌러주세요.")

# 탭 2: 정수 연산
with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔢 정수 입력")
        
        integer_input = st.number_input(
            "정수를 입력하세요",
            min_value=-1000000,
            max_value=1000000,
            value=0,
            step=1,
            key="integer_input"
        )
        
        st.info(f"입력한 값: **{integer_input}**")
        
        if st.button("➗ 2로 나누기", type="primary", key="integer_submit"):
            try:
                response = requests.get(f"{API_URL}/integer/{integer_input}")
                
                st.session_state.integer_response = response.json()
                st.session_state.integer_status_code = response.status_code
                st.success("✅ 계산 완료!")
                
            except Exception as e:
                st.error(f"❌ 오류 발생: {str(e)}")
    
    with col2:
        st.subheader("📊 결과")
        
        if 'integer_response' in st.session_state:
            result_data = st.session_state.integer_response
            
            st.markdown("### 계산 결과")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric(
                    label="입력 값", 
                    value=result_data.get('input', 'N/A')
                )
            with col_b:
                st.metric(
                    label="결과 (입력 ÷ 2)", 
                    value=result_data.get('result', 'N/A')
                )
            
            with st.expander("📋 전체 응답 보기"):
                st.json(result_data)
            
            if st.session_state.integer_status_code == 200:
                st.success(f"✅ Status Code: {st.session_state.integer_status_code}")
            else:
                st.error(f"❌ Status Code: {st.session_state.integer_status_code}")
        else:
            st.info("👈 왼쪽에서 정수를 입력하고 버튼을 눌러주세요.")

# 탭 3: BigQuery
with tab3:
    st.subheader("🔍 BigQuery 쿼리 실행")
    
    # 쿼리 템플릿 선택
    query_template = st.selectbox(
        "쿼리 템플릿",
        [
            "직접 입력",
            "샘플: 공개 데이터셋",
            "테이블 정보 조회"
        ]
    )
    
    if query_template == "샘플: 공개 데이터셋":
        default_query = """SELECT 
  name, 
  SUM(number) as total 
FROM `bigquery-public-data.usa_names.usa_1910_2013` 
WHERE state = 'TX' 
GROUP BY name 
ORDER BY total DESC 
LIMIT 10"""
    else:
        default_query = ""
    
    # 쿼리 입력
    query_input = st.text_area(
        "SQL 쿼리를 입력하세요",
        value=default_query,
        height=200,
        placeholder="SELECT * FROM `project.dataset.table` LIMIT 10"
    )
    
    max_results = st.slider("최대 결과 행 수", 10, 1000, 100)
    
    col1, col2 = st.columns([1, 4])
    with col1:
        run_query_btn = st.button("🚀 쿼리 실행", type="primary", key="run_query")
    
    if run_query_btn:
        if query_input.strip():
            with st.spinner("⏳ 쿼리 실행 중..."):
                try:
                    response = requests.post(
                        f"{API_URL}/bigquery/query",
                        json={
                            "query": query_input,
                            "max_results": max_results
                        },
                        timeout=60
                    )
                    
                    result = response.json()
                    
                    if result.get("success"):
                        st.success(f"✅ 쿼리 성공! ({result.get('row_count', 0)} 행)")
                        
                        # 결과를 DataFrame으로 표시
                        if result.get("data"):
                            df = pd.DataFrame(result["data"])
                            
                            # 데이터 프레임 표시
                            st.dataframe(df, use_container_width=True)
                            
                            # 다운로드 버튼
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 CSV 다운로드",
                                data=csv,
                                file_name="bigquery_result.csv",
                                mime="text/csv"
                            )
                            
                            # 통계 정보
                            with st.expander("📊 통계 정보"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric("총 행 수", len(df))
                                    st.metric("총 컬럼 수", len(df.columns))
                                with col2:
                                    st.write("**컬럼 목록:**")
                                    st.write(", ".join(df.columns.tolist()))
                        else:
                            st.info("결과가 없습니다.")
                    else:
                        st.error(f"❌ 쿼리 실패: {result.get('error', '알 수 없는 오류')}")
                        
                except requests.exceptions.Timeout:
                    st.error("⏱️ 쿼리 실행 시간 초과 (60초)")
                except Exception as e:
                    st.error(f"❌ 오류 발생: {str(e)}")
        else:
            st.warning("⚠️ 쿼리를 입력해주세요!")
    
    # 테이블 정보 조회 섹션
    if query_template == "테이블 정보 조회":
        st.markdown("---")
        st.subheader("📋 테이블 스키마 조회")
        
        col1, col2 = st.columns(2)
        with col1:
            dataset_id = st.text_input("Dataset ID", placeholder="your_dataset")
        with col2:
            table_id = st.text_input("Table ID", placeholder="your_table")
        
        if st.button("🔍 스키마 조회", key="get_schema"):
            if dataset_id and table_id:
                try:
                    response = requests.get(
                        f"{API_URL}/bigquery/table/{dataset_id}/{table_id}",
                        timeout=30
                    )
                    
                    result = response.json()
                    
                    if result.get("success"):
                        st.success("✅ 테이블 정보 조회 성공!")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("총 행 수", f"{result.get('row_count', 0):,}")
                        with col2:
                            st.metric("크기 (MB)", f"{result.get('size_mb', 0):.2f}")
                        with col3:
                            st.metric("컬럼 수", len(result.get('schema', [])))
                        
                        # 스키마 테이블로 표시
                        if result.get('schema'):
                            st.markdown("### 테이블 스키마")
                            schema_df = pd.DataFrame(result['schema'])
                            st.dataframe(schema_df, use_container_width=True)
                    else:
                        st.error(f"❌ 조회 실패: {result.get('error', '알 수 없는 오류')}")
                        
                except Exception as e:
                    st.error(f"❌ 오류 발생: {str(e)}")
            else:
                st.warning("⚠️ Dataset ID와 Table ID를 모두 입력해주세요!")

# 탭 4: 서버 상태
with tab4:
    st.subheader("📊 서버 상태 확인")
    
    if st.button("🔄 서버 상태 확인", key="health_check"):
        try:
            health_response = requests.get(f"{API_URL}/health", timeout=5)
            health_data = health_response.json()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                status = health_data.get("status", "unknown")
                st.metric("서버 상태", status)
                if status == "healthy":
                    st.success("✅ 정상")
                else:
                    st.error("❌ 비정상")
            
            with col2:
                db_status = health_data.get("database", "unknown")
                st.metric("데이터베이스", db_status)
                if db_status == "connected":
                    st.success("✅ 연결됨")
                else:
                    st.error("❌ 연결 안됨")
            
            with col3:
                response_time = health_response.elapsed.total_seconds()
                st.metric("응답 시간", f"{response_time:.3f}s")
            
            with st.expander("📋 상세 응답 보기"):
                st.json(health_data)
                
        except requests.exceptions.Timeout:
            st.error("⏱️ 서버 응답 시간 초과 (5초)")
        except requests.exceptions.ConnectionError:
            st.error("🔌 서버 연결 실패")
        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")
    
    st.markdown("---")
    st.markdown("### 📡 사용 가능한 엔드포인트")
    endpoints_data = {
        "엔드포인트": ["/", "/health", "/integer/{value}", "/bigquery/query", "/bigquery/table/{dataset}/{table}"],
        "설명": ["루트 페이지", "서버 상태 확인", "정수를 2로 나누기", "BigQuery 쿼리 실행", "테이블 스키마 조회"],
        "메서드": ["GET", "GET", "GET", "POST", "GET"]
    }
    st.table(endpoints_data)