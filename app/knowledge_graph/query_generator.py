from typing import Dict, List, Any
from knowledge_graph.parser import KnowledgeGraphParser

class QueryGenerator:
    def __init__(self, parser: KnowledgeGraphParser):
        self.parser = parser
    
    def generate_sql(self, keywords: Dict[str, Any]) -> Dict[str, Any]:
        """추출된 키워드로부터 SQL 쿼리 생성"""
        
        # 게임 필터가 있으면 f_common_access 자동 추가
        if keywords.get("game_filters"):
            if "f_common_access" not in keywords["entities"]:
                keywords["entities"].insert(0, "f_common_access")
        
        if not keywords.get("entities"):
            return {
                "success": False,
                "error": "인식된 테이블/엔티티가 없습니다.",
                "keywords": keywords
            }
        
        # 주 엔티티
        main_entity = "f_common_access" if "f_common_access" in keywords["entities"] else keywords["entities"][0]
        main_table = self.parser.get_table_name(main_entity)
        
        if not main_table:
            return {
                "success": False,
                "error": f"테이블을 찾을 수 없습니다: {main_entity}",
                "keywords": keywords
            }
        
        # SELECT 절
        select_parts = []
        
        if keywords.get("aggregations"):
            for agg in keywords["aggregations"]:
                if agg['name'] == 'count':
                    select_parts.append("COUNT(DISTINCT a.game_account_name) as user_count")
                elif agg['name'] == 'sum':
                    select_parts.append("SUM(a.play_seconds) as total_play_seconds")
                elif agg['name'] == 'avg':
                    select_parts.append("AVG(a.play_seconds) as avg_play_seconds")
        
        if not select_parts:
            select_parts.append("COUNT(DISTINCT a.game_account_name) as user_count")
        
        # FROM 절
        from_clause = f"`{main_table}` a"
        
        # JOIN 절 생성
        join_clauses = []
        use_game_join = False
        
        # 게임 필터가 있으면 무조건 JOIN
        if keywords.get("game_filters") and len(keywords["game_filters"]) > 0:
            game_filter = keywords["game_filters"][0]
            game_entity = game_filter.get('table', '').split('.')[-1]
            
            if game_entity:
                game_table = self.parser.get_table_name(game_entity)
                
                if game_table:
                    rel = self.parser.find_relationship(main_entity, game_entity)
                    if rel:
                        join_key = rel.get('join_key')
                        join_clauses.append(f"JOIN `{game_table}` g ON a.{join_key} = g.{join_key}")
                        use_game_join = True
        
        # WHERE 절
        where_parts = []
        
        # 시간 필터
        if keywords.get("time_filters"):
            time_filter = keywords["time_filters"][0]
            time_name = time_filter['name']
            
            if time_name in ['last_week', 'this_week']:
                where_parts.append(f"a.datekey >= {time_filter['sql']}")
            else:
                where_parts.append(f"a.datekey = {time_filter['sql']}")
        
        # 게임 필터 (JOIN이 있을 때만)
        if keywords.get("game_filters") and use_game_join:
            game_filter = keywords["game_filters"][0]
            joyple_code = game_filter.get('joyple_game_code')
            
            if joyple_code:
                where_parts.append(f"g.joyple_game_code = {joyple_code}")
        
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
            "explanation": self._generate_explanation(keywords),
            "debug": {
                "use_game_join": use_game_join,
                "game_filters": keywords.get("game_filters", [])
            }
        }
    
    def _generate_explanation(self, keywords: Dict[str, Any]) -> str:
        """생성된 쿼리에 대한 설명"""
        parts = []
        
        if keywords.get("entities"):
            parts.append(f"테이블: {', '.join(keywords['entities'])}")
        
        if keywords.get("aggregations"):
            parts.append(f"집계: {', '.join([a['name'] for a in keywords['aggregations']])}")
        
        if keywords.get("game_filters"):
            parts.append(f"게임: {', '.join([g.get('full_name', g.get('game_name', '')) for g in keywords['game_filters']])}")
        
        if keywords.get("time_filters"):
            parts.append(f"시간: {', '.join([t['name'] for t in keywords['time_filters']])}")
        
        return " | ".join(parts)