"""
Debug script to test Step 2 rule saving
Run this to check if rules are being saved properly
"""

import json
import mysql.connector
from config.database import get_db_connection

def debug_step2_rules(template_id):
    """Debug function to check what rules are saved for a template"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        print(f"🔍 Debugging template_id: {template_id}")
        print("=" * 50)
        
        # Check template exists
        cursor.execute("SELECT * FROM excel_templates WHERE template_id = %s", (template_id,))
        template = cursor.fetchone()
        print(f"📋 Template: {template}")
        print()
        
        # Check template columns
        cursor.execute("SELECT * FROM template_columns WHERE template_id = %s", (template_id,))
        columns = cursor.fetchall()
        print(f"📝 Template Columns ({len(columns)}):")
        for col in columns:
            print(f"  - {col['column_name']} (ID: {col['column_id']}, Selected: {col['is_selected']})")
        print()
        
        # Check validation rules
        cursor.execute("SELECT * FROM validation_rule_types WHERE is_active = TRUE LIMIT 10")
        rule_types = cursor.fetchall()
        print(f"⚙️ Available Rule Types ({len(rule_types)}):")
        for rule in rule_types:
            print(f"  - {rule['rule_name']} (ID: {rule['rule_type_id']})")
        print()
        
        # Check column validation rules
        cursor.execute("""
            SELECT cvr.*, tc.column_name, vrt.rule_name
            FROM column_validation_rules cvr
            JOIN template_columns tc ON cvr.column_id = tc.column_id
            JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = %s
        """, (template_id,))
        applied_rules = cursor.fetchall()
        print(f"🎯 Applied Validation Rules ({len(applied_rules)}):")
        for rule in applied_rules:
            print(f"  - Column: {rule['column_name']} → Rule: {rule['rule_name']}")
        print()
        
        # Check if rules exist for Step 3
        cursor.execute("""
            SELECT tc.column_name, vrt.rule_name, vrt.source_format
            FROM template_columns tc
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            JOIN validation_rule_types vrt ON cvr.rule_type_id = vrt.rule_type_id
            WHERE tc.template_id = %s AND tc.is_selected = TRUE
            ORDER BY tc.column_name, vrt.rule_name
        """, (template_id,))
        step3_rules = cursor.fetchall()
        print(f"📊 Step 3 Rules Query Result ({len(step3_rules)}):")
        for rule in step3_rules:
            print(f"  - {rule['column_name']}: {rule['rule_name']}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    # Replace with your actual template_id from the session
    template_id = input("Enter your template_id: ")
    try:
        template_id = int(template_id)
        debug_step2_rules(template_id)
    except ValueError:
        print("Please enter a valid template_id number")
