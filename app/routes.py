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
cancellation_flags = {}

def deduplicate_items_by_ean(items_by_xml: dict) -> dict:
    """
    Deduplicate items by EAN/Codebar, tracking all sources.
    
    Args:
        items_by_xml: dict with format {xml_index: [items]}
    
    Returns:
        dict with:
        - deduplicated_items: list of items grouped by EAN with source tracking
        - ean_sources: dict mapping EAN to list of {xml_index, item} occurrences
    """
    ean_sources = {}
    
    # Group items by Codebar (EAN)
    for xml_index in items_by_xml:
        for item in items_by_xml[xml_index]:
            codebar = item.get('Codebar', '')
            if codebar:
                if codebar not in ean_sources:
                    ean_sources[codebar] = []
                ean_sources[codebar].append({
                    'xml_index': xml_index,
                    'xml_filename': item.get('source_xml_filename', 'Unknown'),
                    'item': item.copy()
                })
    
    # Create deduplicated items with source tracking
    deduplicated_items = []
    for codebar in sorted(ean_sources.keys()):
        sources = ean_sources[codebar]
        # Use the first occurrence as the base item
        base_item = sources[0]['item'].copy()
        base_item['xml_sources'] = sources
        base_item['source_count'] = len(sources)
        deduplicated_items.append(base_item)
    
    return {
        'deduplicated_items': deduplicated_items,
        'ean_sources': ean_sources
    }

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
    final_key = session.pop('final_xml_results_key', None)
    if final_key and final_key in temp_xml_cache:
        del temp_xml_cache[final_key]
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
            # For preview display, flatten all items from all XMLs
            all_items_flat = []
            for xml_index in sorted(cached.get('items_by_xml', {}).keys()):
                all_items_flat.extend(cached['items_by_xml'][xml_index])
            xml_preview_items = all_items_flat
            NumeroNFe = cached.get('nfe_number', '')


    elif current_mode == 'xml_verify' and 'final_xml_results_key' in session:
        final_key = session.get('final_xml_results_key')
        cached = temp_xml_cache.get(final_key)
        if cached and isinstance(cached, dict) and 'all_missing' in cached:
            results = cached.get('all_missing', [])
        elif cached and isinstance(cached, list):
            # Backwards compatibility
            results = cached
        else:
            results = []
        NumeroNFe = session.get('NumeroNFe', '')

    if request.method == 'POST':
        post_mode = request.form.get('mode')
        
        if post_mode == 'manual':
            session.pop('xml_preview_key', None)
            final_key = session.pop('final_xml_results_key', None)
            if final_key and final_key in temp_xml_cache:
                del temp_xml_cache[final_key]
            
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
            final_key = session.pop('final_xml_results_key', None)
            if final_key and final_key in temp_xml_cache:
                del temp_xml_cache[final_key]
            
            xml_files = []
            try:
                candidate = request.files.getlist('xml_files')
                if candidate and hasattr(candidate, '__iter__'):
                    xml_files.extend(candidate)
            except Exception:
                pass

            if not xml_files:
                return redirect(url_for('main.search_products', current_mode='xml', error="Nenhum arquivo XML foi anexado."))
            
            try:
                xml_metadata = []
                items_by_xml = {}
                nfe_numbers = []
                errors = []
                
                for xml_index, xml_file in enumerate(xml_files):
                    if not xml_file or getattr(xml_file, 'filename', '') == '':
                        continue
                    try:
                        xml_filename = xml_file.filename
                        xml_content = xml_file.read().decode('utf-8')
                        xml_items, nfe_number, parse_error = parse_nfe_xml(xml_content, xml_filename=xml_filename, xml_index=xml_index)
                        
                        if parse_error:
                            errors.append(f"{xml_filename}: {parse_error}")
                            continue
                        
                        if not xml_items:
                            errors.append(f"{xml_filename}: Nenhum produto válido foi encontrado.")
                            continue
                        
                        # Store items organized by XML index
                        items_by_xml[xml_index] = xml_items
                        xml_metadata.append({
                            'filename': xml_filename,
                            'index': xml_index,
                            'nfe_number': nfe_number,
                            'item_count': len(xml_items)
                        })
                        if nfe_number:
                            nfe_numbers.append(nfe_number)
                    except Exception as e:
                        errors.append(f"{xml_file.filename}: Erro ao processar - {str(e)}")
                
                if not items_by_xml:
                    error_msg = '; '.join(errors) if errors else 'Nenhum arquivo válido processado.'
                    return redirect(url_for('main.search_products', current_mode='xml', error=error_msg))
                
                xml_preview_key = str(uuid.uuid4())
                nfe_display = ', '.join(nfe_numbers) if nfe_numbers else 'S/N'
                
                # Store structured data with metadata
                temp_xml_cache[xml_preview_key] = {
                    'xml_metadata': xml_metadata,
                    'items_by_xml': items_by_xml,
                    'nfe_number': nfe_display,
                    'errors': errors
                }
                session['xml_preview_key'] = xml_preview_key
                session['NumeroNFe'] = nfe_display
                
                return redirect(url_for('main.search_products', current_mode='xml_preview_render'))
            
            except Exception as e:
                return redirect(url_for('main.search_products', current_mode='xml', error=f"Erro ao processar o(s) arquivo(s): {str(e)}"))

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
    
    if not auth_token:
        return redirect(url_for('main.authenticate'))
    
    if not cached or 'items_by_xml' not in cached:
        return redirect(url_for('main.search_products', current_mode='xml', error="Chave de pré-visualização expirada. Faça o upload novamente."))

    items_by_xml = cached.get('items_by_xml', {})
    xml_metadata = cached.get('xml_metadata', [])
    
    if not items_by_xml:
        return redirect(url_for('main.search_products', current_mode='xml', error="Nenhum item para verificar."))

    # Verify items per XML file while preserving structure
    verified_by_xml = {}
    cancellation_flags.clear()
    
    for xml_index in sorted(items_by_xml.keys()):
        xml_items = items_by_xml[xml_index]
        missing_items, error = verify_xml_items_in_api(auth_token, xml_items, cancellation_flags)
        
        if error:
            return redirect(url_for('main.search_products', current_mode='xml', error=error))
        
        verified_by_xml[xml_index] = missing_items or []

    if cached:
        session['NumeroNFe'] = cached.get('nfe_number', '')
    if xml_preview_key in temp_xml_cache:
        del temp_xml_cache[xml_preview_key]
    session.pop('xml_preview_key', None)
    
    # Check if all items were found
    all_missing = []
    for xml_index in verified_by_xml:
        all_missing.extend(verified_by_xml[xml_index])
    
    final_key = str(uuid.uuid4())
    temp_xml_cache[final_key] = {
        'verified_by_xml': verified_by_xml,
        'xml_metadata': xml_metadata,
        'all_missing': all_missing
    }
    session['final_xml_results_key'] = final_key
    if not all_missing:
        session['success_message'] = "Sucesso: Todos os itens do XML foram encontrados na API!"

    return redirect(url_for('main.search_products', current_mode='xml_verify'))

@routes_bp.route('/search-combined', methods=['GET'])
def search_combined():
    """Get combined deduplicated results from verified XMLs"""
    final_key = session.get('final_xml_results_key')
    if not final_key:
        return jsonify({'error': 'No verification data available'}), 400
    
    cached = temp_xml_cache.get(final_key)
    if not cached:
        return jsonify({'error': 'Verification data expired'}), 400
    
    # Handle both old and new cache structures
    if isinstance(cached, dict) and 'verified_by_xml' in cached:
        verified_by_xml = cached.get('verified_by_xml', {})
        xml_metadata = cached.get('xml_metadata', [])
    else:
        # Backwards compatibility - old flat list format
        return jsonify({'error': 'Invalid cache format'}), 400
    
    # Convert to items_by_xml format for deduplication
    items_by_xml = verified_by_xml
    
    # Deduplicate
    result = deduplicate_items_by_ean(items_by_xml)
    deduplicated = result['deduplicated_items']
    
    return jsonify({
        'deduplicated_items': deduplicated,
        'xml_metadata': xml_metadata,
        'total_unique': len(deduplicated)
    })

@routes_bp.route('/search-tab/<int:xml_index>', methods=['GET'])
def search_tab(xml_index):
    """Get items for a specific XML tab"""
    final_key = session.get('final_xml_results_key')
    if not final_key:
        return jsonify({'error': 'No verification data available'}), 400
    
    cached = temp_xml_cache.get(final_key)
    if not cached:
        return jsonify({'error': 'Verification data expired'}), 400
    
    # Handle both old and new cache structures
    if isinstance(cached, dict) and 'verified_by_xml' in cached:
        verified_by_xml = cached.get('verified_by_xml', {})
        xml_metadata = cached.get('xml_metadata', [])
    else:
        return jsonify({'error': 'Invalid cache format'}), 400
    
    items = verified_by_xml.get(xml_index, [])
    
    # Find corresponding filename
    filename = next((m['filename'] for m in xml_metadata if m['index'] == xml_index), 'Unknown')
    
    return jsonify({
        'items': items,
        'xml_index': xml_index,
        'filename': filename,
        'total_items': len(items)
    })
