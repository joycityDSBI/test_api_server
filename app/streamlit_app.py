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
API_URL = "http://localhost:8000"

# 제목
st.title("🚀 FastAPI 서버 테스트")
st.markdown("---")

# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")
    endpoint = st.selectbox(
        "API 엔드포인트",
        ["/", "/health"]
    )

# 메인 영역
col1, col2 = st.columns(2)

with col1:
    st.subheader("📝 입력")
    
    # 입력 박스
    user_input = st.text_input(
        "데이터 입력",
        placeholder="여기에 데이터를 입력하세요..."
    )
    
    # 전송 버튼
    if st.button("🚀 전송", type="primary"):
        if user_input:
            try:
                # API 호출
                response = requests.get(
                    f"{API_URL}{endpoint}",
                    params={"data": user_input}
                )
                
                # 응답 저장
                st.session_state.response = response.json()
                st.session_state.status_code = response.status_code
                st.success("✅ 요청 성공!")
                
            except Exception as e:
                st.error(f"❌ 오류 발생: {str(e)}")
        else:
            st.warning("⚠️ 데이터를 입력해주세요!")

with col2:
    st.subheader("📤 응답")
    
    # 응답 표시
    if 'response' in st.session_state:
        st.json(st.session_state.response)
        
        # 상태 코드 표시
        if st.session_state.status_code == 200:
            st.success(f"Status Code: {st.session_state.status_code}")
        else:
            st.error(f"Status Code: {st.session_state.status_code}")
    else:
        st.info("👈 왼쪽에서 데이터를 입력하고 전송 버튼을 눌러주세요.")

# 하단 정보
st.markdown("---")
st.markdown("### 📊 서버 상태")

if st.button("🔄 서버 상태 확인"):
    try:
        health_response = requests.get(f"{API_URL}/health")
        health_data = health_response.json()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("서버 상태", health_data.get("status", "unknown"))
        with col2:
            st.metric("데이터베이스", health_data.get("database", "unknown"))
        with col3:
            st.metric("응답 시간", f"{health_response.elapsed.total_seconds():.3f}s")
            
    except Exception as e:
        st.error(f"서버 연결 실패: {str(e)}")