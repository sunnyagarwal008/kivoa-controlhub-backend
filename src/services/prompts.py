"""
Transformation Prompts for Image Transformer

This file contains all the transformation prompts organized by categories.
You can easily add, modify, or remove prompts here.
"""

# Nature and landscape prompts
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

# Urban and architectural prompts
RING_PROMPTS_MODEL_HAND = [
    "Editorial close-up: A North Indian model wearing a ring, focus on the jewellery with luxury tones, satin and stone textures softly behind. Focus on the ring and blur the background. Do not change the input ring in any way."
    "A North Indian jewellery model showcasing a ring, focus on her hand and ring, blurred satin and perfume props in the background. Focus on the ring and blur the background. Do not change the input ring in any way.",
    "A close-up of a North Indian woman’s hand wearing a luxury ring, soft satin cloth in the background. Focus on the ring and blur the background. Do not change the input ring in any way.",
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

DEFAULT_PROMPTS = [
    ""
    ]

# All prompt categories for easy access
ALL_PROMPT_CATEGORIES = {
    'necklace': [NECKLACE_PROMPTS],
    'ring': [RING_PROMPTS_MODEL_HAND, RING_PROMPTS_SATIN, RING_PROMPTS_MIRROR],
    'default' : [DEFAULT_PROMPTS],
}

def get_prompts_by_category(category: str):
    """
    Get prompts by category
    
    Args:
        category: Category name ('default', 'nature', 'urban', etc.)
        
    Returns:
        List of prompts for the specified category
    """
    return ALL_PROMPT_CATEGORIES.get(category.lower())


def get_all_prompts():
    """
    Get all prompts from all categories combined
    
    Returns:
        List of all available prompts
    """
    all_prompts = []
    for prompts in ALL_PROMPT_CATEGORIES.values():
        all_prompts.extend(prompts)
    return all_prompts


def get_available_categories():
    """
    Get list of available prompt categories
    
    Returns:
        List of category names
    """
    return list(ALL_PROMPT_CATEGORIES.keys())
