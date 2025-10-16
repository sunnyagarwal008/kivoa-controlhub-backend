import mimetypes
import os
import random

import requests
from flask import current_app
from google import genai
from google.genai import types

from src.services.prompts import get_prompts_by_category


class GeminiService:
    """Service class for Google Gemini AI operations"""

    def __init__(self):
        self.client = None

    def _get_client(self):
        """Get or create Gemini client"""
        if self.client is None:
            self.client = genai.Client(api_key=current_app.config['GEMINI_API_KEY'])
            # AIzaSyDcuBmFCnnoi8GRMS5TlxtXsebkUIrK9s8
        return self.client

    def generate_images(self, input_file_path: str, prompt_category: str, number_of_images: int = 3):
        prompts = get_prompts_by_category(prompt_category)
        output_images = []
        for i in range(1, number_of_images + 1):
            prompt = random.choice(prompts[i - 1])
            image_name = input_file_path.split("/")[-1]
            input_image_parts = image_name.split(".")
            image_prefix = input_image_parts[0]

            sku = image_prefix[:image_prefix.rfind('-')]
            output_image_name = f"{sku}-0{i}.{input_image_parts[1]}"
            output_file = os.path.join("/tmp", f"{output_image_name}")
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
        #client = self._get_client()
        client = genai.Client(api_key=current_app.config['GEMINI_API_KEY'])
        # AIzaSyDcuBmFCnnoi8GRMS5TlxtXsebkUIrK9s8
        print(current_app.config['GEMINI_API_KEY'])
        stream = client.models.generate_content_stream(
            model=current_app.config['GEMINI_MODEL'],
            contents=contents,
            config=generate_content_config,
        )

        _process_api_stream_response(stream, output_file)


# Create a singleton instance
gemini_service = GeminiService()


def _save_binary_file(file_name: str, data: bytes):
    """Saves binary data to a specified file."""
    with open(file_name, "wb") as f:
        f.write(data)
    print(f"File saved to: {file_name}")


def download_image(image_url, download_dir="/tmp"):
    # Ensure the directory exists
    os.makedirs(download_dir, exist_ok=True)

    # Get filename from URL or fallback to a default
    filename = os.path.basename(image_url.split("?")[0])
    file_path = os.path.join(download_dir, filename)

    # Download the image
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()

    # Save to local file
    with open(file_path, "wb") as f:
        f.write(response.content)

    return os.path.abspath(file_path)


def _get_mime_type(file_path: str) -> str:
    """Guesses the MIME type of a file based on its extension."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        raise ValueError(f"Could not determine MIME type for {file_path}")
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
