import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Security settings
    SECRET_KEY = os.urandom(24).hex()
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # File upload settings
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    UPLOAD_EXTENSIONS = ['.xlsx', '.xls', '.csv', '.txt']
    
    # CORS settings
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8080", "*"]
    
    @staticmethod
    def init_directories():
        """Initialize required directories"""
        # Session directory
        session_dir = '/tmp/sessions' if os.path.exists('/tmp') else './sessions'
        os.makedirs(session_dir, exist_ok=True)
        
        # Upload directory
        upload_dir = '/tmp/uploads' if os.path.exists('/tmp') else './uploads'
        os.makedirs(upload_dir, exist_ok=True)
        
        return session_dir, upload_dir