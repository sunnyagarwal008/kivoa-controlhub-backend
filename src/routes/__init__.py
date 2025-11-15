from flask import Blueprint
from src.routes.health import health_bp
from src.routes.s3 import s3_bp
from src.routes.products import products_bp
from src.routes.categories import categories_bp
from src.routes.raw_images import raw_images_bp
from src.routes.prompts import prompts_bp
from src.routes.catalogs import catalogs_bp
from src.routes.orders import orders_bp

api = Blueprint('api', __name__, url_prefix='/api')

# Register sub-blueprints
api.register_blueprint(health_bp)
api.register_blueprint(s3_bp)
api.register_blueprint(products_bp)
api.register_blueprint(categories_bp)
api.register_blueprint(raw_images_bp)
api.register_blueprint(prompts_bp)
api.register_blueprint(catalogs_bp)
api.register_blueprint(orders_bp)

