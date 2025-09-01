import os
import mysql.connector
import mysql.connector.pooling
from mysql.connector import errorcode
from flask import g
import logging
from dotenv import load_dotenv

load_dotenv()

class DatabaseConfig:
    @staticmethod
    def get_connection_config():
        return {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'user': os.getenv('MYSQL_USER', 'root'), 
            'password': os.getenv('MYSQL_PASSWORD', 'Keansa@2024'),
            'database': os.getenv('MYSQL_DATABASE', 'data_validation_36'),
            'autocommit': False,
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci'
        }

class DatabaseManager:
    _connection_pool = None
    
    @classmethod
    def initialize_pool(cls, config: dict, pool_size: int = 10):
        """Initialize connection pool for better performance"""
        try:
            cls._connection_pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="web_app_pool",
                pool_size=pool_size,
                pool_reset_session=True,
                **config
            )
            logging.info(f"Database connection pool initialized with {pool_size} connections")
        except Exception as e:
            logging.error(f"Failed to initialize connection pool: {e}")
            raise
    
    @classmethod
    def get_connection(cls):
        """Get connection from pool"""
        if cls._connection_pool is None:
            cls.initialize_pool(DatabaseConfig.get_connection_config())
        
        return cls._connection_pool.get_connection()

def get_db_connection():
    """Get database connection from pool or create new connection"""
    if 'db' not in g:
        try:
            # First try to create database if it doesn't exist
            config = DatabaseConfig.get_connection_config()
            db_name = config.pop('database')
            
            # Connect without database to create it if needed
            conn = mysql.connector.connect(**config)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            cursor.close()
            conn.close()
            
            # Now connect with database
            config['database'] = db_name
            g.db = DatabaseManager.get_connection() if DatabaseManager._connection_pool else mysql.connector.connect(**config)
            logging.info("Database connection established successfully")
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                logging.error("Database connection failed: Access denied")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                logging.error("Database connection failed: Database does not exist")
            else:
                logging.error(f"Database connection failed: {err}")
            raise Exception(f"Failed to connect to database: {str(err)}")
    return g.db

def close_db(error):
    """Proper connection cleanup"""
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")

def init_db():
    """Initialize database tables with full schema from original app.py"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create all tables from original app.py
        tables = [
            """
            CREATE TABLE IF NOT EXISTS login_details (
                id INT AUTO_INCREMENT PRIMARY KEY,
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                email VARCHAR(255) UNIQUE,
                mobile VARCHAR(10),
                password VARCHAR(255)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS excel_templates (
                template_id BIGINT PRIMARY KEY AUTO_INCREMENT,
                template_name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                user_id INT NOT NULL,
                sheet_name VARCHAR(255),
                headers JSON,
                status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE',
                is_corrected BOOLEAN DEFAULT FALSE,
                remote_file_path VARCHAR(512),
                FOREIGN KEY (user_id) REFERENCES login_details(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS template_columns (
                column_id BIGINT PRIMARY KEY AUTO_INCREMENT,
                template_id BIGINT NOT NULL,
                column_name VARCHAR(255) NOT NULL,
                column_position INT NOT NULL,
                is_validation_enabled BOOLEAN DEFAULT FALSE,
                is_selected BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (template_id) REFERENCES excel_templates(template_id) ON DELETE CASCADE,
                UNIQUE (template_id, column_name)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS validation_rule_types (
                rule_type_id BIGINT PRIMARY KEY AUTO_INCREMENT,
                rule_name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                parameters TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                is_custom BOOLEAN DEFAULT FALSE,
                column_name VARCHAR(255),
                template_id BIGINT,
                data_type VARCHAR(50),
                source_format VARCHAR(50),
                target_format VARCHAR(50),
                FOREIGN KEY (template_id) REFERENCES excel_templates(template_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS column_validation_rules (
                column_validation_id BIGINT PRIMARY KEY AUTO_INCREMENT,
                column_id BIGINT NOT NULL,
                rule_type_id BIGINT NOT NULL,
                rule_config JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (column_id) REFERENCES template_columns(column_id) ON DELETE CASCADE,
                FOREIGN KEY (rule_type_id) REFERENCES validation_rule_types(rule_type_id) ON DELETE RESTRICT,
                UNIQUE (column_id, rule_type_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS validation_history (
                history_id BIGINT PRIMARY KEY AUTO_INCREMENT,
                template_id BIGINT NOT NULL,
                template_name VARCHAR(255) NOT NULL,
                error_count INT NOT NULL,
                corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                corrected_file_path VARCHAR(512) NOT NULL,
                user_id INT NOT NULL,
                FOREIGN KEY (template_id) REFERENCES excel_templates(template_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES login_details(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS validation_corrections (
                correction_id BIGINT PRIMARY KEY AUTO_INCREMENT,
                history_id BIGINT NOT NULL,
                row_index INT NOT NULL,
                column_name VARCHAR(255) NOT NULL,
                original_value TEXT,
                corrected_value TEXT,
                rule_failed VARCHAR(255) DEFAULT NULL,
                FOREIGN KEY (history_id) REFERENCES validation_history(history_id) ON DELETE CASCADE
            )
            """
        ]
        
        # Execute table creation
        for table_sql in tables:
            cursor.execute(table_sql)
        
        # Add columns that might not exist (from original app.py)
        add_column_queries = [
            "ALTER TABLE validation_rule_types ADD COLUMN IF NOT EXISTS source_format VARCHAR(50)",
            "ALTER TABLE validation_rule_types ADD COLUMN IF NOT EXISTS target_format VARCHAR(50)", 
            "ALTER TABLE validation_rule_types ADD COLUMN IF NOT EXISTS data_type VARCHAR(50)",
            "ALTER TABLE excel_templates ADD COLUMN IF NOT EXISTS remote_file_path VARCHAR(512)",
            "ALTER TABLE template_columns ADD COLUMN IF NOT EXISTS is_selected BOOLEAN DEFAULT FALSE"
        ]
        
        for query in add_column_queries:
            try:
                cursor.execute(query)
            except mysql.connector.Error:
                # Column might already exist, continue
                pass
        
        conn.commit()
        cursor.close()
        logging.info("Database tables initialized successfully")
        
    except Exception as e:
        logging.error(f"Failed to initialize database: {str(e)}")
        raise
