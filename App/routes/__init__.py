# routes/__init__.py
import logging
from .auth import auth_bp
from .templates import templates_bp
from .validation import validation_bp
from .sftp import sftp_bp
from .steps import step_bp
from .analytics import analytics_bp

def register_blueprints(app):
    """Register all blueprints with comprehensive error handling"""
    try:
        app.register_blueprint(auth_bp, url_prefix='')
        app.register_blueprint(templates_bp, url_prefix='')
        app.register_blueprint(validation_bp, url_prefix='')
        app.register_blueprint(sftp_bp, url_prefix='')
        app.register_blueprint(step_bp, url_prefix='')
        app.register_blueprint(analytics_bp, url_prefix='')
        
        logging.info("All blueprints registered successfully")
    except Exception as e:
        logging.error(f"Error registering blueprints: {str(e)}")
        raise
