from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from sqlalchemy.orm import joinedload

from src.database import db
from src.models import Product
from src.schemas import PlaceOrderSchema
from src.services import shopify_service

orders_bp = Blueprint('orders', __name__)

place_order_schema = PlaceOrderSchema()


@orders_bp.route('/orders/place', methods=['POST'])
def place_order():
    """
    Place an order on Shopify and reduce inventory

    This endpoint:
    1. Validates the order request
    2. Checks if the product exists and has sufficient inventory
    3. Finds or creates customer in Shopify by phone number
    4. Creates an order in Shopify with tax-inclusive pricing
    5. Reduces the inventory in the database

    Request Body:
        {
            "sku": "ELEC-0001-0124",
            "quantity": 2,
            "per_unit_price": 999.99,
            "shipping_charges": 50.00,
            "customer_name": "John Doe",
            "customer_phone": "+1234567890",
            "customer_address": {
                "address1": "123 Main St",
                "city": "New York",
                "province": "NY",
                "country": "United States",
                "zip": "10001"
            }
        }

    Response:
        {
            "success": true,
            "message": "Order placed successfully",
            "data": {
                "product": {
                    "id": 1,
                    "sku": "ELEC-0001-0124",
                    "inventory": 8,
                    ...
                },
                "shopify_order": {
                    "draft_order": {...},
                    "order": {...},
                    "customer": {...}
                }
            }
        }
    """
    try:
        # Validate request data
        data = place_order_schema.load(request.get_json())
        
        sku = data['sku']
        quantity = data['quantity']
        per_unit_price = float(data['per_unit_price'])
        shipping_charges = float(data['shipping_charges'])
        customer_name = data['customer_name']
        customer_phone = data['customer_phone']
        customer_address = data['customer_address']
        
        current_app.logger.info(f"Processing order for SKU: {sku}, Quantity: {quantity}")
        
        # Find product by SKU
        product = Product.query.filter_by(sku=sku).first()
        
        if not product:
            return jsonify({
                'success': False,
                'error': f'Product with SKU "{sku}" not found'
            }), 404
        
        # Check if product has sufficient inventory
        if product.inventory < quantity:
            return jsonify({
                'success': False,
                'error': f'Insufficient inventory. Available: {product.inventory}, Requested: {quantity}'
            }), 400

        # Place order on Shopify first
        current_app.logger.info(f"Placing order on Shopify for SKU {sku}, Quantity: {quantity}")

        # Generate product title if not set
        product_title = product.title or f"{product.category_ref.name} - {sku}"

        try:
            shopify_order = shopify_service.create_order(
                sku=sku,
                title=product_title,
                quantity=quantity,
                per_unit_price=per_unit_price,
                shipping_charges=shipping_charges,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_address=customer_address
            )

            current_app.logger.info(f"Successfully placed order on Shopify for SKU {sku}")

        except Exception as shopify_error:
            # Shopify order failed, don't update inventory
            current_app.logger.error(f"Shopify order failed: {str(shopify_error)}")

            return jsonify({
                'success': False,
                'error': f'Failed to place order on Shopify: {str(shopify_error)}'
            }), 500

        # Shopify order successful, now reduce inventory
        original_inventory = product.inventory
        product.inventory -= quantity

        current_app.logger.info(f"Reducing inventory for SKU {sku} from {original_inventory} to {product.inventory}")

        # Commit inventory reduction
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Order placed successfully',
            'data': {
                'shopify_order': shopify_order
            }
        }), 201
    
    except ValidationError as e:
        current_app.logger.warning(f"Validation error in place order: {e.messages}")
        return jsonify({
            'success': False,
            'error': 'Validation error',
            'details': e.messages
        }), 400
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error placing order: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

