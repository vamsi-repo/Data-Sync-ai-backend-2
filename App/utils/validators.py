import re
from typing import List, Tuple, Any, Dict
import logging

class InputValidator:
    @staticmethod
    def validate_required_fields(data: dict, required_fields: List[str]) -> Tuple[bool, List[str]]:
        """Validate that all required fields are present and non-empty"""
        missing_fields = [field for field in required_fields if not data.get(field) or str(data.get(field)).strip() == '']
        return len(missing_fields) == 0, missing_fields
    
    @staticmethod
    def validate_email_format(email: str) -> bool:
        """Comprehensive email format validation"""
        pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return bool(re.match(pattern, email)) and len(email) <= 255
    
    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """Validate password strength requirements"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'\d', password):
            return False, "Password must contain at least one digit"
        
        return True, "Password meets requirements"
    
    @staticmethod
    def validate_password_match(password: str, confirm_password: str) -> bool:
        """Validate password confirmation"""
        return password == confirm_password
    
    @staticmethod
    def validate_phone_number(phone: str) -> bool:
        """Validate phone number format"""
        # Remove common separators
        clean_phone = re.sub(r'[\s\-\(\)\.]+', '', phone)
        # Check if it's 10 digits (adjust pattern as needed)
        return bool(re.match(r'^\d{10}$', clean_phone))
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str] = None) -> bool:
        """Validate file extension"""
        if allowed_extensions is None:
            allowed_extensions = ['.xlsx', '.xls', '.csv', '.txt', '.dat']
        
        file_ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        return file_ext in allowed_extensions
    
    @staticmethod
    def validate_file_size(file_size_bytes: int, max_size_mb: int = 100) -> bool:
        """Validate file size"""
        max_size_bytes = max_size_mb * 1024 * 1024
        return file_size_bytes <= max_size_bytes
    
    @staticmethod
    def validate_template_id(template_id: Any) -> bool:
        """Validate template ID format"""
        try:
            return isinstance(template_id, int) and template_id > 0
        except:
            return False
    
    @staticmethod
    def validate_json_structure(data: Dict, required_structure: Dict) -> Tuple[bool, str]:
        """Validate JSON data structure"""
        try:
            for key, expected_type in required_structure.items():
                if key not in data:
                    return False, f"Missing required key: {key}"
                
                if not isinstance(data[key], expected_type):
                    return False, f"Invalid type for {key}: expected {expected_type.__name__}"
            
            return True, "Valid structure"
        except Exception as e:
            return False, f"Structure validation error: {str(e)}"
    
    @staticmethod
    def validate_formula_syntax(formula: str, column_name: str, available_columns: List[str] = None) -> Tuple[bool, str]:
        """Comprehensive formula syntax validation for custom rules"""
        try:
            column_name = column_name.strip().lower()
            
            # Check if formula starts with column name in quotes
            if not formula.startswith(f"'{column_name}'"):
                return False, "Formula must start with 'column_name' in quotes"
            
            is_arithmetic = ' = ' in formula
            
            if is_arithmetic:
                # Validate arithmetic formula: 'column_name = expression'
                formula_parts = formula.strip().split(' = ', 1)
                if len(formula_parts) != 2 or formula_parts[0] != f"'{column_name}'":
                    return False, "Arithmetic formula must be 'column_name = expression'"
                
                # Check for required operators and columns
                expression = formula_parts[1]
                arithmetic_operators = ['+', '-', '/', '*', '%', 'AND', 'OR']
                
                # Find column references in quotes
                column_refs = re.findall(r"'([^']+)'", expression)
                
                # Check if referenced columns exist
                if available_columns:
                    for col_ref in column_refs:
                        if col_ref.lower() not in [c.lower() for c in available_columns]:
                            return False, f"Referenced column '{col_ref}' not found in available columns"
                
                # Check for operators
                has_operator = any(op in expression for op in arithmetic_operators)
                if not has_operator:
                    return False, "Arithmetic formula must contain at least one operator (+, -, /, *, %, AND, OR)"
            else:
                # Validate comparison formula: 'column_name <operator> operand'
                parts = formula.strip().split(' ')
                if len(parts) < 3 or parts[0] != f"'{column_name}'" or parts[1] not in ['=', '>', '<', '>=', '<=']:
                    return False, "Comparison formula must be 'column_name <operator> operand'"
                
                # Validate operand (must be number or column reference)
                operand = ' '.join(parts[2:])  # Handle multi-word operands
                
                # Check if operand is a number
                try:
                    float(operand)
                except ValueError:
                    # Check if it's a column reference
                    if operand.startswith("'") and operand.endswith("'"):
                        col_ref = operand[1:-1]
                        if available_columns and col_ref.lower() not in [c.lower() for c in available_columns]:
                            return False, f"Referenced column '{col_ref}' not found in available columns"
                    else:
                        return False, "Operand must be a number or a column reference in quotes"
            
            return True, "Valid formula"
            
        except Exception as e:
            return False, f"Formula validation error: {str(e)}"
    
    @staticmethod
    def validate_sftp_config(config: Dict) -> Tuple[bool, str]:
        """Validate SFTP configuration"""
        required_fields = ['hostname', 'username', 'password']
        is_valid, missing = InputValidator.validate_required_fields(config, required_fields)
        
        if not is_valid:
            return False, f"Missing required SFTP fields: {', '.join(missing)}"
        
        # Validate hostname format
        hostname = config['hostname']
        if not re.match(r'^[a-zA-Z0-9\.-]+$', hostname):
            return False, "Invalid hostname format"
        
        # Validate port if provided
        port = config.get('port', 22)
        try:
            port = int(port)
            if not (1 <= port <= 65535):
                return False, "Port must be between 1 and 65535"
        except (ValueError, TypeError):
            return False, "Invalid port number"
        
        return True, "Valid SFTP configuration"
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove or replace problematic characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Ensure it's not too long
        if len(sanitized) > 200:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            sanitized = name[:200-len(ext)-1] + ('.' + ext if ext else '')
        
        return sanitized.strip('_')
    
    @staticmethod
    def validate_date_format(date_string: str, expected_formats: List[str]) -> Tuple[bool, str]:
        """Validate date string against expected formats"""
        from datetime import datetime
        
        for fmt in expected_formats:
            try:
                datetime.strptime(date_string, fmt)
                return True, fmt
            except ValueError:
                continue
        
        return False, f"Date does not match any expected format: {expected_formats}"
    
    @staticmethod
    def validate_numeric_range(value: Any, min_value: float = None, max_value: float = None) -> Tuple[bool, str]:
        """Validate numeric value is within specified range"""
        try:
            num_value = float(value)
            
            if min_value is not None and num_value < min_value:
                return False, f"Value {num_value} is below minimum {min_value}"
            
            if max_value is not None and num_value > max_value:
                return False, f"Value {num_value} is above maximum {max_value}"
            
            return True, "Valid numeric value"
        except (ValueError, TypeError):
            return False, f"'{value}' is not a valid number"
    
    @staticmethod
    def validate_column_names(column_names: List[str]) -> Tuple[bool, str]:
        """Validate column names for safety and consistency"""
        if not column_names:
            return False, "No column names provided"
        
        # Check for duplicates
        if len(column_names) != len(set(column_names)):
            return False, "Duplicate column names found"
        
        # Check for empty or whitespace-only names
        for i, name in enumerate(column_names):
            if not name or not str(name).strip():
                return False, f"Column name at position {i+1} is empty or whitespace"
        
        # Check for problematic characters
        problematic_chars = ['<', '>', '"', "'", '&', '\n', '\r', '\t']
        for name in column_names:
            if any(char in str(name) for char in problematic_chars):
                return False, f"Column name '{name}' contains problematic characters"
        
        return True, "Valid column names"

class DataValidator:
    """Data validation utilities for business logic"""
    
    @staticmethod
    def validate_correction_data(corrections: Dict, available_columns: List[str]) -> Tuple[bool, str]:
        """Validate correction data structure"""
        if not isinstance(corrections, dict):
            return False, "Corrections must be a dictionary"
        
        for column, row_corrections in corrections.items():
            if column not in available_columns:
                return False, f"Column '{column}' not found in available columns"
            
            if not isinstance(row_corrections, dict):
                return False, f"Row corrections for column '{column}' must be a dictionary"
            
            for row_index, value in row_corrections.items():
                try:
                    int(row_index)  # Validate row index is numeric
                except ValueError:
                    return False, f"Invalid row index '{row_index}' for column '{column}'"
        
        return True, "Valid correction data"
    
    @staticmethod
    def validate_template_data(template_data: Dict) -> Tuple[bool, str]:
        """Validate template data structure"""
        required_fields = ['template_name', 'sheet_name', 'headers']
        is_valid, missing = InputValidator.validate_required_fields(template_data, required_fields)
        
        if not is_valid:
            return False, f"Missing template fields: {', '.join(missing)}"
        
        # Validate headers
        headers = template_data.get('headers', [])
        if not isinstance(headers, list) or len(headers) == 0:
            return False, "Headers must be a non-empty list"
        
        headers_valid, headers_msg = InputValidator.validate_column_names(headers)
        if not headers_valid:
            return False, f"Invalid headers: {headers_msg}"
        
        return True, "Valid template data"
