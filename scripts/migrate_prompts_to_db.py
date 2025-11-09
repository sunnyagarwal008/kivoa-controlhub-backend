#!/usr/bin/env python
"""
Database migration script to migrate prompts from prompts.py to database
This script:
1. Creates the prompts table if it doesn't exist
2. Migrates all existing prompts from src/services/prompts.py to the database
3. Preserves category and type information
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.database import db
from src.models.prompt import Prompt
from src.models.product import Category
from sqlalchemy import text


# Define the prompts to migrate (copied from prompts.py)
NECKLACE_PROMPTS = [
    "A high-resolution fashion photography portrait of a stunning female model in traditional saree with subtle makeup and natural looking hair, royal background, rich cultural elegance, natural expressions wearing attached jewellery. The model looks elegant, lively, and expressive with a natural smile, styled in a modern luxurious outfit. Classy indoor studio lighting with cinematic depth of field. The jewellery is the focus — detailed, sharp, and sparkling, captured with professional DSLR camera quality. Editorial, Vogue-style, rich colors, realistic skin texture, natural expressions, no artificial look, cinematic light.",
    "A high-resolution fashion photography portrait of a stunning female Indian model in a modern luxurious outfit, styled with  attached jewellery. She has subtle makeup, glossy natural skin, and effortlessly styled hair. The setting is chic and contemporary. The model looks lively, confident, and expressive with natural candid expressions. Editorial Vogue-style, captured with professional DSLR quality, 85mm lens, cinematic depth of field. The jewellery is the hero — sharp, detailed, and sparkling. Rich tones, modern elegance, realistic skin texture, natural expressions, no artificial look, cinematic lighting.",
    "A high-resolution fashion photography portrait of a stunning female Indian model with natural black hair in a traditional dress, styled with attached jewellery. The earring size is medium, not too big. She has subtle makeup, glossy natural skin, and effortlessly styled hair. The setting is chic and contemporary. The model looks lively, confident, and expressive with natural candid expressions. Editorial Vogue-style, captured with professional DSLR quality, 85mm lens, cinematic depth of field. The jewellery is the hero — sharp, detailed, and sparkling. Rich tones, modern elegance, realistic skin texture, natural expressions, no artificial look, cinematic lighting. Full light and focus on necklace. Make it stand out",
    "A high-resolution studio product photograph of uploaded jewellery displayed on a model with neutral expressions. Clean plain background (white or light beige), soft professional studio lighting, minimal shadows, jewellery centered and in focus. The model is styled simply with natural makeup and neat hair to avoid distractions. The jewellery is the hero — sharp, detailed, and sparkling, captured with DSLR quality and catalogue-style clarity. Realistic skin tones, no artificial look, minimalistic composition. Full light and focus on necklace. Make it stand out. Female model should be real looking Indian woman with real expressions.",
    "Jewellery displayed against a blurred artistic background royal architecture. Soft golden lighting, warm tones, jewellery glowing and catching the light.",
    "Elegant flat lay photo of jewellery placed on velvet or silk fabric, minimal props (jewellery box, soft flowers). Overhead shot, soft golden lighting, luxurious catalogue look.",
    "A high-end lifestyle photoshoot of a real, natural-looking female model with real hair wearing a [type of jewellery, e.g., pearl choker necklace], in a soft indoor setting with warm ambient lighting, professional makeup, neutral-toned outfit (e.g., linen shirt or evening dress), natural pose, soft smile or candid expression, editorial photography style, soft bokeh background, emphasis on the jewellery, classy and elegant, realistic skin texture, cinematic lighting. Remember Don't change the input jewellery in any way.",
    "A professional studio photoshoot of an elegant attached jewellery, displayed on a neutral-toned velvet display stand, isolated on a soft beige or gradient white background, soft diffused lighting with sharp focus on the jewellery details, high resolution, reflections and shadows for realism, minimal background distractions, commercial product photography style, luxurious and classy mood. Remember Don't change the input jewellery in any way."
]

RING_PROMPTS_MODEL_HAND = [
    "Editorial close-up: A North Indian model wearing a ring, focus on the jewellery with luxury tones, satin and stone textures softly behind. Focus on the ring and blur the background. Do not change the input ring in any way.",
    "A North Indian jewellery model showcasing a ring, focus on her hand and ring, blurred satin and perfume props in the background. Focus on the ring and blur the background. Do not change the input ring in any way.",
    "A close-up of a North Indian woman's hand wearing a luxury ring, soft satin cloth in the background. Focus on the ring and blur the background. Do not change the input ring in any way.",
]

RING_PROMPTS_SATIN = [
    "Artistic focus shot of a ring placed on satin cloth, surrounded by scattered gemstones and a luxury perfume bottle in background. Focus on the ring and blur the background. Do not change the input ring in any way.",
    "Minimalist product shot of a ring placed on satin, a single luxury perfume bottle and polished stone as accent prop in the background. Focus on the ring and blur the background. Do not change the input ring in any way.",
]

RING_PROMPTS_MIRROR = [
    "A standing mirror reflecting a ring placed in front, luxury styling with satin drapes and perfume bottles blurred in the background. Focus on the ring and blur the background. Do not change the input ring in any way.",
    "Macro shot of a ring resting on a polished stone surface, soft reflections from a nearby mirror, luxury editorial feel. Focus on the ring and blur the background. Do not change the input ring in any way.",
    "A standing mirror reflecting a ring placed in front, luxury styling with satin drapes and perfume bottles blurred in the background. Focus on the ring and blur the background. Do not change the input ring in any way.",
]

EARRING_PROMPTS = [
    "Artistic focus shot of earrings placed on satin cloth, surrounded by scattered gemstones and a luxury perfume bottle in background. Focus on the earrings and blur the background. Do not change the input earrings in any way.",
]

DEFAULT_PROMPTS = [
    ""
]


def migrate_prompts():
    """Migrate prompts from prompts.py to database"""
    app = create_app()
    
    with app.app_context():
        try:
            print("=" * 60)
            print("Migrating Prompts to Database")
            print("=" * 60)
            print()
            
            # Step 1: Create prompts table if it doesn't exist
            print("[1/3] Creating prompts table if it doesn't exist...")
            db.create_all()
            print("   ✓ Table ready")
            
            # Step 2: Check if prompts already exist
            print("\n[2/3] Checking existing prompts...")
            existing_count = Prompt.query.count()
            print(f"   Found {existing_count} existing prompts in database")
            
            if existing_count > 0:
                response = input("\n   Prompts already exist. Do you want to:\n   1. Skip migration\n   2. Clear existing and re-migrate\n   3. Add new prompts (duplicates may occur)\n   Enter choice (1/2/3): ")
                
                if response == '1':
                    print("\n   Skipping migration.")
                    return
                elif response == '2':
                    print("\n   Clearing existing prompts...")
                    Prompt.query.delete()
                    db.session.commit()
                    print("   ✓ Existing prompts cleared")
                elif response == '3':
                    print("\n   Adding new prompts alongside existing ones...")
                else:
                    print("\n   Invalid choice. Exiting.")
                    return
            
            # Step 3: Load categories from database
            print("\n[3/4] Loading categories from database...")
            categories_map = {}
            categories = Category.query.all()

            if not categories:
                print("   ✗ No categories found in database!")
                print("   Please create categories first before migrating prompts.")
                print("   Required categories: necklace, ring, earring, default")
                return

            for category in categories:
                categories_map[category.name.lower()] = category.id

            print(f"   ✓ Found {len(categories_map)} categories: {', '.join(categories_map.keys())}")

            # Step 4: Migrate prompts
            print("\n[4/5] Migrating prompts...")

            prompts_to_create = []

            # Necklace prompts
            if 'necklaces' in categories_map:
                for prompt_text in NECKLACE_PROMPTS:
                    if prompt_text.strip():  # Skip empty prompts
                        prompts_to_create.append({
                            'text': prompt_text,
                            'category_id': categories_map['necklaces'],
                            'type': None,
                            'tags': None,
                            'is_active': True
                        })
            else:
                print("   ⚠ Warning: 'necklaces' category not found, skipping necklace prompts")

            # Ring prompts - model_hand type
            if 'rings' in categories_map:
                for prompt_text in RING_PROMPTS_MODEL_HAND:
                    if prompt_text.strip():
                        prompts_to_create.append({
                            'text': prompt_text,
                            'category_id': categories_map['rings'],
                            'type': 'model_hand',
                            'tags': None,
                            'is_active': True
                        })

                # Ring prompts - satin type
                for prompt_text in RING_PROMPTS_SATIN:
                    if prompt_text.strip():
                        prompts_to_create.append({
                            'text': prompt_text,
                            'category_id': categories_map['rings'],
                            'type': 'satin',
                            'tags': None,
                            'is_active': True
                        })

                # Ring prompts - mirror type
                for prompt_text in RING_PROMPTS_MIRROR:
                    if prompt_text.strip():
                        prompts_to_create.append({
                            'text': prompt_text,
                            'category_id': categories_map['rings'],
                            'type': 'mirror',
                            'tags': None,
                            'is_active': True
                        })
            else:
                print("   ⚠ Warning: 'rings' category not found, skipping ring prompts")

            # Earring prompts
            if 'earrings' in categories_map:
                for prompt_text in EARRING_PROMPTS:
                    if prompt_text.strip():
                        prompts_to_create.append({
                            'text': prompt_text,
                            'category_id': categories_map['earrings'],
                            'type': None,
                            'tags': None,
                            'is_active': True
                        })
            else:
                print("   ⚠ Warning: 'earring' category not found, skipping earring prompts")

            # Default prompts
            if 'default' in categories_map:
                for prompt_text in DEFAULT_PROMPTS:
                    if prompt_text.strip():
                        prompts_to_create.append({
                            'text': prompt_text,
                            'category_id': categories_map['default'],
                            'type': None,
                            'tags': None,
                            'is_active': True
                        })
            else:
                print("   ⚠ Warning: 'default' category not found, skipping default prompts")

            # Create prompts in database
            created_count = 0
            for prompt_data in prompts_to_create:
                prompt = Prompt(**prompt_data)
                db.session.add(prompt)
                created_count += 1

            db.session.commit()
            
            print(f"   ✓ Successfully migrated {created_count} prompts")

            # Step 5: Verify migration
            print("\n[5/5] Verifying migration...")

            # Count by category
            category_counts = db.session.query(
                Category.name,
                db.func.count(Prompt.id)
            ).join(Prompt).group_by(Category.name).all()

            print("   Prompts by category:")
            for category_name, count in category_counts:
                print(f"      • {category_name}: {count} prompts")

            # Count by type for rings
            if 'ring' in categories_map:
                ring_types = db.session.query(
                    Prompt.type,
                    db.func.count(Prompt.id)
                ).filter(Prompt.category_id == categories_map['ring']).group_by(Prompt.type).all()

                if ring_types:
                    print("   Ring prompts by type:")
                    for prompt_type, count in ring_types:
                        type_name = prompt_type if prompt_type else 'None'
                        print(f"      • {type_name}: {count} prompts")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("\nNext steps:")
            print("1. The prompts are now in the database")
            print("2. You can manage them via the /api/prompts endpoints")
            print("3. The prompts.py service will now fetch from database")
            print("=" * 60 + "\n")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Error during migration: {str(e)}")
            print("\nMigration failed. Database rolled back.")
            raise


if __name__ == '__main__':
    migrate_prompts()

