# services/session_manager.py
"""
Session management service for handling user sessions and temporary data
"""

import logging
from typing import Dict, Any, List, Optional
from flask import session
from datetime import datetime, timedelta

class SessionManager:
    """Enhanced session management service"""

    @staticmethod
    def initialize_upload_session(file_path: str, template_id: int, df_json: str, 
                                 headers: List[str], sheet_name: str, header_row: int,
                                 has_existing_rules: bool = False, validations: Dict = None,
                                 selected_headers: List[str] = None):
        """Initialize session data for file upload process"""
        try:
            # Clear previous upload session data
            SessionManager.clear_upload_session()
            
            # Set new session data
            session_data = {
                'file_path': file_path,
                'template_id': template_id,
                'df': df_json,
                'headers': headers,
                'sheet_name': sheet_name,
                'header_row': header_row,
                'has_existing_rules': has_existing_rules,
                'current_step': 1 if not has_existing_rules else 3,
                'validations': validations or {},
                'selected_headers': selected_headers or [],
                'upload_timestamp': datetime.now().isoformat()
            }
            
            for key, value in session_data.items():
                session[key] = value
            
            logging.info(f"Upload session initialized for template {template_id}")
            return True
        except Exception as e:
            logging.error(f"Error initializing upload session: {str(e)}")
            return False

    @staticmethod
    def clear_upload_session():
        """Clear upload-related session data"""
        upload_keys = [
            'df', 'header_row', 'headers', 'sheet_name', 'current_step',
            'selected_headers', 'validations', 'error_cell_locations',
            'data_rows', 'corrected_file_path', 'file_path', 'template_id',
            'has_existing_rules', 'upload_timestamp', 'corrected_df'
        ]
        
        for key in upload_keys:
            session.pop(key, None)
        
        logging.debug("Upload session data cleared")

    @staticmethod
    def get_upload_session_data() -> Dict[str, Any]:
        """Get all upload-related session data"""
        upload_keys = [
            'file_path', 'template_id', 'df', 'headers', 'sheet_name', 'header_row',
            'current_step', 'selected_headers', 'validations', 'has_existing_rules',
            'error_cell_locations', 'data_rows', 'corrected_file_path', 'corrected_df'
        ]
        
        return {key: session.get(key) for key in upload_keys}

    @staticmethod
    def update_validation_step(step: int, validations: Dict = None, selected_headers: List[str] = None):
        """Update validation step in session"""
        session['current_step'] = step
        if validations is not None:
            session['validations'] = validations
        if selected_headers is not None:
            session['selected_headers'] = selected_headers
        
        logging.debug(f"Validation step updated to {step}")

    @staticmethod
    def set_validation_results(error_cell_locations: Dict, data_rows: List[Dict]):
        """Set validation results in session"""
        session['error_cell_locations'] = error_cell_locations
        session['data_rows'] = data_rows
        session['validation_timestamp'] = datetime.now().isoformat()
        
        logging.debug(f"Validation results set: {len(error_cell_locations)} columns with errors")

    @staticmethod
    def set_corrected_data(corrected_df_json: str, corrected_file_path: str):
        """Set corrected data in session"""
        session['corrected_df'] = corrected_df_json
        session['corrected_file_path'] = corrected_file_path
        session['correction_timestamp'] = datetime.now().isoformat()
        
        logging.debug(f"Corrected data set in session: {corrected_file_path}")

    @staticmethod
    def is_upload_session_valid() -> bool:
        """Check if upload session has required data"""
        required_keys = ['template_id', 'df', 'headers']
        return all(key in session for key in required_keys)

    @staticmethod
    def get_session_summary() -> Dict[str, Any]:
        """Get session summary for debugging"""
        return {
            'user_authenticated': 'user_id' in session,
            'user_id': session.get('user_id'),
            'upload_session_active': SessionManager.is_upload_session_valid(),
            'current_step': session.get('current_step'),
            'template_id': session.get('template_id'),
            'has_data': 'df' in session,
            'has_validations': bool(session.get('validations')),
            'has_corrections': 'corrected_df' in session,
            'session_keys_count': len(session.keys())
        }

    @staticmethod
    def cleanup_expired_data():
        """Clean up expired session data"""
        try:
            # Check upload timestamp
            upload_timestamp = session.get('upload_timestamp')
            if upload_timestamp:
                upload_time = datetime.fromisoformat(upload_timestamp)
                if datetime.now() - upload_time > timedelta(hours=24):
                    SessionManager.clear_upload_session()
                    logging.info("Expired upload session data cleaned up")
        except Exception as e:
            logging.error(f"Error cleaning up expired data: {str(e)}")

    @staticmethod
    def extend_session():
        """Extend session timeout"""
        session.permanent = True
        session['last_activity'] = datetime.now().isoformat()

    @staticmethod
    def get_session_age() -> Optional[timedelta]:
        """Get session age"""
        try:
            start_time = session.get('upload_timestamp') or session.get('last_activity')
            if start_time:
                return datetime.now() - datetime.fromisoformat(start_time)
        except Exception as e:
            logging.error(f"Error calculating session age: {str(e)}")
        return None

class TemporaryDataManager:
    """Manage temporary data storage during processing"""

    @staticmethod
    def store_processing_data(key: str, data: Any, ttl_minutes: int = 60):
        """Store temporary processing data with TTL"""
        session[f"temp_{key}"] = {
            'data': data,
            'expires_at': (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat()
        }

    @staticmethod
    def retrieve_processing_data(key: str) -> Optional[Any]:
        """Retrieve temporary processing data if not expired"""
        temp_key = f"temp_{key}"
        if temp_key in session:
            temp_data = session[temp_key]
            expires_at = datetime.fromisoformat(temp_data['expires_at'])
            if datetime.now() < expires_at:
                return temp_data['data']
            else:
                # Remove expired data
                session.pop(temp_key, None)
        return None

    @staticmethod
    def clear_processing_data(key: str = None):
        """Clear specific temporary data or all temporary data"""
        if key:
            session.pop(f"temp_{key}", None)
        else:
            # Clear all temporary data
            keys_to_remove = [k for k in session.keys() if k.startswith('temp_')]
            for k in keys_to_remove:
                session.pop(k, None)

    @staticmethod
    def cleanup_expired_temp_data():
        """Clean up all expired temporary data"""
        try:
            current_time = datetime.now()
            keys_to_remove = []
            
            for key, value in session.items():
                if key.startswith('temp_') and isinstance(value, dict):
                    expires_at = datetime.fromisoformat(value.get('expires_at', ''))
                    if current_time >= expires_at:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                session.pop(key, None)
            
            if keys_to_remove:
                logging.debug(f"Cleaned up {len(keys_to_remove)} expired temporary data items")
        except Exception as e:
            logging.error(f"Error cleaning up expired temporary data: {str(e)}")
