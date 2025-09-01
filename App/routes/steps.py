from flask import Blueprint, request, jsonify, session, current_app
import os
import json
import pandas as pd
from io import StringIO
import logging
from models.validation import ValidationRule, DataValidator
from services.file_handler import FileHandler
from config.database import get_db_connection

step_bp = Blueprint('steps', __name__)

@step_bp.route('/1', methods=['POST'])
def submit_step_one():
    """Submit step 1 - from original app.py"""
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

        from services.file_handler import FileHandler
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
        
        # Mark template as configured after successful rule assignment
        cursor.execute("""
            UPDATE excel_templates 
            SET is_corrected = TRUE 
            WHERE template_id = %s AND user_id = %s
        """, (template_id, session['user_id']))
        conn.commit()
        cursor.close()
        logging.info(f"Step 1 completed: headers={headers}, auto-assigned rules={validations}")
        return jsonify({'success': True, 'headers': headers, 'validations': validations})
    except Exception as e:
        logging.error(f"Error in step 1: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@step_bp.route('/validate-existing/<int:template_id>', methods=['POST'])
def save_existing_template_corrections(template_id):
    """Save corrections for existing template - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        data = request.get_json()
        corrections = data.get('corrections', {})
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get template details
        cursor.execute("""
            SELECT template_name, sheet_name, headers 
            FROM excel_templates 
            WHERE template_id = %s AND user_id = %s
        """, (template_id, session['user_id']))
        template = cursor.fetchone()
        if not template:
            cursor.close()
            return jsonify({'success': False, 'message': 'Template not found'}), 404
        
        # Get the data to correct
        df_json = session.get('df')
        if not df_json:
            cursor.close()
            return jsonify({'success': False, 'message': 'No data available in session'}), 400
        
        df = pd.read_json(StringIO(df_json))
        headers = json.loads(template['headers'])
        df.columns = headers
        df = df.iloc[session.get('header_row', 0) + 1:].reset_index(drop=True)
        
        # Apply corrections
        correction_count = 0
        for column, row_corrections in corrections.items():
            if column not in headers:
                continue
            for row_str, value in row_corrections.items():
                try:
                    row_index = int(row_str)
                    if 0 <= row_index < len(df):
                        # Store original value for correction tracking
                        original_value = df.at[row_index, column]
                        df.at[row_index, column] = value
                        correction_count += 1
                        logging.info(f"Applied correction: Row {row_index+1}, Column {column}, {original_value} → {value}")
                except (ValueError, IndexError) as e:
                    logging.warning(f"Invalid correction: {row_str}, {column}, {value} - {str(e)}")
                    continue
        
        # Save corrected file
        base_name, ext = os.path.splitext(template['template_name'])
        corrected_filename = f"{base_name}_corrected{ext}"
        corrected_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], corrected_filename)
        
        try:
            if ext.lower() == '.xlsx':
                df.to_excel(corrected_file_path, index=False, sheet_name=template['sheet_name'])
                logging.info(f"Saved Excel file: {corrected_file_path}")
            else:
                df.to_csv(corrected_file_path, index=False)
                logging.info(f"Saved CSV file: {corrected_file_path}")
        except Exception as save_error:
            cursor.close()
            logging.error(f"Failed to save corrected file: {str(save_error)}")
            return jsonify({'success': False, 'message': f'Failed to save corrected file: {str(save_error)}'}), 500
        
        # Save to validation history
        cursor.execute("""
            INSERT INTO validation_history (template_id, template_name, error_count, corrected_file_path, user_id)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                corrected_file_path = VALUES(corrected_file_path),
                error_count = VALUES(error_count)
        """, (template_id, corrected_filename, correction_count, corrected_file_path, session['user_id']))
        history_id = cursor.lastrowid or cursor.execute("SELECT LAST_INSERT_ID()").fetchone()[0]
        
        # Save individual corrections for tracking
        correction_records = []
        for column, row_corrections in corrections.items():
            if column not in headers:
                continue
            for row_str, corrected_value in row_corrections.items():
                try:
                    row_index = int(row_str)
                    if 0 <= row_index < len(df):
                        # Get original value from session data for comparison
                        original_df = pd.read_json(StringIO(session['df']))
                        original_df.columns = headers
                        original_df = original_df.iloc[session.get('header_row', 0) + 1:].reset_index(drop=True)
                        
                        original_value = str(original_df.at[row_index, column]) if row_index < len(original_df) else 'NULL'
                        
                        correction_records.append((
                            history_id, 
                            row_index + 1, 
                            column, 
                            original_value, 
                            corrected_value, 
                            'validation_rule'
                        ))
                except (ValueError, IndexError):
                    continue
        
        if correction_records:
            cursor.executemany("""
                INSERT INTO validation_corrections 
                (history_id, row_index, column_name, original_value, corrected_value, rule_failed)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    corrected_value = VALUES(corrected_value),
                    rule_failed = VALUES(rule_failed)
            """, correction_records)
        
        conn.commit()
        cursor.close()
        
        # Update session with corrected data
        session['corrected_df'] = df.to_json()
        session['corrected_file_path'] = corrected_file_path
        
        logging.info(f"Successfully saved {correction_count} corrections for template {template_id}")
        
        return jsonify({
            'success': True, 
            'corrected_file_path': corrected_file_path, 
            'history_id': history_id,
            'correction_count': correction_count,
            'message': f'{correction_count} corrections applied successfully'
        })
        
    except Exception as e:
        logging.error(f"Error saving corrections: {str(e)}")
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'success': False, 'message': f'Failed to save corrections: {str(e)}'}), 500

@step_bp.route('/2', methods=['POST'])
def submit_step_two():
    """Submit step 2 - from original app.py"""
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
        logging.info(f"Step 2 submitted: action={action}, validations={validations}")
        
        if not validations and action == 'review':
            logging.error("No validations provided for review")
            return jsonify({'success': False, 'message': 'No validations provided'}), 400

        template_id = session.get('template_id')
        if not template_id:
            logging.error("Session missing template_id")
            return jsonify({'success': False, 'message': 'Session data missing'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Debug: Check what rules exist in validation_rule_types
        cursor.execute("SELECT rule_type_id, rule_name FROM validation_rule_types WHERE is_active = TRUE")
        available_rules = cursor.fetchall()
        logging.info(f"Available rules in database: {available_rules}")
        
        # Debug: Check template columns
        cursor.execute("SELECT column_id, column_name FROM template_columns WHERE template_id = %s", (template_id,))
        template_columns = cursor.fetchall()
        logging.info(f"Template columns: {template_columns}")
        
        # Delete existing rules first
        cursor.execute("""
            DELETE FROM column_validation_rules
            WHERE column_id IN (
                SELECT column_id FROM template_columns WHERE template_id = %s
            )
        """, (template_id,))
        deleted_rows = cursor.rowcount
        logging.info(f"Deleted {deleted_rows} existing validation rules")
        
        # Insert new rules
        rules_inserted = 0
        for header, rules in validations.items():
            logging.info(f"Processing header '{header}' with rules {rules}")
            
            cursor.execute("""
                SELECT column_id FROM template_columns
                WHERE template_id = %s AND column_name = %s
            """, (template_id, header))
            result = cursor.fetchone()
            
            if not result:
                logging.warning(f"Column '{header}' not found in template_columns")
                continue
                
            column_id = result['column_id']
            logging.info(f"Found column_id {column_id} for header '{header}'")
            
            for rule_name in rules:
                logging.info(f"Looking for rule '{rule_name}' in validation_rule_types")
                
                cursor.execute("""
                    SELECT rule_type_id FROM validation_rule_types
                    WHERE rule_name = %s
                """, (rule_name,))
                result = cursor.fetchone()
                
                if result:
                    rule_type_id = result['rule_type_id']
                    logging.info(f"Found rule_type_id {rule_type_id} for rule '{rule_name}'")
                    
                    cursor.execute("""
                        INSERT IGNORE INTO column_validation_rules (column_id, rule_type_id, rule_config)
                        VALUES (%s, %s, %s)
                    """, (column_id, rule_type_id, '{}'))
                    
                    if cursor.rowcount > 0:
                        rules_inserted += 1
                        logging.info(f"Inserted validation rule: column_id={column_id}, rule_type_id={rule_type_id}")
                    else:
                        logging.warning(f"Rule already exists or insert failed: column_id={column_id}, rule_type_id={rule_type_id}")
                else:
                    logging.error(f"Rule '{rule_name}' not found in validation_rule_types table")
        
        logging.info(f"Total rules inserted: {rules_inserted}")
        
        # Mark template as configured after successful rule assignment
        cursor.execute("""
            UPDATE excel_templates 
            SET is_corrected = TRUE 
            WHERE template_id = %s AND user_id = %s
        """, (template_id, session['user_id']))
        
        conn.commit()
        cursor.close()

        session['validations'] = validations
        session['current_step'] = 3 if action == 'review' else 2
        logging.info(f"Step 2 completed: action={action}, validations={validations}, rules_inserted={rules_inserted}")
        return jsonify({'success': True, 'message': f'Step 2 completed successfully. {rules_inserted} rules saved.'})
    except Exception as e:
        logging.error(f"Error in step 2: {str(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': str(e)}), 500

@step_bp.route('/3', methods=['GET'])
def get_step_three():
    """Get step 3 data with configured rules - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        template_id = session.get('template_id')
        logging.info(f"Step 3 GET called with template_id: {template_id}")
        
        if not template_id:
            return jsonify({'error': 'No template found in session'}), 400
            
        # Get configured rules from database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Debug: First check if template exists
        cursor.execute("SELECT template_id, template_name FROM excel_templates WHERE template_id = %s", (template_id,))
        template_check = cursor.fetchone()
        logging.info(f"Template check result: {template_check}")
        
        # Debug: Check columns
        cursor.execute("SELECT column_id, column_name, is_selected FROM template_columns WHERE template_id = %s", (template_id,))
        columns_check = cursor.fetchall()
        logging.info(f"Columns check result: {columns_check}")
        
        # Debug: Check rules
        cursor.execute("""
            SELECT tc.column_name, vrt.rule_name, vrt.source_format, cvr.column_validation_id
            FROM template_columns tc
            LEFT JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            LEFT JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = %s
            ORDER BY tc.column_name, vrt.rule_name
        """, (template_id,))
        all_rules_debug = cursor.fetchall()
        logging.info(f"All rules debug result: {all_rules_debug}")
        
        cursor.execute("""
            SELECT tc.column_name, vrt.rule_name, vrt.source_format
            FROM template_columns tc
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = %s AND tc.is_selected = TRUE
            ORDER BY tc.column_name, vrt.rule_name
        """, (template_id,))
        rules_data = cursor.fetchall()
        logging.debug(f"Rules data retrieved: {rules_data}")
        cursor.close()
        
        # Build validations object
        validations = {}
        for rule in rules_data:
            column_name = rule['column_name']
            rule_name = rule['rule_name']
            if column_name not in validations:
                validations[column_name] = []
            validations[column_name].append(rule_name)
        
        session['validations'] = validations
        selected_headers = list(validations.keys())
        session['selected_headers'] = selected_headers
        
        logging.info(f"Step 3 GET: returning validations={validations}, headers={selected_headers}")
        return jsonify({
            'success': True,
            'validations': validations,
            'selected_headers': selected_headers,
            'headers': session.get('headers', [])
        })
    except Exception as e:
        logging.error(f"Error in step 3 GET: {str(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@step_bp.route('/validate-existing/<int:template_id>', methods=['GET'])
def validate_existing_template(template_id):
    """Validate existing template with configured rules - from original app.py"""
    if 'loggedin' not in session or 'user_id' not in session:
        logging.warning("Unauthorized access to /validate-existing: session missing")
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    try:
        df_json = session.get('df')
        if not df_json:
            logging.error("No data available in session")
            return jsonify({'success': False, 'message': 'No data available'}), 400
        df = pd.read_json(StringIO(df_json))
        headers = session['headers']
        df.columns = headers
        df = df.iloc[session['header_row'] + 1:].reset_index(drop=True)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT tc.column_name, vrt.rule_name, vrt.source_format
            FROM template_columns tc
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = %s AND tc.is_selected = TRUE AND vrt.rule_name NOT LIKE 'Transform-Date(%'
        """, (template_id,))
        rules = cursor.fetchall()
        cursor.close()

        error_cell_locations = {}
        accepted_date_formats = ['%d-%m-%Y', '%m-%d-%Y', '%m/%d/%Y', '%d/%m/%Y', '%m-%Y', '%m-%y', '%m/%Y', '%m/%y']
        for rule in rules:
            column_name = rule['column_name']
            rule_name = rule['rule_name']
            if rule_name.startswith('Date(') and rule['source_format']:
                format_map = {
                    'MM-DD-YYYY': '%m-%d-%Y', 'DD-MM-YYYY': '%d-%m-%Y', 'MM/DD/YYYY': '%m/%d/%Y', 'DD/MM/YYYY': '%d/%m/%Y',
                    'MM-YYYY': '%m-%Y', 'MM-YY': '%m-%y', 'MM/YYYY': '%m/%Y', 'MM/YY': '%m/%y'
                }
                accepted_date_formats = [format_map.get(rule['source_format'], '%d-%m-%Y')]
            error_count, locations = DataValidator.check_special_characters_in_column(
                df, column_name, rule_name, accepted_date_formats, check_null_cells=True
            )
            if error_count > 0:
                error_cell_locations[column_name] = [
                    {'row': loc[0], 'value': loc[1], 'rule_failed': loc[2], 'reason': loc[3]}
                    for loc in locations
                ]

        data_rows = df.to_dict('records')
        for row in data_rows:
            for key, value in row.items():
                if pd.isna(value) or value == '':
                    row[key] = 'NULL'

        logging.info(f"Validation completed for template {template_id}: {len(error_cell_locations)} columns with errors")
        return jsonify({
            'success': True,
            'error_cell_locations': error_cell_locations,
            'data_rows': data_rows
        })
    except Exception as e:
        logging.error(f"Error validating template {template_id}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@step_bp.route('/<int:step>', methods=['GET', 'POST'])
def handle_step(step):
    """Handle different validation steps - from original app.py"""
    if 'loggedin' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if 'df' not in session or session['df'] is None:
        logging.error("Session data missing: 'df' not found or is None")
        return jsonify({'error': 'Please upload a file first'}), 400
    
    session['current_step'] = step
    try:
        df = pd.read_json(StringIO(session['df']))
    except Exception as e:
        logging.error(f"Error reading session['df']: {str(e)}")
        return jsonify({'error': 'Invalid session data: Unable to load DataFrame'}), 500
    
    headers = session['headers']
    
    if step == 1:
        if request.method == 'POST':
            selected_headers = request.form.getlist('headers')
            new_header_row = request.form.get('new_header_row')
            if new_header_row:
                try:
                    header_row = int(new_header_row)
                    headers = df.iloc[header_row].tolist()
                    session['header_row'] = header_row
                    session['headers'] = headers
                    return jsonify({'headers': headers})
                except ValueError:
                    return jsonify({'error': 'Invalid header row number'}), 400
            if not selected_headers:
                return jsonify({'error': 'Please select at least one column'}), 400
            session['selected_headers'] = selected_headers
            session['current_step'] = 2

            # Auto-detect rules based on column data types (missing functionality)
            df.columns = session['headers']
            df_for_detection = df.iloc[session.get('header_row', 0) + 1:].reset_index(drop=True)
            validations = DataValidator.assign_default_rules_to_columns(df_for_detection, selected_headers)
            session['validations'] = validations
            logging.info(f"Auto-assigned validation rules: {validations}")

            # Mark selected headers in the database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE template_columns SET is_selected = FALSE WHERE template_id = %s", (session['template_id'],))
            for header in selected_headers:
                cursor.execute("""
                    UPDATE template_columns
                    SET is_selected = TRUE
                    WHERE template_id = %s AND column_name = %s
                """, (session['template_id'], header))
                
                # Auto-assign validation rules to database
                cursor.execute("""
                    SELECT column_id FROM template_columns
                    WHERE template_id = %s AND column_name = %s
                """, (session['template_id'], header))
                column_result = cursor.fetchone()
                if column_result:
                    column_id = column_result[0]
                    for rule_name in validations.get(header, []):
                        cursor.execute("""
                            SELECT rule_type_id FROM validation_rule_types
                            WHERE rule_name = %s AND is_custom = FALSE
                        """, (rule_name,))
                        rule_result = cursor.fetchone()
                        if rule_result:
                            rule_type_id = rule_result[0]
                            cursor.execute("""
                                INSERT IGNORE INTO column_validation_rules (column_id, rule_type_id, rule_config)
                                VALUES (%s, %s, %s)
                            """, (column_id, rule_type_id, '{}'))
            conn.commit()
            cursor.close()

            return jsonify({'success': True, 'headers': selected_headers, 'validations': validations})
        return jsonify({'headers': headers})
    
    elif step == 2:
        if 'selected_headers' not in session:
            session['current_step'] = 1
            return jsonify({'error': 'Select headers first'}), 400
        selected_headers = session['selected_headers']
        if request.method == 'POST':
            try:
                logging.debug(f"Received form data: {dict(request.form)}")
                validations = {header: request.form.getlist(f'validations_{header}') 
                              for header in selected_headers}
                logging.debug(f"Constructed validations: {validations}")
                session['validations'] = validations
                df.columns = session['headers']
                logging.debug(f"DataFrame after setting headers: {df.to_dict()}")
                df = df.iloc[session['header_row'] + 1:].reset_index(drop=True)
                logging.debug(f"DataFrame after removing header row: {df.to_dict()}")

                conn = get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT column_id, column_name FROM template_columns WHERE template_id = %s", (session['template_id'],))
                column_map = {row['column_name']: row['column_id'] for row in cursor.fetchall()}
                cursor.execute("SELECT rule_type_id, rule_name FROM validation_rule_types WHERE is_active = TRUE")
                rule_map = {row['rule_name']: row['rule_type_id'] for row in cursor.fetchall()}
                cursor.execute("DELETE FROM column_validation_rules WHERE column_id IN (SELECT column_id FROM template_columns WHERE template_id = %s)", (session['template_id'],))

                validation_data = []
                for header, rule_names in validations.items():
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
                session['current_step'] = 3
                return jsonify({'success': True})
            except Exception as e:
                logging.error(f"Error in step 2: {str(e)}")
                return jsonify({'error': str(e)}), 500
        return jsonify({'headers': selected_headers, 'validations': session.get('validations', {})})
    
    elif step == 3:
        # Return configured rules for display in Step 3
        template_id = session.get('template_id')
        if not template_id:
            return jsonify({'error': 'No template found in session'}), 400
            
        # Get configured rules from database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT tc.column_name, vrt.rule_name, vrt.source_format
            FROM template_columns tc
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = %s AND tc.is_selected = TRUE
            ORDER BY tc.column_name, vrt.rule_name
        """, (template_id,))
        rules_data = cursor.fetchall()
        cursor.close()
        
        # Build validations object for frontend display
        validations = {}
        for rule in rules_data:
            column_name = rule['column_name']
            rule_name = rule['rule_name']
            if column_name not in validations:
                validations[column_name] = []
            validations[column_name].append(rule_name)
        
        session['validations'] = validations
        selected_headers = list(validations.keys())
        session['selected_headers'] = selected_headers
        
        logging.info(f"Step 3: returning configured rules - validations={validations}, headers={selected_headers}")
        
        # Return the configured rules for Step 3 display
        return jsonify({
            'success': True,
            'validations': validations,
            'selected_headers': selected_headers,
            'headers': session.get('headers', []),
            'step': 3
        })
    
    return jsonify({'error': 'Invalid step'}), 400

@step_bp.route('/<int:step>/save-corrections', methods=['POST'])
def save_corrections(step):
    """Save corrections for a specific step"""
    if 'loggedin' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        data = request.get_json()
        corrections = data.get('corrections', {})
        
        if step == 3:
            # Process step 3 corrections
            df_json = session.get('df')
            if not df_json:
                return jsonify({'error': 'No data available in session'}), 400
            
            df = pd.read_json(StringIO(df_json))
            headers = session['headers']
            df.columns = headers
            df = df.iloc[session['header_row'] + 1:].reset_index(drop=True)
            
            # Apply corrections
            correction_count = 0
            for column, row_corrections in corrections.items():
                if column not in headers:
                    continue
                for row_str, value in row_corrections.items():
                    try:
                        row_index = int(row_str)
                        if 0 <= row_index < len(df):
                            df.at[row_index, column] = value
                            correction_count += 1
                    except (ValueError, IndexError):
                        continue
            
            # Save corrected file
            template_name = session.get('template_name', 'corrected_file')
            corrected_file_path = FileHandler.save_corrected_file(
                df, template_name, current_app.config['UPLOAD_FOLDER'], session.get('sheet_name')
            )
            
            # Save to validation history
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO validation_history (template_id, template_name, error_count, corrected_file_path, user_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (session['template_id'], os.path.basename(corrected_file_path), correction_count, corrected_file_path, session['user_id']))
            history_id = cursor.lastrowid
            
            # Save individual corrections
            correction_records = []
            for column, row_corrections in corrections.items():
                for row_str, corrected_value in row_corrections.items():
                    try:
                        row_index = int(row_str)
                        if 0 <= row_index < len(df):
                            correction_records.append((
                                history_id, row_index + 1, column, 'original_value', corrected_value, 'validation_rule'
                            ))
                    except (ValueError, IndexError):
                        continue
            
            if correction_records:
                cursor.executemany("""
                    INSERT INTO validation_corrections 
                    (history_id, row_index, column_name, original_value, corrected_value, rule_failed)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, correction_records)
            
            conn.commit()
            cursor.close()
            
            session['corrected_file_path'] = corrected_file_path
            
            return jsonify({
                'success': True,
                'corrected_file_path': corrected_file_path,
                'history_id': history_id,
                'correction_count': correction_count
            })
        else:
            return jsonify({'error': f'Corrections not supported for step {step}'}), 400
            
    except Exception as e:
        logging.error(f"Error saving corrections for step {step}: {str(e)}")
        return jsonify({'error': f'Failed to save corrections: {str(e)}'}), 500

@step_bp.route('/custom-rule', methods=['POST'])
def create_custom_rule():
    """Create custom validation rule"""
    if 'loggedin' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        data = request.get_json()
        rule_name = data.get('rule_name')
        formula = data.get('formula')
        column_name = data.get('column_name')
        template_id = session.get('template_id')
        
        if not all([rule_name, formula, column_name, template_id]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Validate formula syntax
        from utils.validators import InputValidator
        is_valid, message = InputValidator.validate_formula_syntax(formula, column_name, session.get('headers', []))
        if not is_valid:
            return jsonify({'error': f'Invalid formula: {message}'}), 400
        
        # Create custom rule
        rule_type_id = ValidationRule.create_custom_rule(rule_name, formula, column_name, template_id)
        
        return jsonify({
            'success': True,
            'message': 'Custom rule created successfully',
            'rule_type_id': rule_type_id
        })
        
    except Exception as e:
        logging.error(f"Error creating custom rule: {str(e)}")
        return jsonify({'error': f'Failed to create custom rule: {str(e)}'}), 500

@step_bp.route('/validate-formula', methods=['POST'])
def validate_formula():
    """Validate formula syntax"""
    try:
        data = request.get_json()
        formula = data.get('formula')
        column_name = data.get('column_name')
        
        if not formula or not column_name:
            return jsonify({'error': 'Missing formula or column name'}), 400
        
        from utils.validators import InputValidator
        is_valid, message = InputValidator.validate_formula_syntax(formula, column_name, session.get('headers', []))
        
        return jsonify({
            'valid': is_valid,
            'message': message
        })
        
    except Exception as e:
        logging.error(f"Error validating formula: {str(e)}")
        return jsonify({'error': f'Formula validation failed: {str(e)}'}), 500
