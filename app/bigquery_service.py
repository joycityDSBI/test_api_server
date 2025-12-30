from google.cloud import bigquery
import os
import pandas as pd
from typing import Optional

class BigQueryService:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID")
        # 서비스 계정 키가 있으면 사용, 없으면 Application Default Credentials 사용
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_path and os.path.exists(credentials_path):
            self.client = bigquery.Client.from_service_account_json(credentials_path)
        else:
            self.client = bigquery.Client(project=self.project_id)
    
    def run_query(self, query: str, max_results: int = 100):
        """BigQuery 쿼리 실행"""
        try:
            query_job = self.client.query(query)
            results = query_job.result(max_results=max_results)
            
            # DataFrame으로 변환
            df = results.to_dataframe()
            
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
                "size_mb": table.num_bytes / (1024 * 1024),
                "schema": schema
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# 싱글톤 인스턴스
bq_service = BigQueryService()