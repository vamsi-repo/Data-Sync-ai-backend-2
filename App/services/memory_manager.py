import gc
import logging
import pandas as pd
from typing import List, Dict

class MemoryManager:
    @staticmethod
    def process_large_file_in_chunks(file_path: str, chunk_size: int = 10000):
        """Process large files in chunks to manage memory"""
        try:
            chunk_list = []
            for chunk in pd.read_csv(file_path, chunksize=chunk_size):
                # Process chunk
                processed_chunk = MemoryManager._process_chunk(chunk)
                chunk_list.append(processed_chunk)
                
                # Periodic garbage collection
                if len(chunk_list) % 10 == 0:
                    gc.collect()
            
            # Combine processed chunks
            return pd.concat(chunk_list, ignore_index=True)
            
        except Exception as e:
            logging.error(f"Error processing large file: {e}")
            raise
    
    @staticmethod
    def _process_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
        """Process individual chunk with memory optimization"""
        # Apply memory-efficient transformations
        for col in chunk.select_dtypes(include=['object']):
            if chunk[col].nunique() / len(chunk) < 0.5:  # High repetition
                chunk[col] = chunk[col].astype('category')
        
        return chunk
    
    @staticmethod
    def cleanup_session_data(session, keep_keys: List[str] = None):
        """Clean up session data to prevent memory bloat"""
        keep_keys = keep_keys or ['loggedin', 'user_id', 'user_email']
        
        keys_to_remove = [key for key in session.keys() if key not in keep_keys]
        for key in keys_to_remove:
            session.pop(key, None)
        
        logging.debug(f"Cleaned up {len(keys_to_remove)} session keys")