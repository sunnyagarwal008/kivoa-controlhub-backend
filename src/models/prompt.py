from datetime import datetime
from src.database import db


class Prompt(db.Model):
    """Prompt model for storing AI transformation prompts"""

    __tablename__ = 'prompts'

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    type = db.Column(db.String(100), nullable=True)  # e.g., 'model_hand', 'satin', 'mirror' for rings
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with Category
    category = db.relationship('Category', backref='prompts', lazy=True)

    def __repr__(self):
        category_name = self.category.name if self.category else 'Unknown'
        return f'<Prompt {self.id} - {category_name}/{self.type}>'

    def to_dict(self, include_category_details=False):
        """
        Convert prompt object to dictionary

        Args:
            include_category_details (bool): Include full category object
        """
        result = {
            'id': self.id,
            'text': self.text,
            'category_id': self.category_id,
            'category': self.category.name if self.category else None,
            'type': self.type,
            'tags': self.tags,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

        if include_category_details and self.category:
            result['category_details'] = self.category.to_dict()

        return result

