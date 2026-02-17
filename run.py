"""
Nearest Pharmacy API - Standalone Entry Point
==============================================
Run this to start the API server independently.

For integration into a parent Flask app, see app/__init__.py for:
  - create_pharmacy_blueprint()
  - init_pharmacy_module()
  - ensure_tables_exist()
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
