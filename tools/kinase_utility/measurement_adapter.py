"""Optional, source-preserving XLSX transport and phosphosite qualification.

No abundance transformation, aggregation, imputation, graph operation or
inference is performed. A declared column/grammar contract is required. The
author's custom site/modification syntax must never be guessed from a header.
Modification grammars must be declared: AlphaBase separate names/positions or
the bounded counted-bracket grammar verified against an authorized descriptor
window. This does not claim general Proteome Discoverer2.1 import support.
"""
from copy import deepcopy
import hashlib
import io
import json
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

from tools.kinase_utility.source_identity import resolve_source_protein_context


POLICY = "explicit-workbook-site-context.v1"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
CELL = re.compile(r"([A-Z]+)([1-9][0-9]*)\Z")
SITE = re.compile(r"([STY])([1-9][0-9]*)\Z")
THREE = {"Ser": "S", "Thr": "T", "Tyr": "Y"}


class AdapterError(ValueError):
    """A source/contract error with a machine-readable diagnostic."""
    def __init__(self, code, detail):
        super().__init__(detail)
        self.diagnostic = {"code": code, "detail": detail, "severity": "error"}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _column(address):
    match = CELL.fullmatch(address or "")
    if not match:
        raise AdapterError("invalid_cell_address", "Expected an explicit A1-style cell address.")
    number = 0
    for letter in match[1]:
        number = 26 * number + ord(letter) - 64
    return number - 1, int(match[2])


def _xml(raw):
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise AdapterError("unsupported_xml_declaration", "DTD/entity declarations are not accepted.")
    return ET.fromstring(raw)


def _rich_text(element):
    # Phonetic runs and formatting are not cell content.
    return "".join(t.text or "" for t in element.findall("s:t", NS)
        + element.findall("s:r/s:t", NS))


def _package(raw, max_member_bytes=512_000_000):
    if not isinstance(raw, bytes):
        raise TypeError("Pass immutable XLSX bytes; the caller owns file access and receipt binding.")
    archive = zipfile.ZipFile(io.BytesIO(raw))
    names = archive.namelist()
    if (len(names) != len(set(names)) or any(i.file_size > max_member_bytes or i.flag_bits & 1 for i in archive.infolist())
            or sum(i.file_size for i in archive.infolist()) > 1_000_000_000):
        archive.close()
        raise AdapterError("invalid_or_oversized_package", "Duplicate or oversized ZIP member.")
    if any("externalLinks/" in n or n.endswith("vbaProject.bin") for n in names):
        archive.close()
        raise AdapterError("external_links_or_macros", "External workbook links/macros require separate review.")
    return archive


def _sheet(archive, sheet_name):
    workbook = _xml(archive.read("xl/workbook.xml"))
    rels = _xml(archive.read("xl/_rels/workbook.xml.rels"))
    links = {}
    for relation in rels:
        rid = relation.get("Id")
        if rid in links:
            raise AdapterError("duplicate_relationship_id", "Workbook relationship ID is duplicated.")
        links[rid] = relation
    sheets = [{"name": s.get("name"), "visibility": s.get("state", "visible"),
               "relationship_id": s.get(RID)} for s in workbook.findall("s:sheets/s:sheet", NS)]
    matched = [s for s in sheets if s["name"] == sheet_name]
    if len(matched) != 1 or matched[0]["visibility"] != "visible":
        raise AdapterError("exact_visible_sheet_required", "Select exactly one visible worksheet by its declared name.")
    relation = links.get(matched[0]["relationship_id"])
    if relation is None or relation.get("TargetMode") == "External":
        raise AdapterError("invalid_sheet_relationship", "The declared sheet must have an internal relationship.")
    target = relation.get("Target", "")
    path = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
    if not path.startswith("xl/worksheets/") or path not in archive.namelist():
        raise AdapterError("invalid_sheet_path", "The declared worksheet target is not a package worksheet.")
    return path, sheets


def _header_row(archive, path):
    # Buffer transport may include following bytes; only the row1 fragment is
    # handed to the XML parser. Do not parse outcome rows during inspection.
    prefix = bytearray()
    with archive.open(path) as handle:
        while True:
            chunk = handle.read(1024)
            if not chunk or len(prefix) > 1_000_000:
                raise AdapterError("header_not_found", "A bounded, explicit row1 header is required.")
            prefix.extend(chunk)
            start = re.search(rb"<(?P<prefix>[A-Za-z_][\w.-]*:)?row\b", prefix)
            if not start:
                continue
            ending = b"</" + (start["prefix"] or b"") + b"row>"
            end = prefix.find(ending, start.start())
            if end >= 0:
                declarations = b" ".join(re.findall(rb'xmlns(?::[\w.-]+)?="[^"]+"', prefix[:start.start()]))
                root = _xml(b"<root " + declarations + b">" + prefix[start.start():end + len(ending)] + b"</root>")
                row = root[0]
                if row.get("r") != "1":
                    raise AdapterError("row1_header_required", "The first source row must be explicitly row1.")
                return row


def _header_strings(archive, wanted):
    if not wanted:
        return {}
    raw = archive.read("xl/sharedStrings.xml")
    first = re.search(rb"<(?:[A-Za-z_][\w.-]*:)?si\b", raw)
    declarations = b" ".join(re.findall(rb'xmlns(?::[\w.-]+)?="[^"]+"', raw[:first.start() if first else len(raw)]))
    # Select raw entries by index; parse only the header's referenced strings.
    entries = re.finditer(rb"<(?:[A-Za-z_][\w.-]*:)?si\b[^>]*(?:/>|>.*?</(?:[A-Za-z_][\w.-]*:)?si>)", raw, re.S)
    found = {}
    for index, match in enumerate(entries):
        if index in wanted:
            element = _xml(b"<root " + declarations + b">" + match[0] + b"</root>")[0]
            found[index] = _rich_text(element)
        if index >= max(wanted):
            break
    if set(found) != wanted:
        raise AdapterError("missing_header_shared_string", "A header shared-string reference is absent.")
    return found


def _cell(cell, strings):
    typ = cell.get("t", "n")
    value = cell.find("s:v", NS)
    literal = value.text if value is not None else None
    inline = cell.find("s:is", NS)
    formula = cell.find("s:f", NS)
    if typ == "s":
        try:
            text = strings[int(literal)]
        except (ValueError, TypeError, KeyError, IndexError) as error:
            raise AdapterError("invalid_shared_string_index", "Cell references an absent shared string.") from error
    elif typ == "inlineStr":
        text = _rich_text(inline) if inline is not None else ""
    else:
        text = literal
    return {"address": cell.get("r"), "present": True, "cell_type": typ,
            "raw_xml_value": literal, "text": text, "style_id": cell.get("s"),
            "formula": None if formula is None else {"text": formula.text, "attributes": dict(formula.attrib)},
            "state": "blank" if text in (None, "") else "source_literal"}


def inspect_workbook_headers(raw, sheet_name):
    """Only package metadata, row1 XML and row1-referenced strings are parsed."""
    with _package(raw) as archive:
        path, sheets = _sheet(archive, sheet_name)
        row = _header_row(archive, path)
        wanted = {int(c.find("s:v", NS).text) for c in row if c.get("t") == "s"}
        strings = _header_strings(archive, wanted)
        headers = [_cell(c, strings) for c in row]
        for cell in headers:
            _, row_number = _column(cell["address"])
            if row_number != 1 or cell["formula"] is not None:
                raise AdapterError("invalid_header_cell", "Headers must be literal cells on row1.")
        indices = [_column(c["address"])[0] for c in headers]
        if indices != list(range(len(headers))):
            raise AdapterError("noncontiguous_header", "Declare contiguous, ordered header cells starting at A1.")
        return {"workbook_sha256": hashlib.sha256(raw).hexdigest(), "sheet_name": sheet_name,
                "worksheet_path": path, "sheets": sheets, "headers": [c["text"] for c in headers],
                "header_cells": headers, "data_rows_parsed": 0}


def _contract(contract):
    if not isinstance(contract, dict) or not isinstance(contract.get("sheet_name"), str):
        raise TypeError("Pass an explicit workbook contract dict with sheet_name.")
    headers = contract.get("headers")
    if not isinstance(headers, list) or not headers or not all(isinstance(h, str) and h for h in headers):
        raise ValueError("Declare the full positional header list; duplicate labels may be meaningful.")
    columns = list(contract.get("fields", {}).values()) + [q["index"] for q in contract.get("quant_columns", [])]
    if any(type(i) is not int or not 0 <= i < len(headers) for i in columns):
        raise ValueError("Column selectors must be zero-based indices within the declared header list.")
    sample_ids = [q["sample_id"] for q in contract.get("quant_columns", [])]
    if len(sample_ids) != len(set(sample_ids)) or any(not isinstance(s, str) or not s for s in sample_ids):
        raise ValueError("Declare distinct sample IDs; source header duplicates are not sample IDs.")
    if not all(q.get("unit") is None or isinstance(q["unit"], str) for q in contract.get("quant_columns", [])):
        raise ValueError("Each declared unit must be a literal string or unknown/None.")
    quant_indices = [q["index"] for q in contract.get("quant_columns", [])]
    if len(quant_indices) != len(set(quant_indices)) or set(quant_indices) & set(contract.get("fields", {}).values()):
        raise ValueError("Quantitative columns must be physically distinct and disjoint from descriptor fields.")
    unavailable = contract.get("unavailable_tokens_by_field", {})
    optional = contract.get("optional_corroboration_fields", [])
    if (not isinstance(unavailable, dict) or any(field not in contract.get("fields", {}) for field in unavailable)
            or any(not isinstance(tokens, list) or any(not isinstance(token, str) for token in tokens)
                   for tokens in unavailable.values())):
        raise ValueError("Unavailable markers must be literal, per-field tokens for declared descriptor columns.")
    if (not isinstance(optional, list) or len(optional) != len(set(optional))
            or any(field not in contract.get("fields", {}) or field not in {"other_modifications"} for field in optional)):
        raise ValueError("Only a declared secondary corroboration field can be optional; core identity evidence remains required.")


def validate_contract(contract):
    """Public pre-access validation; performs no file or data access."""
    _contract(contract)
    return {"policy": POLICY, "status": "contract_valid", "contract_sha256": _digest(contract)}


def inspect_descriptor_rows(raw, contract, *, first_row, last_row, column_indices, data_access_seal=None):
    """Parse only a caller-authorized descriptor window, never other cells.

    Raw row bytes may be transported while selecting fragments. Only permitted
    cell fragments and their referenced shared strings are passed to XML/text
    decoding. This is distinct from full measurement access.
    """
    _contract(contract)
    if not isinstance(data_access_seal, str) or not re.fullmatch(r"[a-f0-9]{64}", data_access_seal):
        raise AdapterError("pre_access_seal_required", "Descriptor access needs its own explicit source-window seal.")
    allowed = set(column_indices)
    if (type(first_row) is not int or type(last_row) is not int or not 2 <= first_row <= last_row
            or not allowed or any(type(i) is not int or not 0 <= i < len(contract["headers"]) for i in allowed)):
        raise ValueError("Declare a bounded data-row window and exact zero-based descriptor columns.")
    if allowed & {q["index"] for q in contract.get("quant_columns", [])}:
        raise AdapterError("descriptor_window_includes_quantitation", "Do not parse sample columns during descriptor-only access.")
    meta = inspect_workbook_headers(raw, contract["sheet_name"])
    if meta["headers"] != contract["headers"] or (contract.get("workbook_sha256") not in (None, meta["workbook_sha256"])):
        raise AdapterError("descriptor_contract_mismatch", "Descriptor source differs from the declared workbook/header contract.")
    selected = []
    wanted = set()
    with _package(raw) as archive:
        buffer = bytearray()
        declarations = None
        done = False
        with archive.open(meta["worksheet_path"]) as handle:
            while not done:
                chunk = handle.read(32768)
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    start = re.search(rb"<(?P<prefix>[A-Za-z_][\w.-]*:)?row\b[^>]*>", buffer)
                    if not start:
                        break
                    if declarations is None:
                        declarations = b" ".join(re.findall(rb'xmlns(?::[\w.-]+)?="[^"]+"', buffer[:start.start()]))
                    ending = b"</" + (start["prefix"] or b"") + b"row>"
                    end = buffer.find(ending, start.end())
                    if end < 0:
                        break
                    opening = start[0]
                    number_match = re.search(rb'\br="([1-9][0-9]*)"', opening)
                    if not number_match:
                        raise AdapterError("row_identity_required", "Descriptor window needs explicit source row numbers.")
                    number = int(number_match[1])
                    fragment = bytes(buffer[start.end():end])
                    del buffer[:end + len(ending)]
                    if number > last_row:
                        done = True
                        break
                    if number < first_row:
                        continue
                    cells = []
                    for match in re.finditer(rb"<(?:[A-Za-z_][\w.-]*:)?c\b(?P<attrs>[^>]*)(?:/>|>.*?</(?:[A-Za-z_][\w.-]*:)?c>)", fragment, re.S):
                        address = re.search(rb'\br="([A-Z]+[1-9][0-9]*)"', match["attrs"])
                        if not address:
                            raise AdapterError("cell_address_required", "Descriptor selection needs explicit cell addresses.")
                        index, row_number = _column(address[1].decode("ascii"))
                        if index not in allowed:
                            continue
                        if row_number != number:
                            raise AdapterError("descriptor_cell_row_conflict", "Selected descriptor cell disagrees with its row.")
                        cell = _xml(b"<root " + (declarations or b"") + b">" + match[0] + b"</root>")[0]
                        if cell.get("t") == "s":
                            wanted.add(int(cell.find("s:v", NS).text))
                        cells.append((index, cell))
                    selected.append((number, cells))
                    if number == last_row:
                        done = True
                        break
                if len(buffer) > 10_000_000:
                    raise AdapterError("descriptor_row_bound_exceeded", "Descriptor fragment exceeds the transport bound.")
        strings = _header_strings(archive, wanted)
        records = []
        for number, cells in selected:
            indices = [i for i, _ in cells]
            if len(indices) != len(set(indices)):
                raise AdapterError("duplicate_descriptor_cell", "A descriptor cell is duplicated in a source row.")
            records.append({"row_number": number, "cells": {i: _cell(c, strings) for i, c in cells}})
    return {"policy": POLICY, "access_kind": "descriptor_window_only", "metadata": meta,
            "data_access_seal": data_access_seal, "first_row": first_row, "last_row": last_row,
            "column_indices": sorted(allowed), "records": records,
            "data_rows_parsed": len(records), "quantitative_cells_parsed": 0}


def read_measurements(raw, contract, *, data_access_seal=None):
    """Transport raw cells only after an explicit caller-owned pre-access seal.

    The seal is a receipt identifier, not an authorization/security service.
    The optional standard reader decodes XML cell types (including numbers),
    without abundance transformation or differential labels. Decoded numeric
    strings are not claimed to retain the original XML lexeme. Formula caches
    are not used; sparse blanks, missing tokens, zeros and units stay distinct.
    """
    _contract(contract)
    if not isinstance(data_access_seal, str) or not re.fullmatch(r"[a-f0-9]{64}", data_access_seal):
        raise AdapterError("pre_access_seal_required", "No data row may be parsed without a caller's sealed access plan.")
    meta = inspect_workbook_headers(raw, contract["sheet_name"])
    expected_sha = contract.get("workbook_sha256")
    if expected_sha is not None and expected_sha != meta["workbook_sha256"]:
        raise AdapterError("workbook_fingerprint_mismatch", "Source bytes differ from the declared workbook.")
    if meta["headers"] != contract["headers"]:
        raise AdapterError("positional_header_contract_mismatch", "Source headers/order differ from the declared contract.")
    # Optional import keeps the app and header/descriptor-only paths independent
    # of a spreadsheet stack. Reuse the standard streaming reader after access.
    try:
        import openpyxl
        from openpyxl.cell.read_only import EmptyCell
    except ImportError as error:
        raise AdapterError("optional_reader_not_installed", "Install the separate measurement-reader requirements.") from error
    if openpyxl.__version__ != "3.1.5":
        raise AdapterError("optional_reader_version_mismatch", "This source transport was verified with openpyxl3.1.5.")
    records = []
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=False, keep_links=False)
    except (ValueError, IndexError, KeyError, ET.ParseError) as error:
        raise AdapterError("standard_reader_source_error", "The declared source is not a valid standard-reader workbook.") from error
    try:
        worksheet = workbook[contract["sheet_name"]]
        # Public documented remedy for unreliable producer-supplied dimensions;
        # stream actual rows rather than truncating to a cached used-range hint.
        worksheet.reset_dimensions()
        for number, row in enumerate(worksheet.iter_rows(min_row=2, values_only=False), 2):
            cells = {}
            for index, cell in enumerate(row):
                if isinstance(cell, EmptyCell):
                    continue
                if index >= len(meta["headers"]):
                    if cell.value is not None:
                        raise AdapterError("cell_position_outside_contract", "A source value extends beyond the declared table headers.")
                    continue
                typ, value = cell.data_type, cell.value
                text = value if isinstance(value, str) or value is None else str(value)
                formula = {"text": text[1:] if isinstance(text, str) and text.startswith("=") else text,
                           "attributes": None} if typ == "f" else None
                cells[index] = {"address": cell.coordinate, "present": True, "cell_type": typ,
                    "raw_xml_value": None, "text": text, "style_id": None, "number_format": cell.number_format,
                    "formula": formula, "state": "blank" if value in (None, "") else "source_literal",
                    "representation": "openpyxl_decoded_not_original_xml_lexeme",
                    "decoded_python_type": type(value).__name__}
            records.append({"row_number": number, "cells": cells})
            if len(records) > contract.get("max_rows", 500_000):
                raise AdapterError("row_bound_exceeded", "Source exceeds the declared row bound.")
    except (ValueError, IndexError, KeyError, ET.ParseError) as error:
        if isinstance(error, AdapterError):
            raise
        raise AdapterError("standard_reader_source_error", "A selected source cell cannot be decoded by the standard reader.") from error
    finally:
        workbook.close()
    return {"policy": POLICY, "metadata": meta, "contract_sha256": _digest(contract),
            "data_access_seal": data_access_seal, "records": records,
            "data_rows_parsed": len(records),
            "reader": {"name": "openpyxl", "version": openpyxl.__version__, "read_only": True,
                       "data_only": False, "cached_formula_values_used": False,
                       "numeric_representation": "Decoded Python numeric string; original XML remains in fingerprinted source bytes."},
            "numerical_abundance_interpretation_performed": False}


def _source_cell(record, index):
    cells = record["cells"]
    if index in cells and str(index) in cells:
        raise AdapterError("ambiguous_serialized_cell_index", "One source column has two index representations.")
    return deepcopy(cells.get(index, cells.get(str(index), {"present": False, "text": None, "state": "missing_cell",
        "cell_type": None, "raw_xml_value": None, "style_id": None, "formula": None, "address": None})))


def _counted_modifications(raw, ignored_labels):
    """Declared counted bracket grammar; exact scores retained, not calibrated."""
    if raw == "":
        return [], []
    parsed, ignored = [], []
    end = 0
    blocks = list(re.finditer(r"(?:(?P<count>[1-9][0-9]*)x)?(?P<name>[A-Za-z0-9_+-]+) \[(?P<tokens>[^\]]+)\]", raw))
    for block in blocks:
        if raw[end:block.start()] not in ("", "; ", ";"):
            raise AdapterError("unsupported_modification_block", "A modification block/gap does not match the declared grammar.")
        end = block.end()
        if block["name"] in ignored_labels:
            ignored.append({"raw": block[0], "name": block["name"], "semantics_assessed": False})
            continue
        tokens = block["tokens"].split(";")
        if block["count"] is None or int(block["count"]) != len(tokens):
            raise AdapterError("modification_count_mismatch", "Counted modification and reported locations disagree.")
        for token in tokens:
            match = re.fullmatch(r"\s*([A-Z])([1-9][0-9]*)(?:\(([0-9]+(?:\.[0-9]+)?)\))?\s*", token)
            if not match:
                raise AdapterError("unlocalized_or_unsupported_modification", "Unlocalized, terminal or unsupported modification position is not rescued.")
            parsed.append({"name": block["name"], "residue": match[1], "peptide_position": int(match[2]),
                           "localization_score_raw": match[3]})
    if not blocks or end != len(raw):
        raise AdapterError("unsupported_modification_block", "The complete source modification string must match the declared grammar.")
    return parsed, ignored


def qualify_record(record, contract, registry, sequence_reference):
    """Qualify literal identifier/peptide/site consistency, not assay truth.

    No group/isoform/secondary/alias/coordinate rescue is attempted. Modification
    names and peptide-relative positions use one explicitly declared grammar.
    Other source grammars fail with a diagnostic, preserving
    every input cell. Multisite quantities are not expanded into independent sites.
    Quantitative formula/error warnings are cell-scoped and do not invalidate
    independent descriptor mapping; the caller applies per-group missingness.
    """
    _contract(contract)
    result = {"policy": POLICY, "row_number": record["row_number"], "raw_record": deepcopy(record),
        "status": "unresolved", "protein_id": None, "site": None, "canonical_site_id": None,
        "diagnostics": [], "quantitative_diagnostics": [], "candidate_fixes": [], "raw_quant_values": [],
        "field_availability": {},
        "assay_proteoform_identity_established": False, "localization_confidence_established": False,
        "citation_grounding_status": "not_assessed", "quantitative_eligibility_assessed": False}
    fields = contract.get("fields", {})
    def issue(code, field, detail):
        result["diagnostics"].append({"code": code, "field": field, "detail": detail, "severity": "error"})
    def text(field, allow_empty=False):
        if field not in fields:
            issue("required_field_not_declared", field, "Declare a source column; do not infer it from another value.")
            return None
        c = _source_cell(record, fields[field])
        if c["formula"] is not None or c["cell_type"] == "e":
            issue("formula_or_error_cell", field, "Formula/cache/error cannot serve as literal evidence.")
            return None
        value = c["text"]
        if value in contract.get("unavailable_tokens_by_field", {}).get(field, []):
            optional = field in contract.get("optional_corroboration_fields", [])
            result["field_availability"][field] = {"state": "not_reported", "raw_literal": value,
                "basis": "contract_declared_unavailable_token", "required_for_identity": not optional}
            if not optional:
                issue("required_descriptor_field_unavailable", field, "A declared missing marker cannot replace required identity/site evidence.")
            return None
        if allow_empty and value in (None, ""):
            return ""
        if not isinstance(value, str) or not value:
            issue("missing_literal_field", field, "The source field is unavailable.")
            return None
        if value.strip() != value:
            issue("literal_whitespace_requires_review", field, "No whitespace normalization is applied automatically.")
            result["candidate_fixes"].append({"kind": "trim_surrounding_whitespace", "field": field,
                "original": value, "candidate": value.strip(), "applied": False,
                "scope": "Lexical representation only; identifier/site consistency must be rechecked after approval."})
            return None
        return value
    for q in contract.get("quant_columns", []):
        c = _source_cell(record, q["index"])
        # Quantitative source tokens remain strings, including literal zero.
        if c["formula"] is not None or c["cell_type"] == "e":
            result["quantitative_diagnostics"].append({"code": "formula_or_error_quantitation", "field": q["sample_id"],
                "detail": "Only this source cell is unavailable; the raw formula/error is preserved without evaluation.",
                "severity": "unavailable", "scope": "cell_only"})
        state = ("declared_missing_token" if c["text"] in contract.get("missing_tokens", [])
                 and c["present"] and c["state"] != "blank" else c["state"])
        result["raw_quant_values"].append({**deepcopy(q), "source_header": contract["headers"][q["index"]],
            "cell": c, "source_value_state": state})
    accession, peptide, site_literal = text("accession"), text("peptide"), text("protein_site")
    syntax = contract.get("modification_syntax")
    if syntax not in {"alphabase_separate", "counted_bracket_modifications.v1"}:
        issue("unsupported_modification_syntax", "modifications", "Declare and verify the author grammar before reading it as peptide sites.")
        return result
    if any(v is None for v in [accession, peptide, site_literal]):
        return result
    if syntax == "alphabase_separate":
        names, positions = text("modification_names"), text("modification_positions")
        if names is None or positions is None:
            return result
        name_tokens, position_tokens = names.split(";"), positions.split(";")
        if len(name_tokens) != len(position_tokens):
            issue("modification_count_mismatch", "modifications", "Each named modification needs one declared peptide-relative position.")
            return result
        modifications = []
        for name, position in zip(name_tokens, position_tokens):
            m = re.fullmatch(r"([^;@]+)@([A-Z])", name)
            if not m or not re.fullmatch(r"[1-9][0-9]*", position):
                issue("unsupported_modification_token", "modifications", "Do not discard unknown or terminal modification semantics.")
                return result
            modifications.append({"name": m[1], "residue": m[2], "peptide_position": int(position)})
    else:
        raw_mods = text("modifications_raw")
        phospho_mods = text("phospho_modifications")
        other_mods = text("other_modifications", allow_empty=True)
        other_unavailable = (result["field_availability"].get("other_modifications", {}).get("state") == "not_reported"
            and "other_modifications" in contract.get("optional_corroboration_fields", []))
        if raw_mods is None or phospho_mods is None or (other_mods is None and not other_unavailable):
            return result
        try:
            modifications, ignored = _counted_modifications(raw_mods, set(contract.get("unassessed_label_modifications", [])))
            reported_phospho, _ = _counted_modifications(phospho_mods, set())
            reported_other = None if other_unavailable else _counted_modifications(other_mods, set())[0]
        except AdapterError as error:
            issue(error.diagnostic["code"], "modifications", error.diagnostic["detail"])
            return result
        key = lambda m: (m["name"], m["residue"], m["peptide_position"])
        actual_phospho = [m for m in modifications if m["name"] == "Phospho"]
        actual_other = [m for m in modifications if m["name"] != "Phospho"]
        if (any(m["name"] != "Phospho" for m in reported_phospho)
                or sorted(map(key, actual_phospho)) != sorted(map(key, reported_phospho))
                or (reported_other is not None and sorted(map(key, actual_other)) != sorted(map(key, reported_other)))):
            issue("raw_processed_modification_conflict", "modifications", "Raw, processed phospho and other-modification fields disagree.")
            return result
        result["unassessed_source_label_modifications"] = ignored
        result["other_modification_corroboration"] = {"status": "not_reported" if other_unavailable else "available_consistent",
            "absence_of_biological_PTMs_inferred": False}
        result["localization_scores_raw"] = [m.get("localization_score_raw") for m in actual_phospho]
        result["localization_score_unit_or_calibration_inferred"] = False
    separator = contract.get("accession_separator")
    group = accession.split(separator) if separator else [accession]
    result["reported_accession_members"] = group
    if len(group) != 1:
        issue("protein_group_not_single_literal_product", "accession", "Preserve the group; do not choose its first member.")
        return result
    if contract.get("accession_syntax") == "bare_uniprot":
        pid = "UniProtKB:" + accession
    elif contract.get("accession_syntax") == "uniprot_curie":
        pid = accession
    else:
        issue("unsupported_accession_syntax", "accession", "Declare a literal namespace representation.")
        return result
    context = resolve_source_protein_context(pid, registry, sequence_reference)
    result["protein_reference_context"] = context
    if context["status"] != "qualified_source_protein_context":
        issue("literal_protein_context_unresolved", "accession", "; ".join(context["reasons"]))
        return result
    if contract.get("peptide_syntax") != "plain_uppercase" or not re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWY]+", peptide):
        issue("unsupported_peptide_syntax", "peptide", "Require a declared unmodified uppercase peptide; no stripping, I/L substitution or flank inference.")
        return result
    if ";" in site_literal or site_literal == "NULL":
        issue("multisite_or_unlocalized_measurement_not_expanded", "protein_site", "Preserve the peptide-level signal; do not choose/expand one protein site.")
        return result
    if contract.get("protein_site_syntax") == "residue_position":
        match = SITE.fullmatch(site_literal)
    elif contract.get("protein_site_syntax") == "three_letter_position":
        m = re.fullmatch(r"(Ser|Thr|Tyr)([1-9][0-9]*)", site_literal)
        match = SITE.fullmatch(THREE[m[1]] + m[2]) if m else None
    else:
        match = None
    if not match:
        issue("unsupported_protein_site_syntax", "protein_site", "Unknown/ambiguous site syntax is not repaired from the peptide.")
        return result
    for modification in modifications:
        p = modification["peptide_position"]
        if p > len(peptide) or peptide[p - 1] != modification["residue"]:
            issue("modification_peptide_residue_conflict", "modifications", "Modification residue/position disagrees with the literal peptide.")
            return result
    result["reported_modifications"] = modifications
    phospho = [m for m in modifications if m["name"] == "Phospho"]
    if len(phospho) != 1 or phospho[0]["residue"] not in "STY":
        issue("requires_one_explicit_phosphosite", "modifications", "Absent/multisite peptide signal is preserved without expansion or site selection.")
        return result
    residue, position = match[1], int(match[2])
    sequence = sequence_reference[pid.removeprefix("UniProtKB:")]["Sequence"]
    if position > len(sequence) or sequence[position - 1] != residue or phospho[0]["residue"] != residue:
        issue("canonical_site_reference_conflict", "protein_site", "Reported residue/site does not match the captured exact product.")
        return result
    start = position - phospho[0]["peptide_position"] + 1
    if start < 1 or sequence[start - 1:start - 1 + len(peptide)] != peptide:
        issue("peptide_site_alignment_conflict", "peptide", "Peptide-relative modification and protein site do not share an exact reference alignment.")
        return result
    result["reference_alignment"] = {"one_based_peptide_start": start, "peptide_length": len(peptide),
        "protein_site": residue + str(position), "peptide_site": phospho[0]["peptide_position"]}
    if not result["diagnostics"]:
        result.update(status="qualified_reference_coordinate_context", protein_id=pid,
            site=residue + str(position), canonical_site_id=pid + ":" + residue + str(position))
    return result


def qualify_protein_record(record, contract, registry, sequence_reference):
    """Source-host protein context for a separate abundance sensitivity.

    Declared source group-count=1 and unique-peptide-count>=1 are eligibility
    conditions, not proof of group cardinality, proteoform identity or a direct
    abundance measurement. Never select the first member of a protein group.
    Quantitative cell warnings remain separate from descriptor eligibility.
    """
    _contract(contract)
    result = {"policy": POLICY, "row_number": record["row_number"], "raw_record": deepcopy(record),
        "status": "unresolved", "protein_id": None, "diagnostics": [], "quantitative_diagnostics": [], "raw_quant_values": [],
        "assay_proteoform_identity_established": False, "protein_group_cardinality_established": False,
        "direct_abundance_validation_performed": False, "citation_grounding_status": "not_assessed",
        "quantitative_eligibility_assessed": False}
    fields = contract.get("fields", {})
    def issue(code, field, detail):
        result["diagnostics"].append({"code": code, "field": field, "detail": detail, "severity": "error"})
    def value(field):
        if field not in fields:
            issue("required_field_not_declared", field, "The source eligibility field must be declared.")
            return None
        c = _source_cell(record, fields[field])
        if c["formula"] is not None or c["cell_type"] in {"e", "b"} or not isinstance(c["text"], str) or not c["text"]:
            issue("missing_or_nonliteral_source_field", field, "Counts/identifiers cannot be inferred from missing, formula, bool or error cells.")
            return None
        return c["text"]
    for q in contract.get("quant_columns", []):
        c = _source_cell(record, q["index"])
        state = ("declared_missing_token" if c["text"] in contract.get("missing_tokens", [])
                 and c["present"] and c["state"] != "blank" else c["state"])
        result["raw_quant_values"].append({**deepcopy(q), "source_header": contract["headers"][q["index"]],
            "cell": c, "source_value_state": state})
        if c["formula"] is not None or c["cell_type"] == "e":
            result["quantitative_diagnostics"].append({"code": "formula_or_error_quantitation", "field": q["sample_id"],
                "detail": "Only this source cell is unavailable; the raw formula/error is preserved without evaluation.",
                "severity": "unavailable", "scope": "cell_only"})
    accession = value("accession")
    group_count = value("source_group_count")
    unique_count = value("source_unique_peptides")
    result["source_count_literals"] = {"source_group_count": group_count, "source_unique_peptides": unique_count}
    if accession is None or group_count is None or unique_count is None:
        return result
    separator = contract.get("accession_separator")
    members = accession.split(separator) if separator else [accession]
    result["reported_accession_members"] = members
    if len(members) != 1 or accession.strip() != accession:
        issue("protein_group_or_nonliteral_accession", "accession", "Do not select a group representative or normalize its identifier silently.")
        return result
    if contract.get("accession_syntax") == "bare_uniprot":
        pid = "UniProtKB:" + accession
    elif contract.get("accession_syntax") == "uniprot_curie":
        pid = accession
    else:
        issue("unsupported_accession_syntax", "accession", "Declare a literal namespace representation.")
        return result
    context = resolve_source_protein_context(pid, registry, sequence_reference)
    result["protein_reference_context"] = context
    if context["status"] != "qualified_source_protein_context":
        issue("literal_protein_context_unresolved", "accession", "; ".join(context["reasons"]))
        return result
    if not re.fullmatch(r"[0-9]+(?:\.0+)?", group_count) or not re.fullmatch(r"[0-9]+(?:\.0+)?", unique_count):
        issue("source_count_not_nonnegative_integer", "source_counts", "Require literal nonnegative integral counts; raw values remain unchanged.")
        return result
    groups, unique = int(group_count.split(".")[0]), int(unique_count.split(".")[0])
    result["declared_source_count_eligibility"] = {"group_count_equals_one": groups == 1, "unique_peptides_at_least_one": unique >= 1}
    if groups != 1 or unique < 1:
        issue("source_count_eligibility_not_met", "source_counts", "Declared group-count/unique-peptide sensitivity conditions are unmet.")
    if "gene" in fields:
        gene_cell = _source_cell(record, fields["gene"])
        gene = gene_cell["text"]
        result["reported_gene_corroboration"] = {"raw": gene, "status": "unavailable"}
        if gene not in (None, ""):
            ok = gene_cell["formula"] is None and gene == context["approved_symbol"]
            result["reported_gene_corroboration"]["status"] = "exact_current_primary" if ok else "not_exact_current_primary"
            if not ok:
                issue("source_gene_context_not_exact", "gene", "Gene label is corroboration only; no alias lookup or ID replacement.")
    if not result["diagnostics"]:
        result.update(status="qualified_reference_protein_context", protein_id=pid)
    return result
