# config.py 
from dotenv import load_dotenv
import os
import anthropic
import openai

from llm_client import LLM_Client


# Load environment variables from .env file - search in multiple paths
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


service_openai= "openai"     # The LLM service to use
model_4omini = "gpt-4o-mini"       # The model name

service_claude = "anthropic"     # The LLM service to use
model_claude = "claude-3-7-sonnet-20250219"       # The model name

service_google = "google"     # The LLM service to use
model_google= "gemini-2.5-pro-exp-03-25"

service_ds = "deepseek"     # The LLM service to use
model_ds = "deepseek-chat"       # The model name

api_key = OPENAI_API_KEY       # Your API key (replace with your actual key)
openai_client = LLM_Client(llm_service=service_openai, model_name=model_4omini, api_key=OPENAI_API_KEY)
claude_client = LLM_Client(llm_service=service_claude, model_name=model_claude, api_key=ANTHROPIC_API)
google_client = LLM_Client(llm_service=service_google, model_name=model_google, api_key=GOOGLE_AI_API)



dsv3_client = LLM_Client(llm_service=service_ds, model_name=model_ds, api_key=DEEPSEEK_API)
ollama_model_name="gemma3:12b"
# ollama_model_name="exaone-deep"
ollama_client = LLM_Client(llm_service="ollama", model_name=ollama_model_name, api_key="", ollama_host="http://localhost:11434")