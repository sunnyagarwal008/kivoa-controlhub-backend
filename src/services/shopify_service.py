import requests
from flask import current_app


class ShopifyService:
    """Service for interacting with Shopify API"""

    def __init__(self):
        self.store_url = None
        self.access_token = None
        self.api_version = None

    def _get_config(self):
        """Get Shopify configuration from Flask app config"""
        if not self.store_url:
            self.store_url = current_app.config.get('SHOPIFY_STORE_URL')
            self.access_token = current_app.config.get('SHOPIFY_ACCESS_TOKEN')
            self.api_version = current_app.config.get('SHOPIFY_API_VERSION', '2024-01')

            # Ensure store URL has https:// scheme
            if self.store_url and not self.store_url.startswith(('http://', 'https://')):
                self.store_url = f'https://{self.store_url}'
                current_app.logger.info(f"Added https:// scheme to Shopify store URL: {self.store_url}")

        if not self.store_url or not self.access_token:
            raise ValueError('Shopify configuration is missing. Please set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN')

    def _get_headers(self):
        """Get headers for Shopify API requests"""
        self._get_config()
        return {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.access_token
        }

    def _get_api_url(self, endpoint):
        """Construct full API URL for a given endpoint"""
        self._get_config()
        # Remove trailing slash from store_url if present
        base_url = self.store_url.rstrip('/')
        return f"{base_url}/admin/api/{self.api_version}/{endpoint}"

    def create_draft_order(self, sku, title, quantity, per_unit_price, shipping_charges,
                          customer_name, customer_phone, customer_address):
        """
        Create a draft order in Shopify

        Args:
            sku (str): Product SKU
            title (str): Product title
            quantity (int): Quantity to order
            per_unit_price (float): Price per unit
            shipping_charges (float): Shipping charges
            customer_name (str): Customer name
            customer_phone (str): Customer phone number
            customer_address (dict): Customer address with fields:
                - address1 (str): Street address
                - city (str): City
                - province (str): State/Province
                - country (str): Country
                - zip (str): Postal/ZIP code

        Returns:
            dict: Shopify draft order response
        """
        self._get_config()

        # Construct draft order payload
        payload = {
            "draft_order": {
                "line_items": [
                    {
                        "title": title,
                        "sku": sku,
                        "quantity": quantity,
                        "price": str(per_unit_price)
                    }
                ],
                "customer": {
                    "first_name": customer_name.split()[0] if customer_name else "",
                    "last_name": " ".join(customer_name.split()[1:]) if len(customer_name.split()) > 1 else "",
                    "phone": customer_phone
                },
                "shipping_address": {
                    "first_name": customer_name.split()[0] if customer_name else "",
                    "last_name": " ".join(customer_name.split()[1:]) if len(customer_name.split()) > 1 else "",
                    "address1": customer_address.get('address1', ''),
                    "city": customer_address.get('city', ''),
                    "province": customer_address.get('province', ''),
                    "country": customer_address.get('country', ''),
                    "zip": customer_address.get('zip', ''),
                    "phone": customer_phone
                },
                "shipping_line": {
                    "title": "Standard Shipping",
                    "price": str(shipping_charges)
                },
                "use_customer_default_address": False
            }
        }
        
        # Make API request to create draft order
        url = self._get_api_url('draft_orders.json')
        headers = self._get_headers()
        
        current_app.logger.info(f"Creating Shopify draft order for SKU: {sku}, Quantity: {quantity}")
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            error_msg = f"Shopify API error: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)
        
        draft_order = response.json()
        current_app.logger.info(f"Successfully created Shopify draft order: {draft_order.get('draft_order', {}).get('id')}")
        
        return draft_order

    def complete_draft_order(self, draft_order_id):
        """
        Complete a draft order (convert to order)
        
        Args:
            draft_order_id (int): Draft order ID
        
        Returns:
            dict: Completed order response
        """
        self._get_config()
        
        url = self._get_api_url(f'draft_orders/{draft_order_id}/complete.json')
        headers = self._get_headers()
        
        current_app.logger.info(f"Completing Shopify draft order: {draft_order_id}")
        
        response = requests.put(url, json={}, headers=headers)
        
        if response.status_code not in [200, 201]:
            error_msg = f"Shopify API error completing draft order: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)
        
        order = response.json()
        current_app.logger.info(f"Successfully completed draft order {draft_order_id} to order: {order.get('draft_order', {}).get('order_id')}")
        
        return order

    def create_order(self, sku, title, quantity, per_unit_price, shipping_charges,
                    customer_name, customer_phone, customer_address):
        """
        Create and complete an order in Shopify

        This is a convenience method that creates a draft order and immediately completes it.

        Args:
            sku (str): Product SKU
            title (str): Product title
            quantity (int): Quantity to order
            per_unit_price (float): Price per unit
            shipping_charges (float): Shipping charges
            customer_name (str): Customer name
            customer_phone (str): Customer phone number
            customer_address (dict): Customer address

        Returns:
            dict: Response containing both draft_order and order information
        """
        # Create draft order
        draft_order_response = self.create_draft_order(
            sku=sku,
            title=title,
            quantity=quantity,
            per_unit_price=per_unit_price,
            shipping_charges=shipping_charges,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address
        )
        
        draft_order_id = draft_order_response['draft_order']['id']
        
        # Complete the draft order
        completed_order = self.complete_draft_order(draft_order_id)
        
        return {
            'draft_order': draft_order_response['draft_order'],
            'order': completed_order.get('draft_order', {})
        }


# Create a singleton instance
shopify_service = ShopifyService()

