import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Google Generative AI
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

genai.configure(api_key=GOOGLE_API_KEY)

def list_available_models():
    try:
        # Get all available models
        models = genai.list_models()
        
        print("Available models:")
        print("=" * 50)
        
        for model in models:
            print(f"Model name: {model.name}")
            print(f"Display name: {model.display_name}")
            print(f"Description: {model.description}")
            print(f"Supported generation methods: {', '.join(model.supported_generation_methods)}")
            print(f"Input token limit: {model.input_token_limit}")
            print(f"Output token limit: {model.output_token_limit}")
            print("-" * 50)
        
        return models
    except Exception as e:
        print(f"Error listing models: {str(e)}")
        return None

if __name__ == "__main__":
    list_available_models()