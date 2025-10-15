import os
import requests
import json
from flask import Flask, request, session, redirect, url_for, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24) 

API_URL = os.getenv('API_ENDPOINT_URL')

def clean_input_list(data: str) -> list:
    if not data:
        return []
    return [item.strip() for item in data.replace('\n', ',').split(',') if item.strip()]

def api_call(auth_token: str, payload: dict) -> dict:
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

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap');
        /* Fundo escuro */
        body { font-family: 'Inter', sans-serif; background-color: #2f3136; } 
        .container { max-width: 1024px; display: flex; flex-direction: column;}
        /* Labels: Cinza claro */
        .input-group label { margin-bottom: 0.5rem; display: block; font-weight: 500; color: #d1d5db; }
        /* Inputs/Textareas: Fundo escuro, texto claro, borda sutil */
        .input-group textarea, .input-group input { 
            border-radius: 0.5rem; border: 1px solid #4b5563; padding: 0.5rem 0.75rem; 
            width: 100%; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); 
            transition: border-color 0.15s ease-in-out;
            background-color: #374151;
            color: #f3f4f6;
        }
        .input-group textarea::placeholder, .input-group input::placeholder {
            color: #9ca3af;
        }
        .input-group textarea:focus, .input-group input:focus { 
            border-color: #60a5fa; 
            ring-width: 2px; outline: none; 
        }
        .table-responsive { overflow-y: auto; height: 600px; }
        /* Cabeçalho da Tabela: Fundo escuro/cinza, texto claro */
        th { background-color: #4b5563; color: #d1d5db; }
    </style>
</head>
<body class="p-4 sm:p-8">
    <div class="container mx-auto">
        <h1 class="text-3xl font-bold text-indigo-300 mb-6 self-center">{{ title }}</h1>
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

AUTH_PAGE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
{% block content %}
    <p class="text-gray-300 mb-8 self-center">Por favor, insira seu token de Autorização.</p>
    <form method="POST" action="{{ url_for('authenticate') }}" class="bg-gray-700 p-6 rounded-lg shadow-xl max-w-lg mx-auto w-full">
        <div class="mb-4 input-group">
            <input type="text" id="auth_token" name="auth_token" required 
                    class="shadow-sm focus:ring-indigo-400 focus:border-indigo-400 block w-full sm:text-sm border-gray-600 rounded-md p-2 bg-gray-700 text-white"
                    placeholder="Cole seu token puro aqui...">
        </div>
        <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2 px-4 rounded-lg transition duration-150 ease-in-out shadow-md">
            Salvar e Continuar
        </button>
    </form>
{% endblock %}
""")

SEARCH_PAGE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
{% block content %}
    {% if error %}
        <div class="p-4 mb-4 text-sm text-red-300 bg-red-900 rounded-lg" role="alert">
            <span class="font-medium">Erro:</span> {{ error }}
        </div>
    {% endif %}

    <div class="flex flex-col md:flex-row gap-6 mb-8">
        <div class="bg-gray-700 p-6 rounded-lg shadow-xl w-full md:w-1/3">
            <h2 class="text-xl font-semibold mb-4 text-gray-200">1. Buscar Produtos</h2>
            <form method="POST" action="{{ url_for('search_products') }}" class="space-y-4">
                <div class="input-group">
                    <label for="codebar">Codebar (Codebar)</label>
                    <textarea id="codebar" name="codebar" rows="3" class="resize-none" placeholder="1234567890, 0987654321, ... (um por linha ou separados por vírgula)">{{ last_codebar | default('', true) }}</textarea>
                </div>
                <p class="text-sm text-gray-400">Ou, se preferir, use a busca combinada:</p>
                <div class="input-group">
                    <label for="referencia">Referências (Referencia)</label>
                    <textarea id="referencia" name="referencia" rows="3" class="resize-none" placeholder="REF001, REF002, ...">{{ last_referencia | default('', true) }}</textarea>
                </div>
                <div class="input-group">
                    <label for="codigo_produto">Códigos de Produto (CodigoProduto)</label>
                    <textarea id="codigo_produto" name="codigo_produto" rows="3" class="resize-none" placeholder="1289925, 1289926, ...">{{ last_codigo_produto | default('', true) }}</textarea>
                </div>
                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2 px-4 rounded-lg transition duration-150 ease-in-out shadow-md">
                    Pesquisar
                </button>
            </form>
        </div>
        
        <div class="bg-gray-700 p-6 rounded-lg shadow-xl w-full md:w-2/3">
            <h2 class="text-xl font-semibold mb-4 text-gray-200">2. Resultados da Pesquisa ({{ results|length }} Encontrados)</h2>
            <div class="table-responsive">
                {% if results %}
                    <table class="min-w-full divide-y divide-gray-700 rounded-lg">
                        <thead>
                            <tr>
                                <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider rounded-tl-lg">Codebar (Identificador)</th>
                                <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider">Referencia</th>
                                <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider">CodigoProduto</th>
                                <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider rounded-tr-lg">CodigoAuxiliar</th>
                            </tr>
                        </thead>
                        <tbody class="bg-gray-700 divide-y divide-gray-600">
                            {% for item in results %}
                            <tr class="hover:bg-gray-600 transition duration-100">
                                <td class="px-4 py-2 whitespace-nowrap text-sm font-medium text-white">{{ item['Codebar'] | default('N/A', true) }}</td>
                                <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['Referencia'] | default('N/A', true) }}</td>
                                <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['CodigoProduto'] | default('N/A', true) }}</td>
                                <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['CodigoAuxiliar'] | default('N/A', true) }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                {% else %}
                    <p class="text-gray-400 p-4">Nenhum resultado para exibir. Use o formulário à esquerda para pesquisar.</p>
                {% endif %}
            </div>
        </div>
    </div>
    
    <div class="mt-8 text-center">
        <a href="{{ url_for('logout') }}" class="text-sm text-red-400 hover:text-red-500 underline">Remover Token de Autenticação</a>
    </div>
{% endblock %}
""")

@app.route('/', methods=['GET', 'POST'])
def authenticate():
    if request.method == 'POST':
        auth_token = request.form.get('auth_token')
        if auth_token:
            cleaned_token = auth_token.strip()
            session['auth_token'] = cleaned_token
            return redirect(url_for('search_products'))
        else:
            return render_template_string(AUTH_PAGE, title="Autenticação da API de Produtos")

    if 'auth_token' in session:
        return redirect(url_for('search_products'))
        
    return render_template_string(AUTH_PAGE, title="Autenticação da API de Produtos")


@app.route('/logout')
def logout():
    session.pop('auth_token', None)
    return redirect(url_for('authenticate'))


@app.route('/search', methods=['GET', 'POST'])
def search_products():
    auth_token = session.get('auth_token')
    if not auth_token:
        return redirect(url_for('authenticate'))

    results = []
    error = None
    
    last_codebar = ''
    last_referencia = ''
    last_codigo_produto = ''


    if request.method == 'POST':
        last_codebar = request.form.get('codebar', '')
        last_referencia = request.form.get('referencia', '')
        last_codigo_produto = request.form.get('codigo_produto', '')

        codebars = clean_input_list(last_codebar)
        references = clean_input_list(last_referencia)
        product_codes = clean_input_list(last_codigo_produto)
        
        max_len = max(len(codebars), len(references), len(product_codes))

        if max_len > 0:
            for i in range(max_len):
                current_codebar = codebars[i] if i < len(codebars) else None
                current_reference = references[i] if i < len(references) else None
                current_product_code = product_codes[i] if i < len(product_codes) else None

                if not (current_codebar or current_reference or current_product_code):
                    continue
                
                payload = {
                    "CodigoProduto": current_product_code,
                    "NomeProduto": None, 
                    "Referencia": current_reference,
                    "Codebar": current_codebar,
                    "CodigoAuxiliar": None,
                    "CodigoIntegracaoOMS": None
                }
                
                api_response = api_call(auth_token, payload)
                
                if "error" in api_response:
                    error = api_response["error"]
                    break
                
                produtos = api_response.get("Produtos", [])
                
                filtered_products = []
                for produto in produtos:
                    match_codebar = True
                    match_ref = True
                    match_prod_code = True

                    if current_codebar:
                        is_codebar_in_list = any(cb['Codebar'] == current_codebar for cb in produto.get('Codebars', []))
                        if not is_codebar_in_list:
                            match_codebar = False

                    if current_reference and produto.get("Referencia") != current_reference:
                        match_ref = False

                    if current_product_code and str(produto.get("CodigoProduto")) != current_product_code:
                        match_prod_code = False

                    if match_codebar and match_ref and match_prod_code:
                        filtered_products.append(produto)

                for produto in filtered_products:
                    principal_codebar = next((cb['Codebar'] for cb in produto.get('Codebars', []) if cb.get('Principal')), None)
                    display_codebar = principal_codebar or current_codebar or "N/A"

                    results.append({
                        "Codebar": display_codebar,
                        "Referencia": produto.get("Referencia"),
                        "CodigoProduto": produto.get("CodigoProduto"),
                        "CodigoAuxiliar": produto.get("CodigoAuxiliar"),
                    })
        
        unique_results = []
        seen = set()
        for item in results:
            key = (item['Codebar'], item['Referencia'], str(item['CodigoProduto']))
            if key not in seen:
                seen.add(key)
                unique_results.append(item)
        results = unique_results


    # PASSA AS VARIÁVEIS PARA O TEMPLATE
    return render_template_string(
        SEARCH_PAGE,
        title="Consulta de Produtos",
        results=results,
        error=error,
        last_codebar=last_codebar,
        last_referencia=last_referencia,
        last_codigo_produto=last_codigo_produto
    )

if __name__ == '__main__':
    print("--- INICIANDO APLICAÇÃO FLASK ---")
    print(f"Acesse: http://127.0.0.1:5000/")
    app.run(debug=True)
