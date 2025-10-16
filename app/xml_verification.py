import os
from .api_client import api_call

def verify_xml_items_in_api(auth_token: str, xml_items: list) -> tuple[list, str | None]:
    missing_items = []
    error = None

    for item in xml_items:
        current_codebar = item.get("Codebar")
        current_reference = item.get("Referencia")
        current_product_code = item.get("CodigoProduto")
        
        payload = {
            "CodigoProduto": current_product_code if current_product_code else "",
            "NomeProduto": "", 
            "Referencia": current_reference if current_reference else "",
            "Codebar": current_codebar if current_codebar else "",
            "CodigoAuxiliar": item.get("CodigoAuxiliar", ""),
            "CodigoIntegracaoOMS": ""
        }
        
        api_response = api_call(auth_token, payload)
        
        if "error" in api_response:
            return missing_items, api_response["error"]
        
        produtos = api_response.get("Produtos", [])
        
        is_found = False
        for produto in produtos:
            match_codebar = True
            match_ref = True
            match_prod_code = True

            product_codebars = [cb['Codebar'] for cb in produto.get('Codebars', [])]
            if current_codebar and current_codebar not in product_codebars:
                match_codebar = False

            if current_reference and produto.get("Referencia") != current_reference:
                match_ref = False

            if current_product_code and str(produto.get("CodigoProduto")) != current_product_code:
                match_prod_code = False

            if match_codebar and match_ref and match_prod_code:
                is_found = True
                break
                
        if not is_found:
            missing_items.append(item)

    return missing_items, error