import json
import logging
import re
import pandas as pd
import numexpr
import operator
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from config.database import get_db_connection

class ValidationRule:
    @staticmethod
    def create_default_rules():
        """Create default validation rules from original app.py"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            default_rules = [
                ("Required", "Ensures the field is not null", '{"allow_null": false}', None, None, None),
                ("Int", "Validates integer format", '{"format": "integer"}', None, None, "Int"),
                ("Float", "Validates number format (integer or decimal)", '{"format": "float"}', None, None, "Float"),
                ("Text", "Allows text with quotes and parentheses", '{"allow_special": false}', None, None, "Text"),
                ("Email", "Validates email format", '{"regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\\\.[a-zA-Z0-9-.]+$"}', None, None, "Email"),
                ("Date", "Validates date", '{"format": "%d-%m-%Y"}', "DD-MM-YYYY", None, "Date"),
                ("Boolean", "Validates boolean format (true/false or 0/1)", '{"format": "boolean"}', None, None, "Boolean"),
                ("Alphanumeric", "Validates alphanumeric format", '{"format": "alphanumeric"}', None, None, "Alphanumeric")
            ]
            
            cursor.executemany("""
                INSERT IGNORE INTO validation_rule_types (rule_name, description, parameters, is_custom, source_format, target_format, data_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, [(name, desc, params, False, source, target, dtype) for name, desc, params, source, target, dtype in default_rules])
            
            conn.commit()
            cursor.close()
            logging.info("Default validation rules ensured successfully")
        except Exception as e:
            logging.error(f"Failed to ensure default validation rules: {str(e)}")
            raise

    @staticmethod
    def create_custom_rule(rule_name: str, parameters: str, column_name: str, template_id: int):
        """Create custom validation rule"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO validation_rule_types 
                (rule_name, parameters, is_custom, column_name, template_id, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (rule_name, parameters, True, column_name, template_id, True))
            
            rule_type_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            return rule_type_id
        except Exception as e:
            logging.error(f"Failed to create custom rule: {str(e)}")
            raise

    @staticmethod
    def get_template_rules(template_id: int) -> List[Dict]:
        """Get all rules for a template"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT tc.column_name, vrt.rule_name, vrt.source_format, vrt.is_custom, vrt.parameters
                FROM template_columns tc
                JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
                WHERE tc.template_id = %s AND tc.is_selected = TRUE AND vrt.is_active = TRUE
            """, (template_id,))
            
            rules = cursor.fetchall()
            cursor.close()
            return rules
        except Exception as e:
            logging.error(f"Failed to get template rules: {str(e)}")
            raise

class DataValidator:
    @staticmethod
    def detect_column_type(series: pd.Series) -> str:
        """Auto-detect column data type from original app.py"""
        non_null = series.dropna().astype(str)
        if non_null.empty:
            return "Text"
        
        # Email detection
        if non_null.str.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$").all():
            return "Email"
        
        # Date detection
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
        
        # Integer detection
        if non_null.str.match(r"^-?\d+$").all():
            return "Int"
        
        # Float detection
        if non_null.str.match(r"^-?\d+(\.\d+)?$").all():
            return "Float"
        
        # Alphanumeric detection
        if non_null.str.match(r"^[a-zA-Z0-9]+$").all():
            return "Alphanumeric"
        
        return "Text"

    @staticmethod
    def assign_default_rules_to_columns(df: pd.DataFrame, headers: List[str]) -> Dict[str, List[str]]:
        """Assign default validation rules based on data type"""
        assignments = {}
        for col in headers:
            col_type = DataValidator.detect_column_type(df[col])
            rules = ["Required"]
            
            if col_type != "Text" or not any(
                col.lower().startswith(prefix) for prefix in ["name", "address", "phone", "username", "status", "period"]
            ):
                rules.append(col_type)
            else:
                rules.append("Text")
            
            assignments[col] = rules
        return assignments

    @staticmethod
    def has_special_characters_except_quotes_and_parenthesis(s: str) -> bool:
        """Check for special characters in text validation"""
        if not isinstance(s, str):
            logging.debug(f"Value '{s}' is not a string, failing Text validation")
            return True
        
        for char in s:
            if char not in ['"', '(', ')'] and not char.isalpha() and char != ' ':
                logging.debug(f"Character '{char}' in '{s}' is not allowed for Text validation")
                return True
        return False

    @staticmethod
    def is_valid_date_format(date_string: str, accepted_date_formats: List[str]) -> bool:
        """Validate date format"""
        if not isinstance(date_string, str):
            return False
        
        for date_format in accepted_date_formats:
            try:
                datetime.strptime(date_string, date_format)
                return True
            except ValueError:
                pass
        return False

    @staticmethod
    def check_special_characters_in_column(df: pd.DataFrame, col_name: str, metadata_type: str, 
                                         accepted_date_formats: List[str], check_null_cells: bool = True) -> Tuple[int, List]:
        """Main validation function from original app.py"""
        try:
            logging.debug(f"Validating column: {col_name}, type: {metadata_type}, check_null_cells: {check_null_cells}")
            special_char_count, error_cell_locations = 0, []
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT parameters, is_custom, source_format, data_type
                FROM validation_rule_types
                WHERE rule_name = %s
            """, (metadata_type,))
            rule_data = cursor.fetchone()
            cursor.close()
            
            accepted_formats = accepted_date_formats
            if metadata_type.startswith("Date(") and rule_data and rule_data['source_format']:
                format_map = {
                    'MM-DD-YYYY': '%m-%d-%Y', 'DD-MM-YYYY': '%d-%m-%Y', 'MM/DD/YYYY': '%m/%d/%Y', 'DD/MM/YYYY': '%d/%m/%Y',
                    'MM-YYYY': '%m-%Y', 'MM-YY': '%m-%y', 'MM/YYYY': '%m/%Y', 'MM/YY': '%m/%y'
                }
                accepted_formats = [format_map.get(rule_data['source_format'], '%d-%m-%Y')]
                logging.debug(f"Using specific date format for {col_name}: {rule_data['source_format']} ({accepted_formats[0]})")
            
            # Handle custom rules
            if rule_data and rule_data['is_custom'] and not metadata_type.startswith('Date('):
                params = json.loads(rule_data['parameters'])
                logic = params.get('logic')
                base_rules = params.get('base_rules', [])
                
                for i, cell_value in enumerate(df[col_name], start=1):
                    cell_value = str(cell_value).strip() if pd.notna(cell_value) else ""
                    error_reason = None
                    rule_failed = metadata_type
                    
                    if check_null_cells and pd.isna(cell_value):
                        special_char_count += 1
                        error_reason = "Value is null"
                        error_cell_locations.append((i, "NULL", rule_failed, error_reason))
                        continue
                    
                    if not cell_value and metadata_type == "Required":
                        special_char_count += 1
                        error_reason = "Value is empty"
                        error_cell_locations.append((i, "EMPTY", rule_failed, error_reason))
                        continue
                    
                    # Process base rules for custom validation
                    valid = True if logic == "OR" else False
                    for base_rule in base_rules:
                        base_valid, base_errors = DataValidator.check_special_characters_in_column(
                            df.iloc[[i-1]], col_name, base_rule, accepted_date_formats, check_null_cells
                        )
                        if logic == "AND":
                            valid = valid and (base_valid == 0)
                        elif logic == "OR":
                            valid = valid or (base_valid == 0)
                        
                        if base_valid > 0:
                            for err in base_errors:
                                special_char_count += 1
                                error_reason = err[3] if len(err) > 3 else "Failed base rule"
                                error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                    
                    if not valid and not error_cell_locations:
                        special_char_count += 1
                        error_reason = f"Failed custom rule {metadata_type}"
                        error_cell_locations.append((i, cell_value, rule_failed, error_reason))
            else:
                # Handle standard validation rules
                for i, cell_value in enumerate(df[col_name], start=1):
                    error_reason = None
                    rule_failed = metadata_type
                    
                    if check_null_cells and pd.isna(cell_value):
                        special_char_count += 1
                        error_reason = "Value is null"
                        error_cell_locations.append((i, "NULL", rule_failed, error_reason))
                        continue
                    
                    cell_value = str(cell_value).strip() if pd.notna(cell_value) else ""
                    
                    if not cell_value and metadata_type == "Required":
                        special_char_count += 1
                        error_reason = "Value is empty"
                        error_cell_locations.append((i, "EMPTY", rule_failed, error_reason))
                        continue
                    
                    # Date validation
                    if metadata_type.startswith("Date("):
                        if not cell_value:
                            special_char_count += 1
                            error_reason = "Value is empty"
                            error_cell_locations.append((i, "EMPTY", rule_failed, error_reason))
                        elif not DataValidator.is_valid_date_format(cell_value, accepted_formats):
                            special_char_count += 1
                            error_reason = f"Invalid date format (expected {rule_data['source_format']})"
                            error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                            logging.debug(f"Date validation failed for {col_name} at row {i}: {cell_value}, expected {rule_data['source_format']}")
                    
                    # Alphanumeric validation
                    elif metadata_type == "Alphanumeric":
                        if not cell_value:
                            special_char_count += 1
                            error_reason = "Value is empty or contains only whitespace"
                            error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                        elif not re.match(r'^[a-zA-Z0-9]+$', cell_value):
                            special_char_count += 1
                            error_reason = "Contains non-alphanumeric characters"
                            error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                    
                    # Integer validation
                    elif metadata_type == "Int":
                        if not cell_value.replace('-', '', 1).isdigit():
                            special_char_count += 1
                            error_reason = "Must be an integer"
                            error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                    
                    # Float validation
                    elif metadata_type == "Float":
                        try:
                            float(cell_value)
                        except ValueError:
                            special_char_count += 1
                            error_reason = "Must be a number (integer or decimal)"
                            error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                    
                    # Text validation
                    elif metadata_type == "Text":
                        has_special = DataValidator.has_special_characters_except_quotes_and_parenthesis(cell_value)
                        if has_special:
                            special_char_count += 1
                            error_reason = "Contains invalid characters"
                            error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                    
                    # Email validation
                    elif metadata_type == "Email":
                        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', cell_value):
                            special_char_count += 1
                            error_reason = "Invalid email format"
                            error_cell_locations.append((i, cell_value, rule_failed, error_reason))
                    
                    # Boolean validation
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
                           headers: List[str], data_type: str) -> Tuple[bool, List[Tuple[int, str, str, str]]]:
        """Evaluate custom column formulas from original app.py"""
        try:
            error_locations = []
            column_name = column_name.strip().lower()
            headers_lower = [h.strip().lower() for h in headers]

            if column_name not in df.columns.str.lower():
                return False, [(0, "", "ColumnNotFound", f"Column '{column_name}' not found in data")]

            is_arithmetic = ' = ' in formula

            if is_arithmetic:
                formula_parts = formula.strip().split(' = ', 1)
                if len(formula_parts) != 2 or formula_parts[0] != f"'{column_name}'":
                    return False, [(0, "", "InvalidFormula", "Arithmetic formula must be 'column_name = expression'")]
                
                right_side = formula_parts[1]
                referenced_columns = [item.strip().lower() for item in re.findall(r"'([^']+)'", right_side)]
                
                for col in referenced_columns:
                    if col not in df.columns.str.lower():
                        return False, [(0, "", "ColumnNotFound", f"Referenced column '{col}' not found in data")]
                
                # Validate numeric values
                for col in referenced_columns + [column_name]:
                    for i, value in enumerate(df[col]):
                        if pd.isna(value) or str(value).strip() == "":
                            error_locations.append((i + 1, "NULL", f"{column_name}_Formula", f"Value is null or empty in column {col}"))
                        else:
                            try:
                                float(str(value).strip())
                            except ValueError:
                                error_locations.append((i + 1, str(value), f"{column_name}_DataType", f"Invalid numeric value in column {col}: {value}"))

                valid = True
                for i in range(len(df)):
                    row_errors = [err for err in error_locations if err[0] == i + 1]
                    if row_errors:
                        valid = False
                        continue

                    local_dict = {}
                    try:
                        for col in referenced_columns:
                            local_dict[col] = float(df.at[i, col])
                    except ValueError:
                        valid = False
                        error_locations.append((i + 1, "", f"{column_name}_DataType", f"Invalid numeric value in referenced columns for row {i+1}"))
                        continue

                    expr = right_side.replace("'", "").replace(" AND ", " and ").replace(" OR ", " or ")
                    
                    try:
                        expected = eval(expr, {"__builtins__": {}}, local_dict)
                        expected_num = float(expected)
                    except Exception as eval_err:
                        valid = False
                        error_locations.append((i + 1, "", "FormulaEvaluation", f"Error evaluating formula for row {i+1}: {str(eval_err)}"))
                        continue

                    actual = df.at[i, column_name]
                    if pd.isna(actual):
                        valid = False
                        error_locations.append((i + 1, "NULL", f"{column_name}_Formula", "Value is null"))
                        continue

                    actual_value = str(actual).strip()
                    expected_value = str(expected_num)
                    try:
                        actual_num = float(actual_value)
                        if abs(actual_num - expected_num) > 1e-10:
                            valid = False
                            error_locations.append((i + 1, actual_value, f"{column_name}_Formula", f"Data Error: {column_name} ({actual_value}) does not match formula {right_side} ({expected_value})"))
                    except ValueError:
                        valid = False
                        error_locations.append((i + 1, actual_value, f"{column_name}_DataType", f"Invalid numeric value for {column_name}: {actual_value}"))

                return valid, error_locations
            else:
                # Handle comparison formulas
                parts = formula.strip().split(' ', 3)
                if len(parts) != 3 or parts[0] != f"'{column_name}'" or parts[1] not in ['=', '>', '<', '>=', '<=']:
                    return False, [(0, "", "InvalidFormula", "Comparison formula must be 'column_name <operator> operand'")]
                
                operator_str = parts[1]
                operand = parts[2]
                valid = True
                operator_map = {'=': operator.eq, '>': operator.gt, '<': operator.lt, '>=': operator.ge, '<=': operator.le}
                op_func = operator_map[operator_str]
                
                if operand.startswith("'") and operand.endswith("'"):
                    second_column = operand[1:-1].strip().lower()
                    if second_column not in df.columns.str.lower():
                        return False, [(0, "", "ColumnNotFound", f"Second column '{second_column}' not found in data")]
                    
                    for i in range(len(df)):
                        left_value = df.iloc[i][column_name]
                        right_value = df.iloc[i][second_column]
                        if pd.isna(left_value) or str(left_value).strip() == "":
                            error_locations.append((i + 1, "NULL", f"{column_name}_Formula", f"Value is null in column {column_name}"))
                            valid = False
                            continue
                        if pd.isna(right_value) or str(right_value).strip() == "":
                            error_locations.append((i + 1, str(left_value), f"{column_name}_Formula", f"Value is null in column {second_column}"))
                            valid = False
                            continue
                        
                        try:
                            left_num = float(str(left_value).strip())
                            right_num = float(str(right_value).strip())
                            if not op_func(left_num, right_num):
                                valid = False
                                error_locations.append((i + 1, str(left_value), f"{column_name}_Formula", f"Failed comparison: {left_value} {operator_str} {right_value}"))
                        except ValueError:
                            valid = False
                            error_locations.append((i + 1, str(left_value), f"{column_name}_DataType", f"Invalid numeric value in column {column_name}: {left_value} or {second_column}: {right_value}"))
                else:
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
                                    error_locations.append((i + 1, str(value), f"{column_name}_Formula", f"Failed comparison: {value} {operator_str} {operand_value}"))
                            except ValueError:
                                valid = False
                                error_locations.append((i + 1, str(value), f"{column_name}_DataType", f"Invalid numeric value in column {column_name}: {value}"))
                    except ValueError:
                        return False, [(0, "", "InvalidOperand", f"Invalid operand for comparison: {operand}")]

                return valid, error_locations

        except Exception as e:
            return False, error_locations + [(0, "", "FormulaEvaluation", f"Error evaluating formula for column {column_name}: {str(e)}")]

    @staticmethod
    def transform_date(value: Any, source_format: str, target_format: str) -> Any:
        """Transform date from one format to another"""
        try:
            if not value or pd.isna(value) or str(value).strip() in ['NULL', '', 'nan']:
                return value
                
            value_str = str(value).strip()
            
            # Format mapping from display format to Python strftime format
            format_map = {
                'MM-DD-YYYY': '%m-%d-%Y', 
                'DD-MM-YYYY': '%d-%m-%Y', 
                'MM/DD/YYYY': '%m/%d/%Y', 
                'DD/MM/YYYY': '%d/%m/%Y',
                'MM-YYYY': '%m-%Y', 
                'MM-YY': '%m-%y', 
                'MM/YYYY': '%m/%Y', 
                'MM/YY': '%m/%y'
            }
            
            # Get Python formats
            source_py_format = format_map.get(source_format)
            target_py_format = format_map.get(target_format)
            
            if not source_py_format or not target_py_format:
                logging.error(f"Invalid date format: source={source_format}, target={target_format}")
                return value
                
            # Parse date with source format and convert to target format
            parsed_date = datetime.strptime(value_str, source_py_format)
            transformed_value = parsed_date.strftime(target_py_format)
            
            logging.debug(f"Date transformation: '{value_str}' ({source_format}) -> '{transformed_value}' ({target_format})")
            return transformed_value
            
        except ValueError as ve:
            logging.error(f"Date parsing error: {ve} - value: '{value}', source: {source_format}, target: {target_format}")
            return value
        except Exception as e:
            logging.error(f"Error transforming date {value} from {source_format} to {target_format}: {str(e)}")
            return value

    @staticmethod
    def register_validator(validator_type: str, validator_func):
        """Extend validation capabilities with custom validators"""
        # This can be extended to register custom validation functions
        pass
