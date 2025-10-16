import os
from dotenv import load_dotenv
from app import create_app

load_dotenv()

app = create_app()

if __name__ == '__main__':
    if not os.getenv('API_ENDPOINT_URL'):
        print("AVISO: A variável de ambiente 'API_ENDPOINT_URL' não foi definida no .env ou está vazia.")
        
    app.run(debug=True)
