from google.cloud import bigquery
import os
import pandas as pd
import numpy as np
from typing import Optional

class BigQueryService:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.client = None
        self.error = None
        
        try:
            # 서비스 계정 키가 있으면 사용
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if credentials_path and os.path.exists(credentials_path):
                self.client = bigquery.Client.from_service_account_json(credentials_path)
            elif self.project_id:
                # Application Default Credentials 사용
                self.client = bigquery.Client(project=self.project_id)
            else:
                self.error = "GCP_PROJECT_ID가 설정되지 않았습니다."
        except Exception as e:
            self.error = f"BigQuery 클라이언트 초기화 실패: {str(e)}"
            print(f"Warning: {self.error}")
    
    def is_available(self):
        """BigQuery 사용 가능 여부 확인"""
        return self.client is not None
    
    def clean_dataframe(self, df):
        """DataFrame의 NaN, Infinity 값을 JSON 호환 값으로 변환"""
        # NaN을 None으로 변환
        df = df.replace({np.nan: None})
        
        # Infinity 값 처리
        df = df.replace([np.inf, -np.inf], None)
        
        return df
    
    def run_query(self, query: str, max_results: int = 100):
        """BigQuery 쿼리 실행"""
        if not self.is_available():
            return {
                "success": False,
                "error": self.error or "BigQuery 클라이언트가 초기화되지 않았습니다."
            }
        
        try:
            query_job = self.client.query(query)
            results = query_job.result(max_results=max_results)
            
            # DataFrame으로 변환
            df = results.to_dataframe()
            
            # NaN/Infinity 값 처리
            df = self.clean_dataframe(df)
            
            return {
                "success": True,
                "row_count": len(df),
                "columns": df.columns.tolist(),
                "data": df.to_dict(orient='records')
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_table_schema(self, dataset_id: str, table_id: str):
        """테이블 스키마 조회"""
        if not self.is_available():
            return {
                "success": False,
                "error": self.error or "BigQuery 클라이언트가 초기화되지 않았습니다."
            }
        
        try:
            table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
            table = self.client.get_table(table_ref)
            
            schema = [
                {
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode
                }
                for field in table.schema
            ]
            
            return {
                "success": True,
                "table": table_ref,
                "row_count": table.num_rows,
                "size_mb": round(table.num_bytes / (1024 * 1024), 2),
                "schema": schema
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# 싱글톤 인스턴스
bq_service = BigQueryService()