from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    # General Configurations
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')

    # Google Maps API Key
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')

class DevelopmentConfig(Config):
    DEBUG = True
    FLASK_ENV = 'development'

class TestingConfig(Config):
    TESTING = True
    DEBUG = True

class ProductionConfig(Config):
    pass
