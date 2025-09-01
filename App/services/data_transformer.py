import pandas as pd
import logging
from datetime import  datetime
from typing import Dict, List

class DataTransformer:
    @staticmethod
    def apply_corrections_to_dataframe(df: pd.DataFrame, corrections: Dict, headers: List[str]) -> int:
        """Apply user corrections to DataFrame with comprehensive tracking"""
        correction_count = 0
        
        try:
            for column, row_corrections in corrections.items():
                if column not in headers:
                    logging.warning(f"Column {column} not found in headers")
                    continue
                
                for row_str, corrected_value in row_corrections.items():
                    try:
                        row_index = int(row_str)
                        if row_index < len(df):
                            original_value = df.at[row_index, column]
                            df.at[row_index, column] = corrected_value
                            correction_count += 1
                            logging.debug(f"Applied correction: Row {row_index}, Column {column}, "
                                         f"'{original_value}' -> '{corrected_value}'")
                    except (ValueError, IndexError) as e:
                        logging.warning(f"Invalid correction: {row_str}, {column}, {corrected_value}: {e}")
                        continue
            
            return correction_count
            
        except Exception as e:
            logging.error(f"Error applying corrections: {str(e)}")
            raise
    
    @staticmethod
    def transform_date(value: str, source_format: str, target_format: str) -> str:
        """Transform dates between formats with comprehensive error handling"""
        try:
            if pd.isna(value) or not str(value).strip():
                return value
            
            value_str = str(value).strip()
            
            # Format mapping for common date formats
            format_map = {
                'MM-DD-YYYY': '%m-%d-%Y', 'DD-MM-YYYY': '%d-%m-%Y',
                'MM/DD/YYYY': '%m/%d/%Y', 'DD/MM/YYYY': '%d/%m/%Y',
                'MM-YYYY': '%m-%Y', 'MM-YY': '%m-%y',
                'MM/YYYY': '%m/%Y', 'MM/YY': '%m/%y',
                'YYYY-MM-DD': '%Y-%m-%d', 'YYYY/MM/DD': '%Y/%m/%d'
            }
            
            source_strftime = format_map.get(source_format, '%d-%m-%Y')
            target_strftime = format_map.get(target_format, '%Y-%m-%d')
            
            # Parse source date
            parsed_date = datetime.strptime(value_str, source_strftime)
            
            # Format to target
            transformed_date = parsed_date.strftime(target_strftime)
            
            logging.debug(f"Date transformation: {value_str} ({source_format}) -> "
                         f"{transformed_date} ({target_format})")
            return transformed_date
            
        except ValueError as e:
            logging.warning(f"Date transformation failed for '{value}': {e}")
            return value  # Return original value if transformation fails
        except Exception as e:
            logging.error(f"Unexpected error in date transformation: {e}")
            return value