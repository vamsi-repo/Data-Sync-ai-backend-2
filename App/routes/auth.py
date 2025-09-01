from flask import Blueprint, request, jsonify, session, g
import logging
from models.user import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/check-auth', methods=['GET'])
def check_auth():
    """Check authentication status - from original app.py"""
    try:
        logging.debug(f"Checking auth with session: {dict(session)}")
        if 'loggedin' in session and 'user_id' in session:
            user = User.get_user_by_id(session['user_id'])
            if user:
                logging.info(f"User {session.get('user_email')} is authenticated")
                return jsonify({
                    'success': True,
                    'user': {
                        'email': user['email'],
                        'id': session['user_id'],
                        'first_name': user['first_name']
                    }
                })
            else:
                logging.warning("User not found in database")  
                session.clear()
                return jsonify({'success': False, 'message': 'User not found'}), 401
        logging.warning("User not authenticated")
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    except Exception as e:
        logging.error(f"Error in check-auth endpoint: {str(e)}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@auth_bp.route('/authenticate', methods=['POST'])
def authenticate():
    """User authentication endpoint - from original app.py"""
    try:
        email = request.form.get('username') or request.form.get('email')
        password = request.form.get('password')
        logging.debug(f"Login attempt: email={email}, password={'*' * len(password) if password else 'None'}")
        
        if not email or not password:
            logging.warning(f"Login failed: Email or password missing")
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400

        # Authenticate user
        user = User.authenticate_user(email, password)
        if user:
            session['loggedin'] = True
            session['user_email'] = user['email']
            session['user_id'] = user['id']
            session.permanent = True
            logging.info(f"User {email} logged in successfully. Session: {dict(session)}")
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': {'email': user['email'], 'id': user['id']}
            }), 200
        else:
            logging.warning(f"Invalid credentials for {email}")
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    except Exception as e:
        logging.error(f"Unexpected error during login: {str(e)}")
        return jsonify({'success': False, 'message': f'Unexpected error: {str(e)}'}), 500

@auth_bp.route('/register', methods=['POST'])
def register():
    """User registration endpoint - from original app.py"""
    try:
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([first_name, last_name, email, mobile, password, confirm_password]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        if password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match'}), 400

        user_id = User.create_user(first_name, last_name, email, mobile, password)
        session['loggedin'] = True
        session['user_email'] = email
        session['user_id'] = user_id
        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'user': {'email': email, 'id': user_id}
        }), 200
    except Exception as e:
        logging.error(f"Error during registration: {str(e)}")
        return jsonify({'success': False, 'message': f'Registration error: {str(e)}'}), 500

@auth_bp.route('/reset_password', methods=['POST'])
def reset_password():
    """Password reset endpoint - from original app.py"""
    try:
        data = request.get_json() or request.form.to_dict()
        email = data.get('email')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not all([email, new_password, confirm_password]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match'}), 400
        
        success = User.reset_password(email, new_password)
        if success:
            return jsonify({'success': True, 'message': 'Password reset successful'}), 200
        else:
            return jsonify({'success': False, 'message': 'Email not found'}), 404
    except Exception as e:
        logging.error(f"Error during password reset: {str(e)}")
        return jsonify({'success': False, 'message': f'Error resetting password: {str(e)}'}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """User logout endpoint"""
    try:
        user_email = session.get('user_email')
        session.clear()
        logging.info(f"User {user_email} logged out successfully")
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        logging.error(f"Error during logout: {str(e)}")
        return jsonify({'success': False, 'message': 'Logout error'}), 500

@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get user profile information"""
    try:
        if 'loggedin' not in session or 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not logged in'}), 401
        
        user = User.get_user_by_id(session['user_id'])
        if user:
            return jsonify({
                'success': True,
                'user': {
                    'email': user['email'],
                    'first_name': user['first_name'],
                    'last_name': user['last_name']
                }
            })
        else:
            return jsonify({'success': False, 'message': 'User not found'}), 404
    except Exception as e:
        logging.error(f"Error getting profile: {str(e)}")
        return jsonify({'success': False, 'message': 'Error fetching profile'}), 500

@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """Update user profile information"""
    try:
        if 'loggedin' not in session or 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not logged in'}), 401
        
        data = request.get_json() or request.form.to_dict()
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        mobile = data.get('mobile')
        
        if not all([first_name, last_name, mobile]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        success = User.update_user_profile(session['user_id'], first_name, last_name, mobile)
        if success:
            return jsonify({'success': True, 'message': 'Profile updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update profile'}), 500
    except Exception as e:
        logging.error(f"Error updating profile: {str(e)}")
        return jsonify({'success': False, 'message': 'Error updating profile'}), 500
