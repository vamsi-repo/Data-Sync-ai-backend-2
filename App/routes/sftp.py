from flask import Blueprint, request, jsonify, session
import logging
from services.sftp_handler import SFTPHandler
from utils.decorators import require_auth, handle_exceptions

sftp_bp = Blueprint('sftp', __name__)

@sftp_bp.route('/test-connection', methods=['POST'])
@require_auth
@handle_exceptions
def test_sftp_connection():
    """Test SFTP connection with provided credentials"""
    try:
        data = request.get_json()
        required_fields = ['hostname', 'username', 'password']
        
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        sftp_config = {
            'hostname': data['hostname'],
            'username': data['username'],
            'password': data['password'],
            'port': data.get('port', 22)
        }
        
        success, message = SFTPHandler.test_connection(sftp_config)
        
        if success:
            return jsonify({'success': True, 'message': 'SFTP connection successful'})
        else:
            return jsonify({'success': False, 'message': f'SFTP connection failed: {message}'}), 400
            
    except Exception as e:
        logging.error(f"Error testing SFTP connection: {str(e)}")
        return jsonify({'success': False, 'message': 'SFTP connection test failed'}), 500

@sftp_bp.route('/upload-file', methods=['POST'])
@require_auth
@handle_exceptions
def upload_file_to_sftp():
    """Upload file to SFTP server"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['local_path', 'remote_path', 'sftp_config']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        local_path = data['local_path']
        remote_path = data['remote_path']
        sftp_config = data['sftp_config']
        
        # Upload file
        success, message = SFTPHandler.upload_file(sftp_config, local_path, remote_path)
        
        if success:
            return jsonify({
                'success': True, 
                'message': 'File uploaded successfully',
                'remote_path': remote_path
            })
        else:
            return jsonify({'success': False, 'message': f'Upload failed: {message}'}), 500
            
    except Exception as e:
        logging.error(f"Error uploading file to SFTP: {str(e)}")
        return jsonify({'success': False, 'message': 'SFTP upload failed'}), 500

@sftp_bp.route('/download-file', methods=['POST'])
@require_auth
@handle_exceptions
def download_file_from_sftp():
    """Download file from SFTP server"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['remote_path', 'local_path', 'sftp_config']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        remote_path = data['remote_path']
        local_path = data['local_path']
        sftp_config = data['sftp_config']
        
        # Download file
        success, message = SFTPHandler.download_file(sftp_config, remote_path, local_path)
        
        if success:
            return jsonify({
                'success': True, 
                'message': 'File downloaded successfully',
                'local_path': local_path
            })
        else:
            return jsonify({'success': False, 'message': f'Download failed: {message}'}), 500
            
    except Exception as e:
        logging.error(f"Error downloading file from SFTP: {str(e)}")
        return jsonify({'success': False, 'message': 'SFTP download failed'}), 500

@sftp_bp.route('/list-files', methods=['POST'])
@require_auth
@handle_exceptions
def list_sftp_files():
    """List files in SFTP directory"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['remote_path', 'sftp_config']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        remote_path = data['remote_path']
        sftp_config = data['sftp_config']
        
        # List files
        files, message = SFTPHandler.list_files(sftp_config, remote_path)
        
        if files is not None:
            return jsonify({
                'success': True,
                'files': files,
                'message': 'Files listed successfully'
            })
        else:
            return jsonify({'success': False, 'message': f'List failed: {message}'}), 500
            
    except Exception as e:
        logging.error(f"Error listing SFTP files: {str(e)}")
        return jsonify({'success': False, 'message': 'SFTP file listing failed'}), 500

@sftp_bp.route('/delete-file', methods=['DELETE'])
@require_auth
@handle_exceptions
def delete_sftp_file():
    """Delete file from SFTP server"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['remote_path', 'sftp_config']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        remote_path = data['remote_path']
        sftp_config = data['sftp_config']
        
        # Delete file
        success, message = SFTPHandler.delete_file(sftp_config, remote_path)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'File deleted successfully'
            })
        else:
            return jsonify({'success': False, 'message': f'Delete failed: {message}'}), 500
            
    except Exception as e:
        logging.error(f"Error deleting SFTP file: {str(e)}")
        return jsonify({'success': False, 'message': 'SFTP file deletion failed'}), 500

@sftp_bp.route('/create-directory', methods=['POST'])
@require_auth
@handle_exceptions
def create_sftp_directory():
    """Create directory on SFTP server"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['remote_path', 'sftp_config']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        remote_path = data['remote_path']
        sftp_config = data['sftp_config']
        
        # Create directory
        success, message = SFTPHandler.create_directory(sftp_config, remote_path)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Directory created successfully'
            })
        else:
            return jsonify({'success': False, 'message': f'Directory creation failed: {message}'}), 500
            
    except Exception as e:
        logging.error(f"Error creating SFTP directory: {str(e)}")
        return jsonify({'success': False, 'message': 'SFTP directory creation failed'}), 500

@sftp_bp.route('/get-file-info', methods=['POST'])
@require_auth
@handle_exceptions
def get_sftp_file_info():
    """Get file information from SFTP server"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['remote_path', 'sftp_config']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        remote_path = data['remote_path']
        sftp_config = data['sftp_config']
        
        # Get file info
        file_info, message = SFTPHandler.get_file_info(sftp_config, remote_path)
        
        if file_info is not None:
            return jsonify({
                'success': True,
                'file_info': file_info,
                'message': 'File info retrieved successfully'
            })
        else:
            return jsonify({'success': False, 'message': f'Get file info failed: {message}'}), 500
            
    except Exception as e:
        logging.error(f"Error getting SFTP file info: {str(e)}")
        return jsonify({'success': False, 'message': 'SFTP file info retrieval failed'}), 500
