import os
import logging
import json
from flask import Flask, jsonify, session, request, current_app
from datetime import datetime

# Import configuration and database
from config.settings import Config
from config.database import init_db, close_db, get_db_connection

# Import models for initialization
from models.user import User
from models.validation import ValidationRule

# Import routes
from routes import register_blueprints

def create_app():
    """Application factory pattern for different environments"""
    # Initialize comprehensive logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # Create Flask application instance
    app = Flask(__name__, static_folder='./dist', static_url_path='')
    
    # Initialize required directories
    session_dir, upload_dir = Config.init_directories()
    
    # Configure application with centralized settings
    app.config.from_object(Config)
    app.config['SESSION_FILE_DIR'] = session_dir
    app.config['UPLOAD_FOLDER'] = upload_dir
    
    # Initialize extensions with proper configuration
    from flask_cors import CORS
    from flask_session import Session
    
    CORS(app, origins=[
        "http://localhost:3000",
        "https://your-frontend-domain.railway.app",  # Update this after frontend deployment
        "https://*.railway.app"
    ])
    
    # Register cleanup handlers
    app.teardown_appcontext(close_db)
    
    # Register all route blueprints
    register_blueprints(app)
    
    # Add legacy routes for backward compatibility with frontend
    @app.route('/check-auth', methods=['GET'])
    def legacy_check_auth():
        from routes.auth import check_auth
        return check_auth()
    
    @app.route('/authenticate', methods=['POST'])
    def legacy_authenticate():
        from routes.auth import authenticate
        return authenticate()
    
    @app.route('/register', methods=['POST'])
    def legacy_register():
        from routes.auth import register
        return register()
    
    @app.route('/logout', methods=['POST'])
    def legacy_logout():
        from routes.auth import logout
        return logout()
    
    @app.route('/reset_password', methods=['POST'])
    def legacy_reset_password():
        from routes.auth import reset_password
        return reset_password()
    
    # Add legacy validation routes
    @app.route('/rule-configurations', methods=['GET'])
    def legacy_rule_configurations():
        from routes.validation import get_rule_configurations
        return get_rule_configurations()
    
    @app.route('/validation-history', methods=['GET'])
    def legacy_validation_history():
        from routes.validation import get_validation_history
        return get_validation_history()
    
    # Add more legacy routes that your frontend might need
    @app.route('/validate-existing/<int:template_id>', methods=['GET', 'POST'])
    def legacy_validate_existing(template_id):
        if request.method == 'GET':
            from routes.validation import validate_existing_template
            return validate_existing_template(template_id)
        else:
            from routes.validation import save_existing_template_corrections
            return save_existing_template_corrections(template_id)
    
    @app.route('/validation-corrections/<int:history_id>', methods=['GET'])
    def legacy_validation_corrections(history_id):
        from routes.validation import get_validation_corrections
        return get_validation_corrections(history_id)
    
    # Add legacy template routes
    @app.route('/upload', methods=['POST'])
    def legacy_upload():
        from routes.templates import upload
        return upload()
    
    @app.route('/rules', methods=['GET'])
    def legacy_get_rules():
        # Implementation from original app.py
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT rule_type_id AS rule_id, rule_name, description, parameters, is_custom, 
                       column_name, template_id, source_format, target_format, data_type, is_active
                FROM validation_rule_types
            """)
            rules = cursor.fetchall()
            
            cursor.close()
            
            logging.info(f"Returning {len(rules)} rules from getRules endpoint")
            
            return jsonify({'success': True, 'rules': rules})
        except Exception as e:
            logging.error(f"Error fetching rules: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/template/<int:template_id>/<sheet_name>', methods=['GET'])
    def legacy_get_template(template_id, sheet_name):
        # Implementation from original app.py
        if 'loggedin' not in session or 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT template_name, sheet_name, headers
                FROM excel_templates
                WHERE template_id = %s AND user_id = %s AND status = 'ACTIVE'
            """, (template_id, session['user_id']))
            template_record = cursor.fetchone()
            if not template_record:
                cursor.close()
                return jsonify({'error': 'Template not found'}), 404

            headers = json.loads(template_record['headers']) if template_record['headers'] else []
            stored_sheet_name = template_record['sheet_name'] or sheet_name
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], template_record['template_name'])

            cursor.execute("""
                SELECT COUNT(*) as rule_count
                FROM template_columns tc
                JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                WHERE tc.template_id = %s AND tc.is_selected = TRUE
            """, (template_id,))
            rule_count = cursor.fetchone()['rule_count']
            has_existing_rules = rule_count > 0

            cursor.close()
            return jsonify({
                'success': True,
                'sheets': {stored_sheet_name: {'headers': headers}},
                'file_name': template_record['template_name'],
                'file_path': file_path,
                'sheet_name': stored_sheet_name,
                'has_existing_rules': has_existing_rules
            })
        except Exception as e:
            logging.error(f"Database error in get_template: {str(e)}")
            return jsonify({'error': f'Database error: {str(e)}'}), 500
    
    # Add legacy step routes
    @app.route('/step/<int:step>', methods=['GET', 'POST'])
    def legacy_step(step):
        from routes.steps import handle_step
        return handle_step(step)
    
    # Static file serving for React frontend
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return app.send_static_file(path)
        return app.send_static_file('index.html')
    
    # Health check endpoint for monitoring
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0'
        })
    
    return app

def initialize_app_data():
    """Initialize database and create default data"""
    try:
        logging.info("Initializing database schema...")
        init_db()
        
        logging.info("Creating admin user...")
        User.create_admin_user()
        
        logging.info("Creating default validation rules...")
        ValidationRule.create_default_rules()
        
        logging.info("Application initialization completed successfully")
    except Exception as e:
        logging.error(f"Failed to initialize application: {e}")
        raise

if __name__ == '__main__':
    try:
        # Create the application using factory pattern
        app = create_app()
        
        # Initialize database and default data within app context
        with app.app_context():
            initialize_app_data()
        
        # Get port from environment or use default
        port = int(os.getenv('PORT', 5000))
        
        # Start the application server
        logging.info("Starting Flask server...")
        app.run(debug=False, host='0.0.0.0', port=port)
        
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        raise
