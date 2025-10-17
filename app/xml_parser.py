import xml.etree.ElementTree as ET
import re

NFE_NS = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

def find_robust(elem, tag_name):
    elem_with_ns = elem.find(f'nfe:{tag_name}', NFE_NS)
    if elem_with_ns is not None:
        return elem_with_ns
    return elem.find(tag_name)

def parse_nfe_xml(xml_content: str) -> tuple[list, str | None]:
    xml_items = []
    error = None
    
    try:
        xml_content = re.sub(r'xmlns="[^"]+"', '', xml_content, count=1)
        root = ET.fromstring(xml_content)
        
        nfe_root = root.find('NFe') or root.find('infNFe') or root 
        
        dets = nfe_root.findall('.//det') 
        
        if not dets:
            error = "Nenhum item de produto (<det>) encontrado no XML."
            return [], error
            
        for det in dets:
            prod = find_robust(det, 'prod')
            
            if prod is None:
                continue
                
            codebar_ean_elem = find_robust(prod, 'cEAN')
            code_aux_elem = find_robust(prod, 'cProd')
            xprod_elem = find_robust(prod, 'xProd')
            
            n_item = det.get('nItem')
            
            codebar_ean = codebar_ean_elem.text.strip() if codebar_ean_elem is not None else ''
            code_aux = code_aux_elem.text.strip() if code_aux_elem is not None else ''
            xprod = xprod_elem.text.strip() if xprod_elem is not None else ''
            
            # Referência: Apenas os primeiros dígitos antes do '-' em xProd
            reference_match = re.match(r'^([\d\w]+)', xprod)
            reference = reference_match.group(1) if reference_match is not None else ''
            
            nameProduto = xprod.split(' ', 1) 
            
            if len(nameProduto) > 1:
                nameProduto_trim = nameProduto[1]
            else:
                nameProduto_trim = ""
            
            if codebar_ean:
                xml_items.append({
                    "nItem": n_item,
                    "Codebar": codebar_ean,
                    "NomeProduto": nameProduto_trim,
                    "Referencia": reference,
                    "CodigoProduto": codebar_ean,
                    "CodigoAuxiliar": code_aux,
                })

    except ET.ParseError as e:
        error = f"Erro de parsing XML: A estrutura do arquivo está inválida. ({e})"
    except Exception as e:
        error = f"Erro inesperado no parser XML: {str(e)}"
        
    return xml_items, error