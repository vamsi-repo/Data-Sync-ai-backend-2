import time
import logging
import functools
from flask import request, session
from datetime import import datetime

class PerformanceMonitor:
    @staticmethod
    def monitor_endpoint(endpoint_name: str):
        """Decorator to monitor endpoint performance"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    logging.info(f"Endpoint {endpoint_name} executed successfully in {execution_time:.3f}s")
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    logging.error(f"Endpoint {endpoint_name} failed after {execution_time:.3f}s: {str(e)}")
                    raise
                
                return wrapper
            return decorator
    
    @staticmethod
    def log_request_info():
        """Log detailed request information"""
        user_id = session.get('user_id', 'anonymous')
        logging.info(f"Request: {request.method} {request.path} - User: {user_id} - IP: {request.remote_addr}")

# Application metrics collection
class ApplicationMetrics:
    @staticmethod
    def track_file_upload(filename: str, file_size: int, processing_time: float):
        """Track file upload metrics"""
        logging.info(f"File Upload Metrics - Name: {filename}, Size: {file_size} bytes, "
                    f"Processing Time: {processing_time:.3f}s")
    
    @staticmethod
    def track_validation_performance(template_id: int, row_count: int, error_count: int,
                                   validation_time: float):
        """Track validation performance metrics"""
        logging.info(f"Validation Metrics - Template: {template_id}, Rows: {row_count}, "
                    f"Errors: {error_count}, Time: {validation_time:.3f}s")