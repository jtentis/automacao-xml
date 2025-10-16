import requests
import json
from flask import current_app

def api_call(auth_token: str, payload: dict) -> dict:
    API_URL = current_app.config['API_URL']
    
    clean_payload = {k: v if v is not None else "" for k, v in payload.items()}
    json_payload = json.dumps(clean_payload)
    content_length = str(len(json_payload.encode('utf-8')))

    headers = {
        'Authorization': auth_token,
        'Content-Type': 'application/json',
        'Accept': '*/*', 
        'User-Agent': 'PostmanRuntime/7.4.0', 
        'Cache-Control': 'no-cache',
        'Content-Length': content_length,
    }
    
    try:
        response = requests.post(API_URL, headers=headers, data=json_payload, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {"error": f"Erro na API: {response.status_code} - {response.text[:100]}..."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Erro de Conexão: {e}"}