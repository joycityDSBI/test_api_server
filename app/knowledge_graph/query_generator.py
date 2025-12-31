from typing import Dict, List, Any
from knowledge_graph.parser import KnowledgeGraphParser

class QueryGenerator:
    def __init__(self, parser: KnowledgeGraphParser):
        self.parser = parser
    
    def generate_sql(self, keywords: Dict[str, Any]) -> Dict[str, Any]:
        """추출된 키워드로부터 SQL 쿼리 생성"""
        
        if not keywords.get("entities"):
            return {
                "success": False,
                "error": "인식된 테이블/엔티티가 없습니다.",
                "keywords": keywords
            }
        
        # 주 엔티티 결정
        main_entity = keywords["entities"][0]
        main_table = self.parser.get_table_name(main_entity)
        
        # SELECT 절 생성
        select_parts = []
        
        # 집계 함수가 있는 경우
        if keywords.get("aggregations"):
            for agg in keywords["aggregations"]:
                # 집계할 컬럼 찾기
                if keywords.get("columns"):
                    col = keywords["columns"][0]
                    select_parts.append(
                        f"{agg['function']}({col['column']}) as {col['column']}_{agg['name']}"
                    )
                else:
                    # 기본적으로 COUNT(*) 사용
                    select_parts.append(f"{agg['function']}(*) as count")
        else:
            # 집계 없으면 전체 컬럼 또는 특정 컬럼
            if keywords.get("columns"):
                for col in keywords["columns"]:
                    select_parts.append(col["column"])
            else:
                select_parts.append("*")
        
        # FROM 절
        from_clause = f"`{main_table}`"
        
        # WHERE 절 생성
        where_parts = []
        
        # 시간 필터
        if keywords.get("time_filters"):
            time_filter = keywords["time_filters"][0]
            # 날짜 컬럼 찾기
            date_columns = [col for col in keywords.get("columns", []) 
                          if col.get("type") == "timestamp"]
            if date_columns:
                date_col = date_columns[0]["column"]
                where_parts.append(f"{date_col} >= {time_filter['sql']}")
        
        # 숫자 조건 (예: "100 이상")
        if keywords.get("numbers"):
            numeric_columns = [col for col in keywords.get("columns", []) 
                             if col.get("type") == "numeric"]
            if numeric_columns:
                num_col = numeric_columns[0]["column"]
                num_value = keywords["numbers"][0]
                where_parts.append(f"{num_col} >= {num_value}")
        
        # 쿼리 조합
        query_parts = [
            f"SELECT {', '.join(select_parts)}",
            f"FROM {from_clause}"
        ]
        
        if where_parts:
            query_parts.append(f"WHERE {' AND '.join(where_parts)}")
        
        # LIMIT 추가
        query_parts.append("LIMIT 100")
        
        sql_query = "\n".join(query_parts)
        
        return {
            "success": True,
            "sql": sql_query,
            "keywords": keywords,
            "explanation": self._generate_explanation(keywords)
        }
    
    def _generate_explanation(self, keywords: Dict[str, Any]) -> str:
        """생성된 쿼리에 대한 설명"""
        parts = []
        
        if keywords.get("entities"):
            entities = ", ".join(keywords["entities"])
            parts.append(f"테이블: {entities}")
        
        if keywords.get("aggregations"):
            aggs = ", ".join([a["name"] for a in keywords["aggregations"]])
            parts.append(f"집계: {aggs}")
        
        if keywords.get("time_filters"):
            times = ", ".join([t["name"] for t in keywords["time_filters"]])
            parts.append(f"시간 필터: {times}")
        
        return " | ".join(parts)