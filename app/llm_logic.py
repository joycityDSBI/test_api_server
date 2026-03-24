import os
import glob
import yaml
from langchain_google_vertexai import ChatVertexAI, VertexAIEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# 1. YAML 파일 병합 함수
def load_and_merge_yamls(directory_path):
    merged_data = {
        'entities': {}, 'relationships': [], 'game_mappings': {},
        'time_expressions': {}, 'aggregations': {}, 'filters': {}
    }
    
    yaml_files = glob.glob(os.path.join(directory_path, "*.yaml"))
    
    for file_path in yaml_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = yaml.safe_load(f)
                if not data: continue

                # Dictionary 병합
                for key in ['entities', 'game_mappings', 'time_expressions', 'aggregations', 'filters']:
                    if key in data:
                        merged_data[key].update(data[key])
                
                # List 병합
                if 'relationships' in data:
                    merged_data['relationships'].extend(data['relationships'])
                    
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    return merged_data

# 2. 프롬프트 컨텍스트 생성 함수
def parse_schema_to_prompt(data):
    prompt_context = "### Database Schema & Aliases ###\n"
    
    # Entities
    for entity_name, entity_info in data.get('entities', {}).items():
        table = entity_info.get('table', entity_name)
        prompt_context += f"- Table: {table}\n"
        for col, col_info in entity_info.get('columns', {}).items():
            aliases = ", ".join(col_info.get('aliases', []))
            prompt_context += f"  * Column: {col} (Aliases: {aliases})\n"
            
    # Relationships
    prompt_context += "\n### Joins ###\n"
    for rel in data.get('relationships', []):
        prompt_context += f"- JOIN {rel['from']} AND {rel['to']} ON {rel['join_key']}\n"
        
    # Mappings (Business Logic)
    prompt_context += "\n### Value Mappings ###\n"
    for key, mapping in data.get('game_mappings', {}).items():
        prompt_context += f"- '{mapping.get('full_name')}' or '{key}' -> {mapping.get('column')} = {mapping.get('joyple_game_code')}\n"

    # Time Expressions
    prompt_context += "\n### Time SQL ###\n"
    for key, expr in data.get('time_expressions', {}).items():
        prompt_context += f"- '{key}' -> {expr.get('sql')}\n"
        
    return prompt_context

# 3. [핵심] Gemini Chain 생성 함수
def get_gemini_chain(model_name="gemini-2.5-flash"):
    """
    Gemini 모델과 프롬프트를 결합하여 LangChain 실행 체인을 반환합니다.
    """
    
    # 1. 모델 초기화 (SQL 생성은 temperature=0 권장)
    llm = ChatVertexAI(
        model_name=model_name,
        temperature=0,
        max_output_tokens=8192,
        # location="asia-northeast3" # 필요 시 리전 지정 (서울), 기본값은 us-central1
    )

    # 2. 시스템 프롬프트 정의
    system_template = """
    You are a BigQuery SQL Expert.
    Convert the user's natural language question into a SQL query based strictly on the provided Context.
    
    Context:
    {context}
    
    Rules:
    1. Use ONLY the tables and columns defined in the Context.
    2. Do NOT use markdown formatting (no ```sql or ```).
    3. Return ONLY the SQL query string.
    4. 데이터베이스 이름은 반드시 백틱(`)으로 감싸주세요.
    예: `datahub-478802`
    5. 특히 이름에 하이픈(-)이 포함된 경우 백틱은 필수입니다.
    """

    # 3. 프롬프트 템플릿 결합
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "{question}")
    ])

    # 4. 체인 연결 (Prompt -> LLM -> String Output)
    chain = prompt | llm | StrOutputParser()
    
    return chain


# [추가] 벡터 저장소(Retriever) 생성 함수
def create_schema_retriever(full_schema_data):
    """
    YAML 데이터를 기반으로 FAISS 벡터 저장소를 생성합니다.
    각 테이블 정보를 Document 객체로 만들어 인덱싱합니다.
    """
    documents = []
    
    # full_schema_data는 {'dataset': {'table': {schema...}}} 구조라고 가정
    for dataset_name, tables in full_schema_data.items():
        for table_name, table_info in tables.items():
            # 1. 검색에 사용될 텍스트 (테이블 이름 + 설명 + 컬럼명)
            # 이 내용이 '검색'의 기준이 됩니다.
            description = table_info.get('description', '')
            columns = ", ".join(table_info.get('columns', {}).keys())
            
            page_content = f"Table: {dataset_name}.{table_name}\nDescription: {description}\nColumns: {columns}"
            
            # 2. 실제 LLM에게 넘겨줄 전체 스키마 텍스트 (Metadata에 저장)
            # parse_schema_to_prompt 함수가 만드는 포맷과 유사하게 개별 테이블용 스키마 문자열 생성
            full_schema_text = f"""
            - Table: `{dataset_name}.{table_name}`
            Description: {description}
            Columns:
            """
            for col, col_desc in table_info.get('columns', {}).items():
                full_schema_text += f"    - {col}: {col_desc}\n"

            # Document 객체 생성
            doc = Document(
                page_content=page_content, # 검색용 텍스트
                metadata={"schema_text": full_schema_text, "table_name": f"{dataset_name}.{table_name}"} # 실제 데이터
            )
            documents.append(doc)

    # 3. 임베딩 모델 설정 (Vertex AI)
    embeddings = VertexAIEmbeddings(model_name="text-embedding-004")
    
    # 4. 벡터 저장소 생성
    vectorstore = FAISS.from_documents(documents, embeddings)
    
    # 5. Retriever 반환 (유사도 높은 상위 5개 테이블만 가져오도록 설정)
    return vectorstore.as_retriever(search_kwargs={"k": 5})


# [추가] 질문에 맞는 스키마 텍스트 추출 함수
def get_relevant_context(retriever, query):
    # 질문과 관련된 테이블 검색
    relevant_docs = retriever.invoke(query)
    
    # 검색된 테이블들의 스키마 텍스트만 합침
    context_string = "Here is the schema of the relevant tables:\n"
    for doc in relevant_docs:
        context_string += doc.metadata["schema_text"] + "\n"
        
    return context_string