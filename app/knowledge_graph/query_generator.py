from typing import Dict, List, Any
from knowledge_graph.parser import KnowledgeGraphParser

class QueryGenerator:
    def __init__(self, parser: KnowledgeGraphParser):
        self.parser = parser
    
    def generate_sql(self, keywords: Dict[str, Any]) -> Dict[str, Any]:
        """추출된 키워드로부터 SQL 쿼리 생성"""
        
        # 게임 필터가 있으면 관련 엔티티 추가
        if keywords.get("game_filters"):
            if "f_common_access" not in keywords["entities"]:
                keywords["entities"].insert(0, "f_common_access")
        
        if not keywords.get("entities"):
            return {
                "success": False,
                "error": "인식된 테이블/엔티티가 없습니다.",
                "keywords": keywords
            }
        
        # 주 엔티티 결정
        main_entity = "f_common_access" if "f_common_access" in keywords["entities"] else keywords["entities"][0]
        main_table = self.parser.get_table_name(main_entity)
        
        if not main_table:
            return {
                "success": False,
                "error": f"테이블을 찾을 수 없습니다: {main_entity}",
                "keywords": keywords,
                "debug": {
                    "main_entity": main_entity,
                    "available_entities": list(self.parser.entities.keys())
                }
            }
        
        # SELECT 절 생성
        select_parts = []
        
        if keywords.get("aggregations"):
            for agg in keywords["aggregations"]:
                if agg['name'] == 'count':
                    select_parts.append("COUNT(DISTINCT a.game_account_name) as user_count")
                elif agg['name'] == 'sum':
                    numeric_cols = [col for col in keywords.get("columns", []) 
                                  if col.get('type') in ['integer', 'numeric']]
                    if numeric_cols:
                        col = numeric_cols[0]
                        select_parts.append(f"SUM(a.{col['column']}) as total_{col['column']}")
                    else:
                        select_parts.append("SUM(a.play_seconds) as total_play_seconds")
                elif agg['name'] == 'avg':
                    numeric_cols = [col for col in keywords.get("columns", []) 
                                  if col.get('type') in ['integer', 'numeric']]
                    if numeric_cols:
                        col = numeric_cols[0]
                        select_parts.append(f"AVG(a.{col['column']}) as avg_{col['column']}")
        
        if not select_parts:
            select_parts.append("COUNT(DISTINCT a.game_account_name) as user_count")
        
        # FROM 절
        from_clause = f"`{main_table}` a"
        
        # JOIN 절
        join_clauses = []
        use_game_join = False
        
        if keywords.get("game_filters"):
            game_filter = keywords["game_filters"][0]
            game_entity = game_filter['table'].split('.')[-1]
            game_table = self.parser.get_table_name(game_entity)
            
            if game_table:
                rel = self.parser.find_relationship(main_entity, game_entity)
                if rel:
                    join_key = rel.get('join_key')
                    join_clauses.append(f"JOIN `{game_table}` g ON a.{join_key} = g.{join_key}")
                    use_game_join = True
        
        # WHERE 절
        where_parts = []
        
        # 시간 필터 (범위로 처리)
        if keywords.get("time_filters"):
            time_filter = keywords["time_filters"][0]
            time_name = time_filter['name']
            
            # "일주일", "지난주" 등은 범위로 처리
            if time_name in ['last_week', 'this_week']:
                where_parts.append(f"a.datekey >= {time_filter['sql']}")
            else:
                # "오늘", "어제" 등은 정확한 날짜
                where_parts.append(f"a.datekey = {time_filter['sql']}")
        
        # 게임 필터
        if keywords.get("game_filters") and use_game_join:
            game_filter = keywords["game_filters"][0]
            if 'joyple_game_code' in game_filter:
                where_parts.append(f"g.joyple_game_code = {game_filter['joyple_game_code']}")
        
        # 쿼리 조합
        query_parts = [
            f"SELECT {', '.join(select_parts)}",
            f"FROM {from_clause}"
        ]
        
        if join_clauses:
            query_parts.extend(join_clauses)
        
        if where_parts:
            query_parts.append(f"WHERE {' AND '.join(where_parts)}")
        
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
        
        if keywords.get("game_filters"):
            games = ", ".join([g.get("full_name", g.get("game_name")) for g in keywords["game_filters"]])
            parts.append(f"게임: {games}")
        
        if keywords.get("time_filters"):
            times = ", ".join([t["name"] for t in keywords["time_filters"]])
            parts.append(f"시간: {times}")
        
        return " | ".join(parts)