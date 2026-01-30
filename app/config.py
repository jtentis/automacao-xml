import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY=os.urandom(24),
    API_URL=os.getenv('API_ENDPOINT_URL'),
    API_LOGIN_URL=os.getenv('API_ENDPOINT_LOGIN_URL'),
    API_AUTH_URL=os.getenv('API_ENDPOINT_AUTH_URL')
)
