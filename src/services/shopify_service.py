import requests
from flask import current_app
from urllib.parse import quote


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
            self.api_version = current_app.config.get('SHOPIFY_API_VERSION', '2024-07')

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
        # URL-encode the phone number to handle special characters and spaces
        encoded_phone = quote(customer_phone, safe='')
        search_url = self._get_api_url(f'customers/search.json?query=phone:{encoded_phone}')
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

        # Look up the product variant by SKU to get variant_id for inventory tracking
        variant_id = None
        product = self.find_product_by_sku(sku)
        if product:
            # Find the matching variant by SKU
            for variant in product.get('variants', []):
                if variant.get('sku') == sku:
                    variant_id = variant.get('id')
                    current_app.logger.info(f"Found variant_id {variant_id} for SKU: {sku}")
                    break
        
        if not variant_id:
            current_app.logger.warning(f"No variant found for SKU: {sku}. Creating custom line item (inventory will NOT be tracked).")

        # Construct draft order payload
        # Use variant_id if found to link to actual product for inventory tracking
        if variant_id:
            line_item = {
                "variant_id": variant_id,
                "quantity": quantity,
                "price": str(per_unit_price),
                "taxable": False  # Mark as non-taxable since price is tax-inclusive
            }
        else:
            # Fallback to custom line item (no inventory tracking)
            line_item = {
                "title": title,
                "sku": sku,
                "quantity": quantity,
                "price": str(per_unit_price),
                "taxable": False  # Mark as non-taxable since price is tax-inclusive
            }

        payload = {
            "draft_order": {
                "line_items": [line_item],
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
        Find a product in Shopify by SKU using GraphQL API

        Args:
            sku (str): Product SKU to search for

        Returns:
            dict: Shopify product object if found, None otherwise
        """
        self._get_config()

        current_app.logger.info(f"Searching for product with SKU: {sku}")

        # Use GraphQL API to search by SKU efficiently
        graphql_url = self._get_api_url('graphql.json')
        headers = self._get_headers()

        # GraphQL query to search for product variant by SKU
        query = """
        query($sku: String!) {
          productVariants(first: 1, query: $sku) {
            edges {
              node {
                id
                sku
                product {
                  id
                  legacyResourceId
                  title
                  descriptionHtml
                  vendor
                  productType
                  tags
                  variants(first: 100) {
                    edges {
                      node {
                        id
                        legacyResourceId
                        sku
                        price
                        inventoryQuantity
                      }
                    }
                  }
                  images(first: 10) {
                    edges {
                      node {
                        id
                        url
                        altText
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """

        payload = {
            "query": query,
            "variables": {
                "sku": f"sku:{sku}"
            }
        }

        response = requests.post(graphql_url, json=payload, headers=headers)

        if response.status_code not in [200, 201]:
            error_msg = f"Shopify GraphQL API error: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        result = response.json()

        # Check for GraphQL errors
        if 'errors' in result:
            error_msg = f"Shopify GraphQL errors: {result['errors']}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        # Extract product from GraphQL response
        edges = result.get('data', {}).get('productVariants', {}).get('edges', [])
        
        if not edges:
            current_app.logger.info(f"No product found with SKU: {sku}")
            return None

        # Convert GraphQL response to REST API format for compatibility
        graphql_product = edges[0]['node']['product']
        
        # Transform to REST API format
        product = {
            'id': graphql_product['legacyResourceId'],
            'title': graphql_product['title'],
            'body_html': graphql_product['descriptionHtml'],
            'vendor': graphql_product['vendor'],
            'product_type': graphql_product['productType'],
            'tags': graphql_product['tags'],
            'variants': [
                {
                    'id': v['node']['legacyResourceId'],
                    'sku': v['node']['sku'],
                    'price': v['node']['price'],
                    'inventory_quantity': v['node']['inventoryQuantity']
                }
                for v in graphql_product['variants']['edges']
            ],
            'images': [
                {
                    'id': img['node']['id'],
                    'src': img['node']['url'],
                    'alt': img['node']['altText']
                }
                for img in graphql_product['images']['edges']
            ]
        }

        current_app.logger.info(f"Found product with SKU {sku}: product_id={product['id']}")
        return product

    def create_product(self, title, description, sku, price, inventory_quantity, weight=None,
                      images=None, tags=None, vendor=None, product_type=None):
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
            product_type (str): Product type/category (optional)

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
                "product_type": product_type or "",
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

        # Add images if provided (convert CDN URLs to S3 URLs for Shopify compatibility)
        if images:
            payload["product"]["images"] = [
                {"src": self._convert_cdn_to_s3_url(img_url)} for img_url in images
            ]

        url = self._get_api_url('products.json')
        headers = self._get_headers()

        current_app.logger.info(f"Creating Shopify product: {title} (SKU: {sku})")

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code not in [200, 201]:
            error_msg = f"Shopify API error creating product: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        product = response.json().get('product', {})
        product_id = product.get('id')
        current_app.logger.info(f"Successfully created Shopify product: {product_id} (SKU: {sku})")

        # Update product category using GraphQL (REST API doesn't support this)
        try:
            self._update_product_category_graphql(product_id)
            current_app.logger.info(f"Successfully set product category to 'Apparel & Accessories > Jewelry' for product {product_id}")
        except Exception as e:
            current_app.logger.warning(f"Failed to set product category for product {product_id}: {str(e)}")

        return product

    def update_product(self, product_id, title=None, description=None, price=None,
                      inventory_quantity=None, weight=None, images=None, tags=None, product_type=None):
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
            product_type (str): Product type/category (optional)

        Returns:
            dict: Updated Shopify product object
        """
        self._get_config()

        # Log what's being updated
        update_fields = []
        if title is not None:
            update_fields.append(f"title='{title[:50]}...' " if len(title) > 50 else f"title='{title}'")
        if description is not None:
            desc_preview = description[:100] + "..." if len(description) > 100 else description
            update_fields.append(f"description='{desc_preview}'")
        if price is not None:
            update_fields.append(f"price={price}")
        if inventory_quantity is not None:
            update_fields.append(f"inventory={inventory_quantity}")
        if weight is not None:
            update_fields.append(f"weight={weight}g")
        if images is not None:
            update_fields.append(f"images={len(images)} images")
        if tags is not None:
            update_fields.append(f"tags='{tags}'")

        current_app.logger.info(f"Updating Shopify product {product_id}: {', '.join(update_fields) if update_fields else 'no changes'}")

        # Build update payload - only include fields that are provided
        payload = {"product": {}}

        if title is not None:
            payload["product"]["title"] = title

        if description is not None:
            payload["product"]["body_html"] = description

        if tags is not None:
            payload["product"]["tags"] = tags

        if product_type is not None:
            payload["product"]["product_type"] = product_type

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
            variant_updates = []

            if price is not None:
                variant_payload["variant"]["price"] = str(price)
                variant_updates.append(f"price={price}")

            if weight is not None:
                variant_payload["variant"]["weight"] = weight
                variant_payload["variant"]["weight_unit"] = "g"
                variant_updates.append(f"weight={weight}g")

            current_app.logger.info(f"Updating variant {variant_id}: {', '.join(variant_updates)}")

            variant_url = self._get_api_url(f'variants/{variant_id}.json')
            variant_response = requests.put(variant_url, json=variant_payload, headers=headers)

            if variant_response.status_code not in [200, 201]:
                error_msg = f"Shopify API error updating variant: {variant_response.status_code} - {variant_response.text}"
                current_app.logger.error(error_msg)
                raise Exception(error_msg)

            current_app.logger.info(f"Successfully updated variant {variant_id}")

            # Update inventory if provided
            if inventory_quantity is not None:
                # Get inventory item ID from variant
                inventory_item_id = variants[0].get('inventory_item_id')
                if inventory_item_id:
                    current_app.logger.info(f"Updating inventory for item {inventory_item_id} to {inventory_quantity}")

                    # Get available locations
                    locations_url = self._get_api_url('locations.json')
                    locations_response = requests.get(locations_url, headers=headers)

                    if locations_response.status_code in [200, 201]:
                        locations = locations_response.json().get('locations', [])
                        if locations:
                            location_id = locations[0]['id']
                            location_name = locations[0].get('name', 'Unknown')
                            current_app.logger.info(f"Setting inventory at location '{location_name}' (ID: {location_id})")

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
                            else:
                                current_app.logger.info(f"Successfully updated inventory to {inventory_quantity}")
                        else:
                            current_app.logger.warning("No locations found for inventory update")
                    else:
                        current_app.logger.warning(f"Failed to get locations: {locations_response.text}")
                else:
                    current_app.logger.warning("No inventory_item_id found for variant")

        # Update product-level fields if any were provided
        if payload["product"]:
            product_updates = list(payload["product"].keys())
            current_app.logger.info(f"Updating product-level fields: {', '.join(product_updates)}")

            update_url = self._get_api_url(f'products/{product_id}.json')
            response = requests.put(update_url, json=payload, headers=headers)

            if response.status_code not in [200, 201]:
                error_msg = f"Shopify API error updating product: {response.status_code} - {response.text}"
                current_app.logger.error(error_msg)
                raise Exception(error_msg)

            product = response.json().get('product', {})
            current_app.logger.info(f"Successfully updated product-level fields")

        # Handle images if provided
        if images is not None:
            existing_image_count = len(product.get('images', []))
            current_app.logger.info(f"Replacing {existing_image_count} existing images with {len(images)} new images")

            # Delete existing images
            deleted_count = 0
            for img in product.get('images', []):
                delete_img_url = self._get_api_url(f'products/{product_id}/images/{img["id"]}.json')
                delete_response = requests.delete(delete_img_url, headers=headers)
                if delete_response.status_code in [200, 204]:
                    deleted_count += 1

            current_app.logger.info(f"Deleted {deleted_count} existing images")

            # Add new images (convert CDN URLs to S3 URLs for Shopify compatibility)
            added_count = 0
            for img_url in images:
                # Convert CDN URL to S3 URL so Shopify can download it
                s3_url = self._convert_cdn_to_s3_url(img_url)
                img_payload = {"image": {"src": s3_url}}
                img_create_url = self._get_api_url(f'products/{product_id}/images.json')
                img_response = requests.post(img_create_url, json=img_payload, headers=headers)
                if img_response.status_code in [200, 201]:
                    added_count += 1

            current_app.logger.info(f"Added {added_count}/{len(images)} new images")

        current_app.logger.info(f"✓ Successfully updated Shopify product: {product_id}")

        # Update product category using GraphQL if product_type was provided
        if product_type is not None:
            try:
                self._update_product_category_graphql(product_id)
                current_app.logger.info(f"Successfully set product category to 'Apparel & Accessories > Jewelry' for product {product_id}")
            except Exception as e:
                current_app.logger.warning(f"Failed to set product category for product {product_id}: {str(e)}")

        # Fetch updated product
        response = requests.get(get_url, headers=headers)
        return response.json().get('product', {})

    def _update_product_category_graphql(self, product_id):
        """
        Update product category using GraphQL API
        REST API doesn't support setting product category, so we use GraphQL

        Args:
            product_id (int): Shopify product ID (REST API format)

        Returns:
            dict: GraphQL response
        """
        self._get_config()

        current_app.logger.info(f"Using Shopify API version: {self.api_version}")

        # Convert REST API product ID to GraphQL GID
        product_gid = f"gid://shopify/Product/{product_id}"
        
        # Taxonomy category GID for "Apparel & Accessories > Jewelry"
        category_gid = "gid://shopify/TaxonomyCategory/aa-6"

        # GraphQL mutation to update product category using productSet
        # Note: productSet is available in API version 2024-04+
        # In API 2024-07, product ID is included in the input, not as a separate identifier
        mutation = """
        mutation productSet($input: ProductSetInput!, $synchronous: Boolean) {
          productSet(input: $input, synchronous: $synchronous) {
            product {
              id
              category {
                id
                fullName
              }
            }
            userErrors {
              field
              message
            }
          }
        }
        """

        variables = {
            "input": {
                "id": product_gid,
                "category": category_gid
            },
            "synchronous": True
        }

        graphql_url = self._get_api_url('graphql.json')
        headers = self._get_headers()

        payload = {
            "query": mutation,
            "variables": variables
        }

        response = requests.post(graphql_url, json=payload, headers=headers)

        if response.status_code not in [200, 201]:
            error_msg = f"Shopify GraphQL API error: {response.status_code} - {response.text}"
            raise Exception(error_msg)

        result = response.json()

        # Check for GraphQL errors
        if 'errors' in result:
            error_msg = f"Shopify GraphQL errors: {result['errors']}"
            raise Exception(error_msg)

        # Check for user errors
        user_errors = result.get('data', {}).get('productUpdate', {}).get('userErrors', [])
        if user_errors:
            error_msg = f"Shopify GraphQL user errors: {user_errors}"
            raise Exception(error_msg)

        return result

    def _convert_cdn_to_s3_url(self, url):
        """
        Convert CloudFront CDN URL to direct S3 URL
        Shopify needs to be able to download images, and CloudFront may have access restrictions

        Args:
            url (str): Image URL (may be CDN or S3)

        Returns:
            str: S3 URL
        """
        cdn_domain = current_app.config.get('CDN_DOMAIN')
        bucket_name = current_app.config.get('S3_BUCKET_NAME')
        region = current_app.config.get('AWS_REGION', 'ap-south-1')

        if cdn_domain and cdn_domain in url:
            # Extract key from CDN URL: https://{cdn_domain}/{key}
            key = url.split(f"{cdn_domain}/")[1]
            # Convert to S3 URL: https://{bucket}.s3.{region}.amazonaws.com/{key}
            s3_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{key}"
            current_app.logger.debug(f"Converted CDN URL to S3: {url} -> {s3_url}")
            return s3_url

        # Already an S3 URL or other format
        return url

    def update_product_images(self, product_id, images):
        """
        Update only the images for a product in Shopify

        Args:
            product_id (int): Shopify product ID
            images (list): List of image URLs to set (can be CDN or S3 URLs)

        Returns:
            dict: Updated Shopify product object with success/failure info
        """
        self._get_config()

        get_url = self._get_api_url(f'products/{product_id}.json')
        headers = self._get_headers()

        # Get current product to access existing images
        response = requests.get(get_url, headers=headers)

        if response.status_code not in [200, 201]:
            error_msg = f"Shopify API error retrieving product: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        product = response.json().get('product', {})
        existing_images = product.get('images', [])

        current_app.logger.info(f"Updating images for Shopify product {product_id}: {len(existing_images)} existing, {len(images) if images else 0} new")

        # Delete existing images (ignore 404 errors - image may already be deleted)
        deleted_count = 0
        for img in existing_images:
            delete_img_url = self._get_api_url(f'products/{product_id}/images/{img["id"]}.json')
            delete_response = requests.delete(delete_img_url, headers=headers)
            if delete_response.status_code in [200, 204]:
                deleted_count += 1
            elif delete_response.status_code == 404:
                # Image already deleted, ignore
                current_app.logger.debug(f"Image {img['id']} already deleted")
            else:
                current_app.logger.warning(f"Failed to delete image {img['id']}: {delete_response.text}")

        current_app.logger.info(f"Deleted {deleted_count} existing images from Shopify product {product_id}")

        # Add new images (convert CDN URLs to S3 URLs for Shopify compatibility)
        added_count = 0
        failed_images = []

        if images:
            for img_url in images:
                # Convert CDN URL to S3 URL so Shopify can download it
                s3_url = self._convert_cdn_to_s3_url(img_url)

                img_payload = {"image": {"src": s3_url}}
                img_create_url = self._get_api_url(f'products/{product_id}/images.json')
                img_response = requests.post(img_create_url, json=img_payload, headers=headers)

                if img_response.status_code in [200, 201]:
                    added_count += 1
                    current_app.logger.debug(f"Successfully added image: {s3_url}")
                else:
                    failed_images.append({
                        'original_url': img_url,
                        's3_url': s3_url,
                        'error': img_response.text
                    })
                    current_app.logger.error(f"Failed to add image {s3_url} (original: {img_url}): {img_response.text}")

        if failed_images:
            current_app.logger.error(
                f"Failed to add {len(failed_images)} images to Shopify product {product_id}. "
                f"This may be due to CloudFront/CDN access restrictions. "
                f"Shopify needs to be able to download images from the URLs."
            )
            # Log the first failed image details for debugging
            if failed_images:
                current_app.logger.error(f"First failed image details: {failed_images[0]}")

        current_app.logger.info(
            f"Image update complete for Shopify product {product_id}: "
            f"Added {added_count}/{len(images) if images else 0} images, "
            f"Failed: {len(failed_images)}"
        )

        # Fetch updated product
        response = requests.get(get_url, headers=headers)
        return response.json().get('product', {})


# Create a singleton instance
shopify_service = ShopifyService()

