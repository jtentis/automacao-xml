import os
import uuid
from flask import request, session, redirect, url_for, render_template, Blueprint, flash, jsonify
from .api_client import api_call, api_login, get_final_auth_token
from .manual_search import search_manual_products
from .xml_parser import parse_nfe_xml
from .xml_verification import verify_xml_items_in_api

routes_bp = Blueprint('main', __name__)

temp_xml_cache = {}
temp_manual_cache = {}
cancellation_flags = {}  # Use a simple dict to track cancellation per session

def clean_input_list(data: str) -> list:
    if not data:
        return []
    return [item.strip() for item in data.replace('\n', ',').split(',') if item.strip()]

@routes_bp.route('/', methods=['GET'])
def authenticate():
    if 'auth_token' in session:
        return redirect(url_for('main.search_products'))
    return render_template('auth_page.html', title="Autenticação da API de Produtos")

@routes_bp.route('/get-temp-token', methods=['POST'])
def get_temp_token():
    data = request.get_json()
    login = data.get('login')
    senha = data.get('senha')

    if not login or not senha:
        return jsonify({'error': 'Login e Senha são obrigatórios.'}), 400

    login_response = api_login(login, senha)

    if 'error' in login_response:
        return jsonify({'error': login_response['error']}), 500

    temp_token = login_response.get('TokenTemporario')
    if not temp_token:
        return jsonify({'error': 'Token temporário não encontrado na resposta de login.'}), 500
    
    return jsonify({'temp_token': temp_token})

@routes_bp.route('/get-final-token', methods=['POST'])
def get_final_token():
    data = request.get_json()
    temp_token = data.get('temp_token')

    if not temp_token:
        return jsonify({'error': 'Token temporário não fornecido.'}), 400

    auth_response = get_final_auth_token(temp_token)

    if 'error' in auth_response:
        return jsonify({'error': auth_response['error']}), 500

    auth_token = auth_response.get('auth_token')
    if auth_token:
        session['auth_token'] = auth_token
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Token de autorização final não encontrado na resposta.'}), 500

@routes_bp.route('/logout')
def logout():
    session.pop('auth_token', None)
    session.pop('xml_preview_key', None)
    session.pop('final_xml_results', None)
    session.pop('last_manual_key', None)
    session.pop('last_form_data', None)
    session.pop('NumeroNFe', None)
    return redirect(url_for('main.authenticate'))

@routes_bp.route('/cancel', methods=['POST'])
def cancel_operation():
    # cancelamento global
    cancellation_flags['_global_cancel'] = True
    print("[CANCEL] User clicked cancel button")
    return {'status': 'cancelled'}, 200

@routes_bp.route('/search', methods=['GET', 'POST'])
def search_products():
    auth_token = session.get('auth_token')
    if not auth_token:
        return redirect(url_for('main.authenticate'))

    error = None
    success_message = None
    results = []
    xml_preview_items = None
    NumeroNFe = ''
    
    form_data = session.get('last_form_data', {})
    last_codebar = form_data.get('codebar', '')
    last_referencia = form_data.get('referencia', '')
    last_codigo_produto = form_data.get('codigo_produto', '')
    
    current_mode = request.args.get('current_mode', 'manual')
    
    if request.args.get('error'):
        error = request.args.get('error')
    
    if 'success_message' in session:
        success_message = session.pop('success_message')

    if current_mode == 'manual':
        last_manual_key = session.get('last_manual_key')
        results = temp_manual_cache.get(last_manual_key, [])
        form_data = session.get('last_form_data', {})
        last_codebar = form_data.get('codebar', '')
        last_referencia = form_data.get('referencia', '')
        last_codigo_produto = form_data.get('codigo_produto', '')

    elif current_mode == 'xml_preview_render' and 'xml_preview_key' in session:
        xml_preview_key = session.get('xml_preview_key')
        cached = temp_xml_cache.get(xml_preview_key)
        
        if cached is None:
             error = "Sessão de pré-visualização expirada. Faça o upload novamente."
             current_mode = 'xml'
        else:
            xml_preview_items = cached.get('items', [])
            NumeroNFe = cached.get('nfe_number', '')

    elif current_mode == 'xml_verify' and 'final_xml_results' in session:
        results = session.get('final_xml_results', [])
        NumeroNFe = session.get('NumeroNFe', '')

    if request.method == 'POST':
        post_mode = request.form.get('mode')
        
        if post_mode == 'manual':
            session.pop('xml_preview_key', None)
            session.pop('final_xml_results', None)
            
            last_codebar = request.form.get('codebar', '')
            last_referencia = request.form.get('referencia', '')
            last_codigo_produto = request.form.get('codigo_produto', '')

            codebars = clean_input_list(last_codebar)
            references = clean_input_list(last_referencia)
            product_codes = clean_input_list(last_codigo_produto)
            
            session['last_form_data'] = {
                'codebar': last_codebar,
                'referencia': last_referencia,
                'codigo_produto': last_codigo_produto
            }

            if codebars or references or product_codes:
                cancellation_flags.clear()
                results, error = search_manual_products(auth_token, codebars, references, product_codes, cancellation_flags)
                if not error:
                    manual_key = str(uuid.uuid4())
                    temp_manual_cache[manual_key] = results
                    session['last_manual_key'] = manual_key
                
            return redirect(url_for('main.search_products', current_mode='manual', error=error))

        elif post_mode == 'xml_preview':
            session.pop('last_manual_key', None)
            session.pop('last_form_data', None)
            session.pop('final_xml_results', None)
            
            xml_file = request.files.get('xml_file')
            
            if not xml_file or xml_file.filename == '':
                return redirect(url_for('main.search_products', current_mode='xml', error="Nenhum arquivo XML foi anexado."))
            
            try:
                xml_content = xml_file.read().decode('utf-8')
                xml_items, nfe_number, parse_error = parse_nfe_xml(xml_content)
                
                if parse_error:
                    return redirect(url_for('main.search_products', current_mode='xml', error=parse_error))
                
                if not xml_items:
                    return redirect(url_for('main.search_products', current_mode='xml', error="Nenhum produto válido foi encontrado no XML."))
                
                xml_preview_key = str(uuid.uuid4())
                temp_xml_cache[xml_preview_key] = {'items': xml_items, 'nfe_number': nfe_number}
                session['xml_preview_key'] = xml_preview_key
                
                session['NumeroNFe'] = nfe_number
                
                return redirect(url_for('main.search_products', current_mode='xml_preview_render'))
            
            except Exception as e:
                return redirect(url_for('main.search_products', current_mode='xml', error=f"Erro ao processar o arquivo: {str(e)}"))

    return render_template(
        'search_page.html',
        title="Consulta de Produtos (NFe & Manual)",
        results=results,
        error=error,
        success_message=success_message,
        current_mode=current_mode, 
        xml_preview_items=xml_preview_items,
        NumeroNFe=locals().get('NumeroNFe', ''),
        last_codebar=last_codebar,
        last_referencia=last_referencia,
        last_codigo_produto=last_codigo_produto,
    )

@routes_bp.route('/verify-xml', methods=['GET', 'POST'])
def verify_xml_items():
    auth_token = session.get('auth_token')
    xml_preview_key = session.get('xml_preview_key')
    cached = temp_xml_cache.get(xml_preview_key)
    xml_items = cached.get('items') if cached else None
    
    if not auth_token:
        return redirect(url_for('main.authenticate'))
        
    if not xml_items:
        return redirect(url_for('main.search_products', current_mode='xml', error="Chave de pré-visualização expirada. Faça o upload novamente."))

    cancellation_flags.clear()
    missing_items, error = verify_xml_items_in_api(auth_token, xml_items, cancellation_flags)

    if cached:
        session['NumeroNFe'] = cached.get('nfe_number', '')
    if xml_preview_key in temp_xml_cache:
        del temp_xml_cache[xml_preview_key]
    session.pop('xml_preview_key', None)
    
    if error:
        return redirect(url_for('main.search_products', current_mode='xml', error=error))

    if not missing_items:
        session['final_xml_results'] = []
        session['success_message'] = "Sucesso: Todos os itens do XML foram encontrados na API!"
    else:
        session['final_xml_results'] = missing_items

    return redirect(url_for('main.search_products', current_mode='xml_verify'))
