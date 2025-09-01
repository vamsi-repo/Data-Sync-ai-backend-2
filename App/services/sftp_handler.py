import paramiko
import os
import logging
from datetime import  datetime
from typing import List, Dict, Tuple

class SFTPHandler:
    @staticmethod
    def test_connection(hostname: str, username: str, password: str,
                       port: int = 22, path: str = "") -> Tuple[bool, str]:
        """Test SFTP connection with comprehensive error reporting"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Establish SSH connection
            client.connect(
                hostname=hostname,
                port=port,
                username=username,
                password=password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False
            )
            
            # Test SFTP operations
            sftp = client.open_sftp()
            try:
                # Test directory access
                sftp.listdir(path or '.')
                return True, f"SFTP connection successful to path {path or '.'}"
            except IOError as io_err:
                return False, f"Invalid path: {str(io_err)}"
            finally:
                sftp.close()
        
        except paramiko.AuthenticationException:
            return False, "Authentication failed: Invalid credentials"
        except paramiko.SSHException as ssh_err:
            return False, f"SSH connection failed: {str(ssh_err)}"
        except Exception as conn_err:
            return False, f"Failed to connect to SFTP server: {str(conn_err)}"
        finally:
            client.close()
    
    @staticmethod
    def fetch_file(hostname: str, username: str, password: str, remote_file_path: str,
                   local_upload_folder: str, port: int = 22) -> Tuple[bool, str, str]:
        """Securely fetch file from SFTP server"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Connect and authenticate
            client.connect(
                hostname=hostname,
                port=port,
                username=username,
                password=password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False
            )
            
            sftp = client.open_sftp()
            try:
                # Ensure local directory exists
                os.makedirs(local_upload_folder, exist_ok=True)
                
                # Extract filename and create local path
                filename = os.path.basename(remote_file_path)
                if not filename:
                    return False, "Invalid remote file path", None
                
                local_file_path = os.path.join(local_upload_folder, filename)
                
                # Download file
                sftp.get(remote_file_path, local_file_path)
                
                logging.info(f"Successfully downloaded {remote_file_path} to {local_file_path}")
                return True, "File downloaded successfully", local_file_path
                
            except IOError as io_err:
                return False, f"File not found or inaccessible: {str(io_err)}", None
            finally:
                sftp.close()
        
        except paramiko.AuthenticationException:
            return False, "Authentication failed: Invalid credentials", None
        except Exception as e:
            return False, f"SFTP operation failed: {str(e)}", None
        finally:
            client.close()
    
    @staticmethod
    def move_and_upload_file(hostname: str, username: str, password: str,
                            local_file_path: str, original_remote_path: str,
                            port: int = 22) -> Tuple[bool, str]:
        """Move original file to processing and upload corrected file to outbound"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            client.connect(hostname=hostname, username=username, password=password, timeout=10)
            sftp = client.open_sftp()
            
            try:
                # Define standardized folder structure
                inbound_path = "/Inbound"
                outbound_path = "/Outbound"
                processing_path = "/processing"
                
                # Verify required folders exist
                for folder in [inbound_path, outbound_path, processing_path]:
                    try:
                        sftp.stat(folder)
                    except IOError as e:
                        return False, f"{folder} folder not found: {str(e)}"
                
                # Upload corrected file to Outbound directory
                outbound_file_path = f"{outbound_path}/{os.path.basename(local_file_path)}"
                sftp.put(local_file_path, outbound_file_path)
                
                # Move original file from Inbound to processing
                template_name = os.path.basename(original_remote_path)
                inbound_files = sftp.listdir(inbound_path)
                inbound_files_lower = {f.lower(): f for f in inbound_files}
                template_name_lower = template_name.lower()
                
                # Search for original file with possible extensions
                possible_extensions = ['', '.xlsx', '.csv', '.txt', '.dat']
                found_original = False
                
                for ext in possible_extensions:
                    test_file_lower = f"{template_name_lower}{ext.lower()}"
                    if test_file_lower in inbound_files_lower:
                        original_file = f"{inbound_path}/{inbound_files_lower[test_file_lower]}"
                        process_file_path = f"{processing_path}/{os.path.basename(original_file)}"
                        sftp.rename(original_file, process_file_path)
                        found_original = True
                        logging.info(f"Moved original file from {original_file} to {process_file_path}")
                        break
                
                if not found_original:
                    logging.warning(f"Original file not found for moving: {template_name}")
                
                return True, "File approved and moved successfully"
                
            except IOError as e:
                return False, f"File operation failed: {str(e)}"
            finally:
                sftp.close()
        except Exception as e:
            return False, f"SFTP operation failed: {str(e)}"
        finally:
            client.close()