import mysql.connector
import json
from config.database import get_db_connection

def debug_step2_step3_flow(template_id):
    """Debug the data flow between Step 2 and Step 3"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        print(f"=== DEBUGGING TEMPLATE {template_id} ===")
        
        # 1. Check template exists
        cursor.execute("SELECT * FROM excel_templates WHERE template_id = %s", (template_id,))
        template = cursor.fetchone()
        print(f"1. Template: {template}")
        
        # 2. Check template columns
        cursor.execute("SELECT * FROM template_columns WHERE template_id = %s", (template_id,))
        columns = cursor.fetchall()
        print(f"2. Template columns ({len(columns)}):")
        for col in columns:
            print(f"   - {col['column_name']} (ID: {col['column_id']}, Selected: {col['is_selected']})")
        
        # 3. Check all validation rules
        cursor.execute("SELECT * FROM validation_rule_types WHERE is_active = TRUE LIMIT 10")
        all_rules = cursor.fetchall()
        print(f"3. Available validation rules ({len(all_rules)}):")
        for rule in all_rules:
            print(f"   - {rule['rule_name']} (ID: {rule['rule_type_id']})")
        
        # 4. Check column validation rules (what Step 2 should have saved)
        cursor.execute("""
            SELECT cvr.*, tc.column_name, vrt.rule_name
            FROM column_validation_rules cvr
            JOIN template_columns tc ON cvr.column_id = tc.column_id
            JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = %s
        """, (template_id,))
        saved_rules = cursor.fetchall()
        print(f"4. Saved validation rules ({len(saved_rules)}):")
        for rule in saved_rules:
            print(f"   - Column: {rule['column_name']} -> Rule: {rule['rule_name']}")
        
        # 5. Check Step 3 query (what Step 3 should retrieve)
        cursor.execute("""
            SELECT tc.column_name, vrt.rule_name, vrt.source_format, tc.is_selected
            FROM template_columns tc
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = %s AND tc.is_selected = TRUE
            ORDER BY tc.column_name, vrt.rule_name
        """, (template_id,))
        step3_data = cursor.fetchall()
        print(f"5. Step 3 query result ({len(step3_data)}):")
        for rule in step3_data:
            print(f"   - {rule['column_name']}: {rule['rule_name']} (Selected: {rule['is_selected']})")
        
        # 6. Build the validations object like Step 3 does
        validations = {}
        for rule in step3_data:
            column_name = rule['column_name']
            rule_name = rule['rule_name']
            if column_name not in validations:
                validations[column_name] = []
            validations[column_name].append(rule_name)
        
        print(f"6. Step 3 validations object: {validations}")
        
        cursor.close()
        conn.close()
        
        if not step3_data:
            print("\n*** PROBLEM FOUND ***")
            if not saved_rules:
                print("- No rules were saved in Step 2")
            else:
                print("- Rules were saved but columns are not marked as selected (is_selected = FALSE)")
                print("- Need to fix column selection in Step 2")
        else:
            print(f"\n*** SUCCESS: Step 3 should show {len(validations)} columns with rules ***")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    template_id = input("Enter template_id: ")
    try:
        debug_step2_step3_flow(int(template_id))
    except ValueError:
        print("Invalid template_id")
