import yaml
from typing import Dict, List, Optional, Any
import re

class KnowledgeGraphParser:
    def __init__(self, schema_path: str = "knowledge_graph/schema.yml"):
        with open(schema_path, 'r', encoding='utf-8') as f:
            self.schema = yaml.safe_load(f)
        
        self.entities = self.schema.get('entities', {})
        self.relationships = self.schema.get('relationships', [])
        self.aggregations = self.schema.get('aggregations', {})
        self.time_expressions = self.schema.get('time_expressions', {})
        self.filters = self.schema.get('filters', {})
    
    def extract_keywords(self, query: str) -> Dict[str, Any]:
        """자연어 질의에서 키워드 추출"""
        query_lower = query.lower()
        
        result = {
            "entities": [],
            "columns": [],
            "aggregations": [],
            "time_filters": [],
            "conditions": [],
            "raw_query": query
        }
        
        # 엔티티 추출
        for entity_name, entity_info in self.entities.items():
            # 엔티티 이름 매칭
            if entity_name in query_lower:
                result["entities"].append(entity_name)
                continue
            
            # 별칭 매칭
            for alias in entity_info.get('aliases', []):
                if alias in query_lower:
                    result["entities"].append(entity_name)
                    break
            
            # 컬럼 추출
            for col_name, col_info in entity_info.get('columns', {}).items():
                if col_name in query_lower:
                    result["columns"].append({
                        "entity": entity_name,
                        "column": col_name,
                        "type": col_info.get('type')
                    })
                    continue
                
                # 컬럼 별칭 매칭
                for alias in col_info.get('aliases', []):
                    if alias in query_lower:
                        result["columns"].append({
                            "entity": entity_name,
                            "column": col_name,
                            "type": col_info.get('type')
                        })
                        break
        
        # 집계 함수 추출
        for agg_name, agg_info in self.aggregations.items():
            for alias in agg_info.get('aliases', []):
                if alias in query_lower:
                    result["aggregations"].append({
                        "name": agg_name,
                        "function": agg_info.get('function')
                    })
                    break
        
        # 시간 표현 추출
        for time_name, time_info in self.time_expressions.items():
            for alias in time_info.get('aliases', []):
                if alias in query_lower:
                    result["time_filters"].append({
                        "name": time_name,
                        "sql": time_info.get('sql')
                    })
                    break
        
        # 숫자 추출
        numbers = re.findall(r'\d+', query)
        result["numbers"] = [int(n) for n in numbers]
        
        return result
    
    def get_table_name(self, entity: str) -> str:
        """엔티티로부터 실제 테이블명 가져오기"""
        return self.entities.get(entity, {}).get('table', '')
    
    def find_relationship(self, entity1: str, entity2: str) -> Optional[Dict]:
        """두 엔티티 간의 관계 찾기"""
        for rel in self.relationships:
            if (rel['from'] == entity1 and rel['to'] == entity2) or \
               (rel['from'] == entity2 and rel['to'] == entity1):
                return rel
        return None