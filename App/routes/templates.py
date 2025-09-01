from flask import Blueprint, request, jsonify, session, send_file, current_app, g
import os
import json
import pandas as pd
from io import StringIO
import logging
from models.template import Template
from models.user import User
from models.validation import ValidationRule, DataValidator
from services.file_handler import FileHandler
from config.database import get_db_connection

templates_bp = Blueprint('templates', __name__)

@templates_bp.route('/templates', methods=['GET'])
def get_templates():
    """Get templates list - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        logging.warning("Unauthorized access to /templates: session missing")
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT template_id, template_name, created_at, status
            FROM excel_templates
            WHERE user_id = %s AND status = 'ACTIVE'
            ORDER BY created_at DESC
            LIMIT 100
        """, (session['user_id'],))
        templates = cursor.fetchall()
        cursor.execute("SHOW COLUMNS FROM excel_templates LIKE 'is_corrected'")
        if cursor.fetchone():
            cursor.execute("""
                SELECT template_id, template_name, created_at, status, is_corrected
                FROM excel_templates
                WHERE user_id = %s AND status = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT 100
            """, (session['user_id'],))
            templates = cursor.fetchall()
        cursor.close()
        logging.info(f"Fetched {len(templates)} templates for user {session['user_id']}")
        return jsonify({'success': True, 'templates': templates})
    except Exception as e:
        logging.error(f'Error fetching templates: {str(e)}')
        return jsonify({'success': False, 'message': f'Error fetching templates: {str(e)}'}), 500

@templates_bp.route('/upload', methods=['POST'])
def upload():
    """File upload endpoint - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        logging.warning("Unauthorized access to /upload: session missing")
        return jsonify({'error': 'Not logged in'}), 401
    if 'file' not in request.files:
        logging.warning("No file provided in upload request")
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if file.filename == '':
        logging.warning("No file selected in upload request")
        return jsonify({'error': 'No file selected'}), 400
    
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    try:
        file.save(file_path)
        logging.info(f"File saved: {file_path}")
    except Exception as e:
        logging.error(f"Failed to save file {file.filename}: {str(e)}")
        return jsonify({'error': f'Failed to save file: {str(e)}'}), 500

    try:
        sheets = FileHandler.read_file(file_path)
        logging.debug(f"Sheets extracted: {list(sheets.keys())}")
    except Exception as e:
        logging.error(f"Failed to read file {file_path}: {str(e)}")
        return jsonify({'error': f'Failed to read file: {str(e)}'}), 400

    try:
        sheet_names = list(sheets.keys())
        if not sheet_names:
            logging.error("No sheets found in the file")
            return jsonify({'error': 'No sheets found in the file'}), 400
        sheet_name = sheet_names[0]
        df = sheets[sheet_name]
        logging.debug(f"Raw DataFrame: {df.to_dict()}")
        logging.debug(f"DataFrame shape: {df.shape}")
        header_row = FileHandler.find_header_row(df)
        if header_row == -1:
            logging.warning(f"Could not detect header row in file {file.filename}")
            return jsonify({'error': 'Could not detect header row'}), 400
        headers = df.iloc[header_row].tolist()
        logging.debug(f"Headers extracted: {headers}")
        if not headers or all(not h for h in headers):
            logging.error("No valid headers found in file")
            return jsonify({'error': 'No valid headers found in the file'}), 400
    except Exception as e:
        logging.error(f"Error processing file {file.filename}: {str(e)}")
        return jsonify({'error': f'Error processing file: {str(e)}'}), 400

    # Clear session data
    session.pop('df', None)
    session.pop('header_row', None)
    session.pop('headers', None)
    session.pop('sheet_name', None)
    session.pop('current_step', None)
    session.pop('selected_headers', None)
    session.pop('validations', None)
    session.pop('error_cell_locations', None)
    session.pop('data_rows', None)
    session.pop('corrected_file_path', None)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if a template with the same name, headers, and sheet name exists
        cursor.execute("""
            SELECT template_id, headers, sheet_name
            FROM excel_templates
            WHERE template_name = %s AND user_id = %s AND status = 'ACTIVE'
            ORDER BY created_at DESC
        """, (file.filename, session['user_id']))
        existing_templates = cursor.fetchall()
        logging.info(f"Found {len(existing_templates)} existing templates with name {file.filename}")

        template_id = None
        has_existing_rules = False
        validations = {}
        selected_headers = []

        matching_template = None
        for template in existing_templates:
            stored_headers = json.loads(template['headers']) if template['headers'] else []
            stored_sheet_name = template['sheet_name']
            if stored_headers == headers and stored_sheet_name == sheet_name:
                matching_template = template
                break

        if matching_template:
            template_id = matching_template['template_id']
            # Check for existing rules
            cursor.execute("""
                SELECT tc.column_name, vrt.rule_name
                FROM template_columns tc
                JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
                WHERE tc.template_id = %s AND tc.is_selected = TRUE
            """, (template_id,))
            rules_data = cursor.fetchall()
            for row in rules_data:
                column_name = row['column_name']
                rule_name = row['rule_name']
                if column_name not in validations:
                    validations[column_name] = []
                validations[column_name].append(rule_name)
                if column_name not in selected_headers:
                    selected_headers.append(column_name)
            has_existing_rules = len(validations) > 0
        else:
            # New template
            cursor.execute("""
                INSERT INTO excel_templates (template_name, user_id, sheet_name, headers, is_corrected)
                VALUES (%s, %s, %s, %s, %s)
            """, (file.filename, session['user_id'], sheet_name, json.dumps(headers), False))
            template_id = cursor.lastrowid
            column_data = [(template_id, header, i + 1, False) for i, header in enumerate(headers)]
            cursor.executemany("""
                INSERT INTO template_columns (template_id, column_name, column_position, is_selected)
                VALUES (%s, %s, %s, %s)
            """, column_data)

        conn.commit()
        cursor.close()

        session['file_path'] = file_path
        session['template_id'] = template_id
        session['df'] = df.to_json()
        session['header_row'] = header_row
        session['headers'] = headers
        session['sheet_name'] = sheet_name
        session['current_step'] = 1 if not has_existing_rules else 3
        session['validations'] = validations
        session['selected_headers'] = selected_headers
        session['has_existing_rules'] = has_existing_rules

        logging.info(f"Upload processed: template_id={template_id}, filename={file.filename}, has_existing_rules={has_existing_rules}, redirecting to step={'3' if has_existing_rules else '1'}")

        return jsonify({
            'success': True,
            'sheets': {sheet_name: {'headers': headers}},
            'file_name': file.filename,
            'template_id': template_id,
            'has_existing_rules': has_existing_rules,
            'sheet_name': sheet_name,
            'skip_to_step_3': has_existing_rules
        })
    except Exception as e:
        logging.error(f'Error saving template: {str(e)}')
        return jsonify({'error': f'Error saving template: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@templates_bp.route('/step/1', methods=['POST'])
def submit_step_one():
    """Step 1 submission - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        logging.warning("Unauthorized access to /step/1: session missing")
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    try:
        headers = request.form.getlist('headers')
        new_header_row = request.form.get('new_header_row')
        logging.debug(f"Step 1 submitted: headers={headers}, new_header_row={new_header_row}")
        if not headers:
            logging.error("No headers provided in step 1")
            return jsonify({'success': False, 'message': 'No headers provided'}), 400
        if 'file_path' not in session or 'template_id' not in session:
            logging.error("Session missing file_path or template_id")
            return jsonify({'success': False, 'message': 'Session data missing'}), 400

        file_path = session['file_path']
        template_id = session['template_id']
        sheets = FileHandler.read_file(file_path)
        sheet_name = session.get('sheet_name', list(sheets.keys())[0])
        df = sheets[sheet_name]
        header_row = FileHandler.find_header_row(df)
        if header_row == -1:
            logging.error("Could not detect header row")
            return jsonify({'success': False, 'message': 'Could not detect header row'}), 400
        df.columns = session['headers']
        df = df.iloc[header_row + 1:].reset_index(drop=True)

        # Auto-detect rules
        validations = DataValidator.assign_default_rules_to_columns(df, headers)
        session['selected_headers'] = headers
        session['validations'] = validations
        session['current_step'] = 2

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE template_columns
            SET is_selected = FALSE
            WHERE template_id = %s
        """, (template_id,))
        for header in headers:
            cursor.execute("""
                UPDATE template_columns
                SET is_selected = TRUE
                WHERE template_id = %s AND column_name = %s
            """, (template_id, header))
            cursor.execute("""
                SELECT column_id FROM template_columns
                WHERE template_id = %s AND column_name = %s
            """, (template_id, header))
            column_id = cursor.fetchone()[0]
            for rule_name in validations.get(header, []):
                cursor.execute("""
                    SELECT rule_type_id FROM validation_rule_types
                    WHERE rule_name = %s AND is_custom = FALSE
                """, (rule_name,))
                result = cursor.fetchone()
                if result:
                    rule_type_id = result[0]
                    cursor.execute("""
                        INSERT IGNORE INTO column_validation_rules (column_id, rule_type_id, rule_config)
                        VALUES (%s, %s, %s)
                    """, (column_id, rule_type_id, '{}'))
        conn.commit()
        cursor.close()
        logging.info(f"Step 1 completed: headers={headers}, auto-assigned rules={validations}")
        return jsonify({'success': True, 'headers': headers, 'validations': validations})
    except Exception as e:
        logging.error(f"Error in step 1: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@templates_bp.route('/step/2', methods=['POST'])
def submit_step_two():
    """Step 2 submission - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        logging.warning("Unauthorized access to /step/2: session missing")
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    try:
        action = request.form.get('action', 'save')
        validations = {}
        for key, values in request.form.lists():
            if key.startswith('validations_'):
                header = key.replace('validations_', '')
                validations[header] = values
        logging.debug(f"Step 2 submitted: action={action}, validations={validations}")
        if not validations and action == 'review':
            logging.error("No validations provided for review")
            return jsonify({'success': False, 'message': 'No validations provided'}), 400

        template_id = session.get('template_id')
        if not template_id:
            logging.error("Session missing template_id")
            return jsonify({'success': False, 'message': 'Session data missing'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM column_validation_rules
            WHERE column_id IN (
                SELECT column_id FROM template_columns WHERE template_id = %s
            )
        """, (template_id,))
        for header, rules in validations.items():
            cursor.execute("""
                SELECT column_id FROM template_columns
                WHERE template_id = %s AND column_name = %s
            """, (template_id, header))
            result = cursor.fetchone()
            if not result:
                continue
            column_id = result[0]
            for rule_name in rules:
                cursor.execute("""
                    SELECT rule_type_id FROM validation_rule_types
                    WHERE rule_name = %s
                """, (rule_name,))
                result = cursor.fetchone()
                if result:
                    rule_type_id = result[0]
                    cursor.execute("""
                        INSERT IGNORE INTO column_validation_rules (column_id, rule_type_id, rule_config)
                        VALUES (%s, %s, %s)
                    """, (column_id, rule_type_id, '{}'))
        conn.commit()
        cursor.close()

        session['validations'] = validations
        session['current_step'] = 3 if action == 'review' else 2
        logging.info(f"Step 2 completed: action={action}, validations={validations}")
        return jsonify({'success': True, 'message': 'Step 2 completed successfully'})
    except Exception as e:
        logging.error(f"Error in step 2: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Add missing routes from old.py exactly as they work
@templates_bp.route('/upload', methods=['POST'])
def upload():
    """File upload endpoint - exactly like old.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    try:
        file.save(file_path)
        logging.info(f"File saved: {file_path}")
    except Exception as e:
        return jsonify({'error': f'Failed to save file: {str(e)}'}), 500

    try:
        from services.file_handler import FileHandler
        sheets = FileHandler.read_file(file_path)
        sheet_names = list(sheets.keys())
        if not sheet_names:
            return jsonify({'error': 'No sheets found in the file'}), 400
            
        sheet_name = sheet_names[0]
        df = sheets[sheet_name]
        header_row = FileHandler.find_header_row(df)
        if header_row == -1:
            return jsonify({'error': 'Could not detect header row'}), 400
            
        headers = df.iloc[header_row].tolist()
        if not headers or all(not h for h in headers):
            return jsonify({'error': 'No valid headers found in the file'}), 400
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 400

    # Clear session data
    for key in ['df', 'header_row', 'headers', 'sheet_name', 'current_step', 'selected_headers', 'validations', 'error_cell_locations', 'data_rows', 'corrected_file_path']:
        session.pop(key, None)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check for existing templates - exactly like old.py
        cursor.execute("""
            SELECT template_id, headers, sheet_name
            FROM excel_templates
            WHERE template_name = %s AND user_id = %s AND status = 'ACTIVE'
            ORDER BY created_at DESC
        """, (file.filename, session['user_id']))
        existing_templates = cursor.fetchall()

        template_id = None
        has_existing_rules = False
        validations = {}
        selected_headers = []

        matching_template = None
        for template in existing_templates:
            stored_headers = json.loads(template['headers']) if template['headers'] else []
            stored_sheet_name = template['sheet_name']
            if stored_headers == headers and stored_sheet_name == sheet_name:
                matching_template = template
                break

        if matching_template:
            template_id = matching_template['template_id']
            cursor.execute("""
                SELECT tc.column_name, vrt.rule_name
                FROM template_columns tc
                JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
                JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
                WHERE tc.template_id = %s AND tc.is_selected = TRUE
            """, (template_id,))
            rules_data = cursor.fetchall()
            for row in rules_data:
                column_name = row['column_name']
                rule_name = row['rule_name']
                if column_name not in validations:
                    validations[column_name] = []
                validations[column_name].append(rule_name)
                if column_name not in selected_headers:
                    selected_headers.append(column_name)
            has_existing_rules = len(validations) > 0
        else:
            cursor.execute("""
                INSERT INTO excel_templates (template_name, user_id, sheet_name, headers, is_corrected)
                VALUES (%s, %s, %s, %s, %s)
            """, (file.filename, session['user_id'], sheet_name, json.dumps(headers), False))
            template_id = cursor.lastrowid
            column_data = [(template_id, header, i + 1, False) for i, header in enumerate(headers)]
            cursor.executemany("""
                INSERT INTO template_columns (template_id, column_name, column_position, is_selected)
                VALUES (%s, %s, %s, %s)
            """, column_data)

        conn.commit()
        cursor.close()

        # Set session data - exactly like old.py
        session['file_path'] = file_path
        session['template_id'] = template_id
        session['df'] = df.to_json()
        session['header_row'] = header_row
        session['headers'] = headers
        session['sheet_name'] = sheet_name
        session['current_step'] = 1 if not has_existing_rules else 3
        session['validations'] = validations
        session['selected_headers'] = selected_headers
        session['has_existing_rules'] = has_existing_rules

        return jsonify({
            'success': True,
            'sheets': {sheet_name: {'headers': headers}},
            'file_name': file.filename,
            'template_id': template_id,
            'has_existing_rules': has_existing_rules,
            'sheet_name': sheet_name,
            'skip_to_step_3': has_existing_rules
        })
    except Exception as e:
        logging.error(f'Error saving template: {str(e)}')
        return jsonify({'error': f'Error saving template: {str(e)}'}), 500

@templates_bp.route('/step/1', methods=['POST'])
def submit_step_one():
    """Step 1 submission - exactly like old.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        headers = request.form.getlist('headers')
        if not headers:
            return jsonify({'success': False, 'message': 'No headers provided'}), 400
        if 'file_path' not in session or 'template_id' not in session:
            return jsonify({'success': False, 'message': 'Session data missing'}), 400

        from services.file_handler import FileHandler
        from models.validation import DataValidator
        
        file_path = session['file_path']
        template_id = session['template_id']
        sheets = FileHandler.read_file(file_path)
        sheet_name = session.get('sheet_name', list(sheets.keys())[0])
        df = sheets[sheet_name]
        header_row = FileHandler.find_header_row(df)
        if header_row == -1:
            return jsonify({'success': False, 'message': 'Could not detect header row'}), 400
        df.columns = session['headers']
        df = df.iloc[header_row + 1:].reset_index(drop=True)

        # Auto-detect rules - exactly like old.py
        validations = DataValidator.assign_default_rules_to_columns(df, headers)
        session['selected_headers'] = headers
        session['validations'] = validations
        session['current_step'] = 2

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE template_columns SET is_selected = FALSE WHERE template_id = %s", (template_id,))
        for header in headers:
            cursor.execute("""
                UPDATE template_columns SET is_selected = TRUE
                WHERE template_id = %s AND column_name = %s
            """, (template_id, header))
            cursor.execute("""
                SELECT column_id FROM template_columns
                WHERE template_id = %s AND column_name = %s
            """, (template_id, header))
            column_id = cursor.fetchone()[0]
            for rule_name in validations.get(header, []):
                cursor.execute("""
                    SELECT rule_type_id FROM validation_rule_types
                    WHERE rule_name = %s AND is_custom = FALSE
                """, (rule_name,))
                result = cursor.fetchone()
                if result:
                    rule_type_id = result[0]
                    cursor.execute("""
                        INSERT IGNORE INTO column_validation_rules (column_id, rule_type_id, rule_config)
                        VALUES (%s, %s, %s)
                    """, (column_id, rule_type_id, '{}'))
        conn.commit()
        cursor.close()
        return jsonify({'success': True, 'headers': headers, 'validations': validations})
    except Exception as e:
        logging.error(f"Error in step 1: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Duplicate function removed - keeping only the first get_templates() function above

@templates_bp.route('/<int:template_id>/<sheet_name>', methods=['GET'])
def get_template(template_id, sheet_name):
    """Get specific template - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        logging.warning("Unauthorized access to /template: session missing")
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
        logging.debug(f"Template query result for template_id {template_id}: {template_record}")
        if not template_record:
            logging.error(f"Template not found for template_id: {template_id}, user_id: {session['user_id']}")
            cursor.close()
            return jsonify({'error': 'Template not found'}), 404

        headers = json.loads(template_record['headers']) if template_record['headers'] else []
        stored_sheet_name = template_record['sheet_name'] or sheet_name
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], template_record['template_name'])
        logging.debug(f"Template details: template_name={template_record['template_name']}, sheet_name={stored_sheet_name}, headers={headers}, file_path={file_path}")

        cursor.execute("""
            SELECT COUNT(*) as rule_count
            FROM template_columns tc
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            WHERE tc.template_id = %s AND tc.is_selected = TRUE
        """, (template_id,))
        rule_count = cursor.fetchone()['rule_count']
        has_existing_rules = rule_count > 0
        logging.debug(f"Template {template_id} has {rule_count} validation rules, has_existing_rules: {has_existing_rules}")

        if not headers or not os.path.exists(file_path):
            logging.warning(f"No headers or file missing for template_id: {template_id}, attempting to read from file")
            if os.path.exists(file_path):
                try:
                    sheets = FileHandler.read_file(file_path)
                    sheet_names = list(sheets.keys())
                    logging.debug(f"Available sheets: {sheet_names}")
                    if not sheet_names:
                        logging.error(f"No sheets found in file {file_path}")
                        cursor.close()
                        return jsonify({'error': 'No sheets found in the file'}), 400
                    actual_sheet_name = stored_sheet_name if stored_sheet_name in sheets else sheet_names[0]
                    df = sheets[actual_sheet_name]
                    header_row = FileHandler.find_header_row(df)
                    if header_row == -1:
                        logging.error(f"Could not detect header row in file {file_path}")
                        cursor.close()
                        return jsonify({'error': 'Could not detect header row'}), 400
                    headers = df.iloc[header_row].tolist()
                    logging.debug(f"Headers extracted from file: {headers}")
                    # Update database with new headers
                    cursor.execute("""
                        UPDATE excel_templates
                        SET headers = %s, sheet_name = %s
                        WHERE template_id = %s
                    """, (json.dumps(headers), actual_sheet_name, template_id))
                    conn.commit()
                    session['file_path'] = file_path
                    session['template_id'] = template_id
                    session['df'] = df.to_json()
                    session['header_row'] = header_row
                    session['headers'] = headers
                    session['sheet_name'] = actual_sheet_name
                    session['current_step'] = 1
                except Exception as e:
                    logging.error(f"Error reading file {file_path}: {str(e)}")
                    cursor.close()
                    return jsonify({'error': f'Error reading file: {str(e)}'}), 400
            else:
                logging.error(f"Template file not found: {file_path}")
                cursor.close()
                return jsonify({'error': 'Template file not found and no headers stored'}), 404

        if not headers:
            logging.error(f"No valid headers could be retrieved for template_id: {template_id}")
            cursor.close()
            return jsonify({'error': 'No valid headers found'}), 400

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
    finally:
        if conn:
            conn.close()

@templates_bp.route('/<int:template_id>/rules', methods=['GET'])
def get_template_rules(template_id):
    """Get template validation rules - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT tc.column_name, vrt.rule_name
            FROM template_columns tc
            LEFT JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            LEFT JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = %s AND tc.is_selected = TRUE
        """, (template_id,))
        rules_data = cursor.fetchall()
        logging.debug(f"Rules data for template_id {template_id}: {rules_data}")
        cursor.close()

        rules = {}
        for row in rules_data:
            column_name = row['column_name']
            rule_name = row['rule_name']
            if column_name not in rules:
                rules[column_name] = []
            if rule_name:
                rules[column_name].append(rule_name)

        logging.debug(f"Constructed rules for template_id {template_id}: {rules}")
        return jsonify({'success': True, 'rules': rules})
    except Exception as e:
        logging.error(f'Error fetching template rules: {str(e)}')
        return jsonify({'error': f'Error fetching template rules: {str(e)}'}), 500

@templates_bp.route('/<int:template_id>/rules', methods=['POST'])
def update_template_rules(template_id):
    """Update template validation rules - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.get_json()
    rules = data.get('rules', {})

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT column_id, column_name FROM template_columns WHERE template_id = %s AND is_selected = TRUE", (template_id,))
        column_map = {row['column_name']: row['column_id'] for row in cursor.fetchall()}

        cursor.execute("SELECT rule_type_id, rule_name FROM validation_rule_types WHERE is_active = TRUE")
        rule_map = {row['rule_name']: row['rule_type_id'] for row in cursor.fetchall()}

        cursor.execute("DELETE FROM column_validation_rules WHERE column_id IN (SELECT column_id FROM template_columns WHERE template_id = %s AND is_selected = TRUE)", (template_id,))

        validation_data = []
        for header, rule_names in rules.items():
            column_id = column_map.get(header)
            if not column_id:
                continue
            for rule_name in rule_names:
                rule_type_id = rule_map.get(rule_name)
                if rule_type_id:
                    validation_data.append((column_id, rule_type_id, json.dumps({})))
                else:
                    logging.warning(f"No rule_type_id found for validation {rule_name}")
        if validation_data:
            cursor.executemany("""
                INSERT INTO column_validation_rules (column_id, rule_type_id, rule_config)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE rule_config = VALUES(rule_config)
            """, validation_data)
            logging.debug(f"Inserted validation rules: {validation_data}")
        conn.commit()
        cursor.close()
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f'Error updating template rules: {str(e)}')
        return jsonify({'error': f'Error updating template rules: {str(e)}'}), 500

@templates_bp.route('/delete-template/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    """Delete template - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        logging.warning("Unauthorized access to /delete-template: session missing")
        return jsonify({'error': 'Not logged in'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT template_name
            FROM excel_templates
            WHERE template_id = %s AND user_id = %s AND status = 'ACTIVE'
        """, (template_id, session['user_id']))
        template_entry = cursor.fetchone()
        if not template_entry:
            cursor.close()
            return jsonify({'error': 'Template not found'}), 404

        cursor.execute("""
            DELETE FROM validation_history
            WHERE template_id = %s AND user_id = %s
        """, (template_id, session['user_id']))

        cursor.execute("""
            DELETE FROM excel_templates
            WHERE template_id = %s AND user_id = %s
        """, (template_id, session['user_id']))

        conn.commit()
        cursor.close()
        return jsonify({'success': True, 'message': 'Template deleted successfully'})
    except Exception as e:
        logging.error(f'Error deleting template: {str(e)}')
        return jsonify({'error': f'Error deleting template: {str(e)}'}), 500
