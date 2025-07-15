import os
import openai

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PUBMED_EMAIL = os.environ.get("PUBMED_EMAIL", "kossi.fianko.bio@gmail.com")
    PUBMED_API_KEY = "eb01f6d104f197ad29db4bc4e7a33935dc08"
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Initialisation de la clé OpenAI si elle existe
#if Config.OPENAI_API_KEY:
 #   openai.api_key = Config.OPENAI_API_KEY

