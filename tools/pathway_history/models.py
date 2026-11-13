"""Optional XSD execution and compatibility aliases for the core literal reader."""
from biograph_steward.file_utils import sha
from biograph_steward.wiki_history import (DATASOURCE_CODES, FULL_ID, GPML, NS,
    SUPPORTED_NODE_TYPES, archive_member_id, assess_subject, bridge_for_subject,
    inspect_fields, inspect_model, need)


def official_schema_validator(path, expected_sha256):
    """Compile the supplied byte-pinned released author XSD with lxml.

    This executes the standard XML Schema validator, not a replacement GPML
    curation algorithm. It checks syntax/format only, not biological semantics.
    """
    from lxml import etree
    need(sha(path) == expected_sha256, "author schema bytes differ from explicit pin.")
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    schema = etree.XMLSchema(etree.parse(str(path), parser))

    def validate(raw):
        doc = etree.fromstring(raw, parser)
        passed = schema.validate(doc)
        return {"executed": True, "passed": passed, "package": "lxml",
                "package_version": ".".join(str(x) for x in etree.LXML_VERSION),
                "schema_sha256": expected_sha256,
                "errors": [{"line": e.line, "message": e.message, "type": e.type_name}
                           for e in schema.error_log]}
    return validate


