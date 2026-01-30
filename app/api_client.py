import requests
import json
import re
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

def api_login(login: str, senha: str) -> dict:
    LOGIN_API_URL = current_app.config['API_LOGIN_URL']
    
    payload = {
        "Login": login,
        "Senha": senha,
        "EhPos": False
    }
    json_payload = json.dumps(payload)
    content_length = str(len(json_payload.encode('utf-8')))

    headers = {
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'User-Agent': 'PostmanRuntime/7.4.0',
        'Cache-Control': 'no-cache',
        'Content-Length': content_length,
    }

    try:
        response = requests.post(LOGIN_API_URL, headers=headers, data=json_payload, timeout=15)
        response.raise_for_status()
        # print(response.text)
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {"error": f"Erro na API de Login: {response.status_code} - {response.text[:100]}..."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Erro de Conexão com a API de Login: {e}"}

def get_final_auth_token(temp_token: str) -> dict:
    AUTH_API_URL = current_app.config['API_AUTH_URL']
    params = {'f_token': temp_token}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }

    try:
        response = requests.get(AUTH_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        html_content = response.text
        
        match = re.search(r'var KeysAPI\s*=\s*(\[.*?\]);', html_content)
        
        if not match:
            return {"error": "Não foi possível encontrar as chaves da API no HTML de resposta."}
            
        json_str = match.group(1)
        
        try:
            keys_data = json.loads(json_str)
            if isinstance(keys_data, list) and len(keys_data) > 0 and 'Valor' in keys_data[0]:
                auth_token = keys_data[0]['Valor']
                # print(auth_token)
                return {"auth_token": auth_token}
            else:
                return {"error": "Formato inesperado dos dados das chaves da API."}
        except json.JSONDecodeError:
            return {"error": "Erro ao decodificar os dados das chaves da API do HTML."}

    except requests.exceptions.HTTPError as e:
        return {"error": f"Erro na API de autenticação: {response.status_code} - {response.text[:100]}..."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Erro de Conexão com a API de autenticação: {e}"}