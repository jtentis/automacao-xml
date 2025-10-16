import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24) 

    app.config['API_URL'] = os.getenv('API_ENDPOINT_URL')

    from .routes import routes_bp
    app.register_blueprint(routes_bp)
    
    return app