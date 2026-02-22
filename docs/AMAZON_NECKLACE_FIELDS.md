# Amazon NECKLACE Product Type - Required Fields

Based on the Product Type Definition API response, here are the key property groups for NECKLACE listings:

## Property Groups

### 1. Product Identity (REQUIRED)
- `item_name` - Product title ✅ (we have this)
- `brand` - Brand name ✅ (we have this)
- `externally_assigned_product_identifier` - UPC/EAN/GTIN
- `manufacturer` - Manufacturer name

### 2. Product Details (IMPORTANT)
- `product_description` - Product description
- `bullet_point` - Product features/bullets
- `department` - Department (e.g., "womens", "mens", "unisex-adult")
- `target_gender` - Target gender
- `metal_type` - Type of metal (e.g., "gold", "silver", "platinum")
- `material` - Material composition
- `chain_type` - Type of chain
- `chain_length` - Chain length with unit
- `clasp_type` - Type of clasp
- `color` - Product color
- `item_type_name` - Item type
- `gem_type` - Type of gemstone (if applicable)
- `stone` - Stone details
- `metal_stamp` - Metal purity stamp (e.g., "18k", "14k")

### 3. Images (REQUIRED)
- `main_product_image_locator` - Main image ✅ (we have this)
- `other_product_image_locator_1` through `_8` - Additional images ✅ (we have this)

### 4. Offer (REQUIRED)
- `purchasable_offer` - Price information ✅ (we have this)
- `condition_type` - Condition ✅ (we have this - "new_new")
- `fulfillment_availability` - Inventory ✅ (we have this)

### 5. Safety & Compliance
- `country_of_origin` - Country where manufactured
- `item_weight` - Product weight

### 6. Shipping
- `item_dimensions` - Product dimensions
- `item_package_weight` - Package weight

## Common Missing Fields

Based on "missing information" error, likely missing:

1. **department** - Required for categorization
2. **target_gender** - Required for jewelry
3. **metal_type** - Important for necklaces
4. **chain_type** - Important for necklaces
5. **color** - Product color
6. **country_of_origin** - Compliance requirement

## Recommended Sync Payload

```json
{
  "brand": "Kivoa",
  "category": "NECKLACE",
  "attributes": {
    "department": "womens",
    "target_gender": "female",
    "metal_type": "gold",
    "metal_stamp": "18k",
    "chain_type": "cable",
    "color": "gold",
    "country_of_origin": "IN",
    "item_type_name": "necklace"
  }
}
```

## Field Values Reference

### department
- "womens"
- "mens"
- "girls"
- "boys"
- "unisex-adult"

### target_gender
- "male"
- "female"
- "unisex"

### metal_type
- "gold"
- "silver"
- "platinum"
- "white-gold"
- "rose-gold"
- "stainless-steel"

### chain_type
- "cable"
- "rope"
- "box"
- "snake"
- "bead"
- "figaro"
- "curb"

### clasp_type
- "lobster"
- "spring-ring"
- "toggle"
- "magnetic"
- "hook"

### metal_stamp
- "10k"
- "14k"
- "18k"
- "22k"
- "24k"
- "925" (for silver)
- "950" (for platinum)

## Next Steps

Update the product sync to include these required fields based on your product data.
