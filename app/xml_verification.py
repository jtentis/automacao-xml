import os
import re
from .api_client import api_call
from .manual_search import search_manual_products

def verify_xml_items_in_api(auth_token: str, xml_items: list) -> tuple[list, str | None]:
    missing_items = []
    error = None

    total_items = len(xml_items)
    
    print(f"--- Verificando {total_items} itens ---")

    for index, item in enumerate(xml_items, start=1):
        current_codebar = item.get("Codebar")
        current_reference = item.get("Referencia")
        current_product_code = item.get("CodigoProduto")
        current_codigo_auxiliar = item.get("CodigoAuxiliar")
        
        payload = {
            "CodigoProduto": "",
            "NomeProduto": "",
            "Referencia": current_codigo_auxiliar if current_codigo_auxiliar else "",
            "Codebar": current_codebar if current_codebar else "",
            "CodigoAuxiliar": "",
            "CodigoIntegracaoOMS": ""
        }
        api_response = api_call(auth_token, payload)
        if "error" in api_response:
            print(f"[{index}/{total_items}] API ERROR: {api_response['error']}")
            return missing_items, api_response["error"]
        produtos = api_response.get("Produtos", [])
        is_found = False
        for produto in produtos:
            api_codebars = produto.get('Codebars', [])
            try:
                api_codebar_values = [cb['Codebar'] for cb in api_codebars]
            except Exception:
                api_codebar_values = [str(cb) for cb in api_codebars]
            if current_codebar and len(api_codebars) == 1:
                if any(cb.get('Codebar') == current_codebar for cb in api_codebars):
                    is_found = True
                    print(f"[{index}/{total_items}] ENCONTRADO ✅: {current_codebar}")
                    break
            elif current_codebar and len(api_codebars) > 1:
                item_copy = item.copy()
                item_copy['ApiCodebars'] = ', '.join(api_codebar_values)
                missing_items.append(item_copy)
                print(f"[{index}/{total_items}] MULTIPLOS CODEBARS ⚠️: {current_codebar} → {api_codebar_values}")
                is_found = True
                break
        if not is_found:
            missing_items.append(item)
            print(f"[{index}/{total_items}] NAO ENCONTRADO ❌: {current_codebar}")
    print(f"--- Fim. {len(missing_items)} itens não encontrados ou inválidos. ---")
    return missing_items, error