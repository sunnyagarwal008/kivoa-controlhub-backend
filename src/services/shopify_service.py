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

    def get_orders(self, status=None, limit=50, page_info=None, created_at_min=None,
                   created_at_max=None, financial_status=None, fulfillment_status=None):
        """
        Retrieve orders from Shopify with pagination and filters

        Args:
            status (str): Filter by order status (open, closed, cancelled, any). Default: any
            limit (int): Number of orders to retrieve (1-250). Default: 50
            page_info (str): Page info token for pagination (from Link header)
            created_at_min (str): Show orders created after date (ISO 8601 format)
            created_at_max (str): Show orders created before date (ISO 8601 format)
            financial_status (str): Filter by financial status (authorized, pending, paid, etc.)
            fulfillment_status (str): Filter by fulfillment status (shipped, partial, unshipped, any)

        Returns:
            dict: Response containing:
                - orders: List of order objects
                - page_info: Pagination info with next/previous page tokens
        """
        self._get_config()

        # Build query parameters
        params = []

        if status:
            params.append(f'status={status}')
        else:
            params.append('status=any')

        if limit:
            # Shopify allows max 250 orders per request
            limit = min(limit, 250)
            params.append(f'limit={limit}')

        if created_at_min:
            params.append(f'created_at_min={created_at_min}')

        if created_at_max:
            params.append(f'created_at_max={created_at_max}')

        if financial_status:
            params.append(f'financial_status={financial_status}')

        if fulfillment_status:
            params.append(f'fulfillment_status={fulfillment_status}')

        # Add order by created_at descending to get latest orders first
        params.append('order=created_at desc')

        # Build URL with pagination
        if page_info:
            # Use page_info for cursor-based pagination
            params.append(f'page_info={page_info}')

        query_string = '&'.join(params)
        url = self._get_api_url(f'orders.json?{query_string}')
        headers = self._get_headers()

        current_app.logger.info(f"Fetching orders from Shopify with params: {query_string}")

        response = requests.get(url, headers=headers)

        if response.status_code not in [200, 201]:
            error_msg = f"Shopify API error retrieving orders: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        orders = response.json().get('orders', [])

        # Extract pagination info from Link header
        link_header = response.headers.get('Link', '')
        page_info_result = self._parse_link_header(link_header)

        current_app.logger.info(f"Successfully retrieved {len(orders)} orders from Shopify")

        return {
            'orders': orders,
            'page_info': page_info_result
        }

    def _parse_link_header(self, link_header):
        """
        Parse Shopify's Link header for pagination info

        Args:
            link_header (str): Link header from Shopify response

        Returns:
            dict: Pagination info with next and previous page tokens
        """
        page_info = {
            'next': None,
            'previous': None
        }

        if not link_header:
            return page_info

        # Parse Link header format: <url>; rel="next", <url>; rel="previous"
        links = link_header.split(',')

        for link in links:
            parts = link.strip().split(';')
            if len(parts) != 2:
                continue

            url_part = parts[0].strip('<> ')
            rel_part = parts[1].strip()

            # Extract page_info from URL
            if 'page_info=' in url_part:
                page_info_value = url_part.split('page_info=')[1].split('&')[0]

                if 'rel="next"' in rel_part:
                    page_info['next'] = page_info_value
                elif 'rel="previous"' in rel_part:
                    page_info['previous'] = page_info_value

        return page_info

    def find_product_by_sku(self, sku):
        """
        Find a product in Shopify by SKU

        Args:
            sku (str): Product SKU to search for

        Returns:
            dict: Shopify product object if found, None otherwise
        """
        self._get_config()

        # Search for product by SKU using GraphQL would be better, but REST API works too
        # We'll search through variants since SKU is stored at variant level
        url = self._get_api_url(f'products.json?limit=250')
        headers = self._get_headers()

        current_app.logger.info(f"Searching for product with SKU: {sku}")

        # Note: This is a simplified search. For production, consider using GraphQL API
        # or maintaining a local mapping of SKU to Shopify product ID
        response = requests.get(url, headers=headers)

        if response.status_code not in [200, 201]:
            current_app.logger.error(f"Shopify API error searching products: {response.status_code} - {response.text}")
            return None

        products = response.json().get('products', [])

        # Search through products and their variants for matching SKU
        for product in products:
            for variant in product.get('variants', []):
                if variant.get('sku') == sku:
                    current_app.logger.info(f"Found product with SKU {sku}: product_id={product['id']}, variant_id={variant['id']}")
                    return product

        current_app.logger.info(f"No product found with SKU: {sku}")
        return None

    def create_product(self, title, description, sku, price, inventory_quantity, weight=None,
                      images=None, tags=None, vendor=None):
        """
        Create a new product in Shopify

        Args:
            title (str): Product title
            description (str): Product description (HTML allowed)
            sku (str): Product SKU
            price (float): Product price
            inventory_quantity (int): Initial inventory quantity
            weight (int): Weight in grams (optional)
            images (list): List of image URLs (optional)
            tags (str): Comma-separated tags (optional)
            vendor (str): Vendor name (optional)

        Returns:
            dict: Created Shopify product object
        """
        self._get_config()

        # Build product payload
        payload = {
            "product": {
                "title": title,
                "body_html": description,
                "vendor": vendor or "Kivoa",
                "product_type": "",
                "tags": tags or "",
                "variants": [
                    {
                        "sku": sku,
                        "price": str(price),
                        "inventory_management": "shopify",
                        "inventory_quantity": inventory_quantity,
                        "weight": weight,
                        "weight_unit": "g" if weight else None
                    }
                ]
            }
        }

        # Add images if provided
        if images:
            payload["product"]["images"] = [{"src": img_url} for img_url in images]

        url = self._get_api_url('products.json')
        headers = self._get_headers()

        current_app.logger.info(f"Creating Shopify product: {title} (SKU: {sku})")

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code not in [200, 201]:
            error_msg = f"Shopify API error creating product: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        product = response.json().get('product', {})
        current_app.logger.info(f"Successfully created Shopify product: {product.get('id')} (SKU: {sku})")

        return product

    def update_product(self, product_id, title=None, description=None, price=None,
                      inventory_quantity=None, weight=None, images=None, tags=None):
        """
        Update an existing product in Shopify

        Args:
            product_id (int): Shopify product ID
            title (str): Product title (optional)
            description (str): Product description (optional)
            price (float): Product price (optional)
            inventory_quantity (int): Inventory quantity (optional)
            weight (int): Weight in grams (optional)
            images (list): List of image URLs (optional)
            tags (str): Comma-separated tags (optional)

        Returns:
            dict: Updated Shopify product object
        """
        self._get_config()

        # Build update payload - only include fields that are provided
        payload = {"product": {}}

        if title is not None:
            payload["product"]["title"] = title

        if description is not None:
            payload["product"]["body_html"] = description

        if tags is not None:
            payload["product"]["tags"] = tags

        # Handle variant updates (price, inventory, weight)
        # First, get the product to find the variant ID
        get_url = self._get_api_url(f'products/{product_id}.json')
        headers = self._get_headers()

        response = requests.get(get_url, headers=headers)

        if response.status_code not in [200, 201]:
            error_msg = f"Shopify API error retrieving product: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        product = response.json().get('product', {})
        variants = product.get('variants', [])

        if not variants:
            raise Exception(f"Product {product_id} has no variants")

        # Update the first variant (assuming single variant products)
        variant_id = variants[0]['id']

        # Update variant if price, inventory, or weight is provided
        if price is not None or inventory_quantity is not None or weight is not None:
            variant_payload = {"variant": {}}

            if price is not None:
                variant_payload["variant"]["price"] = str(price)

            if weight is not None:
                variant_payload["variant"]["weight"] = weight
                variant_payload["variant"]["weight_unit"] = "g"

            variant_url = self._get_api_url(f'variants/{variant_id}.json')
            variant_response = requests.put(variant_url, json=variant_payload, headers=headers)

            if variant_response.status_code not in [200, 201]:
                error_msg = f"Shopify API error updating variant: {variant_response.status_code} - {variant_response.text}"
                current_app.logger.error(error_msg)
                raise Exception(error_msg)

            # Update inventory if provided
            if inventory_quantity is not None:
                # Get inventory item ID from variant
                inventory_item_id = variants[0].get('inventory_item_id')
                if inventory_item_id:
                    # Get available locations
                    locations_url = self._get_api_url('locations.json')
                    locations_response = requests.get(locations_url, headers=headers)

                    if locations_response.status_code in [200, 201]:
                        locations = locations_response.json().get('locations', [])
                        if locations:
                            location_id = locations[0]['id']

                            # Set inventory level
                            inventory_url = self._get_api_url('inventory_levels/set.json')
                            inventory_payload = {
                                "location_id": location_id,
                                "inventory_item_id": inventory_item_id,
                                "available": inventory_quantity
                            }

                            inventory_response = requests.post(inventory_url, json=inventory_payload, headers=headers)

                            if inventory_response.status_code not in [200, 201]:
                                current_app.logger.warning(f"Failed to update inventory: {inventory_response.text}")

        # Update product-level fields if any were provided
        if payload["product"]:
            update_url = self._get_api_url(f'products/{product_id}.json')
            response = requests.put(update_url, json=payload, headers=headers)

            if response.status_code not in [200, 201]:
                error_msg = f"Shopify API error updating product: {response.status_code} - {response.text}"
                current_app.logger.error(error_msg)
                raise Exception(error_msg)

            product = response.json().get('product', {})

        # Handle images if provided
        if images is not None:
            # Delete existing images
            for img in product.get('images', []):
                delete_img_url = self._get_api_url(f'products/{product_id}/images/{img["id"]}.json')
                requests.delete(delete_img_url, headers=headers)

            # Add new images
            for img_url in images:
                img_payload = {"image": {"src": img_url}}
                img_create_url = self._get_api_url(f'products/{product_id}/images.json')
                requests.post(img_create_url, json=img_payload, headers=headers)

        current_app.logger.info(f"Successfully updated Shopify product: {product_id}")

        # Fetch updated product
        response = requests.get(get_url, headers=headers)
        return response.json().get('product', {})


# Create a singleton instance
shopify_service = ShopifyService()

