import os
import uuid
from flask import request, session, redirect, url_for, render_template, Blueprint
from .api_client import api_call
from .manual_search import search_manual_products
from .xml_parser import parse_nfe_xml
from .xml_verification import verify_xml_items_in_api

routes_bp = Blueprint('main', __name__)

temp_xml_cache = {}
temp_manual_cache = {}

def clean_input_list(data: str) -> list:
    if not data:
        return []
    return [item.strip() for item in data.replace('\n', ',').split(',') if item.strip()]

@routes_bp.route('/', methods=['GET', 'POST'])
def authenticate():
    if request.method == 'POST':
        auth_token = request.form.get('auth_token')
        if auth_token:
            cleaned_token = auth_token.strip()
            session['auth_token'] = cleaned_token
            return redirect(url_for('main.search_products'))
        else:
            return render_template('auth_page.html', title="Autenticação da API de Produtos")

    if 'auth_token' in session:
        return redirect(url_for('main.search_products'))
        
    return render_template('auth_page.html', title="Autenticação da API de Produtos")

@routes_bp.route('/logout')
def logout():
    session.pop('auth_token', None)
    session.pop('xml_preview_key', None)
    session.pop('final_xml_results', None)
    session.pop('last_manual_key', None)
    session.pop('last_form_data', None)
    return redirect(url_for('main.authenticate'))

@routes_bp.route('/search', methods=['GET', 'POST'])
def search_products():
    auth_token = session.get('auth_token')
    if not auth_token:
        return redirect(url_for('main.authenticate'))

    error = None
    success_message = None
    results = []
    xml_preview_items = None
    
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
        xml_preview_items = temp_xml_cache.get(xml_preview_key)
        
        if xml_preview_items is None:
             error="Sessão de pré-visualização expirada. Faça o upload novamente."
             current_mode = 'xml'

    elif current_mode == 'xml_verify' and 'final_xml_results' in session:
        results = session.get('final_xml_results', [])

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
                results, error = search_manual_products(auth_token, codebars, references, product_codes)
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
                xml_items, parse_error = parse_nfe_xml(xml_content)
                
                if parse_error:
                    return redirect(url_for('main.search_products', current_mode='xml', error=parse_error))
                
                if not xml_items:
                    return redirect(url_for('main.search_products', current_mode='xml', error="Nenhum produto válido foi encontrado no XML."))
                
                xml_preview_key = str(uuid.uuid4())
                temp_xml_cache[xml_preview_key] = xml_items
                session['xml_preview_key'] = xml_preview_key
                
                return redirect(url_for('main.search_products', current_mode='xml_preview_render'))
            
            except Exception as e:
                return redirect(url_for('main.search_products', current_mode='xml', error=f"Erro ao processar o arquivo: {str(e)}"))

    # Renderiza o template
    return render_template(
        'search_page.html',
        title="Consulta de Produtos (NFe & Manual)",
        results=results,
        error=error,
        success_message=success_message,
        current_mode=current_mode, 
        xml_preview_items=xml_preview_items,
        last_codebar=last_codebar,
        last_referencia=last_referencia,
        last_codigo_produto=last_codigo_produto,
    )

@routes_bp.route('/verify-xml', methods=['GET', 'POST'])
def verify_xml_items():
    auth_token = session.get('auth_token')
    xml_preview_key = session.get('xml_preview_key')
    xml_items = temp_xml_cache.get(xml_preview_key)
    
    if not auth_token:
        return redirect(url_for('main.authenticate'))
        
    if not xml_items:
        return redirect(url_for('main.search_products', current_mode='xml', error="Chave de pré-visualização expirada. Faça o upload novamente."))

    missing_items, error = verify_xml_items_in_api(auth_token, xml_items)

    if xml_preview_key in temp_xml_cache:
        del temp_xml_cache[xml_preview_key]
    session.pop('xml_preview_key', None) 
    
    if error:
        return redirect(url_for('main.search_products', current_mode='xml', error=error))

    if not missing_items:
        session['final_xml_results'] = []
        session['success_message'] = "SUCESSO: Todos os itens do XML foram encontrados na API!"
    else:
        session['final_xml_results'] = missing_items

    return redirect(url_for('main.search_products', current_mode='xml_verify'))
