import re
import html
import logging
from typing import Any, Dict, List

class SecurityValidator:
    # Dangerous patterns to block
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',                # JavaScript protocol
        r'on\w+\s*=',                 # Event handlers
        r'<iframe[^>]*>.*?</iframe>', # Iframe tags
        r'<object[^>]*>.*?</object>', # Object tags
        r'<embed[^>]*>.*?</embed>',   # Embed tags
    ]
    
    @staticmethod
    def sanitize_input(value: Any) -> str:
        """Comprehensive input sanitization"""
        if value is None:
            return ""
        
        # Convert to string and strip whitespace
        clean_value = str(value).strip()
        
        # HTML encode dangerous characters
        clean_value = html.escape(clean_value)
        
        # Check for dangerous patterns
        for pattern in SecurityValidator.DANGEROUS_PATTERNS:
            if re.search(pattern, clean_value, re.IGNORECASE):
                logging.warning(f"Blocked dangerous pattern in input: {pattern}")
                clean_value = re.sub(pattern, '', clean_value, flags=re.IGNORECASE)
        
        return clean_value
    
    @staticmethod
    def validate_file_upload(file) -> Tuple[bool, str]:
        """Comprehensive file upload validation"""
        # Check file size
        if file.content_length and file.content_length > 100 * 1024 * 1024:  # 100MB
            return False, "File too large (max 100MB)"
        
        # Check file extension
        allowed_extensions = ['.xlsx', '.xls', '.csv', '.txt']
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return False, f"File type not allowed. Supported: {', '.join(allowed_extensions)}"
        
        # Check filename for dangerous characters
        if re.search(r'[<>"|?*]', file.filename):
            return False, "Filename contains invalid characters"
        
        return True, "File validation passed"
    
    @staticmethod
    def sanitize_form_data(form_data: Dict) -> Dict:
        """Sanitize all form data recursively"""
        sanitized = {}
        
        for key, value in form_data.items():
            sanitized_key = SecurityValidator.sanitize_input(key)
            if isinstance(value, dict):
                sanitized[sanitized_key] = SecurityValidator.sanitize_form_data(value)
            elif isinstance(value, list):
                sanitized[sanitized_key] = [SecurityValidator.sanitize_input(item) for item in value]
            else:
                sanitized[sanitized_key] = SecurityValidator.sanitize_input(value)
        
        return sanitized