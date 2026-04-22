import json
import re
import time

import requests
from flask import current_app


DEFAULT_TIMEOUT_SECONDS = 20
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 1.5
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


def api_call(auth_token: str, payload: dict) -> dict:
    api_url = current_app.config['API_URL']

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
        response = request_with_retry(
            "POST",
            api_url,
            headers=headers,
            data=json_payload,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            operation_name="Pesquisa de produtos"
        )
        return response.json()
    except requests.exceptions.HTTPError as e:
        response = e.response
        return {"error": f"Erro na API: {response.status_code} - {response.text[:100]}..."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Erro de Conexao: {e}"}


def api_login(login: str, senha: str) -> dict:
    login_api_url = current_app.config['API_LOGIN_URL']

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
        response = request_with_retry(
            "POST",
            login_api_url,
            headers=headers,
            data=json_payload,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            operation_name="Login da API"
        )
        return response.json()
    except requests.exceptions.HTTPError as e:
        response = e.response
        return {"error": f"Erro na API de Login: {response.status_code} - {response.text[:100]}..."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Erro de Conexao com a API de Login: {e}"}


def get_final_auth_token(temp_token: str) -> dict:
    auth_api_url = current_app.config['API_AUTH_URL']
    params = {'f_token': temp_token}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }

    try:
        response = request_with_retry(
            "GET",
            auth_api_url,
            params=params,
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            operation_name="Autenticacao final"
        )

        html_content = response.text
        match = re.search(r'var KeysAPI\s*=\s*(\[.*?\]);', html_content)

        if not match:
            return {"error": "Nao foi possivel encontrar as chaves da API no HTML de resposta."}

        json_str = match.group(1)

        try:
            keys_data = json.loads(json_str)
            if isinstance(keys_data, list) and len(keys_data) > 0 and 'Valor' in keys_data[0]:
                auth_token = keys_data[0]['Valor']
                return {"auth_token": auth_token}
            return {"error": "Formato inesperado dos dados das chaves da API."}
        except json.JSONDecodeError:
            return {"error": "Erro ao decodificar os dados das chaves da API do HTML."}

    except requests.exceptions.HTTPError as e:
        response = e.response
        return {"error": f"Erro na API de autenticacao: {response.status_code} - {response.text[:100]}..."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Erro de Conexao com a API de autenticacao: {e}"}


def request_with_retry(method: str, url: str, operation_name: str, **kwargs) -> requests.Response:
    last_exception = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(method, url, **kwargs)

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                wait_seconds = RETRY_BACKOFF_SECONDS * attempt
                print(
                    f"[RETRY] {operation_name} falhou com status {response.status_code} "
                    f"(tentativa {attempt}/{MAX_RETRIES}). Nova tentativa em {wait_seconds:.1f}s."
                )
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            return response

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exception = e
            if attempt >= MAX_RETRIES:
                break

            wait_seconds = RETRY_BACKOFF_SECONDS * attempt
            print(
                f"[RETRY] {operation_name} falhou por conexao/timeout "
                f"(tentativa {attempt}/{MAX_RETRIES}): {e}. Nova tentativa em {wait_seconds:.1f}s."
            )
            time.sleep(wait_seconds)

        except requests.exceptions.HTTPError as e:
            if e.response is None or e.response.status_code not in RETRYABLE_STATUS_CODES or attempt >= MAX_RETRIES:
                raise

            wait_seconds = RETRY_BACKOFF_SECONDS * attempt
            print(
                f"[RETRY] {operation_name} recebeu HTTP {e.response.status_code} "
                f"(tentativa {attempt}/{MAX_RETRIES}). Nova tentativa em {wait_seconds:.1f}s."
            )
            time.sleep(wait_seconds)
            last_exception = e

    if last_exception:
        raise last_exception

    raise requests.exceptions.RequestException(f"{operation_name} falhou sem resposta valida.")
