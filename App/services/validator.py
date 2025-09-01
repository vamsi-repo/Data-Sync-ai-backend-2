import pandas as pd
import re
import json
import logging
import operator
from datetime import datetime
from typing import List, Tuple, Dict
from config.database import get_db_connection

class DataValidator:
    @staticmethod
    def detect_column_types(series: pd.Series) -> str:
        """Automatically detect column data type using pattern analysis"""
        non_null = series.dropna().astype(str)
        if non_null.empty:
            return "Text"
        
        # Email pattern detection
        if non_null.str.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$').all():
            return "Email"
        
        # Date pattern detection
        try:
            pd.to_datetime(non_null, format="%d-%m-%Y")
            return "Date"
        except Exception:
            try:
                pd.to_datetime(non_null, format="%Y-%m-%d")
                return "Date"
            except Exception:
                pass
        
        # Boolean detection
        if non_null.str.lower().isin(['true', 'false', '0', '1']).all():
            return "Boolean"
        
        # Numeric detection
        if non_null.str.match(r'^-?\d+$').all():
            return "Int"
        
        if non_null.str.match(r'^-?\d+(\.\d+)?$').all():
            return "Float"
        
        # Alphanumeric detection
        if non_null.str.match(r'^[a-zA-Z0-9]+$').all():
            return "Alphanumeric"
        
        return "Text"
    
    @staticmethod
    def assign_default_rules(df: pd.DataFrame, headers: List[str]) -> Dict[str, List[str]]:
        """Intelligently assign validation rules based on column content"""
        assignments = {}
        
        for col in headers:
            col_type = DataValidator.detect_column_type(df[col])
            rules = ["Required"]  # Default rule for all columns
            
            # Special handling for optional columns
            if not any(col.lower().startswith(prefix) for prefix in
                      ["name", "address", "phone", "username", "status", "period"]):
                rules.append(col_type)
            else:
                rules.append("Text")  # Optional text fields
            
            assignments[col] = rules
        
        return assignments
    
    @staticmethod
    def check_column_validation(df: pd.DataFrame, col_name: str, metadata_type: str,
                               accepted_date_formats: List[str], check_null_cells: bool = True) -> Tuple[int, List[Tuple]]:
        """Comprehensive column validation with detailed error reporting"""
        try:
            special_char_count, error_cell_locations = 0, []
            
            # Get rule configuration from database
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT parameters, is_custom, source_format, data_type
                FROM validation_rule_types
                WHERE rule_name = %s
            """, (metadata_type,))
            rule_data = cursor.fetchone()
            cursor.close()
            
            # Handle date format specifics
            accepted_formats = accepted_date_formats
            if metadata_type.startswith("Date(") and rule_data and rule_data['source_format']:
                format_map = {
                    'MM-DD-YYYY': '%m-%d-%Y', 'DD-MM-YYYY': '%d-%m-%Y',
                    'MM/DD/YYYY': '%m/%d/%Y', 'DD/MM/YYYY': '%d/%m/%Y',
                    'MM-YYYY': '%m-%Y', 'MM-YY': '%m-%y',
                    'MM/YYYY': '%m/%Y', 'MM/YY': '%m/%y'
                }
                accepted_formats = [format_map.get(rule_data['source_format'], '%d-%m-%Y')]
            
            # Validate each cell in the column
            for i, cell_value in enumerate(df[col_name], start=1):
                error_reason = None
                rule_failed = metadata_type
                
                # Handle null/empty values
                if check_null_cells and pd.isna(cell_value):
                    special_char_count += 1
                    error_reason = "Value is null"
                    error_cell_locations.append((i, "NULL", rule_failed, error_reason))
                    continue
                
                cell_value = str(cell_value).strip() if pd.notna(cell_value) else ""
                
                # Required field validation
                if not cell_value and metadata_type == "Required":
                    special_char_count += 1
                    error_reason = "Value is empty"
                    error_cell_locations.append((i, "EMPTY", rule_failed, error_reason))
                    continue
                
                # Type-specific validation
                if metadata_type.startswith("Date("):
                    if not DataValidator.validate_date(cell_value, accepted_formats):
                        special_char_count += 1
                        error_reason = f"Invalid date format (expected {rule_data.get('source_format', 'DD-MM-YYYY')})"
                        error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                
                elif metadata_type == "Alphanumeric":
                    if not re.match(r'^[a-zA-Z0-9]+$', cell_value):
                        special_char_count += 1
                        error_reason = "Contains non-alphanumeric characters"
                        error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                
                elif metadata_type == "Int":
                    if not cell_value.replace('-', '', 1).isdigit():
                        special_char_count += 1
                        error_reason = "Must be an integer"
                        error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                
                elif metadata_type == "Float":
                    try:
                        float(cell_value)
                    except ValueError:
                        special_char_count += 1
                        error_reason = "Must be a number (integer or decimal)"
                        error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                
                elif metadata_type == "Email":
                    if not DataValidator.validate_email(cell_value):
                        special_char_count += 1
                        error_reason = "Invalid email format"
                        error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                
                elif metadata_type == "Boolean":
                    if not re.match(r'^(true|false|0|1)$', cell_value, re.IGNORECASE):
                        special_char_count += 1
                        error_reason = "Must be a boolean (true/false or 0/1)"
                        error_cell_locations.append((i, cell_value, rule_failed, error_reason))
            
            return special_char_count, error_cell_locations
            
        except Exception as e:
            logging.error(f"Error validating column {col_name}: {str(e)}")
            raise
    
    @staticmethod
    def evaluate_column_rule(df: pd.DataFrame, column_name: str, formula: str,
                            headers: List[str], data_type: str) -> Tuple[bool, List[Tuple]]:
        """Evaluate custom validation rules (arithmetic and comparison)"""
        try:
            error_locations = []
            column_name = column_name.strip().lower()
            
            # Validate column exists
            if column_name not in df.columns.str.lower():
                return False, [(0, "", "ColumnNotFound", f"Column '{column_name}' not found in data")]
            
            is_arithmetic = ' = ' in formula
            
            if is_arithmetic:
                # Handle arithmetic formulas: 'column' = expression
                formula_parts = formula.strip().split(' = ', 1)
                if len(formula_parts) != 2 or formula_parts[0] != f"'{column_name}'":
                    return False, [(0, "", "InvalidFormula", "Arithmetic formula must be 'column_name = expression'")]
                
                right_side = formula_parts[1]
                referenced_columns = [item.strip().lower() for item in re.findall(r"'([^']+)'", right_side)]
                
                # Validate referenced columns exist
                for col in referenced_columns:
                    if col not in df.columns.str.lower():
                        return False, [(0, "", "ColumnNotFound", f"Referenced column '{col}' not found in data")]
                
                # Validate data types (all must be numeric for arithmetic)
                for col in referenced_columns + [column_name]:
                    for i, value in enumerate(df[col]):
                        if pd.isna(value) or str(value).strip() == "":
                            error_locations.append((i + 1, "NULL", f"{column_name}_Formula",
                                                   f"Value is null or empty in column {col}"))
                        else:
                            try:
                                float(str(value).strip())
                            except ValueError:
                                error_locations.append((i + 1, str(value), f"{column_name}_DataType",
                                                       f"Invalid numeric value in column {col}: {value}"))
                
                # Evaluate formula for each row
                valid = True
                for i in range(len(df)):
                    # Skip rows with existing errors
                    row_errors = [err for err in error_locations if err[0] == i + 1]
                    if row_errors:
                        valid = False
                        continue
                    
                    # Build local variable dictionary for formula evaluation
                    local_dict = {}
                    try:
                        for col in referenced_columns:
                            local_dict[col] = float(df.at[i, col])
                    except ValueError:
                        valid = False
                        error_locations.append((i + 1, "", f"{column_name}_DataType",
                                               f"Invalid numeric value in referenced columns for row {i+1}"))
                        continue
                    
                    # Evaluate the expression safely
                    expr = right_side.replace("'", "").replace(" AND ", " and ").replace(" OR ", " or ")
                    
                    try:
                        expected = eval(expr, {"__builtins__": {}}, local_dict)
                        expected_num = float(expected)
                    except Exception as eval_err:
                        valid = False
                        error_locations.append((i + 1, "", "FormulaEvaluation",
                                               f"Error evaluating formula for row {i+1}: {str(eval_err)}"))
                        continue
                    
                    # Compare actual vs expected values
                    actual = df.at[i, column_name]
                    if pd.isna(actual):
                        valid = False
                        error_locations.append((i + 1, "NULL", f"{column_name}_Formula", "Value is null"))
                        continue
                    
                    try:
                        actual_num = float(str(actual).strip())
                        if abs(actual_num - expected_num) > 1e-10:  # Floating point precision
                            valid = False
                            error_locations.append((i + 1, str(actual), f"{column_name}_Formula",
                                                   f"Data Error: {column_name} ({actual}) does not match formula {right_side} ({expected_num})"))
                    except ValueError:
                        valid = False
                        error_locations.append((i + 1, str(actual), f"{column_name}_DataType",
                                               f"Invalid numeric value for {column_name}: {actual}"))
                
                return valid, error_locations
            else:
                # Handle comparison formulas: 'column' <operator> operand
                parts = formula.strip().split(' ', 2)
                if len(parts) != 3 or parts[0] != f"'{column_name}'" or parts[1] not in ['=', '>', '<', '>=', '<=']:
                    return False, [(0, "", "InvalidFormula",
                                   "Comparison formula must be 'column_name <operator> operand'")]
                
                operator_str = parts[1]
                operand = parts[2]
                valid = True
                operator_map = {
                    '=': operator.eq, '>': operator.gt, '<': operator.lt,
                    '>=': operator.ge, '<=': operator.le
                }
                op_func = operator_map[operator_str]
                
                # Handle column-to-column comparison
                if operand.startswith("'") and operand.endswith("'"):
                    second_column = operand[1:-1].strip().lower()
                    if second_column not in df.columns.str.lower():
                        return False, [(0, "", "ColumnNotFound", f"Second column '{second_column}' not found in data")]
                    
                    # Validate each row
                    for i in range(len(df)):
                        left_value = df.iloc[i][column_name]
                        right_value = df.iloc[i][second_column]
                        
                        # Check for null values
                        if pd.isna(left_value) or str(left_value).strip() == "":
                            error_locations.append((i + 1, "NULL", f"{column_name}_Formula",
                                                   f"Value is null in column {column_name}"))
                            valid = False
                            continue
                        if pd.isna(right_value) or str(right_value).strip() == "":
                            error_locations.append((i + 1, str(left_value), f"{column_name}_Formula",
                                                   f"Value is null in column {second_column}"))
                            valid = False
                            continue
                        
                        # Perform numeric comparison
                        try:
                            left_num = float(str(left_value).strip())
                            right_num = float(str(right_value).strip())
                            if not op_func(left_num, right_num):
                                valid = False
                                error_locations.append((i + 1, str(left_value), f"{column_name}_Formula",
                                                       f"Failed comparison: {left_value} {operator_str} {right_value}"))
                        except ValueError:
                            valid = False
                            error_locations.append((i + 1, str(left_value), f"{column_name}_DataType",
                                                   f"Invalid numeric value: {left_value} or {right_value}"))
                else:
                    # Handle constant value comparison
                    try:
                        operand_value = float(operand)
                        for i, value in enumerate(df[column_name]):
                            if pd.isna(value) or str(value).strip() == "":
                                error_locations.append((i + 1, "NULL", f"{column_name}_Formula", "Value is null"))
                                valid = False
                                continue
                            try:
                                value_num = float(str(value).strip())
                                if not op_func(value_num, operand_value):
                                    valid = False
                                    error_locations.append((i + 1, str(value), f"{column_name}_Formula",
                                                           f"Failed comparison: {value} {operator_str} {operand_value}"))
                            except ValueError:
                                valid = False
                                error_locations.append((i + 1, str(value), f"{column_name}_DataType",
                                                       f"Invalid numeric value: {value}"))
                    except ValueError:
                        return False, [(0, "", "InvalidOperand", f"Invalid operand for comparison: {operand}")]
                
                return valid, error_locations
        
        except Exception as e:
            return False, error_locations + [(0, "", "FormulaEvaluation",
                                             f"Error evaluating formula for column {column_name}: {str(e)}")]
    
    @staticmethod
    def validate_date(date_string, accepted_formats):
        """Validate date string against accepted formats"""
        if not isinstance(date_string, str):
            return False
        for date_format in accepted_formats:
            try:
                datetime.strptime(date_string, date_format)
                return True
            except ValueError:
                pass
        return False
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not isinstance(email, str):
            return False
        return re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email) is not None

# Main validation service class that wraps DataValidator functionality
class ValidationService(DataValidator):
    """Main validation service class that provides high-level validation operations"""
    
    def __init__(self):
        """Initialize validation service"""
        pass
    
    @classmethod
    def validate_template_data(cls, df, template_id, rules):
        """Validate data against template rules"""
        error_locations = {}
        
        for rule in rules:
            column_name = rule.get('column_name')
            rule_name = rule.get('rule_name')
            
            if not column_name or not rule_name:
                continue
                
            try:
                if rule.get('is_custom'):
                    # Handle custom formula rules
                    formula = rule.get('parameters', '')
                    headers = df.columns.tolist()
                    is_valid, errors = cls.evaluate_column_rule(df, column_name, formula, headers, 'Float')
                    
                    if errors:
                        error_locations[column_name] = [
                            {'row': err[0], 'value': err[1], 'rule_failed': err[2], 'reason': err[3]}
                            for err in errors
                        ]
                else:
                    # Handle standard validation rules
                    accepted_formats = ['%d-%m-%Y', '%Y-%m-%d', '%m/%d/%Y']
                    error_count, errors = cls.check_column_validation(
                        df, column_name, rule_name, accepted_formats, True
                    )
                    
                    if error_count > 0:
                        error_locations[column_name] = [
                            {'row': err[0], 'value': err[1], 'rule_failed': err[2], 'reason': err[3]}
                            for err in errors
                        ]
            except Exception as e:
                logging.error(f"Error validating rule {rule_name} for column {column_name}: {str(e)}")
                continue
        
        return error_locations
