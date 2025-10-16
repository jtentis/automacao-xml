import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24) 

API_URL = os.getenv('API_ENDPOINT_URL')
