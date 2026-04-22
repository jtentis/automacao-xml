from .api_client import api_call


def build_verification_key(item: dict) -> str:
    codebar = (item.get("Codebar") or "").strip()
    if codebar:
        return f"codebar:{codebar}"

    reference = (item.get("ReferenciaPosDash") or item.get("Referencia") or "").strip()
    codigo_auxiliar = str(item.get("CodigoAuxiliar") or "").strip()
    codigo_produto = str(item.get("CodigoProduto") or "").strip()
    return f"fallback:{reference}|{codigo_auxiliar}|{codigo_produto}"


def verify_xml_items_in_api(auth_token: str, xml_items: list, cancellation_flags=None) -> tuple[list, str | None]:
    items_by_xml = {0: xml_items or []}
    verified_by_xml, _, error = verify_grouped_xml_items_in_api(
        auth_token,
        items_by_xml,
        cancellation_flags
    )
    return verified_by_xml.get(0, []), error


def verify_grouped_xml_items_in_api(auth_token: str, items_by_xml: dict, cancellation_flags=None, xml_metadata=None) -> tuple[dict, dict, str | None]:
    verified_by_xml = {xml_index: [] for xml_index in items_by_xml.keys()}
    occurrences_by_key = {}
    metadata_by_index = {
        item.get("index"): item
        for item in (xml_metadata or [])
        if item.get("index") is not None
    }

    for xml_index, xml_items in items_by_xml.items():
        for item in xml_items:
            verification_key = build_verification_key(item)
            occurrences_by_key.setdefault(verification_key, []).append({
                "xml_index": xml_index,
                "item": item,
            })

    unique_occurrences = list(occurrences_by_key.items())
    total_unique = len(unique_occurrences)

    stats = {
        "total_items": sum(len(items) for items in items_by_xml.values()),
        "unique_items": total_unique,
        "skipped_duplicates": 0,
        "xml_breakdown": [],
    }
    stats["skipped_duplicates"] = stats["total_items"] - stats["unique_items"]

    print("--- Resumo da verificacao de XMLs ---")
    for xml_index in sorted(items_by_xml.keys()):
        xml_items = items_by_xml.get(xml_index, [])
        unique_keys_in_xml = {build_verification_key(item) for item in xml_items}
        meta = metadata_by_index.get(xml_index, {})
        xml_name = meta.get("filename") or f"xml_{xml_index}"
        nfe_number = meta.get("nfe_number") or "S/N"

        xml_summary = {
            "xml_index": xml_index,
            "filename": xml_name,
            "nfe_number": nfe_number,
            "total_items": len(xml_items),
            "unique_items": len(unique_keys_in_xml),
        }
        stats["xml_breakdown"].append(xml_summary)

        print(
            f"[XML {xml_index}] arquivo={xml_name} | NFe={nfe_number} | "
            f"ocorrencias={xml_summary['total_items']} | unicos={xml_summary['unique_items']}"
        )

    print(
        f"--- Verificando {stats['unique_items']} códigos de barra unicos "
        f"de um total de {stats['total_items']} ocorrências; "
        f"duplicados evitados={stats['skipped_duplicates']} ---"
    )

    for index, (_, occurrences) in enumerate(unique_occurrences, start=1):
        if cancellation_flags and cancellation_flags.get('_global_cancel', False):
            print("[CANCELADO] Verificacao interrompida pelo usuario.")
            break

        base_item = occurrences[0]["item"]
        source_summary = build_source_summary(occurrences, metadata_by_index, base_item)

        print(
            f"[{index}/{total_unique}] Verificando codebar={base_item.get('Codebar') or 'N/A'} | "
            f"ocorrencias={len(occurrences)} | xmls={source_summary}"
        )

        verification_result, error = verify_single_item_in_api(
            auth_token,
            base_item,
            index,
            total_unique,
            source_summary
        )

        if error:
            return verified_by_xml, stats, error

        if verification_result is None:
            continue

        for occurrence in occurrences:
            item_copy = occurrence["item"].copy()

            if verification_result.get("ApiCodebars"):
                item_copy["ApiCodebars"] = verification_result["ApiCodebars"]

            verified_by_xml[occurrence["xml_index"]].append(item_copy)

    missing_total = sum(len(items) for items in verified_by_xml.values())
    print(f"--- Fim. {missing_total} item(ns) nao encontrado(s) ou invalido(s). ---")

    return verified_by_xml, stats, None


def build_source_summary(occurrences: list, metadata_by_index: dict, base_item: dict) -> str:
    source_labels = []

    for occurrence in occurrences:
        meta = metadata_by_index.get(occurrence["xml_index"], {})
        xml_name = meta.get("filename") or base_item.get("source_xml_filename") or f"xml_{occurrence['xml_index']}"
        source_labels.append(xml_name)

    return ", ".join(sorted(set(source_labels)))


def verify_single_item_in_api(auth_token: str, item: dict, index: int, total_items: int, source_summary: str = "") -> tuple[dict | None, str | None]:
    current_codebar = item.get("Codebar")

    payload = {
        "CodigoProduto": "",
        "NomeProduto": "",
        "Referencia": "900314",
        "Codebar": current_codebar if current_codebar else "",
        "CodigoAuxiliar": "",
        "CodigoIntegracaoOMS": ""
    }

    api_response = api_call(auth_token, payload)
    if "error" in api_response:
        print(f"[{index}/{total_items}] API ERROR: {api_response['error']} | xmls={source_summary}")
        return None, api_response["error"]

    produtos = api_response.get("Produtos", [])

    for produto in produtos:
        api_codebars = produto.get('Codebars', [])

        try:
            api_codebar_values = [cb['Codebar'] for cb in api_codebars]
        except Exception:
            api_codebar_values = [str(cb) for cb in api_codebars]

        if current_codebar and len(api_codebars) == 1:
            if any(cb.get('Codebar') == current_codebar for cb in api_codebars):
                print(f"ENCONTRADO ✅: {current_codebar}")
                return None, None

        elif current_codebar and len(api_codebars) > 1:
            print(f"MULTIPLOS CODEBARS: {current_codebar} -> {api_codebar_values}")
            return {
                "missing": True,
                "ApiCodebars": ', '.join(api_codebar_values)
            }, None

    print(f"NAO ENCONTRADO ❌: {current_codebar}")
    return {"missing": True}, None
