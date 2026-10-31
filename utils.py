import os
import re
from cryptography.fernet import Fernet
from PIL import Image
import io
from google import genai
from google.genai import errors

# Fallback encryption key setup
_DEFAULT_FALLBACK_KEY = b'12345678901234567890123456789012'
import base64
_STATIC_KEY = base64.urlsafe_b64encode(_DEFAULT_FALLBACK_KEY)

_ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", _STATIC_KEY)
if isinstance(_ENCRYPTION_KEY, str):
    _ENCRYPTION_KEY = _ENCRYPTION_KEY.encode()

cipher = Fernet(_ENCRYPTION_KEY)

INVALID_PHRASES = ["kya bola", "kya?", "hein?", "samjha nahi", "bata", "are", "hmm"]

# Initialize Gemini Client using official Google GenAI SDK
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Latest high-availability Gemini models list for failover protection
GEMINI_FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-4-argon",
    "gemini-3.6-flash",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash"
]

def ask_gemini_with_fallback(prompt: str) -> str:
    """Tries multiple Gemini models sequentially to prevent response failures."""
    if not ai_client:
        return "Gemini API key configured nahi hai bhai!"
    
    for model_name in GEMINI_FALLBACK_MODELS:
        try:
            response = ai_client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            if response and response.text:
                return response.text
        except Exception as e:
            # Log error internally and try next model in the list
            continue
            
    return "Sabhi AI models filhal busy hain, thodi der baad try karo!"

def validate_input(field: str, value: any) -> dict:
    if isinstance(value, str):
        val_lower = value.strip().lower()
        if val_lower in INVALID_PHRASES:
            return {"valid": False, "error": "invalid_phrase"}

    if field == "name":
        if not isinstance(value, str) or not re.match(r"^[a-zA-Z ]{2,20}$", value):
            return {"valid": False, "error": "Invalid name format (2-20 alphabets)"}
            
    elif field == "age":
        if not isinstance(value, int) or not (12 <= value <= 80):
            return {"valid": False, "error": "Age must be between 12 and 80"}
            
    elif field == "height_cm":
        if not isinstance(value, (int, float)) or not (100 <= value <= 220):
            return {"valid": False, "error": "Height must be between 100 and 220 cm"}
            
    elif field == "current_weight_kg" or field == "target_weight_kg":
        if not isinstance(value, (int, float)) or not (30 <= value <= 200):
            return {"valid": False, "error": "Weight must be between 30 and 200 kg"}
            
    return {"valid": True, "error": None}

def encrypt_data(text: str) -> str:
    if not text:
        return ""
    return cipher.encrypt(text.encode()).decode()

def decrypt_data(encrypted_text: str) -> str:
    if not encrypted_text:
        return ""
    try:
        return cipher.decrypt(encrypted_text.encode()).decode()
    except Exception:
        return encrypted_text

def to_fancy_font(text: str) -> str:
    mapping = {
        'a': 'α', 'b': 'в', 'c': 'ς', 'd': 'ɗ', 'e': 'є', 'f': 'ғ', 'g': 'ց',
        'h': 'н', 'i': 'ι', 'j': 'ʝ', 'k': 'κ', 'l': 'ʟ', 'm': 'м', 'n': 'η',
        'o': 'σ', 'p': 'ρ', 'q': 'զ', 'r': 'я', 's': 'ѕ', 't': 'т', 'u': 'υ',
        'v': 'v', 'w': 'ω', 'x': 'х', 'y': 'ʏ', 'z': 'ȥ',
        'A': 'Α', 'B': 'Β', 'C': 'Ꮯ', 'D': 'Ꭰ', 'E': 'Ε', 'F': 'Ϝ', 'G': 'Ꮹ',
        'H': 'Η', 'I': 'Ι', 'J': 'Ꭻ', 'K': 'Κ', 'L': 'Ꮮ', 'M': 'Ꮇ', 'N': 'Ν',
        'O': 'Ο', 'P': 'Ρ', 'Q': 'ⵕ', 'R': 'Ꭱ', 'S': 'Ꮪ', 'T': 'Ꭲ', 'U': '𝚄',
        'V': 'Ꮩ', 'W': 'Ꮤ', 'X': 'Χ', 'Y': 'Υ', 'Z': 'Ꮓ'
    }
    return "".join(mapping.get(c, c) for c in text)

def check_image_quality(file_bytes: bytes) -> tuple[bool, bool, str]:
    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("L")
        hist = image.histogram()
        pixels = sum(hist)
        brightness = sum(i * w for i, w in enumerate(hist)) / pixels
        
        is_dark = brightness < 65
        is_blurry = False
        
        feedback = "ujale me le" if is_dark else "photo badhiya hai"
        return is_blurry, is_dark, feedback
    except Exception:
        return False, False, "photo check failed"
