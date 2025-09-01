import os

class ProductionConfig:
    # Security hardening
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Database configuration
    DB_CONFIG = {
        'host': os.environ.get('DB_HOST'),
        'user': os.environ.get('DB_USER'),
        'password': os.environ.get('DB_PASSWORD'),
        'database': os.environ.get('DB_NAME'),
        'ssl_disabled': False,
        'charset': 'utf8mb4',
        'pool_size': 20,
        'pool_reset_session': True
    }
    
    # Performance settings
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB
    SEND_FILE_MAX_AGE_DEFAULT = 31536000    # 1 year for static files
    
    # Logging configuration
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s %(levelname)s [%(name)s] %(message)s'