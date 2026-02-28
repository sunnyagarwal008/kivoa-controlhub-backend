"""
Amazon Seller Central API Service for Amazon India

This service integrates with Amazon SP-API (Selling Partner API) to manage product listings.
Amazon SP-API uses OAuth 2.0 with LWA (Login with Amazon) tokens.

Marketplace: Amazon India (A21TJRUUN4KGV)
API: Listings Items API v2021-08-01
Documentation: https://developer-docs.amazon.com/sp-api/
"""

import requests
import json
from datetime import datetime
from flask import current_app

# Default values for Kivoa listings on Amazon India
KIVOA_DEFAULTS = {
    'brand': 'KIVOA',
    'manufacturer': 'KIVOA INTERNATIONAL',
    'manufacturer_contact': (
        'KIVOA INTERNATIONAL, Opposite Paradise Resort, '
        'Pinjore-Nalagarh Road, Vill-Dhamala, Pinjore -HR 134102'
    ),
    'country_of_origin': 'IN',
    'department': 'womens',
    'supplier_declared_dg_hz_regulation': 'not_applicable',
    'hsn_code': '7117',
    'material': 'Stainless Steel',
    'metal_type': 'Stainless Steel',
    'metal_stamp': 'No Metal Stamp',
    'color': 'Gold',
    'size': 'Free',
    'condition': 'new_new',
    'browse_node': '2152562031',  # Jewellery Sets on Amazon India
    'item_type_name': 'Choker Necklace Set',
    'gem_type': ['Created Pearl', 'Created Emerald', 'Created Ruby'],
    'stones': [
        {'type': 'Pearl', 'creation_method': 'Simulated', 'treatment_method': 'Not Treated'},
        {'type': 'Ruby', 'creation_method': 'Simulated', 'treatment_method': 'Not Treated'},
        {'type': 'Emerald', 'creation_method': 'Simulated', 'treatment_method': 'Not Treated'},
    ],
    'item_dimensions': {'length': 110.0, 'width': 40.0, 'height': 5.0},  # in mm
}


class AmazonService:
    """Service for interacting with Amazon Seller Central SP-API"""

    def __init__(self):
        self.seller_id = None
        self.marketplace_id = None
        self.lwa_client_id = None
        self.lwa_client_secret = None
        self.lwa_refresh_token = None
        self.aws_access_key = None
        self.aws_secret_key = None
        self.region = None
        self.endpoint = None
        self.access_token = None
        self.token_expires_at = None

    def _get_config(self):
        """Get Amazon configuration from Flask app config"""
        if not self.seller_id:
            self.seller_id = current_app.config.get('AMAZON_SELLER_ID')
            self.marketplace_id = current_app.config.get('AMAZON_MARKETPLACE_ID', 'A21TJRUUN4KGV')
            self.lwa_client_id = current_app.config.get('AMAZON_LWA_CLIENT_ID')
            self.lwa_client_secret = current_app.config.get('AMAZON_LWA_CLIENT_SECRET')
            self.lwa_refresh_token = current_app.config.get('AMAZON_LWA_REFRESH_TOKEN')
            self.aws_access_key = current_app.config.get('AMAZON_AWS_ACCESS_KEY')
            self.aws_secret_key = current_app.config.get('AMAZON_AWS_SECRET_KEY')
            self.region = current_app.config.get('AMAZON_REGION', 'eu-west-1')
            self.endpoint = current_app.config.get('AMAZON_ENDPOINT', 'https://sellingpartnerapi-eu.amazon.com')

        if not all([self.seller_id, self.lwa_client_id, self.lwa_client_secret,
                   self.lwa_refresh_token, self.aws_access_key, self.aws_secret_key]):
            raise ValueError('Amazon configuration is missing. Please set all required Amazon credentials.')

    def _get_access_token(self):
        """
        Get LWA (Login with Amazon) access token using refresh token.
        Access tokens expire after 1 hour, so we cache and refresh as needed.
        """
        self._get_config()

        if self.access_token and self.token_expires_at:
            if datetime.utcnow().timestamp() < self.token_expires_at:
                return self.access_token

        token_url = 'https://api.amazon.com/auth/o2/token'
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': self.lwa_refresh_token,
            'client_id': self.lwa_client_id,
            'client_secret': self.lwa_client_secret
        }

        current_app.logger.info("Requesting new Amazon LWA access token")
        response = requests.post(token_url, data=payload)

        if response.status_code != 200:
            error_msg = f"Amazon LWA token error: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        token_data = response.json()
        self.access_token = token_data['access_token']
        expires_in = token_data.get('expires_in', 3600)
        self.token_expires_at = datetime.utcnow().timestamp() + expires_in - 60

        current_app.logger.info("Successfully obtained Amazon LWA access token")
        return self.access_token

    def _get_headers(self):
        """Get headers for Amazon SP-API requests"""
        access_token = self._get_access_token()
        return {
            'Content-Type': 'application/json',
            'x-amz-access-token': access_token
        }

    def _text_attr(self, value, language_tag='en_IN'):
        """Build a text attribute with language_tag and marketplace_id"""
        return [{"language_tag": language_tag, "value": value, "marketplace_id": self.marketplace_id}]

    def _value_attr(self, value):
        """Build a simple value attribute with marketplace_id"""
        return [{"value": value, "marketplace_id": self.marketplace_id}]

    def _build_image_attributes(self, images):
        """
        Build image attributes using individually numbered locator fields.
        Amazon expects: main_product_image_locator, other_product_image_locator_1, _2, ... _8
        Each is a single-element array with {media_location, marketplace_id}.
        """
        attrs = {}
        if not images:
            return attrs

        # Main image (first image)
        attrs["main_product_image_locator"] = [{
            "media_location": images[0],
            "marketplace_id": self.marketplace_id
        }]

        # Additional images: other_product_image_locator_1 through _8
        for i, img_url in enumerate(images[1:9], start=1):
            attrs[f"other_product_image_locator_{i}"] = [{
                "media_location": img_url,
                "marketplace_id": self.marketplace_id
            }]

        return attrs

    def create_product_listing(self, sku, title, description, price, quantity,
                              brand, category, images=None, attributes=None,
                              mrp=None, weight=None, bullet_points=None,
                              dimensions=None, color=None, stones_data=None,
                              gem_types=None):
        """
        Create a new product listing on Amazon India.

        Builds the full payload matching Amazon's JEWELRY_SET product type schema,
        including all 7 required fields and important optional fields.

        Args:
            sku: Product SKU (unique in seller account)
            title: Product title (max 200 chars)
            description: Product description
            price: Selling price in INR
            quantity: Available inventory quantity
            brand: Brand name
            category: Amazon product type (e.g. 'JEWELRY_SET')
            images: List of image URLs (first = main, rest = additional, max 9 total)
            attributes: Dict of additional/override attributes in Amazon format
            mrp: Maximum retail price in INR (for strikethrough pricing)
            weight: Product weight in grams
            bullet_points: List of bullet point strings for key product features
            dimensions: Dict with 'length', 'width', 'height' keys in millimeters
                        e.g. {"length": 110.0, "width": 40.0, "height": 5.0}
            color: Color string (e.g. "Gold", "Silver"). Falls back to KIVOA_DEFAULTS.
            stones_data: List of stone dicts, each with 'type', 'creation_method',
                         and 'treatment_method' keys.
                         e.g. [{"type": "Pearl", "creation_method": "Simulated",
                                 "treatment_method": "Not Treated"}]
            gem_types: List of gem type strings (e.g. ["Created Pearl", "Created Ruby"]).

        Returns:
            dict: Response from Amazon API
        """
        self._get_config()
        current_app.logger.info(f"Creating Amazon listing for SKU: {sku}")

        mid = self.marketplace_id

        # --- Build attributes matching the working listing format ---
        attrs = {}

        # == REQUIRED FIELDS (7) ==

        # 1. item_name (Title)
        attrs["item_name"] = self._text_attr(title[:200])

        # 2. brand
        attrs["brand"] = self._text_attr(brand or KIVOA_DEFAULTS['brand'])

        # 3. bullet_point (Key Product Features) - multiple entries
        if bullet_points and isinstance(bullet_points, list):
            attrs["bullet_point"] = [
                {"language_tag": "en_IN", "value": bp, "marketplace_id": mid}
                for bp in bullet_points[:7]  # Amazon allows up to 7
            ]

        # 4. product_description
        if description:
            attrs["product_description"] = self._text_attr(description)

        # 5. country_of_origin
        attrs["country_of_origin"] = self._value_attr(
            (attributes or {}).pop('country_of_origin', KIVOA_DEFAULTS['country_of_origin'])
        )

        # 6. recommended_browse_nodes
        attrs["recommended_browse_nodes"] = self._value_attr(
            (attributes or {}).pop('recommended_browse_nodes', KIVOA_DEFAULTS['browse_node'])
        )

        # 7. supplier_declared_dg_hz_regulation
        attrs["supplier_declared_dg_hz_regulation"] = self._value_attr(
            (attributes or {}).pop('supplier_declared_dg_hz_regulation',
                                  KIVOA_DEFAULTS['supplier_declared_dg_hz_regulation'])
        )

        # == OFFER & INVENTORY ==

        attrs["condition_type"] = self._value_attr(KIVOA_DEFAULTS['condition'])

        # Pricing: our_price + maximum_retail_price (MRP is required for Amazon India)
        effective_mrp = float(mrp) if mrp and float(mrp) >= float(price) else float(price)
        offer = {
            "currency": "INR",
            "audience": "ALL",
            "our_price": [{"schedule": [{"value_with_tax": float(price)}]}],
            "maximum_retail_price": [{"schedule": [{"value_with_tax": effective_mrp}]}],
            "marketplace_id": mid
        }
        attrs["purchasable_offer"] = [offer]

        attrs["fulfillment_availability"] = [{
            "fulfillment_channel_code": "DEFAULT",
            "quantity": int(quantity)
        }]

        # == IMAGES (individually numbered locators) ==
        attrs.update(self._build_image_attributes(images))

        # == PRODUCT IDENTITY & COMPLIANCE ==

        attrs["supplier_declared_has_product_identifier_exemption"] = \
            self._value_attr(True)

        attrs["manufacturer"] = self._text_attr(
            (attributes or {}).pop('manufacturer', KIVOA_DEFAULTS['manufacturer'])
        )

        attrs["part_number"] = self._value_attr(sku)

        attrs["rtip_manufacturer_contact_information"] = self._value_attr(
            (attributes or {}).pop('manufacturer_contact', KIVOA_DEFAULTS['manufacturer_contact'])
        )

        attrs["packer_contact_information"] = self._text_attr(
            (attributes or {}).pop('packer_contact', KIVOA_DEFAULTS['manufacturer_contact'])
        )

        attrs["external_product_information"] = [{
            "entity": "HSN Code",
            "value": (attributes or {}).pop('hsn_code', KIVOA_DEFAULTS['hsn_code']),
            "marketplace_id": mid
        }]

        # == PRODUCT DETAILS ==

        attrs["department"] = self._text_attr(
            (attributes or {}).pop('department', KIVOA_DEFAULTS['department'])
        )
        attrs["material"] = self._text_attr(
            (attributes or {}).pop('material', KIVOA_DEFAULTS['material'])
        )
        attrs["metal_type"] = self._text_attr(
            (attributes or {}).pop('metal_type', KIVOA_DEFAULTS['metal_type'])
        )
        attrs["color"] = self._text_attr(
            color or (attributes or {}).pop('color', KIVOA_DEFAULTS['color'])
        )
        attrs["size"] = self._text_attr(
            (attributes or {}).pop('size', KIVOA_DEFAULTS['size'])
        )

        attrs["metals"] = [{
            "id": 1,
            "metal_stamp": {"language_tag": "en_IN",
                            "value": (attributes or {}).pop('metal_stamp', KIVOA_DEFAULTS['metal_stamp'])},
            "metal_type": {"language_tag": "en_IN",
                           "value": (attributes or {}).pop('metals_metal_type', KIVOA_DEFAULTS['metal_type'])},
            "marketplace_id": mid
        }]

        # == ITEM TYPE NAME ==
        attrs["item_type_name"] = self._text_attr(
            (attributes or {}).pop('item_type_name', KIVOA_DEFAULTS['item_type_name'])
        )

        # == GEM TYPE (multiple text entries) ==
        resolved_gem_types = gem_types or (attributes or {}).pop('gem_type', KIVOA_DEFAULTS['gem_type'])
        if resolved_gem_types and isinstance(resolved_gem_types, list):
            attrs["gem_type"] = [
                {"language_tag": "en_IN", "value": gt, "marketplace_id": mid}
                for gt in resolved_gem_types
            ]

        # == STONES (complex nested format) ==
        resolved_stones = stones_data or (attributes or {}).pop('stones', KIVOA_DEFAULTS['stones'])
        if resolved_stones and isinstance(resolved_stones, list):
            attrs["stones"] = [
                {
                    "id": i + 1,
                    "type": {"language_tag": "en_IN", "value": s.get('type', 'Pearl')},
                    "creation_method": {"language_tag": "en_IN", "value": s.get('creation_method', 'Simulated')},
                    "treatment_method": {"language_tag": "en_IN", "value": s.get('treatment_method', 'Not Treated')},
                    "marketplace_id": mid
                }
                for i, s in enumerate(resolved_stones)
            ]

        # == ITEM DIMENSIONS ==
        resolved_dims = dimensions or (attributes or {}).pop('item_dimensions', KIVOA_DEFAULTS['item_dimensions'])
        if resolved_dims:
            attrs["item_dimensions"] = [{
                "length": {"unit": "millimeters", "value": float(resolved_dims.get('length', 110))},
                "width": {"unit": "millimeters", "value": float(resolved_dims.get('width', 40))},
                "height": {"unit": "millimeters", "value": float(resolved_dims.get('height', 5))},
                "marketplace_id": mid
            }]

        attrs["merchant_shipping_group"] = self._value_attr("legacy-template-id")
        attrs["skip_offer"] = self._value_attr(False)
        attrs["unit_count"] = [{"value": 1.0, "marketplace_id": mid}]

        # Weight
        if weight:
            attrs["item_weight"] = [{
                "unit": "grams",
                "value": float(weight),
                "marketplace_id": mid
            }]

        # == REMAINING CUSTOM ATTRIBUTES (already in Amazon format) ==
        # These are passed through directly — caller is responsible for format
        if attributes:
            for key, value in attributes.items():
                if value is None or value == '' or value == []:
                    continue
                attrs[key] = value

        # --- Build final payload ---
        payload = {
            "productType": category or "JEWELRY_SET",
            "requirements": "LISTING",
            "attributes": attrs
        }

        url = f"{self.endpoint}/listings/2021-08-01/items/{self.seller_id}/{sku}"
        headers = self._get_headers()

        current_app.logger.info(f"Sending create listing request to Amazon for SKU: {sku}")
        current_app.logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.put(url, json=payload, headers=headers, params={
            "marketplaceIds": self.marketplace_id
        })

        if response.status_code not in [200, 201, 202]:
            error_msg = f"Amazon API error creating listing: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        result = response.json()
        current_app.logger.info(f"Successfully created Amazon listing for SKU: {sku}")
        return result

    def update_product_listing(self, sku, title=None, description=None, price=None,
                              quantity=None, images=None, attributes=None,
                              category=None, brand=None, mrp=None, weight=None,
                              bullet_points=None, dimensions=None, color=None,
                              stones_data=None, gem_types=None):
        """
        Update an existing product listing on Amazon India using PATCH.

        Uses the same correct attribute formats as create_product_listing:
        - Text fields include language_tag
        - Images use individually numbered locator fields
        - Pricing includes MRP for strikethrough

        Args:
            sku: Product SKU
            title: Product title (optional)
            description: Product description (optional)
            price: Selling price in INR (optional)
            quantity: Available inventory quantity (optional)
            images: List of image URLs (optional)
            attributes: Dict of additional attributes in Amazon format (optional)
            category: Amazon product type (optional, default JEWELRY_SET)
            brand: Brand name (optional)
            mrp: Maximum retail price in INR (optional)
            weight: Product weight in grams (optional)
            bullet_points: List of bullet point strings (optional)
            dimensions: Dict with 'length', 'width', 'height' keys in millimeters (optional)
            color: Color string (optional, e.g. "Gold")
            stones_data: List of stone dicts with 'type', 'creation_method',
                         'treatment_method' keys (optional)
            gem_types: List of gem type strings (optional)

        Returns:
            dict: Response from Amazon API
        """
        self._get_config()
        current_app.logger.info(f"Updating Amazon listing for SKU: {sku}")

        mid = self.marketplace_id
        patches = []

        # Title
        if title:
            patches.append({
                "op": "replace",
                "path": "/attributes/item_name",
                "value": self._text_attr(title[:200])
            })

        # Brand
        if brand:
            patches.append({
                "op": "replace",
                "path": "/attributes/brand",
                "value": self._text_attr(brand)
            })

        # Description
        if description:
            patches.append({
                "op": "replace",
                "path": "/attributes/product_description",
                "value": self._text_attr(description)
            })

        # Bullet points
        if bullet_points and isinstance(bullet_points, list):
            patches.append({
                "op": "replace",
                "path": "/attributes/bullet_point",
                "value": [
                    {"language_tag": "en_IN", "value": bp, "marketplace_id": mid}
                    for bp in bullet_points[:7]
                ]
            })

        # Pricing (our_price + MRP — MRP is required for Amazon India)
        if price is not None:
            effective_mrp = float(mrp) if mrp and float(mrp) >= float(price) else float(price)
            offer = {
                "currency": "INR",
                "audience": "ALL",
                "our_price": [{"schedule": [{"value_with_tax": float(price)}]}],
                "maximum_retail_price": [{"schedule": [{"value_with_tax": effective_mrp}]}],
                "marketplace_id": mid
            }
            patches.append({
                "op": "replace",
                "path": "/attributes/purchasable_offer",
                "value": [offer]
            })

        # Inventory
        if quantity is not None:
            patches.append({
                "op": "replace",
                "path": "/attributes/fulfillment_availability",
                "value": [{
                    "fulfillment_channel_code": "DEFAULT",
                    "quantity": int(quantity)
                }]
            })

        # Images — individually numbered locator fields
        if images:
            image_attrs = self._build_image_attributes(images)
            for attr_name, attr_value in image_attrs.items():
                patches.append({
                    "op": "replace",
                    "path": f"/attributes/{attr_name}",
                    "value": attr_value
                })

        # Weight
        if weight:
            patches.append({
                "op": "replace",
                "path": "/attributes/item_weight",
                "value": [{"unit": "grams", "value": float(weight), "marketplace_id": mid}]
            })

        # Color (explicit param takes priority over attributes dict)
        resolved_color = color or (attributes or {}).pop('color', None)
        if resolved_color:
            patches.append({
                "op": "replace",
                "path": "/attributes/color",
                "value": self._text_attr(resolved_color)
            })

        # Gem types (explicit param takes priority over attributes dict)
        resolved_gem_types = gem_types or (attributes or {}).pop('gem_type', None)
        if resolved_gem_types and isinstance(resolved_gem_types, list):
            patches.append({
                "op": "replace",
                "path": "/attributes/gem_type",
                "value": [
                    {"language_tag": "en_IN", "value": gt, "marketplace_id": mid}
                    for gt in resolved_gem_types
                ]
            })

        # Stones (explicit param takes priority over attributes dict)
        resolved_stones = stones_data or (attributes or {}).pop('stones', None)
        if resolved_stones and isinstance(resolved_stones, list):
            patches.append({
                "op": "replace",
                "path": "/attributes/stones",
                "value": [
                    {
                        "id": i + 1,
                        "type": {"language_tag": "en_IN", "value": s.get('type', 'Pearl')},
                        "creation_method": {"language_tag": "en_IN", "value": s.get('creation_method', 'Simulated')},
                        "treatment_method": {"language_tag": "en_IN", "value": s.get('treatment_method', 'Not Treated')},
                        "marketplace_id": mid
                    }
                    for i, s in enumerate(resolved_stones)
                ]
            })

        # Dimensions (explicit param takes priority over attributes dict)
        resolved_dims = dimensions or (attributes or {}).pop('item_dimensions', None)
        if resolved_dims and isinstance(resolved_dims, dict):
            patches.append({
                "op": "replace",
                "path": "/attributes/item_dimensions",
                "value": [{
                    "length": {"unit": "millimeters", "value": float(resolved_dims.get('length', 110))},
                    "width": {"unit": "millimeters", "value": float(resolved_dims.get('width', 40))},
                    "height": {"unit": "millimeters", "value": float(resolved_dims.get('height', 5))},
                    "marketplace_id": mid
                }]
            })

        # == REMAINING KNOWN ATTRIBUTE KEYS (pop and wrap in proper Amazon format) ==
        if attributes:
            # Value-type attributes (marketplace_id only)
            value_keys = {
                'country_of_origin': 'country_of_origin',
                'recommended_browse_nodes': 'recommended_browse_nodes',
                'supplier_declared_dg_hz_regulation': 'supplier_declared_dg_hz_regulation',
                'manufacturer_contact': 'rtip_manufacturer_contact_information',
            }
            for src_key, amz_key in value_keys.items():
                val = attributes.pop(src_key, None)
                if val:
                    patches.append({
                        "op": "replace",
                        "path": f"/attributes/{amz_key}",
                        "value": self._value_attr(val)
                    })

            # Text-type attributes (language_tag + marketplace_id)
            text_keys = {
                'manufacturer': 'manufacturer',
                'packer_contact': 'packer_contact_information',
                'department': 'department',
                'material': 'material',
                'metal_type': 'metal_type',
                'size': 'size',
                'item_type_name': 'item_type_name',
            }
            for src_key, amz_key in text_keys.items():
                val = attributes.pop(src_key, None)
                if val:
                    patches.append({
                        "op": "replace",
                        "path": f"/attributes/{amz_key}",
                        "value": self._text_attr(val)
                    })

            # HSN code (special format)
            hsn = attributes.pop('hsn_code', None)
            if hsn:
                patches.append({
                    "op": "replace",
                    "path": "/attributes/external_product_information",
                    "value": [{"entity": "HSN Code", "value": hsn, "marketplace_id": mid}]
                })

            # Metals (special nested format)
            metal_stamp = attributes.pop('metal_stamp', None)
            metals_metal_type = attributes.pop('metals_metal_type', None)
            if metal_stamp or metals_metal_type:
                metals_val = {
                    "id": 1,
                    "metal_stamp": {"language_tag": "en_IN",
                                    "value": metal_stamp or KIVOA_DEFAULTS['metal_stamp']},
                    "metal_type": {"language_tag": "en_IN",
                                   "value": metals_metal_type or KIVOA_DEFAULTS['metal_type']},
                    "marketplace_id": mid
                }
                patches.append({
                    "op": "replace",
                    "path": "/attributes/metals",
                    "value": [metals_val]
                })

            # Remaining custom attributes (already in Amazon format)
            for key, value in attributes.items():
                if value is None or value == '' or value == []:
                    continue
                patches.append({
                    "op": "replace",
                    "path": f"/attributes/{key}",
                    "value": value
                })

        # Build payload
        payload = {
            "productType": category or "JEWELRY_SET",
            "patches": patches
        }

        url = f"{self.endpoint}/listings/2021-08-01/items/{self.seller_id}/{sku}"
        headers = self._get_headers()

        current_app.logger.info(f"Sending update listing request to Amazon for SKU: {sku}")
        current_app.logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.patch(url, json=payload, headers=headers, params={
            "marketplaceIds": self.marketplace_id
        })

        if response.status_code not in [200, 202]:
            error_msg = f"Amazon API error updating listing: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        result = response.json()
        current_app.logger.info(f"Successfully updated Amazon listing for SKU: {sku}")
        return result

    def get_product_type_definition(self, product_type):
        """
        Get product type definition from Amazon to understand required fields
        
        Args:
            product_type (str): Product type (e.g., 'NECKLACE', 'JEWELRY')
            
        Returns:
            dict: Product type definition with required fields
        """
        self._get_config()

        url = f"{self.endpoint}/definitions/2020-09-01/productTypes/{product_type}"
        headers = self._get_headers()

        current_app.logger.info(f"Fetching product type definition for: {product_type}")

        response = requests.get(url, headers=headers, params={
            "marketplaceIds": self.marketplace_id,
            "requirements": "LISTING",
            "requirementsEnforced": "ENFORCED"
        })

        if response.status_code not in [200]:
            error_msg = f"Amazon API error fetching product type: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        result = response.json()
        current_app.logger.info(f"Successfully fetched product type definition for: {product_type}")

        return result

    def get_product_listing(self, sku):
        """
        Get product listing details from Amazon
        
        Args:
            sku (str): Product SKU
            
        Returns:
            dict: Product listing details
        """
        self._get_config()

        url = f"{self.endpoint}/listings/2021-08-01/items/{self.seller_id}/{sku}"
        headers = self._get_headers()

        current_app.logger.info(f"Fetching Amazon listing for SKU: {sku}")

        response = requests.get(url, headers=headers, params={
            "marketplaceIds": self.marketplace_id
        })

        if response.status_code == 404:
            current_app.logger.info(f"No Amazon listing found for SKU: {sku}")
            return None

        if response.status_code not in [200]:
            error_msg = f"Amazon API error fetching listing: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        result = response.json()
        current_app.logger.info(f"Successfully fetched Amazon listing for SKU: {sku}")

        return result

    def delete_product_listing(self, sku):
        """
        Delete a product listing from Amazon
        
        Args:
            sku (str): Product SKU
            
        Returns:
            dict: Response from Amazon API
        """
        self._get_config()

        url = f"{self.endpoint}/listings/2021-08-01/items/{self.seller_id}/{sku}"
        headers = self._get_headers()

        current_app.logger.info(f"Deleting Amazon listing for SKU: {sku}")

        response = requests.delete(url, headers=headers, params={
            "marketplaceIds": self.marketplace_id
        })

        if response.status_code not in [200, 202, 204]:
            error_msg = f"Amazon API error deleting listing: {response.status_code} - {response.text}"
            current_app.logger.error(error_msg)
            raise Exception(error_msg)

        current_app.logger.info(f"Successfully deleted Amazon listing for SKU: {sku}")

        return {"success": True, "message": f"Listing {sku} deleted"}


# Create a singleton instance
amazon_service = AmazonService()
