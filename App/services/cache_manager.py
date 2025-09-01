import json
import logging
from typing import Any, Optional
from flask import session

class CacheManager:
    @staticmethod
    def cache_dataframe(df, key: str):
        """Cache DataFrame in session with compression"""
        try:
            # Convert to JSON with compression
            session[key] = df.to_json(orient='records', date_format='iso')
            logging.debug(f"Cached DataFrame with key: {key}")
        except Exception as e:
            logging.error(f"Error caching DataFrame: {e}")
    
    @staticmethod
    def get_cached_dataframe(key: str):
        """Retrieve cached DataFrame"""
        try:
            if key in session:
                data = session[key]
                return pd.read_json(data, orient='records')
            return None
        except Exception as e:
            logging.error(f"Error retrieving cached DataFrame: {e}")
            return None
    
    @staticmethod
    def cache_validation_results(template_id: int, results: dict):
        """Cache validation results for reuse"""
        cache_key = f"validation_results_{template_id}"
        session[cache_key] = json.dumps(results)
        logging.debug(f"Cached validation results for template {template_id}")
    
    @staticmethod
    def get_cached_validation_results(template_id: int) -> Optional[dict]:
        """Retrieve cached validation results"""
        cache_key = f"validation_results_{template_id}"
        if cache_key in session:
            try:
                return json.loads(session[cache_key])
            except Exception as e:
                logging.error(f"Error retrieving cached validation results: {e}")
                return None
        return None