import json
import logging
from typing import List, Dict, Optional, Tuple
from config.database import get_db_connection

class Template:
    @staticmethod
    def create_template(template_name: str, user_id: int, sheet_name: str,
                       headers: List[str], is_corrected: bool = False,
                       remote_file_path: Optional[str] = None) -> int:
        """Create new template with comprehensive metadata"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO excel_templates
                (template_name, user_id, sheet_name, headers, is_corrected, remote_file_path)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (template_name, user_id, sheet_name, json.dumps(headers), is_corrected, remote_file_path))
            
            template_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            return template_id
        except Exception as e:
            logging.error(f"Template creation error: {str(e)}")
            raise

    @staticmethod
    def create_template_columns(template_id: int, headers: List[str]):
        """Create template columns"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            column_data = [(template_id, header, i + 1, False) for i, header in enumerate(headers)]
            cursor.executemany("""
                INSERT INTO template_columns (template_id, column_name, column_position, is_selected)
                VALUES (%s, %s, %s, %s)
            """, column_data)
            
            conn.commit()
            cursor.close()
        except Exception as e:
            logging.error(f"Error creating template columns: {str(e)}")
            raise
    
    @staticmethod
    def get_user_templates(user_id: int) -> List[Dict]:
        """Retrieve all templates for a specific user"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT template_id, template_name, created_at, updated_at,
                       sheet_name, status, is_corrected
                FROM excel_templates
                WHERE user_id = %s AND status = 'ACTIVE'
                ORDER BY updated_at DESC
            """, (user_id,))
            
            templates = cursor.fetchall()
            cursor.close()
            return templates
        except Exception as e:
            logging.error(f"Error fetching user templates: {str(e)}")
            raise
    
    @staticmethod
    def process_existing_template(filename: str, user_id: int, headers: List[str],
                                 sheet_name: str) -> Tuple[int, bool, Dict, List[str]]:
        """Process existing template or create new one with rule checking"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Check for existing templates with same name and user
            cursor.execute("""
                SELECT template_id, headers, sheet_name
                FROM excel_templates
                WHERE template_name = %s AND user_id = %s AND status = 'ACTIVE'
                ORDER BY created_at DESC
            """, (filename, user_id))
            existing_templates = cursor.fetchall()
            
            template_id = None
            has_existing_rules = False
            validations = {}
            selected_headers = []
            
            # Find exact match based on headers and sheet name
            matching_template = None
            for template in existing_templates:
                stored_headers = json.loads(template['headers']) if template['headers'] else []
                stored_sheet_name = template['sheet_name']
                
                if stored_headers == headers and stored_sheet_name == sheet_name:
                    matching_template = template
                    break
            
            if matching_template:
                template_id = matching_template['template_id']
                
                # Load existing validation rules
                cursor.execute("""
                    SELECT tc.column_name, vrt.rule_name
                    FROM template_columns tc
                    JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                    JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
                    WHERE tc.template_id = %s AND tc.is_selected = TRUE
                """, (template_id,))
                rules_data = cursor.fetchall()
                
                # Group rules by column
                for row in rules_data:
                    column_name = row['column_name']
                    rule_name = row['rule_name']
                    if column_name not in validations:
                        validations[column_name] = []
                    validations[column_name].append(rule_name)
                    if column_name not in selected_headers:
                        selected_headers.append(column_name)
                
                has_existing_rules = len(validations) > 0
            else:
                # Create new template
                template_id = Template.create_template(filename, user_id, sheet_name, headers, False)
                Template.create_template_columns(template_id, headers)
            
            conn.commit()
            cursor.close()
            return template_id, has_existing_rules, validations, selected_headers
            
        except Exception as e:
            logging.error(f"Error processing existing template: {str(e)}")
            raise

    @staticmethod
    def get_template_by_id(template_id: int, user_id: int) -> Optional[Dict]:
        """Get template by ID and user ID"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT * FROM excel_templates
                WHERE template_id = %s AND user_id = %s AND status = 'ACTIVE'
            """, (template_id, user_id))
            
            template = cursor.fetchone()
            cursor.close()
            return template
        except Exception as e:
            logging.error(f"Error fetching template: {str(e)}")
            return None

    @staticmethod
    def update_template_headers(template_id: int, headers: List[str], sheet_name: str):
        """Update template headers and sheet name"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE excel_templates
                SET headers = %s, sheet_name = %s
                WHERE template_id = %s
            """, (json.dumps(headers), sheet_name, template_id))
            
            conn.commit()
            cursor.close()
        except Exception as e:
            logging.error(f"Error updating template headers: {str(e)}")
            raise

    @staticmethod
    def delete_template(template_id: int, user_id: int) -> bool:
        """Delete template and associated data"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Delete validation history first
            cursor.execute("""
                DELETE FROM validation_history
                WHERE template_id = %s AND user_id = %s
            """, (template_id, user_id))
            
            # Delete template
            cursor.execute("""
                DELETE FROM excel_templates
                WHERE template_id = %s AND user_id = %s
            """, (template_id, user_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            cursor.close()
            return success
        except Exception as e:
            logging.error(f"Error deleting template: {str(e)}")
            return False

    @staticmethod
    def update_selected_columns(template_id: int, selected_headers: List[str]):
        """Update selected columns for a template"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Reset all columns to not selected
            cursor.execute("""
                UPDATE template_columns
                SET is_selected = FALSE
                WHERE template_id = %s
            """, (template_id,))
            
            # Set selected columns
            for header in selected_headers:
                cursor.execute("""
                    UPDATE template_columns
                    SET is_selected = TRUE
                    WHERE template_id = %s AND column_name = %s
                """, (template_id, header))
            
            conn.commit()
            cursor.close()
        except Exception as e:
            logging.error(f"Error updating selected columns: {str(e)}")
            raise

    @staticmethod
    def get_template_columns(template_id: int) -> List[Dict]:
        """Get all columns for a template"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT column_id, column_name, column_position, is_selected, is_validation_enabled
                FROM template_columns
                WHERE template_id = %s
                ORDER BY column_position
            """, (template_id,))
            
            columns = cursor.fetchall()
            cursor.close()
            return columns
        except Exception as e:
            logging.error(f"Error fetching template columns: {str(e)}")
            return []

    @staticmethod
    def template_has_rules(template_id: int) -> bool:
        """Check if template has validation rules configured"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) as rule_count
                FROM template_columns tc
                JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                WHERE tc.template_id = %s AND tc.is_selected = TRUE
            """, (template_id,))
            
            result = cursor.fetchone()
            cursor.close()
            return result[0] > 0 if result else False
        except Exception as e:
            logging.error(f"Error checking template rules: {str(e)}")
            return False

class ValidationHistory:
    @staticmethod
    def create_history_entry(template_id: int, template_name: str, error_count: int,
                           corrected_file_path: str, user_id: int) -> int:
        """Create new validation history entry"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO validation_history (template_id, template_name, error_count, corrected_file_path, user_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (template_id, template_name, error_count, corrected_file_path, user_id))
            
            history_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            return history_id
        except Exception as e:
            logging.error(f"Error creating validation history: {str(e)}")
            raise

    @staticmethod
    def save_corrections(history_id: int, corrections: List[Tuple]):
        """Save individual corrections to database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.executemany("""
                INSERT INTO validation_corrections 
                (history_id, row_index, column_name, original_value, corrected_value, rule_failed)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, corrections)
            
            conn.commit()
            cursor.close()
        except Exception as e:
            logging.error(f"Error saving corrections: {str(e)}")
            raise

    @staticmethod
    def get_user_history(user_id: int) -> List[Dict]:
        """Get validation history for user"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT 
                    vh.history_id, 
                    vh.template_id, 
                    vh.template_name, 
                    vh.error_count, 
                    vh.corrected_at, 
                    vh.corrected_file_path,
                    et.created_at AS original_uploaded_at
                FROM validation_history vh
                JOIN excel_templates et ON vh.template_id = et.template_id
                WHERE vh.user_id = %s
                ORDER BY et.created_at DESC, vh.corrected_at DESC
            """, (user_id,))
            
            history = cursor.fetchall()
            cursor.close()
            return history
        except Exception as e:
            logging.error(f"Error fetching validation history: {str(e)}")
            return []

    @staticmethod
    def delete_history_entry(history_id: int, user_id: int) -> bool:
        """Delete validation history entry"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM validation_history
                WHERE history_id = %s AND user_id = %s
            """, (history_id, user_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            cursor.close()
            return success
        except Exception as e:
            logging.error(f"Error deleting validation history: {str(e)}")
            return False

    @staticmethod
    def get_corrections(history_id: int) -> List[Dict]:
        """Get corrections for a history entry"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT row_index, column_name, original_value, corrected_value, rule_failed
                FROM validation_corrections
                WHERE history_id = %s
            """, (history_id,))
            
            corrections = cursor.fetchall()
            cursor.close()
            return corrections
        except Exception as e:
            logging.error(f"Error fetching corrections: {str(e)}")
            return []
