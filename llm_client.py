
import requests
# Import API libraries (conditional imports to avoid hard dependencies)
try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai
except ImportError:
    openai = None
import google.generativeai as genai

###############################################################################
# LLM_Client Class
###############################################################################
class LLM_Client:
    """
    A generic LLM client class that supports 'claude', 'openai', or 'deepseek'.
    It provides a get_response() method to return a response given a prompt.
    """
    def __init__(self, llm_service: str, model_name: str, api_key: str,ollama_host: str = "http://localhost:11434"):
        self.llm_service = llm_service.lower()
        self.model_name = model_name
        self.api_key = api_key
        self.ollama_host = ollama_host

        
        if self.llm_service == "anthropic":
            if anthropic is None:
                raise Exception("Anthropic library not found. Install with: pip install anthropic")
            self.client = anthropic.Anthropic(api_key=self.api_key)
        elif self.llm_service == "openai":
            if openai is None:
                raise Exception("OpenAI library not found. Install with: pip install openai")
            self.client = openai.OpenAI(api_key=self.api_key)
        elif self.llm_service == "deepseek":
            if openai is None:
                raise Exception("Deepseek library not found. Install with: pip install deepseek")
            self.client = openai.OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        elif self.llm_service == "ollama":
            # No specific client initialization needed for Ollama; using requests directly.
            pass
        elif self.llm_service == "google":
            if genai is None:
                raise Exception("Google AI library not found. Install with: pip install google-generativeai")
            genai.configure(api_key=self.api_key) if self.api_key else None
            self.client = genai.GenerativeModel(self.model_name)
        
        
        else:
            raise ValueError(f"Unsupported LLM service: {self.llm_service}")
    
    def get_response(self, prompt: str) -> str:
        try:
            if self.llm_service == "anthropic":
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=15000,
                    temperature=0.7,
                    system="You are a helpful assistant that specializes in explaining complex concepts simply.",
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            elif self.llm_service == "openai":
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=15000
                )
                return response.choices[0].message.content
            elif self.llm_service == "deepseek":
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=8192
                )
                return response.choices[0].message.content
            elif self.llm_service == "ollama":
                response = requests.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                response.raise_for_status()
                return response.json().get("response", "No response from Ollama")
            elif self.llm_service == "google":
                generation_config = {
                        "temperature": 0.7,
                        "max_output_tokens": 28192,
                    }

                response  = self.client.generate_content(
                        prompt,
                        generation_config=generation_config  # Pass config here if needed
                    )
                if response.parts:
                    return response.text
                elif response.prompt_feedback.block_reason:
                    return f"Blocked by Google API: {response.prompt_feedback.block_reason}"
                else:
                    # Try accessing text directly, might work for simpler responses or older API versions
                    try:
                        return response.text
                    except AttributeError:
                        return f"Could not extract text from Google response. Full response: {response}"
                # Optionally check if model exists or store model instance, but configuration is key
                # self.client = genai.GenerativeModel(self.model_name) # Could instantiate here or in get_response
        except Exception as e:
            print(f"Error in LLM_Client.get_response: {e}")
            return f"Error generating summary: {str(e)}"
if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    ENV_PATHS = ['.env', '../.env', 'C:/ArunApps/.env']
    for path in ENV_PATHS:
        if os.path.exists(path):
            load_dotenv(path)
            break
    else:
        print("Warning: No .env file found. Using environment variables directly.")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API = os.getenv("ANTHROPIC_API")
    DEEPSEEK_API = os.getenv("DEEPSEEK_API")
    GOOGLE_AI_API = os.getenv("GOOGLE_AI_API")

    API_KEYS = {
        "anthropic":ANTHROPIC_API,
        "openai": OPENAI_API_KEY,
        "deepseek": DEEPSEEK_API,
        "google": GOOGLE_AI_API,
        "ollama": "N/A"  # Ollama typically doesn't require an API key for local instances
    }

    MODELS = {
        "anthropic": "claude-3-7-sonnet-20250219",  # Example: Use a cost-effective model
        "openai": "gpt-4o-mini",           # Example: Common default
        "deepseek": "deepseek-chat",          # Example: Common deepseek model
        "google": "gemini-2.5-pro-exp-03-25", # Example: Use a cost-effective model
        "ollama": "gemma3:12b"                # Replace with a model you have pulled locally (e.g., llama3, mistral)
    }

    OLLAMA_HOST = "http://localhost:11434" # Adjust if your Ollama runs elsewhere

    TEST_PROMPT = "Explain the concept of a Large Language Model in one sentence."

    SERVICES_TO_TEST = ["anthropic", "openai", "deepseek", "google", "ollama"]
    # You can comment out services you don't want to test, e.g.
    # SERVICES_TO_TEST = ["openai", "ollama"]


    # --- Testing Loop ---
    print("Starting LLM_Client tests...")
    print("=" * 40)

    for service in SERVICES_TO_TEST:
        print(f"Testing service: {service.upper()}")

        api_key = API_KEYS.get(service)
        model_name = MODELS.get(service)
        ollama_host = OLLAMA_HOST if service == "ollama" else None # Pass host only for ollama

        if not model_name:
            print(f"SKIPPING {service.upper()}: Model name not configured.")
            print("-" * 40)
            continue

        # Basic check for placeholder keys (excluding Ollama)
        if service != "ollama" and (not api_key or "YOUR_" in api_key):
            print(f"SKIPPING {service.upper()}: API key is missing or looks like a placeholder ('{api_key}').")
            print("Please replace placeholder keys in the script.")
            print("-" * 40)
            continue
        elif service == "ollama" and api_key == "N/A":
            print("Note: Using 'N/A' as API key for Ollama (expected for local setup).")


        client = None # Ensure client is reset or defined for error scope
        try:
            # Initialize client
            print(f"Initializing client for {service.upper()} with model '{model_name}'...")
            client = LLM_Client(
                llm_service=service,
                model_name=model_name,
                api_key=api_key,
                ollama_host=ollama_host # Pass the specific host if it's ollama
            )
            print("Client initialized successfully.")

            # Get response
            print(f"Sending prompt: '{TEST_PROMPT}'")
            response = client.get_response(TEST_PROMPT)

            print(f"--- Response from {service.upper()} ---")
            print(response)
            print("-" * 40)


        except ImportError as e:
            print(f"FAILED: Could not test {service.upper()} due to missing library: {e}")
            print("Please install the required library.")
            print("-" * 40)
        except Exception as e:
            # Catch initialization errors or unexpected errors during get_response
            error_context = "initializing client" if client is None else "getting response"
            print(f"FAILED {error_context} for {service.upper()}: {type(e).__name__} - {e}")
            print("-" * 40)


    print("LLM_Client testing finished.")
    print("\nIMPORTANT: Remember to handle API keys securely (e.g., environment variables) in production code.")