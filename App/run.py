#!/usr/bin/env python3
"""
Keansa AI Suite 2025 - Startup Script
This script provides a convenient way to start the application with proper initialization
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the current directory to Python path
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))

def setup_logging():
    """Setup application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = [
        'MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please create a .env file with the required configuration")
        return False
    
    return True

def create_directories():
    """Create necessary directories"""
    directories = ['uploads', 'sessions', 'logs', 'backups']
    
    for directory in directories:
        dir_path = current_dir / directory
        dir_path.mkdir(exist_ok=True)
        print(f"✅ Directory ensured: {directory}")

def main():
    """Main startup function"""
    print("🚀 Starting Keansa AI Suite 2025...")
    print(f"📁 Working directory: {current_dir}")
    
    # Setup logging
    setup_logging()
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    try:
        # Import and start the application
        from app import create_app, initialize_app_data
        
        print("🔧 Creating Flask application...")
        flask_app = create_app()
        
        print("🗃️ Initializing database and default data...")
        with flask_app.app_context():
            initialize_app_data()
        
        # Get configuration
        port = int(os.getenv('PORT', 5000))
        host = os.getenv('HOST', '0.0.0.0')
        debug = os.getenv('FLASK_ENV', 'production') == 'development'
        
        print(f"🌐 Server configuration:")
        print(f"   Host: {host}")
        print(f"   Port: {port}")
        print(f"   Debug: {debug}")
        print(f"   Environment: {os.getenv('FLASK_ENV', 'production')}")
        
        print("✅ Application initialized successfully!")
        print(f"🚀 Starting server on http://{host}:{port}")
        print("🛑 Press Ctrl+C to stop the server")
        
        # Start the Flask development server
        flask_app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        logging.error(f"❌ Failed to start application: {str(e)}")
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
