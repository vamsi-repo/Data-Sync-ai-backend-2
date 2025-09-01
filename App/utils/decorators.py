# utils/decorators.py
"""
Common decorators for authentication, validation, and error handling
"""

from functools import wraps
from flask import session, jsonify, request
import logging
from typing import Callable, Any

def require_auth(f: Callable) -> Callable:
    """Decorator to require user authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session or 'user_id' not in session:
            logging.warning(f"Unauthorized access to {request.endpoint}: session missing")
            return jsonify({'success': False, 'message': 'Not logged in'}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_json(f: Callable) -> Callable:
    """Decorator to require JSON request data"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({'success': False, 'message': 'Request must be JSON'}), 400
        return f(*args, **kwargs)
    return decorated_function

def validate_form_fields(required_fields: list):
    """Decorator to validate required form fields"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json() if request.is_json else request.form.to_dict()
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                return jsonify({
                    'success': False, 
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }), 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def handle_exceptions(f: Callable) -> Callable:
    """Decorator to handle exceptions and return JSON error responses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logging.error(f"Exception in {f.__name__}: {str(e)}")
            return jsonify({'success': False, 'message': f'Internal server error: {str(e)}'}), 500
    return decorated_function

def log_requests(f: Callable) -> Callable:
    """Decorator to log incoming requests"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logging.info(f"Request to {request.endpoint}: {request.method} {request.url}")
        if request.is_json:
            logging.debug(f"Request JSON: {request.get_json()}")
        return f(*args, **kwargs)
    return decorated_function

def validate_template_access(f: Callable) -> Callable:
    """Decorator to validate user access to template"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from config.database import get_db_connection
        
        template_id = kwargs.get('template_id')
        if not template_id:
            return jsonify({'success': False, 'message': 'Template ID required'}), 400
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT template_id FROM excel_templates 
                WHERE template_id = %s AND user_id = %s AND status = 'ACTIVE'
            """, (template_id, session['user_id']))
            template = cursor.fetchone()
            cursor.close()
            
            if not template:
                return jsonify({'success': False, 'message': 'Template not found or access denied'}), 404
                
        except Exception as e:
            logging.error(f"Error validating template access: {str(e)}")
            return jsonify({'success': False, 'message': 'Database error'}), 500
        
        return f(*args, **kwargs)
    return decorated_function

def rate_limit(max_requests: int = 100, window_minutes: int = 15):
    """Simple rate limiting decorator"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Simple rate limiting implementation
            # In production, use Redis or more sophisticated solution
            user_id = session.get('user_id', 'anonymous')
            
            # For now, just log the attempt
            logging.debug(f"Rate limit check for user {user_id}: {request.endpoint}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f: Callable) -> Callable:
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') != 1:  # Admin user ID is 1
            return jsonify({'success': False, 'message': 'Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated_function
