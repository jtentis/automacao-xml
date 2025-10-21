import os
from .api_client import api_call

def search_manual_products(auth_token: str, codebars: list, references: list, product_codes: list) -> tuple[list, str | None]:
    results = []
    error = None
    max_len = max(len(codebars), len(references), len(product_codes))

    if max_len > 0:
        for i in range(max_len):
            current_codebar = codebars[i] if i < len(codebars) else None
            current_reference = references[i] if i < len(references) else None
            current_product_code = product_codes[i] if i < len(product_codes) else None

            if not (current_codebar or current_reference or current_product_code):
                continue
            
            payload = {
                "CodigoProduto": current_product_code if current_product_code else "",
                "NomeProduto": "", 
                "Referencia": current_reference if current_reference else "",
                "Codebar": current_codebar if current_codebar else "",
                "CodigoAuxiliar": "",
                "CodigoIntegracaoOMS": ""
            }
            
            api_response = api_call(auth_token, payload)
            
            if "error" in api_response:
                error = api_response["error"]
                break
            
            produtos = api_response.get("Produtos", [])
            
            filtered_products = []
            for produto in produtos:
                is_match = True
                
                if current_codebar and not any(cb['Codebar'] == current_codebar for cb in produto.get('Codebars', [])):
                    is_match = False
                
                if current_reference and produto.get("Referencia") != current_reference:
                    is_match = False

                if current_product_code and str(produto.get("CodigoProduto")) != current_product_code:
                    is_match = False
                
                if is_match:
                    filtered_products.append(produto)

            for produto in filtered_products:
                principal_codebar = next((cb['Codebar'] for cb in produto.get('Codebars', []) if cb.get('Principal')), None)
                display_codebar = principal_codebar or current_codebar or "N/A"

                # print(f"Produto encontrado: {produto.get('NomeProduto')} - Codebar: {display_codebar}, Referencia: {produto.get('Referencia')}, CodigoProduto: {produto.get('CodigoProduto')}")
                
                results.append({
                    "Codebar": display_codebar,
                    "Referencia": produto.get("Referencia"),
                    "CodigoProduto": produto.get("CodigoProduto"),
                    "CodigoAuxiliar": produto.get("CodigoAuxiliar"),
                    "PrecoVenda": produto.get("PrecoVenda")
                })
        
        print(f"Foram encontrados: {len(results)} produtos")
        unique_results = []
        seen = set()
        for item in results:
            key = (item['Codebar'], item['Referencia'], str(item['CodigoProduto']), item['PrecoVenda'])
            if key not in seen:
                seen.add(key)
                unique_results.append(item)
        results = unique_results

    return results, error