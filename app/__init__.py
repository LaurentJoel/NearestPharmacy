"""
Flask Application Factory
"""
from flask import Flask
from .config import Config


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Register blueprints
    from .routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Health check route
    @app.route('/')
    def health():
        return {
            'status': 'ok',
            'service': 'Nearest Pharmacy API',
            'version': '1.0.0'
        }
    
    return app
