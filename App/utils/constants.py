# utils/constants.py
"""
Application constants and configuration values
"""

# File processing constants
SUPPORTED_FILE_EXTENSIONS = ['.xlsx', '.xls', '.csv', '.txt', '.dat']
MAX_FILE_SIZE_MB = 100
MAX_HEADER_DETECTION_ROWS = 10

# Session configuration
SESSION_TIMEOUT_HOURS = 24
DEFAULT_SESSION_TYPE = 'filesystem'

# Database configuration
DEFAULT_DB_POOL_SIZE = 10
DB_CONNECTION_TIMEOUT = 30

# Validation constants
DEFAULT_DATE_FORMATS = [
    '%d-%m-%Y', '%m-%d-%Y', '%m/%d/%Y', '%d/%m/%Y',
    '%m-%Y', '%m-%y', '%m/%Y', '%m/%y'
]

DATE_FORMAT_MAPPING = {
    'MM-DD-YYYY': '%m-%d-%Y', 
    'DD-MM-YYYY': '%d-%m-%Y', 
    'MM/DD/YYYY': '%m/%d/%Y', 
    'DD/MM/YYYY': '%d/%m/%Y',
    'MM-YYYY': '%m-%Y', 
    'MM-YY': '%m-%y', 
    'MM/YYYY': '%m/%Y', 
    'MM/YY': '%m/%y'
}

# Validation rules
DEFAULT_VALIDATION_RULES = [
    ("Required", "Ensures the field is not null", '{"allow_null": false}'),
    ("Int", "Validates integer format", '{"format": "integer"}'),
    ("Float", "Validates number format (integer or decimal)", '{"format": "float"}'),
    ("Text", "Allows text with quotes and parentheses", '{"allow_special": false}'),
    ("Email", "Validates email format", '{"regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\\\.[a-zA-Z0-9-.]+$"}'),
    ("Date", "Validates date", '{"format": "%d-%m-%Y"}'),
    ("Boolean", "Validates boolean format (true/false or 0/1)", '{"format": "boolean"}'),
    ("Alphanumeric", "Validates alphanumeric format", '{"format": "alphanumeric"}')
]

# Error messages
ERROR_MESSAGES = {
    'FILE_NOT_FOUND': 'File not found',
    'INVALID_FILE_TYPE': 'Unsupported file type',
    'FILE_TOO_LARGE': 'File size exceeds maximum limit',
    'NO_HEADERS_FOUND': 'No valid headers found in the file',
    'UNAUTHORIZED': 'Not logged in or unauthorized access',
    'INVALID_CREDENTIALS': 'Invalid email or password',
    'PASSWORDS_DONT_MATCH': 'Passwords do not match',
    'EMAIL_EXISTS': 'Email already registered',
    'TEMPLATE_NOT_FOUND': 'Template not found',
    'VALIDATION_FAILED': 'Data validation failed',
    'DATABASE_ERROR': 'Database operation failed',
    'SESSION_EXPIRED': 'Session has expired'
}

# Success messages
SUCCESS_MESSAGES = {
    'LOGIN_SUCCESS': 'Login successful',
    'REGISTRATION_SUCCESS': 'Registration successful',
    'PASSWORD_RESET_SUCCESS': 'Password reset successful',
    'TEMPLATE_DELETED': 'Template deleted successfully',
    'VALIDATION_SAVED': 'Validation rules saved successfully',
    'CORRECTIONS_APPLIED': 'Corrections applied successfully',
    'FILE_UPLOADED': 'File uploaded successfully'
}

# Regex patterns
REGEX_PATTERNS = {
    'EMAIL': r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$',
    'INTEGER': r'^-?\d+$',
    'FLOAT': r'^-?\d+(\.\d+)?$',
    'ALPHANUMERIC': r'^[a-zA-Z0-9]+$',
    'BOOLEAN': r'^(true|false|0|1)$'
}

# File cleanup settings
TEMP_FILE_CLEANUP_HOURS = 24
BACKUP_RETENTION_DAYS = 30

# Application settings
APP_VERSION = '2.0.0'
DEFAULT_CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8080", "*"]

# Logging configuration
LOG_FORMAT = '%(asctime)s %(levelname)s: %(message)s'
LOG_LEVEL = 'INFO'
