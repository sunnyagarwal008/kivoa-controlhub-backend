from flask import Blueprint
from src.routes.health import health_bp
from src.routes.s3 import s3_bp
from src.routes.products import products_bp

api = Blueprint('api', __name__, url_prefix='/api')

# Register sub-blueprints
api.register_blueprint(health_bp)
api.register_blueprint(s3_bp)
api.register_blueprint(products_bp)

