import bcrypt
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from config.database import get_db_connection

class User:
    @staticmethod
    def create_admin_user():
        """Create default admin user from original app.py"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            admin_password = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("""
                INSERT IGNORE INTO login_details (first_name, last_name, email, mobile, password)
                VALUES (%s, %s, %s, %s, %s)
            """, ('Admin', 'User', 'admin@example.com', '1234567890', admin_password))
            conn.commit()
            cursor.close()
            logging.info("Admin user created or already exists")
        except Exception as e:
            logging.error(f"Failed to create admin user: {str(e)}")
            raise

    @staticmethod
    def authenticate_user(email: str, password: str) -> Optional[Dict]:
        """Authenticate user with email and password"""
        try:
            # Handle admin login
            if email == "admin" and password == "admin":
                return {
                    'id': 1,
                    'email': 'admin@example.com',
                    'first_name': 'Admin',
                    'last_name': 'User'
                }
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM login_details WHERE LOWER(email) = LOWER(%s)", (email.lower(),))
            account = cursor.fetchone()
            cursor.close()
            
            if account and bcrypt.checkpw(password.encode('utf-8'), account['password'].encode('utf-8')):
                return {
                    'id': account['id'],
                    'email': account['email'],
                    'first_name': account['first_name'],
                    'last_name': account['last_name']
                }
            return None
        except Exception as e:
            logging.error(f"Authentication error: {str(e)}")
            return None

    @staticmethod
    def create_user(first_name: str, last_name: str, email: str, mobile: str, password: str) -> int:
        """Create new user from original app.py"""
        try:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO login_details (first_name, last_name, email, mobile, password)
                VALUES (%s, %s, %s, %s, %s)
            """, (first_name, last_name, email, mobile, hashed_password))
            user_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            return user_id
        except Exception as e:
            logging.error(f"User creation error: {str(e)}")
            raise

    @staticmethod
    def reset_password(email: str, new_password: str) -> bool:
        """Reset user password"""
        try:
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE login_details SET password = %s WHERE email = %s", (hashed_password, email))
            success = cursor.rowcount > 0
            conn.commit()
            cursor.close()
            return success
        except Exception as e:
            logging.error(f"Password reset error: {str(e)}")
            return False

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, email, first_name, last_name FROM login_details WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            cursor.close()
            return user
        except Exception as e:
            logging.error(f"Error fetching user: {str(e)}")
            return None

    @staticmethod
    def create_user_with_verification(first_name: str, last_name: str, email: str,
                                    mobile: str, password: str) -> Tuple[int, str]:
        """Create user with email verification token"""
        try:
            # Generate secure password hash
            salt = bcrypt.gensalt(rounds=12)  # Higher rounds for better security
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            
            # Generate verification token
            verification_token = secrets.token_urlsafe(32)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO login_details
                (first_name, last_name, email, mobile, password, verification_token, is_verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, email, mobile, hashed_password, verification_token, False))
            
            user_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            
            return user_id, verification_token
            
        except Exception as e:
            logging.error(f"Enhanced user creation error: {str(e)}")
            raise
    
    @staticmethod
    def verify_user_email(verification_token: str) -> bool:
        """Verify user email with token"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE login_details
                SET is_verified = TRUE, verification_token = NULL
                WHERE verification_token = %s AND is_verified = FALSE
            """, (verification_token,))
            
            success = cursor.rowcount > 0
            conn.commit()
            cursor.close()
            
            return success
            
        except Exception as e:
            logging.error(f"Email verification error: {str(e)}")
            return False
    
    @staticmethod
    def create_password_reset_token(email: str) -> Optional[str]:
        """Create secure password reset token"""
        try:
            token = secrets.token_urlsafe(32)
            expiry = datetime.now() + timedelta(hours=1)  # 1-hour expiry
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE login_details
                SET reset_token = %s, reset_token_expiry = %s
                WHERE email = %s AND is_verified = TRUE
            """, (token, expiry, email))
            
            if cursor.rowcount > 0:
                conn.commit()
                cursor.close()
                return token
            else:
                cursor.close()
                return None
                
        except Exception as e:
            logging.error(f"Password reset token creation error: {str(e)}")
            return None

    @staticmethod
    def validate_reset_token(token: str) -> Optional[str]:
        """Validate password reset token and return email if valid"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT email FROM login_details 
                WHERE reset_token = %s AND reset_token_expiry > %s
            """, (token, datetime.now()))
            
            result = cursor.fetchone()
            cursor.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logging.error(f"Reset token validation error: {str(e)}")
            return None

    @staticmethod
    def update_user_profile(user_id: int, first_name: str, last_name: str, mobile: str) -> bool:
        """Update user profile information"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE login_details 
                SET first_name = %s, last_name = %s, mobile = %s 
                WHERE id = %s
            """, (first_name, last_name, mobile, user_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            cursor.close()
            return success
            
        except Exception as e:
            logging.error(f"Profile update error: {str(e)}")
            return False
