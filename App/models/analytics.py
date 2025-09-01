import time
import logging
import json
from datetime import import datetime
from typing import Dict, List
from flask import session, request

class PerformanceAnalytics:
    @staticmethod
    def track_endpoint_performance(endpoint: str, execution_time: float,
                                  success: bool, error_type: str = None):
        """Track endpoint performance metrics"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'endpoint': endpoint,
            'execution_time': execution_time,
            'success': success,
            'error_type': error_type,
            'user_id': session.get('user_id'),
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')[:100]
        }
        
        # Log metrics (in production, send to monitoring service)
        logging.info(f"METRICS: {json.dumps(metrics)}")
    
    @staticmethod
    def track_file_processing_metrics(file_name: str, file_size: int,
                                    processing_stages: Dict[str, float]):
        """Track detailed file processing performance"""
        total_time = sum(processing_stages.values())
        
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'operation': 'file_processing',
            'file_name': file_name,
            'file_size_mb': file_size / (1024 * 1024),
            'total_processing_time': total_time,
            'stage_breakdown': processing_stages,
            'processing_rate_mb_per_sec': (file_size / (1024 * 1024)) / total_time if total_time > 0 else 0
        }
        
        logging.info(f"FILE_METRICS: {json.dumps(metrics)}")
    
    @staticmethod
    def track_validation_metrics(template_id: int, validation_type: str,
                               row_count: int, error_count: int, validation_time: float):
        """Track validation performance and accuracy"""
        error_rate = (error_count / row_count) * 100 if row_count > 0 else 0
        
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'operation': 'validation',
            'template_id': template_id,
            'validation_type': validation_type,
            'row_count': row_count,
            'error_count': error_count,
            'error_rate_percent': error_rate,
            'validation_time': validation_time,
            'rows_per_second': row_count / validation_time if validation_time > 0 else 0
        }
        
        logging.info(f"VALIDATION_METRICS: {json.dumps(metrics)}")