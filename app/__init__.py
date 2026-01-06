from flask import Flask
from config import Config


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration
    app.config.from_object(Config)
    app.config.from_pyfile("config.py", silent=True)

    # Register main routes
    from app.routes.main import main_bp

    app.register_blueprint(main_bp)

    # Register auth routes
    from app.routes.auth import auth_bp

    app.register_blueprint(auth_bp)

    # Register dashboard routes
    from app.routes.admin import admin_bp
    from app.routes.user import user_bp
    from app.routes.hotel import hotel_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(hotel_bp)

    return app
