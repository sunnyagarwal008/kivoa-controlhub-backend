"""
Utility functions for raw image management
"""

from flask import current_app
from src.database import db
from src.models import RawImage


def delete_raw_image_by_url(image_url):
    """
    Delete a raw image entry from the raw_images table by image URL
    
    Args:
        image_url: The URL of the raw image to delete
        
    Returns:
        bool: True if a raw image was deleted, False if not found
    """
    try:
        raw_image = RawImage.query.filter_by(image_url=image_url).first()
        if raw_image:
            db.session.delete(raw_image)
            current_app.logger.info(f"Deleted raw_image entry for URL: {image_url}")
            return True
        return False
    except Exception as e:
        current_app.logger.error(f"Error deleting raw_image for URL {image_url}: {str(e)}")
        raise

