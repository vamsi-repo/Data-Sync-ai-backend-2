# services/authentication.py
"""
Authentication service layer for handling user sessions and security
"""

import logging
import secrets
from typing import Optional, Dict, Any
from flask import session
from datetime import datetime, timedelta
from models.user import User

class AuthenticationService:
    @staticmethod
    def login_user(email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user and create session
        Returns dict with success status, message, and user data
        """
        try:
            # Authenticate user
            user = User.authenticate_user(email, password)
            if user:
                # Create session
                session['loggedin'] = True
                session['user_email'] = user['email']
                session['user_id'] = user['id']
                session.permanent = True
                
                logging.info(f"User {email} logged in successfully")
                return {
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'id': user['id'],
                        'email': user['email'],
                        'first_name': user['first_name'],
                        'last_name': user['last_name']
                    }
                }
            else:
                logging.warning(f"Failed login attempt for {email}")
                return {
                    'success': False,
                    'message': 'Invalid credentials'
                }
        except Exception as e:
            logging.error(f"Authentication error: {str(e)}")
            return {
                'success': False,
                'message': 'Authentication system error'
            }

    @staticmethod
    def logout_user() -> Dict[str, Any]:
        """Logout user and clear session"""
        try:
            user_email = session.get('user_email')
            session.clear()
            logging.info(f"User {user_email} logged out successfully")
            return {
                'success': True,
                'message': 'Logged out successfully'
            }
        except Exception as e:
            logging.error(f"Logout error: {str(e)}")
            return {
                'success': False,
                'message': 'Logout error'
            }

    @staticmethod
    def check_authentication() -> Dict[str, Any]:
        """Check if user is authenticated"""
        try:
            if 'loggedin' in session and 'user_id' in session:
                user = User.get_user_by_id(session['user_id'])
                if user:
                    return {
                        'success': True,
                        'user': {
                            'id': user['id'],
                            'email': user['email'],
                            'first_name': user['first_name'],
                            'last_name': user['last_name']
                        }
                    }
                else:
                    session.clear()
                    return {'success': False, 'message': 'User not found'}
            return {'success': False, 'message': 'Not logged in'}
        except Exception as e:
            logging.error(f"Auth check error: {str(e)}")
            return {'success': False, 'message': 'Authentication check failed'}

    @staticmethod
    def register_user(first_name: str, last_name: str, email: str, 
                     mobile: str, password: str, confirm_password: str) -> Dict[str, Any]:
        """Register new user"""
        try:
            # Validate password confirmation
            if password != confirm_password:
                return {'success': False, 'message': 'Passwords do not match'}
            
            # Create user
            user_id = User.create_user(first_name, last_name, email, mobile, password)
            
            # Auto-login after registration
            session['loggedin'] = True
            session['user_email'] = email
            session['user_id'] = user_id
            session.permanent = True
            
            logging.info(f"New user registered and logged in: {email}")
            return {
                'success': True,
                'message': 'Registration successful',
                'user': {'id': user_id, 'email': email}
            }
        except Exception as e:
            logging.error(f"Registration error: {str(e)}")
            return {
                'success': False,
                'message': f'Registration error: {str(e)}'
            }

    @staticmethod
    def reset_user_password(email: str, new_password: str, confirm_password: str) -> Dict[str, Any]:
        """Reset user password"""
        try:
            if new_password != confirm_password:
                return {'success': False, 'message': 'Passwords do not match'}
            
            success = User.reset_password(email, new_password)
            if success:
                logging.info(f"Password reset successful for {email}")
                return {'success': True, 'message': 'Password reset successful'}
            else:
                return {'success': False, 'message': 'Email not found'}
        except Exception as e:
            logging.error(f"Password reset error: {str(e)}")
            return {
                'success': False,
                'message': f'Password reset error: {str(e)}'
            }

    @staticmethod
    def is_authenticated() -> bool:
        """Simple boolean check for authentication"""
        return 'loggedin' in session and 'user_id' in session

    @staticmethod
    def get_current_user_id() -> Optional[int]:
        """Get current user ID from session"""
        return session.get('user_id')

    @staticmethod
    def get_current_user_email() -> Optional[str]:
        """Get current user email from session"""
        return session.get('user_email')

    @staticmethod
    def generate_session_token() -> str:
        """Generate secure session token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_session_timeout() -> bool:
        """Check if session has timed out"""
        try:
            if 'session_start' not in session:
                session['session_start'] = datetime.now()
                return True
            
            session_start = session.get('session_start')
            if isinstance(session_start, str):
                session_start = datetime.fromisoformat(session_start)
            
            timeout_hours = 24  # 24 hour timeout
            if datetime.now() - session_start > timedelta(hours=timeout_hours):
                session.clear()
                return False
            
            return True
        except Exception as e:
            logging.error(f"Session timeout validation error: {str(e)}")
            return False

class SessionManager:
    """Session management utilities"""
    
    @staticmethod
    def clear_session_data(keys_to_keep: list = None):
        """Clear session data except specified keys"""
        if keys_to_keep is None:
            keys_to_keep = ['loggedin', 'user_id', 'user_email']
        
        keys_to_remove = [key for key in session.keys() if key not in keys_to_keep]
        for key in keys_to_remove:
            session.pop(key, None)
        
        logging.debug(f"Cleared session data, kept: {keys_to_keep}")

    @staticmethod
    def set_session_data(data: Dict[str, Any]):
        """Set multiple session values"""
        for key, value in data.items():
            session[key] = value

    @staticmethod
    def get_session_info() -> Dict[str, Any]:
        """Get session information for debugging"""
        return {
            'user_id': session.get('user_id'),
            'user_email': session.get('user_email'),
            'loggedin': session.get('loggedin', False),
            'session_keys': list(session.keys())
        }
