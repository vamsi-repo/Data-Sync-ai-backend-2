import pandas as pd
import logging
import json
from typing import Dict, List
from config.database import get_db_connection

class DataHelper:
    @staticmethod
    def normalize_data_rows(data_rows: List[Dict]) -> List[Dict]:
        """Normalize data rows by replacing NaN/empty values with 'NULL'"""
        for row in data_rows:
            for key, value in row.items():
                if pd.isna(value) or value == '':
                    row[key] = 'NULL'
        return data_rows
    
    @staticmethod
    def group_validation_history(history_entries: List[Dict]) -> Dict:
        """Group validation history by template name for organized display"""
        grouped_history = {}
        
        for entry in history_entries:
            template_name = entry['template_name']
            
            # Filter corrected files only
            if not template_name.endswith('_corrected.xlsx') and not template_name.endswith('_corrected.csv'):
                continue
            
            # Extract base template name
            base_template_name = (template_name.replace('_corrected.xlsx', '')
                                 .replace('_corrected.csv', ''))
            
            if base_template_name not in grouped_history:
                # Get original upload timestamp
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("""
                        SELECT created_at FROM excel_templates
                        WHERE template_name = %s AND user_id = %s
                        ORDER BY created_at ASC LIMIT 1
                    """, (base_template_name, entry.get('user_id')))
                    original_entry = cursor.fetchone()
                    cursor.close()
                    
                    original_uploaded_at = (original_entry['created_at'] if original_entry
                                          else entry['original_uploaded_at'])
                except Exception:
                    original_uploaded_at = entry.get('original_uploaded_at', entry['corrected_at'])
                
                grouped_history[base_template_name] = {
                    'original_uploaded_at': original_uploaded_at.isoformat(),
                    'data_loads': []
                }
            
            # Add this validation to the group
            grouped_history[base_template_name]['data_loads'].append({
                'history_id': entry['history_id'],
                'template_id': entry['template_id'],
                'template_name': entry['template_name'],
                'error_count': entry['error_count'],
                'corrected_at': entry['corrected_at'].isoformat(),
                'corrected_file_path': entry['corrected_file_path']
            })
        
        return grouped_history