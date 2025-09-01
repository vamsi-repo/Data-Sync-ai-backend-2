import unittest
import os
import tempfile
from models.user import User
from models.template import Template
from config.database import init_db

class TestUserModel(unittest.TestCase):
    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.mkdtemp()
        init_db()
    
    def test_user_creation(self):
        """Test user creation with valid data"""
        user_id = User.create_user(
            'John', 'Doe', 'john@example.com', '1234567890', 'password123'
        )
        self.assertIsNotNone(user_id)
        
        # Verify user was created
        user = User.get_user_by_email('john@example.com')
        self.assertEqual(user['first_name'], 'John')
    
    def test_user_authentication(self):
        """Test user authentication process"""
        # Create test user
        User.create_user('Jane', 'Smith', 'jane@example.com', '0987654321', 'testpass')
        
        # Test valid authentication
        account = User.authenticate('jane@example.com', 'testpass')
        self.assertIsNotNone(account)
        self.assertEqual(account['email'], 'jane@example.com')
        
        # Test invalid authentication
        invalid_account = User.authenticate('jane@example.com', 'wrongpass')
        self.assertIsNone(invalid_account)

class TestTemplateModel(unittest.TestCase):
    def setUp(self):
        init_db()
        self.user_id = User.create_user('Test', 'User', 'test@example.com', '1111111111', 'password')
    
    def test_template_creation(self):
        """Test template creation and retrieval"""
        headers = ['Name', 'Age', 'Email']
        template_id = Template.create_template(
            'test.xlsx', self.user_id, 'Sheet1', headers, False
        )
        self.assertIsNotNone(template_id)
        
        # Retrieve and verify template
        template = Template.get_template_by_id(template_id, self.user_id)
        self.assertEqual(template['template_name'], 'test.xlsx')
        self.assertEqual(json.loads(template['headers']), headers)