import unittest
import pandas as pd
import tempfile
import os
from services.validator import DataValidator
from services.file_handler import FileHandler

class TestDataValidator(unittest.TestCase):
    def test_column_type_detection(self):
        """Test automatic column type detection"""
        # Test email detection
        email_series = pd.Series(['test@example.com', 'user@domain.org'])
        self.assertEqual(DataValidator.detect_column_type(email_series), 'Email')
        
        # Test integer detection
        int_series = pd.Series(['123', '456', '789'])
        self.assertEqual(DataValidator.detect_column_type(int_series), 'Int')
        
        # Test float detection
        float_series = pd.Series(['12.34', '56.78', '90.12'])
        self.assertEqual(DataValidator.detect_column_type(float_series), 'Float')
    
    def test_rule_assignment(self):
        """Test default rule assignment logic"""
        df = pd.DataFrame({
            'Name': ['John', 'Jane'],
            'Age': [25, 30],
            'Email': ['john@test.com', 'jane@test.com']
        })
        
        rules = DataValidator.assign_default_rules(df, ['Name', 'Age', 'Email'])
        
        self.assertIn('Required', rules['Name'])
        self.assertIn('Text', rules['Name'])
        self.assertIn('Required', rules['Age'])
        self.assertIn('Int', rules['Age'])
        self.assertIn('Required', rules['Email'])
        self.assertIn('Email', rules['Email'])

class TestFileHandler(unittest.TestCase):
    def test_excel_file_reading(self):
        """Test Excel file processing"""
        # Create temporary Excel file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            df = pd.DataFrame({'Col1': [1, 2, 3], 'Col2': ['A', 'B', 'C']})
            df.to_excel(tmp.name, index=False)
            
            # Test reading
            sheets = FileHandler.read_file(tmp.name)
            self.assertIn('Sheet1', sheets)
            self.assertEqual(len(sheets['Sheet1']), 3)
            
            # Cleanup
            os.unlink(tmp.name)
    
    def test_delimiter_detection(self):
        """Test CSV delimiter detection"""
        # Create test CSV with semicolon delimiter
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
            tmp.write('Name;Age;City\nJohn;25;NYC\nJane;30;LA')
            tmp.flush()
            
            delimiter = FileHandler.detect_delimiter(tmp.name)
            self.assertEqual(delimiter, ';')
            
            # Cleanup
            os.unlink(tmp.name)