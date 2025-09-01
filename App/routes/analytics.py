from flask import Blueprint, request, jsonify, session
import logging
from datetime import datetime, timedelta
from config.database import get_db_connection
from utils.decorators import require_auth, handle_exceptions

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/dashboard-stats', methods=['GET'])
@require_auth
@handle_exceptions
def get_dashboard_stats():
    """Get dashboard statistics for the user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Total templates
        cursor.execute("""
            SELECT COUNT(*) as total_templates
            FROM excel_templates
            WHERE user_id = %s AND status = 'ACTIVE'
        """, (user_id,))
        total_templates = cursor.fetchone()['total_templates']
        
        # Templates with rules
        cursor.execute("""
            SELECT COUNT(DISTINCT t.template_id) as templates_with_rules
            FROM excel_templates t
            JOIN template_columns tc ON t.template_id = tc.template_id
            JOIN column_validation_rules cvr ON tc.column_id = cvr.column_id
            WHERE t.user_id = %s AND t.status = 'ACTIVE'
        """, (user_id,))
        templates_with_rules = cursor.fetchone()['templates_with_rules']
        
        # Total validations performed
        cursor.execute("""
            SELECT COUNT(*) as total_validations
            FROM validation_history
            WHERE user_id = %s
        """, (user_id,))
        total_validations = cursor.fetchone()['total_validations']
        
        # Total errors corrected
        cursor.execute("""
            SELECT COALESCE(SUM(error_count), 0) as total_errors_corrected
            FROM validation_history
            WHERE user_id = %s
        """, (user_id,))
        total_errors_corrected = cursor.fetchone()['total_errors_corrected']
        
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        cursor.execute("""
            SELECT COUNT(*) as recent_validations
            FROM validation_history
            WHERE user_id = %s AND corrected_at >= %s
        """, (user_id, thirty_days_ago))
        recent_validations = cursor.fetchone()['recent_validations']
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_templates': total_templates,
                'templates_with_rules': templates_with_rules,
                'total_validations': total_validations,
                'total_errors_corrected': total_errors_corrected,
                'recent_validations': recent_validations,
                'templates_without_rules': total_templates - templates_with_rules
            }
        })
        
    except Exception as e:
        logging.error(f"Error fetching dashboard stats: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to fetch dashboard stats'}), 500

@analytics_bp.route('/validation-trends', methods=['GET'])
@require_auth
@handle_exceptions
def get_validation_trends():
    """Get validation trends over time"""
    try:
        days = request.args.get('days', 30, type=int)
        if days > 365:
            days = 365  # Limit to 1 year
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        user_id = session['user_id']
        
        start_date = datetime.now() - timedelta(days=days)
        
        cursor.execute("""
            SELECT 
                DATE(corrected_at) as validation_date,
                COUNT(*) as validation_count,
                SUM(error_count) as total_errors
            FROM validation_history
            WHERE user_id = %s AND corrected_at >= %s
            GROUP BY DATE(corrected_at)
            ORDER BY validation_date
        """, (user_id, start_date))
        
        trends = cursor.fetchall()
        cursor.close()
        
        return jsonify({
            'success': True,
            'trends': trends
        })
        
    except Exception as e:
        logging.error(f"Error fetching validation trends: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to fetch validation trends'}), 500

@analytics_bp.route('/error-patterns', methods=['GET'])
@require_auth
@handle_exceptions
def get_error_patterns():
    """Get error patterns by rule type and column"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Error patterns by rule type
        cursor.execute("""
            SELECT 
                vc.rule_failed,
                COUNT(*) as error_count,
                COUNT(DISTINCT vh.template_id) as affected_templates
            FROM validation_corrections vc
            JOIN validation_history vh ON vc.history_id = vh.history_id
            WHERE vh.user_id = %s
            GROUP BY vc.rule_failed
            ORDER BY error_count DESC
            LIMIT 10
        """, (user_id,))
        
        rule_errors = cursor.fetchall()
        
        # Error patterns by column
        cursor.execute("""
            SELECT 
                vc.column_name,
                COUNT(*) as error_count,
                COUNT(DISTINCT vh.template_id) as affected_templates
            FROM validation_corrections vc
            JOIN validation_history vh ON vc.history_id = vh.history_id
            WHERE vh.user_id = %s
            GROUP BY vc.column_name
            ORDER BY error_count DESC
            LIMIT 10
        """, (user_id,))
        
        column_errors = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'patterns': {
                'by_rule': rule_errors,
                'by_column': column_errors
            }
        })
        
    except Exception as e:
        logging.error(f"Error fetching error patterns: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to fetch error patterns'}), 500

@analytics_bp.route('/template-usage', methods=['GET'])
@require_auth
@handle_exceptions
def get_template_usage():
    """Get template usage statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Most validated templates
        cursor.execute("""
            SELECT 
                t.template_name,
                COUNT(vh.history_id) as validation_count,
                SUM(vh.error_count) as total_errors_fixed,
                MAX(vh.corrected_at) as last_validated
            FROM excel_templates t
            LEFT JOIN validation_history vh ON t.template_id = vh.template_id
            WHERE t.user_id = %s AND t.status = 'ACTIVE'
            GROUP BY t.template_id, t.template_name
            HAVING validation_count > 0
            ORDER BY validation_count DESC
            LIMIT 10
        """, (user_id,))
        
        template_usage = cursor.fetchall()
        
        # Templates by creation date
        cursor.execute("""
            SELECT 
                DATE(created_at) as creation_date,
                COUNT(*) as templates_created
            FROM excel_templates
            WHERE user_id = %s AND status = 'ACTIVE'
            AND created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
            GROUP BY DATE(created_at)
            ORDER BY creation_date
        """, (user_id,))
        
        creation_trends = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'usage': {
                'most_validated': template_usage,
                'creation_trends': creation_trends
            }
        })
        
    except Exception as e:
        logging.error(f"Error fetching template usage: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to fetch template usage'}), 500

@analytics_bp.route('/data-quality-score', methods=['GET'])
@require_auth
@handle_exceptions
def get_data_quality_score():
    """Calculate data quality score based on error rates"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Calculate quality score based on recent validations
        cursor.execute("""
            SELECT 
                COUNT(*) as total_validations,
                AVG(error_count) as avg_errors_per_validation,
                SUM(error_count) as total_errors
            FROM validation_history
            WHERE user_id = %s
            AND corrected_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """, (user_id,))
        
        quality_data = cursor.fetchone()
        
        if quality_data['total_validations'] > 0:
            # Calculate quality score (0-100)
            avg_errors = quality_data['avg_errors_per_validation'] or 0
            
            # Score decreases as average errors increase
            # Assuming 0 errors = 100%, 10+ errors = 0%
            quality_score = max(0, min(100, 100 - (avg_errors * 10)))
            
            # Quality grade
            if quality_score >= 90:
                grade = 'A'
            elif quality_score >= 80:
                grade = 'B'
            elif quality_score >= 70:
                grade = 'C'
            elif quality_score >= 60:
                grade = 'D'
            else:
                grade = 'F'
        else:
            quality_score = 100  # No validations = perfect score
            grade = 'A'
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'quality_score': {
                'score': round(quality_score, 1),
                'grade': grade,
                'total_validations': quality_data['total_validations'],
                'avg_errors': round(quality_data['avg_errors_per_validation'] or 0, 1),
                'total_errors': quality_data['total_errors']
            }
        })
        
    except Exception as e:
        logging.error(f"Error calculating data quality score: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to calculate quality score'}), 500

@analytics_bp.route('/export-analytics', methods=['GET'])
@require_auth
@handle_exceptions
def export_analytics():
    """Export analytics data to CSV"""
    try:
        import pandas as pd
        from io import BytesIO
        from flask import make_response
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Get comprehensive analytics data
        cursor.execute("""
            SELECT 
                vh.template_name,
                vh.error_count,
                vh.corrected_at,
                COUNT(vc.correction_id) as corrections_made,
                GROUP_CONCAT(DISTINCT vc.rule_failed) as failed_rules
            FROM validation_history vh
            LEFT JOIN validation_corrections vc ON vh.history_id = vc.history_id
            WHERE vh.user_id = %s
            GROUP BY vh.history_id
            ORDER BY vh.corrected_at DESC
        """, (user_id,))
        
        analytics_data = cursor.fetchall()
        cursor.close()
        
        if not analytics_data:
            return jsonify({'success': False, 'message': 'No analytics data available'}), 404
        
        # Convert to DataFrame and CSV
        df = pd.DataFrame(analytics_data)
        
        # Create CSV response
        output = BytesIO()
        df.to_csv(output, index=False, encoding='utf-8')
        output.seek(0)
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=analytics_export_{datetime.now().strftime("%Y%m%d")}.csv'
        
        return response
        
    except Exception as e:
        logging.error(f"Error exporting analytics: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to export analytics'}), 500
