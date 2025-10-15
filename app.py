import os
import requests
import json
from flask import Flask, request, session, redirect, url_for, render_template_string
from dotenv import load_dotenv
import xml.etree.ElementTree as ET

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24) 

API_URL = os.getenv('API_ENDPOINT_URL')
NFE_NS = {'nfe': 'http://www.portalfiscal.inf.br/nfe'} 

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

def parse_nfe_xml(xml_content: str) -> tuple[list, str | None]:
    items = []
    NFE_URI_FULL = '{' + NFE_NS['nfe'] + '}' 
    
    try:
        root = ET.fromstring(xml_content)
        
        det_elements = root.findall('.//nfe:det', NFE_NS)
        
        if not det_elements:
            det_elements = root.findall(f'.//{NFE_URI_FULL}det')
            
        if not det_elements:
            det_elements = root.findall('.//det')
            
        if not det_elements:
            return [], "Nenhuma tag <det> (Detalhe do Item) encontrada no XML. Verifique a estrutura NFe."

        def find_robust(parent, tag_name):
            elem = parent.find(f'nfe:{tag_name}', NFE_NS)
            if elem is None:
                elem = parent.find(f'{NFE_URI_FULL}{tag_name}')
            if elem is None:
                elem = parent.find(tag_name)
            return elem

        for det in det_elements:
            prod = find_robust(det, 'prod')
            
            if prod is None:
                continue

            codebar_ean_elem = find_robust(prod, 'cEAN')
            code_aux_elem = find_robust(prod, 'cProd')
            xprod_elem = find_robust(prod, 'xProd')
            
            c_ean = codebar_ean_elem.text if codebar_ean_elem is not None else ""
            c_prod = code_aux_elem.text if code_aux_elem is not None else ""
            
            referencia = (xprod_elem.text.split('-')[0].strip()
                          if xprod_elem is not None and xprod_elem.text
                          else "")
            
            items.append({
                "nItem": det.get('nItem', 'S/N'),
                "Codebar": c_ean,
                "Referencia": referencia,
                "CodigoProduto": c_ean,
                "CodigoAuxiliar": c_prod
            })
        
        return items, None
    except ET.ParseError:
        return [], "Erro ao processar o XML. Verifique se o formato está correto."
    except Exception as e:
        return [], f"Erro inesperado no parser do XML: {str(e)}"

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
        body { font-family: 'Inter', sans-serif; background-color: #1a1a1a; } 
        .container { max-width: 1024px; }
        .input-group label { margin-bottom: 0.5rem; display: block; font-weight: 500; color: #d1d5db; }
        .input-group textarea, .input-group input:not([type="file"]), .input-group input[type="file"] { 
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
        .table-responsive { overflow-y: auto; max-height: 600px; }
        th { background-color: #4b5563; color: #d1d5db; }
        .tab-button.active { background-color: #4b5563; color: #fff; }

        input[type="file"] {
            border: 1px solid #4b5563;
            padding: 0.5rem;
            cursor: pointer;
        }
        input[type="file"]::-webkit-file-upload-button {
            visibility: hidden;
        }
        input[type="file"]::before {
            content: 'Selecionar arquivo XML';
            display: inline-block;
            background: #6366f1;
            color: white;
            border-radius: 4px;
            padding: 6px 10px;
            outline: none;
            white-space: nowrap;
            -webkit-user-select: none;
            cursor: pointer;
            font-weight: 500;
            font-size: 0.875rem;
            margin-right: 10px;
        }
        
        .loading-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(26, 26, 26, 0.8);
            backdrop-filter: blur(4px);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            color: white;
        }
        .spinner {
            border: 8px solid #374151;
            border-top: 8px solid #6366f1;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            animation: spin 1s linear infinite;
            margin-bottom: 1rem;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body class="p-4 sm:p-8">
    <div class="container mx-auto">
        <h1 class="text-3xl font-bold text-indigo-300 mb-6 self-center">{{ title }}</h1>
        {% block content %}{% endblock %}
    </div>
    <div id="loading-container" class="hidden">
        <div class="loading-overlay">
            <div class="spinner"></div>
            <p id="loading-message" class="text-lg font-semibold">Verificando itens na API...</p>
            <p class="text-sm text-gray-300">Isso pode levar alguns segundos por item do XML.</p>
        </div>
    </div>
    <script>
        function showTab(mode) {
            document.getElementById('manual-form').classList.add('hidden');
            document.getElementById('xml-form').classList.add('hidden');
            document.getElementById('btn-manual').classList.remove('active');
            document.getElementById('btn-xml').classList.remove('active');
            
            document.getElementById(mode + '-form').classList.remove('hidden');
            document.getElementById('btn-' + mode).classList.add('active');
        }
        
        document.addEventListener('DOMContentLoaded', () => {
            const currentMode = "{{ current_mode or 'manual' }}";
            showTab(currentMode.startsWith('xml') ? 'xml' : currentMode.startsWith('xml_verify') ? 'xml' : currentMode);
            
            const loadingContainer = document.getElementById('loading-container');
            const loadingMessage = document.getElementById('loading-message');
            
            const manualForm = document.getElementById('manual-form');
            if (manualForm) {
                manualForm.addEventListener('submit', () => {
                    loadingMessage.textContent = 'Pesquisando produtos manualmente...';
                    loadingContainer.classList.remove('hidden');
                });
            }

            const verifyForm = document.getElementById('verify-form');
            if (verifyForm) {
                verifyForm.addEventListener('submit', () => {
                    loadingMessage.textContent = 'Verificando itens na API...';
                    loadingContainer.classList.remove('hidden');
                });
            }
            const xmlForm = document.getElementById('xml-form');
            if (xmlForm) {
                xmlForm.addEventListener('submit', () => {
                    loadingMessage.textContent = 'Processando arquivo XML...';
                    loadingContainer.classList.remove('hidden');
                });
            }
        });
    </script>
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
        <div class="bg-gray-800 p-6 rounded-lg shadow-xl w-full md:w-1/3">
            <h2 class="text-xl font-semibold mb-4 text-gray-200">1. Opções de Busca</h2>
            
            <div class="flex mb-4 border-b border-gray-700">
                <button id="btn-manual" onclick="showTab('manual')" class="tab-button px-4 py-2 text-sm font-medium rounded-t-lg text-gray-400 hover:text-white transition duration-150">Busca Manual</button>
                <button id="btn-xml" onclick="showTab('xml')" class="tab-button px-4 py-2 text-sm font-medium rounded-t-lg text-gray-400 hover:text-white transition duration-150">Buscar por XML (NFe)</button>
            </div>

            <form id="manual-form" method="POST" action="{{ url_for('search_products') }}" class="space-y-4 hidden">
                <input type="hidden" name="mode" value="manual">
                <div class="input-group">
                    <label for="codebar">Codebar (Codebar)</label>
                    <textarea id="codebar" name="codebar" rows="3" class="resize-none" placeholder="1234567890, 0987654321, ...">{{ last_codebar | default('', true) }}</textarea>
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
                    Pesquisar Manualmente
                </button>
            </form>

            <form id="xml-form" method="POST" action="{{ url_for('search_products') }}" class="space-y-4 hidden" enctype="multipart/form-data">
                <input type="hidden" name="mode" value="xml_preview">
                <div class="input-group">
                    <label for="xml_file">Anexar Arquivo XML (NFe)</label>
                    <input type="file" id="xml_file" name="xml_file" accept=".xml" required>
                </div>
                <button type="submit" class="w-full bg-green-600 hover:bg-green-500 text-white font-semibold py-2 px-4 rounded-lg transition duration-150 ease-in-out shadow-md">
                    1. Pré-visualizar Itens do XML
                </button>
            </form>
        </div>
        
        <div class="bg-gray-800 p-6 rounded-lg shadow-xl w-full md:w-2/3">
            <h2 class="text-xl font-semibold mb-4 text-gray-200">2. Resultados / Pré-visualização</h2>
            <div id="results-content">
                
                {% if xml_preview_items %}
                    <p class="text-sm text-gray-400 mb-4">
                        <span class="text-yellow-400 font-bold">Pré-visualização XML:</span> {{ xml_preview_items|length }} itens extraídos do arquivo.
                    </p>
                    
                    <div class="table-responsive mb-6">
                        <table class="min-w-full divide-y divide-gray-700 rounded-lg">
                            <thead>
                                <tr>
                                    <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider rounded-tl-lg">Item NFe</th>
                                    <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider">cEAN (Codebar/Cód.Produto)</th>
                                    <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider">xProd (Referência)</th>
                                    <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider rounded-tr-lg">cProd (Cód. Auxiliar)</th>
                                </tr>
                            </thead>
                            <tbody class="bg-gray-700 divide-y divide-gray-600">
                                {% for item in xml_preview_items %}
                                <tr class="hover:bg-gray-600 transition duration-100">
                                    <td class="px-4 py-2 whitespace-nowrap text-sm font-bold text-white">{{ item['nItem'] | default('S/N', true) }}</td>
                                    <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['Codebar'] | default('', true) }}</td>
                                    <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['Referencia'] | default('', true) }}</td>
                                    <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['CodigoAuxiliar'] | default('', true) }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                    
                    <form id="verify-form" method="POST" action="{{ url_for('verify_xml_items') }}" class="mt-4">
                        <input type="hidden" name="mode" value="xml_verify">
                        <button type="submit" class="w-full bg-red-600 hover:bg-red-500 text-white font-semibold py-3 px-4 rounded-lg transition duration-150 ease-in-out shadow-md">
                            2. Verificar Itens Faltantes na API ({{ xml_preview_items|length }} itens)
                        </button>
                    </form>
                    
                {% elif results %}
                    <p class="text-sm text-gray-400 mb-4">
                        {% if current_mode == 'xml_verify' %}
                            <span class="text-red-400 font-bold">Modo XML:</span> Exibindo apenas itens do XML <strong>não encontrados</strong> na API.
                            <span class="text-sm text-gray-400">Total Faltante: {{ results|length }}</span>
                        {% else %}
                            <span class="text-indigo-400 font-bold">Modo Manual:</span> Exibindo itens encontrados.
                        {% endif %}
                    </p>
                    <div class="table-responsive">
                        <table class="min-w-full divide-y divide-gray-700 rounded-lg">
                            <thead>
                                <tr>
                                    {% if current_mode == 'xml_verify' %}
                                        <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider rounded-tl-lg">Item NFe</th>
                                        <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider">cEAN (Codebar/Cód.Produto)</th>
                                        <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider">xProd (Referência)</th>
                                        <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider rounded-tr-lg">cProd (Cód. Auxiliar)</th>
                                    {% else %}
                                        <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider rounded-tl-lg">Codebar (Identificador)</th>
                                        <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider">Referencia</th>
                                        <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider">CodigoProduto</th>
                                        <th class="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider rounded-tr-lg">CodigoAuxiliar</th>
                                    {% endif %}
                                </tr>
                            </thead>
                            <tbody class="bg-gray-700 divide-y divide-gray-600">
                                {% for item in results %}
                                <tr class="hover:bg-gray-600 transition duration-100 {% if current_mode == 'xml_verify' %}bg-red-900 bg-opacity-30{% endif %}">
                                    {% if current_mode == 'xml_verify' %}
                                        <td class="px-4 py-2 whitespace-nowrap text-sm font-bold text-white">{{ item['nItem'] | default('S/N', true) }}</td>
                                        <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['Codebar'] | default('N/A', true) }}</td>
                                        <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['Referencia'] | default('N/A', true) }}</td>
                                        <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['CodigoAuxiliar'] | default('N/A', true) }}</td>
                                    {% else %}
                                        <td class="px-4 py-2 whitespace-nowrap text-sm font-medium text-white">{{ item['Codebar'] | default('N/A', true) }}</td>
                                        <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['Referencia'] | default('N/A', true) }}</td>
                                        <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['CodigoProduto'] | default('N/A', true) }}</td>
                                        <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-300">{{ item['CodigoAuxiliar'] | default('N/A', true) }}</td>
                                    {% endif %}
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
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
    current_mode = 'manual'
    xml_preview_items = None
    
    last_codebar = ''
    last_referencia = ''
    last_codigo_produto = ''


    if request.method == 'POST':
        current_mode = request.form.get('mode', 'manual')
        
        if current_mode == 'manual':
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

        elif current_mode == 'xml_preview':
            xml_file = request.files.get('xml_file')
            
            if not xml_file or xml_file.filename == '':
                error = "Nenhum arquivo XML foi anexado."
            elif not xml_file.filename.lower().endswith('.xml'):
                error = "O arquivo anexado deve ser do tipo .xml"
            else:
                try:
                    xml_content = xml_file.read().decode('utf-8')
                    xml_items, parse_error = parse_nfe_xml(xml_content)
                    
                    if parse_error:
                        error = parse_error
                    elif not xml_items:
                        error = "Nenhum produto válido foi encontrado no XML."
                    else:
                        session['xml_items_to_check'] = xml_items
                        
                        return redirect(url_for('search_products', current_mode='xml_preview_render'))
                        

                except Exception as e:
                    error = f"Erro ao processar o arquivo: {str(e)}"
                    
    if request.args.get('current_mode'):
        current_mode = request.args.get('current_mode')

    if current_mode != 'xml_verify' and 'xml_items_to_check' in session:
        xml_preview_items = session.get('xml_items_to_check')
        current_mode = 'xml_preview_render' 

    if request.args.get('error'):
        error = request.args.get('error')
    
    if current_mode == 'xml_verify' and 'final_xml_results' in session:
        results = session.pop('final_xml_results')
        session.pop('xml_items_to_check', None) 
        
    return render_template_string(
        SEARCH_PAGE,
        title="Consulta de Produtos",
        results=results,
        error=error,
        current_mode=current_mode, 
        xml_preview_items=xml_preview_items,
        last_codebar=last_codebar,
        last_referencia=last_referencia,
        last_codigo_produto=last_codigo_produto,
    )


@app.route('/verify-xml', methods=['POST'])
def verify_xml_items():
    auth_token = session.get('auth_token')
    xml_items = session.get('xml_items_to_check')
    
    if not auth_token:
        return redirect(url_for('authenticate'))
        
    if not xml_items:
        return redirect(url_for('search_products', current_mode='xml', error="Nenhum item do XML encontrado na sessão para verificação. Por favor, refaça o upload."))
        
    error = None
    results = []
    all_found_items = set()
    
    print(f"LOG VERIFY: Iniciando verificação de {len(xml_items)} itens XML na API...")
    
    for item in xml_items:
        payload = {
            "CodigoProduto": item['CodigoProduto'], 
            "NomeProduto": None, 
            "Referencia": item['Referencia'], 
            "Codebar": item['Codebar'],
            "CodigoAuxiliar": item['CodigoAuxiliar'],
            "CodigoIntegracaoOMS": None
        }

        api_response = api_call(auth_token, payload)
        
        if "error" in api_response:
            error = api_response["error"]
            break
        
        produtos_encontrados = api_response.get("Produtos", [])
        
        item_key = (item['Codebar'], item['Referencia'], item['CodigoProduto'], item['CodigoAuxiliar'])
        
        found = False
        for produto in produtos_encontrados:
            principal_codebar = next((cb['Codebar'] for cb in produto.get('Codebars', []) if cb.get('Principal')), None)
            
            api_codebar = principal_codebar or produto.get('Codebar')
            api_ref = produto.get('Referencia')
            api_cod_prod = str(produto.get('CodigoProduto'))
            api_cod_aux = produto.get('CodigoAuxiliar')
            
            api_key = (api_codebar, api_ref, api_cod_prod, api_cod_aux)
            
            if item_key == api_key:
                found = True
                break
        
        if found:
            all_found_items.add(item_key)

    if not error:
        
        for item in xml_items:
            item_key = (item['Codebar'], item['Referencia'], item['CodigoProduto'], item['CodigoAuxiliar'])
            
            if item_key not in all_found_items:
                results.append(item)
        
        session['final_xml_results'] = results
        
        print(f"LOG VERIFY: {len(all_found_items)} itens encontrados na API. {len(results)} itens faltantes.")
        
        return redirect(url_for('search_products', current_mode='xml_verify', error=error))

    return redirect(url_for('search_products', current_mode='xml', error=error))


if __name__ == '__main__':
    if not API_URL:
        print("AVISO: A variável de ambiente 'API_ENDPOINT_URL' não foi definida no .env ou está vazia.")
    app.run(debug=True)
