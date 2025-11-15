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

    def find_or_create_customer(self, customer_name, customer_phone, customer_address):
        """
        Find existing customer by phone number or create a new one in Shopify

        Args:
            customer_name (str): Customer name
            customer_phone (str): Customer phone number
            customer_address (dict): Customer address with fields:
                - address1 (str): Street address
                - city (str): City
                - province (str): State/Province
                - country (str): Country
                - zip (str): Postal/ZIP code

        Returns:
            dict: Shopify customer object
        """
        self._get_config()

        # Search for existing customer by phone number
        search_url = self._get_api_url(f'customers/search.json?query=phone:{customer_phone}')
        headers = self._get_headers()

        current_app.logger.info(f"Searching for existing customer with phone: {customer_phone}")

        response = requests.get(search_url, headers=headers)

        if response.status_code == 200:
            customers = response.json().get('customers', [])
            if customers:
                customer = customers[0]
                current_app.logger.info(f"Found existing customer: {customer.get('id')}")
                return customer

        # Customer not found, create new one
        current_app.logger.info(f"Customer not found, creating new customer with phone: {customer_phone}")

        first_name = customer_name.split()[0] if customer_name else ""
        last_name = " ".join(customer_name.split()[1:]) if len(customer_name.split()) > 1 else ""

        payload = {
            "customer": {
                "first_name": first_name,
                "last_name": last_name,
                "phone": customer_phone,
                "addresses": [
                    {
                        "address1": customer_address.get('address1', ''),
                        "city": customer_address.get('city', ''),
                        "province": customer_address.get('province', ''),
                        "country": customer_address.get('country', ''),
                        "zip": customer_address.get('zip', ''),
                        "phone": customer_phone,
                        "first_name": first_name,
                        "last_name": last_name
                    }
                ]
            }
        }

        create_url = self._get_api_url('customers.json')
        response = requests.post(create_url, json=payload, headers=headers)

        if response.status_code not in [200, 201]:
            error_msg = f"Shopify API error creating customer: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        customer = response.json().get('customer', {})
        current_app.logger.info(f"Successfully created customer: {customer.get('id')}")

        return customer

    def create_draft_order(self, sku, title, quantity, per_unit_price, shipping_charges,
                          customer_id, customer_name, customer_phone, customer_address):
        """
        Create a draft order in Shopify

        Args:
            sku (str): Product SKU
            title (str): Product title
            quantity (int): Quantity to order
            per_unit_price (float): Price per unit (tax-inclusive)
            shipping_charges (float): Shipping charges
            customer_id (int): Shopify customer ID
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
                        "price": str(per_unit_price),
                        "taxable": False  # Mark as non-taxable since price is tax-inclusive
                    }
                ],
                "customer": {
                    "id": customer_id
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
                    "price": str(shipping_charges),
                    "taxable": False  # Mark shipping as non-taxable as well
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

    def fulfill_order(self, order_id):
        """
        Fulfill an order in Shopify

        Args:
            order_id (int): Order ID to fulfill

        Returns:
            dict: Fulfillment response
        """
        self._get_config()

        # First, get the order to retrieve line items
        order_url = self._get_api_url(f'orders/{order_id}.json')
        headers = self._get_headers()

        current_app.logger.info(f"Retrieving order details for fulfillment: {order_id}")

        response = requests.get(order_url, headers=headers)

        if response.status_code not in [200, 201]:
            error_msg = f"Shopify API error retrieving order: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        order = response.json().get('order', {})

        # Get all line items for fulfillment
        line_items = []
        for item in order.get('line_items', []):
            line_items.append({
                "id": item['id'],
                "quantity": item['quantity']
            })

        # Create fulfillment payload
        payload = {
            "fulfillment": {
                "line_items": line_items,
                "notify_customer": False
            }
        }

        # Create fulfillment
        fulfillment_url = self._get_api_url(f'orders/{order_id}/fulfillments.json')

        current_app.logger.info(f"Fulfilling Shopify order: {order_id}")

        response = requests.post(fulfillment_url, json=payload, headers=headers)

        if response.status_code not in [200, 201]:
            error_msg = f"Shopify API error fulfilling order: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        fulfillment = response.json()
        current_app.logger.info(f"Successfully fulfilled order: {order_id}")

        return fulfillment

    def create_order(self, sku, title, quantity, per_unit_price, shipping_charges,
                    customer_name, customer_phone, customer_address):
        """
        Create and complete an order in Shopify

        This is a convenience method that:
        1. Finds or creates a customer in Shopify by phone number
        2. Creates a draft order with tax-inclusive pricing
        3. Immediately completes the draft order
        4. Fulfills the order

        Args:
            sku (str): Product SKU
            title (str): Product title
            quantity (int): Quantity to order
            per_unit_price (float): Price per unit (tax-inclusive)
            shipping_charges (float): Shipping charges
            customer_name (str): Customer name
            customer_phone (str): Customer phone number
            customer_address (dict): Customer address

        Returns:
            dict: Response containing draft_order, order, customer, and fulfillment information
        """
        # Find or create customer by phone number
        customer = self.find_or_create_customer(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address
        )

        customer_id = customer.get('id')

        # Create draft order
        draft_order_response = self.create_draft_order(
            sku=sku,
            title=title,
            quantity=quantity,
            per_unit_price=per_unit_price,
            shipping_charges=shipping_charges,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address
        )

        draft_order_id = draft_order_response['draft_order']['id']

        # Complete the draft order
        completed_order = self.complete_draft_order(draft_order_id)

        # Get the order ID from the completed draft order
        order_id = completed_order.get('draft_order', {}).get('order_id')

        # Fulfill the order
        fulfillment = None
        if order_id:
            try:
                fulfillment = self.fulfill_order(order_id)
            except Exception as e:
                current_app.logger.warning(f"Failed to fulfill order {order_id}: {str(e)}")
                # Continue even if fulfillment fails

        return {
            'draft_order': draft_order_response['draft_order'],
            'order': completed_order.get('draft_order', {}),
            'customer': customer,
            'fulfillment': fulfillment
        }


# Create a singleton instance
shopify_service = ShopifyService()

