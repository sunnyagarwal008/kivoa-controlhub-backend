import mimetypes
import os
import random

import requests
from flask import current_app
from google import genai
from google.genai import types
from PIL import Image

from src.services.prompts import get_prompts_by_category


class GeminiService:
    """Service class for Google Gemini AI operations"""

    def __init__(self):
        self.client = None

    def _get_client(self):
        """Get or create Gemini client"""
        if self.client is None:
            self.client = genai.Client(api_key=current_app.config['GEMINI_API_KEY'])
        return self.client

    def generate_images(self, input_file_path: str, prompt_category: str, number_of_images: int = 3, prompt_type: str = None):
        prompts = get_prompts_by_category(prompt_category, prompt_type)
        output_images = []
        for i in range(1, number_of_images + 1):
            prompt = random.choice(prompts[i - 1])
            # Extract base name and extension properly using os.path.splitext
            base_name = os.path.splitext(os.path.basename(input_file_path))[0]
            extension = os.path.splitext(input_file_path)[1]

            output_image_name = f"{base_name}-0{i}{extension}"
            output_file = os.path.join("/tmp", output_image_name)
            self._do_generate_image(input_file_path, output_file, prompt)
            output_images.append(output_file)
        return output_images

    def _do_generate_image(self, image_path, output_file, prompt):
        contents = []
        print(f"Processing {image_path}...")
        with open(image_path, "rb") as f:
            image_data = f.read()
        mime_type = _get_mime_type(image_path)
        contents.append(
            types.Part(inline_data=types.Blob(data=image_data, mime_type=mime_type))
        )
        contents.append(genai.types.Part.from_text(text=prompt))
        generate_content_config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
        print(f"Image {image_path}, prompt: {prompt}")
        client = self._get_client()
        stream = client.models.generate_content_stream(
            model=current_app.config['GEMINI_MODEL'],
            contents=contents,
            config=generate_content_config,
        )

        _process_api_stream_response(stream, output_file)

        if not os.path.exists(output_file):
            raise FileNotFoundError(f"Generated image file not found at {output_file}")

    def generate_title_and_description(self, image_path):
        """
        Generate product title and description from an image using Gemini

        Args:
            image_path: Path to the product image file

        Returns:
            dict: Dictionary with 'title' and 'description' keys
        """
        print(f"Generating title and description for {image_path}...")

        with open(image_path, "rb") as f:
            image_data = f.read()

        mime_type = _get_mime_type(image_path)

        prompt = """Analyze this product image and generate:
1. A concise, SEO-friendly product title (max 100 characters) suitable for Shopify
2. A detailed product description (150-300 words) that highlights key features, benefits, and use cases

Format your response as:
TITLE: [your title here]
DESCRIPTION: [your description here]

Make the title catchy and include key product attributes. Make the description engaging, informative, and persuasive for e-commerce."""

        contents = [
            types.Part(inline_data=types.Blob(data=image_data, mime_type=mime_type)),
            genai.types.Part.from_text(text=prompt)
        ]

        generate_content_config = types.GenerateContentConfig(response_modalities=["TEXT"])

        client = self._get_client()
        response = client.models.generate_content(
            model=current_app.config['GEMINI_MODEL'],
            contents=contents,
            config=generate_content_config,
        )

        # Parse the response
        response_text = response.text.strip()
        print(f"Gemini response: {response_text}")

        # Extract title and description
        title = ""
        description = ""

        lines = response_text.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            if line.startswith('TITLE:'):
                title = line.replace('TITLE:', '').strip()
                current_section = 'title'
            elif line.startswith('DESCRIPTION:'):
                description = line.replace('DESCRIPTION:', '').strip()
                current_section = 'description'
            elif current_section == 'description' and line:
                description += ' ' + line

        # Fallback parsing if the format is not followed
        if not title or not description:
            # Try to split by newlines and take first line as title, rest as description
            parts = response_text.split('\n', 1)
            if len(parts) >= 1:
                title = parts[0].replace('TITLE:', '').strip()
            if len(parts) >= 2:
                description = parts[1].replace('DESCRIPTION:', '').strip()

        # Ensure we have at least something
        if not title:
            title = "Product"
        if not description:
            description = response_text[:500] if response_text else "Product description"

        # Trim title to max 255 characters (database limit)
        title = title[:255]

        print(f"Generated title: {title}")
        print(f"Generated description length: {len(description)} chars")

        return {
            'title': title,
            'description': description.strip()
        }


# Create a singleton instance
gemini_service = GeminiService()


def _save_binary_file(file_name: str, data: bytes):
    """Saves binary data to a specified file."""
    with open(file_name, "wb") as f:
        f.write(data)
    print(f"File saved to: {file_name}")


def validate_and_convert_image(image_path):
    """
    Validate and convert image to a format compatible with Gemini.
    Returns the path to the validated/converted image.
    """
    try:
        # Open and validate the image
        img = Image.open(image_path)

        # Convert RGBA to RGB if necessary (Gemini might not support RGBA)
        if img.mode in ('RGBA', 'LA', 'P'):
            print(f"Converting image from {img.mode} to RGB")
            # Create a white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            print(f"Converting image from {img.mode} to RGB")
            img = img.convert('RGB')

        # Check image size - Gemini has limits
        max_dimension = 3072  # Gemini's max dimension
        if img.width > max_dimension or img.height > max_dimension:
            print(f"Resizing image from {img.width}x{img.height}")
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        # Save as JPEG with good quality
        output_path = os.path.splitext(image_path)[0] + '_validated.jpg'
        img.save(output_path, 'JPEG', quality=95)

        print(f"Image validated and saved to {output_path}")
        return output_path

    except Exception as e:
        print(f"Error validating image: {str(e)}")
        raise ValueError(f"Invalid image file: {str(e)}")


def _extract_google_drive_id(url):
    """
    Extract file ID from Google Drive URL
    Supports various Google Drive URL formats
    """
    if 'drive.google.com' not in url:
        return None

    # Format: https://drive.google.com/file/d/{FILE_ID}/view
    if '/file/d/' in url:
        file_id = url.split('/file/d/')[1].split('/')[0]
        return file_id

    # Format: https://drive.google.com/open?id={FILE_ID}
    if 'id=' in url:
        file_id = url.split('id=')[1].split('&')[0]
        return file_id

    return None


def _is_google_drive_url(url):
    """Check if URL is a Google Drive URL"""
    return 'drive.google.com' in url


def _download_from_google_drive(url, destination):
    """
    Download file from Google Drive URL

    Args:
        url: Google Drive URL
        destination: Local file path to save the downloaded file

    Returns:
        bool: True if successful, False otherwise
    """
    file_id = _extract_google_drive_id(url)

    if not file_id:
        raise ValueError(f"Could not extract file ID from Google Drive URL: {url}")

    print(f"Downloading from Google Drive (file_id: {file_id})")

    # Google Drive direct download URL
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    session = requests.Session()
    response = session.get(download_url, stream=True, timeout=30)

    # Handle large files with confirmation token
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={value}"
            response = session.get(download_url, stream=True, timeout=30)
            break

    if response.status_code != 200:
        raise ValueError(f"Failed to download from Google Drive. Status code: {response.status_code}")

    # Write to file
    with open(destination, 'wb') as f:
        for chunk in response.iter_content(chunk_size=32768):
            if chunk:
                f.write(chunk)

    return True


def download_image(image_url, download_dir="/tmp"):
    # Ensure the directory exists
    os.makedirs(download_dir, exist_ok=True)

    print(f"Downloading image from: {image_url}")

    # Get filename from URL or use a default
    filename = os.path.basename(image_url.split("?")[0])
    if not filename or filename == '':
        filename = 'downloaded_image'

    # Generate temporary file path
    file_path = os.path.join(download_dir, filename)

    # Check if it's a Google Drive URL
    if _is_google_drive_url(image_url):
        print("Detected Google Drive URL")
        _download_from_google_drive(image_url, file_path)
        print(f"Downloaded from Google Drive to: {file_path}")
    else:
        # Regular download for S3 or other URLs
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        # Check content-type to ensure it's an image
        content_type = response.headers.get('content-type', '')
        print(f"Content-Type: {content_type}")

        if not content_type.startswith('image/'):
            # Log the response content for debugging
            print(f"Response content (first 500 chars): {response.text[:500]}")
            raise ValueError(f"URL did not return an image. Content-Type: {content_type}")

        # Check if we got actual image data
        if len(response.content) < 100:
            raise ValueError(f"Downloaded file is too small ({len(response.content)} bytes), likely not a valid image")

        # If filename doesn't have an extension, try to detect from content-type
        if not os.path.splitext(filename)[1]:
            extension = mimetypes.guess_extension(content_type)
            if extension:
                filename = f"{filename}{extension}"
            else:
                # Default to .jpg if we can't determine
                filename = f"{filename}.jpg"

            file_path = os.path.join(download_dir, filename)

        # Save to local file
        with open(file_path, "wb") as f:
            f.write(response.content)

        print(f"Downloaded to: {file_path} ({len(response.content)} bytes)")

    # Validate and convert the image to ensure compatibility
    try:
        validated_path = validate_and_convert_image(file_path)

        # Clean up the original file if it's different from validated
        if validated_path != file_path and os.path.exists(file_path):
            os.remove(file_path)

        return os.path.abspath(validated_path)
    except Exception as e:
        # Clean up the downloaded file on validation error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise


def _get_mime_type(file_path: str) -> str:
    """Guesses the MIME type of a file based on its extension."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        # Default to image/jpeg if we can't determine the MIME type
        print(f"Warning: Could not determine MIME type for {file_path}, defaulting to image/jpeg")
        return "image/jpeg"
    return mime_type


def _process_api_stream_response(stream, output_file: str):
    """Processes the streaming response from the GenAI API, saving images and printing text."""
    file_index = 0
    for chunk in stream:
        if (
                chunk.candidates is None
                or chunk.candidates[0].content is None
                or chunk.candidates[0].content.parts is None
        ):
            continue

        for part in chunk.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                _save_binary_file(output_file, part.inline_data.data)
                file_index += 1
            elif part.text:
                print(part.text)

    if file_index == 0:
        raise ValueError("No image data received from Gemini API")
