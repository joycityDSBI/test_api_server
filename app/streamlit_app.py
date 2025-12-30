import streamlit as st
import requests
import json

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
tab1, tab2, tab3 = st.tabs(["📝 텍스트 입력", "🔢 정수 연산", "📊 서버 상태"])

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
            
            # 결과를 카드 형태로 표시
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
            
            # JSON 응답도 표시
            with st.expander("📋 전체 응답 보기"):
                st.json(result_data)
            
            if st.session_state.integer_status_code == 200:
                st.success(f"✅ Status Code: {st.session_state.integer_status_code}")
            else:
                st.error(f"❌ Status Code: {st.session_state.integer_status_code}")
        else:
            st.info("👈 왼쪽에서 정수를 입력하고 버튼을 눌러주세요.")

# 탭 3: 서버 상태
with tab3:
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
            
            # 상세 정보
            with st.expander("📋 상세 응답 보기"):
                st.json(health_data)
                
        except requests.exceptions.Timeout:
            st.error("⏱️ 서버 응답 시간 초과 (5초)")
        except requests.exceptions.ConnectionError:
            st.error("🔌 서버 연결 실패")
        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")
    
    # 엔드포인트 정보
    st.markdown("---")
    st.markdown("### 📡 사용 가능한 엔드포인트")
    endpoints_data = {
        "엔드포인트": ["/", "/health", "/integer/{value}"],
        "설명": ["루트 페이지", "서버 상태 확인", "정수를 2로 나누기"],
        "메서드": ["GET", "GET", "GET"]
    }
    st.table(endpoints_data)