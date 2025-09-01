# Keansa AI Suite 2025 - Data Validation System

A comprehensive, modular Flask-based web application for Excel/CSV data validation with advanced rule configuration and error correction capabilities.

## 🚀 Features

### Core Functionality
- **File Upload & Processing**: Support for Excel (.xlsx, .xls), CSV, and text files
- **Intelligent Header Detection**: Automatic identification of header rows
- **Multi-Step Validation Workflow**: Guided validation process with configurable rules
- **Real-time Error Detection**: Live validation with detailed error reporting
- **Data Correction Interface**: Interactive correction of validation errors
- **Template Management**: Reusable validation templates with rule persistence
- **SFTP Integration**: Upload/download files to/from SFTP servers

### Validation Rules
- **Built-in Rules**: Required, Integer, Float, Text, Email, Date, Boolean, Alphanumeric
- **Custom Formula Rules**: Support for arithmetic and comparison formulas
- **Date Format Validation**: Multiple date format support with transformation
- **Null Value Handling**: Configurable null value validation
- **Cross-Column Validation**: Formula-based validation across multiple columns

### Advanced Features
- **Session Management**: Persistent workflow state across browser sessions
- **Validation History**: Complete audit trail of all validations and corrections
- **Analytics Dashboard**: Data quality metrics and validation trends
- **Error Pattern Analysis**: Identification of common validation issues
- **Export Functionality**: Export corrected data and analytics reports

## 📁 Project Structure

```
App/
├── app.py                      # Main application entry point
├── config/                     # Configuration management
│   ├── __init__.py
│   ├── database.py            # Database connection and schema
│   ├── settings.py            # Application settings
│   └── production.py          # Production configuration
├── models/                     # Data models and business logic
│   ├── __init__.py
│   ├── analytics.py           # Analytics data models
│   ├── template.py            # Template management
│   ├── user.py                # User authentication
│   └── validation.py          # Validation rules and logic
├── routes/                     # API endpoints and route handlers
│   ├── __init__.py
│   ├── analytics.py           # Analytics endpoints
│   ├── auth.py                # Authentication routes
│   ├── sftp.py                # SFTP functionality
│   ├── steps.py               # Multi-step validation workflow
│   ├── templates.py           # Template management
│   └── validation.py          # Validation endpoints
├── services/                   # Service layer and business logic
│   ├── __init__.py
│   ├── authentication.py      # Auth service layer
│   ├── cache_manager.py       # Caching functionality
│   ├── data_transformer.py    # Data transformation utilities
│   ├── file_handler.py        # File processing and I/O
│   ├── memory_manager.py      # Memory optimization
│   ├── session_manager.py     # Session state management
│   ├── sftp_handler.py        # SFTP operations
│   └── validator.py           # Core validation engine
├── tests/                      # Unit and integration tests
│   ├── test_models.py         # Model tests
│   └── test_services.py       # Service tests
└── utils/                      # Utility functions and helpers
    ├── __init__.py
    ├── constants.py           # Application constants
    ├── decorators.py          # Common decorators
    ├── error_handlers.py      # Error handling utilities
    ├── health_check.py        # System health monitoring
    ├── helpers.py             # General helper functions
    ├── monitoring.py          # Performance monitoring
    ├── security.py           # Security utilities
    └── validators.py          # Input validation utilities
```

## 🛠 Installation & Setup

### Prerequisites
- Python 3.8+
- MySQL 5.7+ or MariaDB 10.3+
- pip package manager

### Environment Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd App
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment Configuration**
Create a `.env` file in the project root:
```env
# Database Configuration
MYSQL_HOST=localhost
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=data_validation_36

# Application Settings
FLASK_ENV=development
SECRET_KEY=your-secret-key
PORT=5000
```

5. **Database Setup**
The application will automatically create the required database and tables on first run.

### Running the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## 🔧 Configuration

### Database Configuration
Edit `config/database.py` to customize database settings:
- Connection pooling
- Timeout settings
- Character encoding

### Application Settings
Modify `config/settings.py` for:
- File upload limits
- Session timeout
- CORS origins
- Supported file formats

### Production Deployment
Use `config/production.py` for production-specific settings:
- SSL configuration
- Performance optimization
- Security hardening

## 📋 API Endpoints

### Authentication
- `POST /api/auth/authenticate` - User login
- `POST /api/auth/register` - User registration
- `GET /api/auth/check-auth` - Authentication status
- `POST /api/auth/logout` - User logout
- `POST /api/auth/reset_password` - Password reset

### Templates
- `GET /api/templates/` - List user templates
- `POST /api/templates/upload` - Upload and process file
- `GET /api/templates/{id}/{sheet}` - Get template details
- `GET /api/templates/{id}/rules` - Get template rules
- `POST /api/templates/{id}/rules` - Update template rules
- `DELETE /api/templates/delete-template/{id}` - Delete template

### Validation
- `GET /api/validation/rule-configurations` - Get templates with rules
- `GET /api/validation/history` - Get validation history
- `GET /api/validation/corrections/{id}` - Get correction details
- `GET /api/validation/validate-existing/{id}` - Validate template
- `POST /api/validation/validate-existing/{id}` - Save corrections
- `POST /api/validation/validate-row/{id}` - Validate single row

### Multi-Step Workflow
- `GET|POST /api/step/{step}` - Handle validation steps
- `POST /api/step/{step}/save-corrections` - Save step corrections
- `POST /api/step/custom-rule` - Create custom validation rule
- `POST /api/step/validate-formula` - Validate formula syntax

### Analytics
- `GET /api/analytics/dashboard-stats` - Dashboard statistics
- `GET /api/analytics/validation-trends` - Validation trends
- `GET /api/analytics/error-patterns` - Error pattern analysis
- `GET /api/analytics/template-usage` - Template usage statistics
- `GET /api/analytics/export-analytics` - Export analytics data

### SFTP Operations
- `POST /api/sftp/test-connection` - Test SFTP connection
- `POST /api/sftp/upload-file` - Upload file to SFTP
- `POST /api/sftp/download-file` - Download file from SFTP
- `POST /api/sftp/list-files` - List SFTP directory contents

## 🎯 Usage Guide

### Basic Workflow

1. **Upload File**
   - Select Excel/CSV file through upload interface
   - System automatically detects headers and data structure

2. **Select Columns**
   - Choose columns for validation
   - System suggests appropriate validation rules

3. **Configure Rules**
   - Modify suggested rules or add custom rules
   - Create formula-based validation rules

4. **Validate Data**
   - Review validation results
   - Identify errors and inconsistencies

5. **Correct Errors**
   - Use interactive correction interface
   - Apply corrections in bulk or individually

6. **Export Results**
   - Download corrected file
   - Export validation report

### Advanced Features

#### Custom Formula Rules
Create complex validation rules using formulas:
- Arithmetic: `'total' = 'price' + 'tax'`
- Comparison: `'age' >= 18`
- Cross-column: `'end_date' > 'start_date'`

#### Template Reuse
- Save validation configurations as templates
- Reuse templates for similar file structures
- Maintain consistency across data validations

#### Batch Processing
- Process multiple files with same validation rules
- Monitor progress through validation history
- Generate reports for compliance and auditing

## 🧪 Testing

### Run Unit Tests
```bash
python -m pytest tests/ -v
```

### Test Coverage
```bash
python -m pytest tests/ --cov=app --cov-report=html
```

### Manual Testing
1. Upload sample data files
2. Configure various validation rules
3. Test error correction workflow
4. Verify template persistence
5. Check analytics functionality

## 🔒 Security Features

- **Session Management**: Secure session handling with timeout
- **Input Validation**: Comprehensive input sanitization
- **SQL Injection Protection**: Parameterized queries
- **File Upload Security**: Extension and size validation
- **Authentication**: Secure password hashing with bcrypt
- **CSRF Protection**: Built-in CSRF protection for forms

## 🚀 Performance Optimization

- **Database Connection Pooling**: Efficient database connections
- **Memory Management**: Optimized DataFrame handling
- **Caching**: Strategic caching of validation rules and templates
- **File Processing**: Streaming file processing for large files
- **Session Cleanup**: Automatic cleanup of expired sessions

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check MySQL service status
   - Verify database credentials in `.env`
   - Ensure database exists and is accessible

2. **File Upload Fails**
   - Check file size limits in `config/settings.py`
   - Verify upload directory permissions
   - Ensure supported file format

3. **Validation Rules Not Working**
   - Check rule syntax and parameters
   - Verify column names match exactly
   - Review validation rule configuration

4. **Session Timeouts**
   - Adjust session timeout in configuration
   - Check session directory permissions
   - Clear browser cookies if needed

### Debugging

Enable debug mode in development:
```python
# In app.py
app.run(debug=True, host='0.0.0.0', port=port)
```

Check logs for detailed error information:
```bash
tail -f app.log
```

## 📈 Monitoring & Analytics

### Built-in Monitoring
- System health checks
- Performance metrics
- Error rate tracking
- User activity monitoring

### Analytics Features
- Data quality scoring
- Validation trend analysis
- Error pattern identification
- Template usage statistics

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

### Development Guidelines
- Follow PEP 8 style guide
- Write comprehensive tests
- Document all functions
- Use type hints where applicable

## 📄 License

This project is proprietary software. All rights reserved.

## 🆘 Support

For technical support or questions:
- Create an issue in the repository
- Contact the development team
- Review documentation and troubleshooting guide

---

**Version**: 2.0.0  
**Last Updated**: August 2025  
**Developed by**: Keansa AI Team
