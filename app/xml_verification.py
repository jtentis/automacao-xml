import os
from .api_client import api_call

def verify_xml_items_in_api(auth_token: str, xml_items: list) -> tuple[list, str | None]:
    missing_items = []
    error = None

    total_items = len(xml_items)
    
    print(f"--- Começando a verificação de {total_items} itens ---\n")

    for index, item in enumerate(xml_items, start=1):
        current_codebar = item.get("Codebar")
        current_reference = item.get("Referencia")
        current_product_code = item.get("CodigoProduto")
        
        item_details = f"Code: {current_product_code or 'N/A'}, Ref: {current_reference or 'N/A'}, Codebar: {current_codebar or 'N/A'}"
        
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
            print(f"[{index}/{total_items}] ERROR: API call failed for item: {item_details}. Error: {api_response['error']}")
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
            print(f"[{index}/{total_items}] NÃO ENCONTRADO ❌: {item_details}")
        else:
            print(f"[{index}/{total_items}] ENCONTRADO ✅: {item_details}")


    print(f"\n--- Verificação da API completa. {len(missing_items)} itens não encontrados! ---")
    return missing_items, error