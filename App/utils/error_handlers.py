import logging
from flask import jsonify
from typing import Tuple

class ErrorHandler:
    @staticmethod
    def handle_validation_error(error: Exception, context: str) -> Tuple[dict, int]:
        """Handle validation-specific errors"""
        logging.error(f"Validation error in {context}: {str(error)}")
        return {
            'success': False,
            'message': f"Validation error: {str(error)}",
            'error_code': 'VALIDATION_ERROR',
            'context': context
        }, 400
    
    @staticmethod
    def handle_database_error(error: Exception, operation: str) -> Tuple[dict, int]:
        """Handle database-specific errors"""
        logging.error(f"Database error during {operation}: {str(error)}")
        return {
            'success': False,
            'message': 'Database operation failed',
            'error_code': 'DATABASE_ERROR',
            'operation': operation
        }, 500
    
    @staticmethod
    def handle_file_error(error: Exception, filename: str) -> Tuple[dict, int]:
        """Handle file operation errors"""
        logging.error(f"File error with {filename}: {str(error)}")
        return {
            'success': False,
            'message': f"File operation failed: {str(error)}",
            'error_code': 'FILE_ERROR',
            'filename': filename
        }, 400

# Standard error response decorators
def handle_errors(operation_name: str):
    """Decorator for consistent error handling"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValueError as ve:
                return ErrorHandler.handle_validation_error(ve, operation_name)
            except Exception as e:
                return ErrorHandler.handle_database_error(e, operation_name)
        return wrapper
    return decorator