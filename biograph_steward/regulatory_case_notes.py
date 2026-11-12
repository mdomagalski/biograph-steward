"""Source-bound project notes from a bounded primary-literature walkthrough.

These are presentation annotations for 24 inspected SIGNOR records, separate
from immutable source observations and local review decisions. The structured
checks follow the existing assertion/context/provenance distinctions; they do
not create a biological truth protocol or automatically clear unexamined rows.
SIGNOR 4.0 source identifiers/data are attributed under CC BY 4.0. Paper rights
remain with their publishers/authors; notes contain short project paraphrases.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote

from .client import digest
from .signor_source import COLUMNS

FORMAT = "biograph-steward.regulatory-case-notes.v1"
AUDIT_KIND = "agent_assisted_literature_check"
AUDIT_DATE = "2026-11-12"
SOURCE_RELEASE = "Oct2026"
SOURCE_SHA256 = "63db6f65e9148e81354f564c3c3cdfc9ee45dc421553bd0926e5fae511ef9d06"
SOURCE_URL = "https://www.signor.uniroma2.it/releases/Oct2026_release.txt"


@lru_cache(maxsize=1)
def _display_labels():
    """Load pinned display names, without applying ontology relationships."""
    raw = Path(__file__).with_name('regulatory_context_labels.json').read_bytes()
    value = json.loads(raw)
    if value.get('content_sha256') != digest({k: v for k, v in value.items() if k != 'content_sha256'}):
        raise ValueError('Regulatory display-label inventory changed.')
    value['asset_sha256'] = hashlib.sha256(raw).hexdigest()
    return value


def context_display(raw):
    labels = _display_labels()
    result = []
    for identifier in raw.split(';') if raw else []:
        term = labels['labels'].get(identifier)
        expected = 'http://purl.obolibrary.org/obo/' + identifier.replace(':', '_')
        if (re.fullmatch(r'BTO:[0-9]{7}', identifier) and isinstance(term, dict)
                and term.get('iri') == expected and term.get('is_obsolete') is False):
            result.append({'id': identifier, 'label': term['label'], 'mapping': 'exact_ontology_identifier_display',
                'url': 'https://www.ebi.ac.uk/ols4/ontologies/bto/classes?iri=' + quote(expected, safe=''),
                'ontology_version_iri': labels['ontology_version_iri'],
                'raw_term_response_sha256': term['source_raw_sha256']})
        else:
            result.append({'id': identifier, 'label': identifier, 'mapping': 'unresolved_literal', 'url': None})
    return result


def organism_display(observation):
    raw = observation.get('source_experimental_organism_raw')
    if raw == '-1':
        return {'label': 'In vitro (source code −1)', 'raw': raw, 'url': None}
    if isinstance(raw, str) and re.fullmatch(r'[1-9][0-9]*', raw):
        name = _display_labels().get('taxon_labels', {}).get(raw)
        return {'label': (name + ' · ' if name else '') + 'NCBITaxon:' + raw, 'raw': raw,
            'url': 'https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=' + raw}
    return {'label': raw or 'Unreported', 'raw': raw, 'url': None}


def display_metadata_basis():
    value = _display_labels()
    return {key: deepcopy(value[key]) for key in ('source', 'ontology_version_iri', 'retrieved_at_utc',
        'matching_policy', 'source_capture_manifest_content_sha256', 'asset_sha256',
        'license', 'taxon_metadata_source') if key in value}

# PMID, CSV data-record ordinal, complete raw-row digest, inspected case.
# Ordinals count parsed data records, not physical lines or independent studies.
_ROW_PINS = {
    "SIGNOR-106500": ("11279155", 42462, "93a429d623e3a0daf0deed7c428a8e3d12c2a0af2192373cca2718e6c1408328", "EGFR_ERBB2_CONSTRUCT"),
    "SIGNOR-121959": ("14967450", 26466, "fd9f24a5e776eb8a1ad93e15b0e981c1b83be1b12d384d11cd9534899f355f0d", "EGFR_PIK3R1_REVIEW"),
    "SIGNOR-156906": ("21779497", 15440, "7e04997856094a07de8f5cb5f85cdc1871ff614f05e01134fdb56dc5200401d7", "KRAS_REVIEW"),
    "SIGNOR-175204": ("21779497", 8072, "f989ddb662daa83a86a28fbca069ede2734a516680a2804b7d7b65aceda8faad", "KRAS_REVIEW"),
    "SIGNOR-236467": ("10653583", 36497, "dfe4a0aaccddbb3a358fd4033d9cf98ba3fd0c14ddba55c20ea71703049ff2de", "EGFR_COORDINATE_CONVENTION"),
    "SIGNOR-236471": ("10653583", 30740, "e1892e257de2fcea5c079e8afe6e0cce6b659daca95f0609d3b9be2ff36a6f96", "EGFR_COORDINATE_CONVENTION"),
    "SIGNOR-236475": ("10653583", 32785, "cd64b50819f1d9e9f3224273c9245fc979a1da9db901e634ac9210d95b85d3c0", "EGFR_COORDINATE_CONVENTION"),
    "SIGNOR-236479": ("10653583", 4706, "6063d7c4feecc8ffa47aea90366bf85881f6bee80ee74945ca4608e1187021d4", "EGFR_COORDINATE_CONVENTION"),
    "SIGNOR-236483": ("10653583", 13597, "fed833c96baaaacb2010e63065d14bac946e4d7158489fe9e6d711f3e70d9817", "EGFR_COORDINATE_CONVENTION"),
    "SIGNOR-236487": ("10653583", 40722, "5417e6a45e225bbae1132c0135dffd7d775dce8a78c11bea73c8943a0ae4c87e", "EGFR_COORDINATE_CONVENTION"),
    "SIGNOR-251093": ("10635327", 9479, "f311d59307ae63d493b2385b5df053c12f4d86666b982f6dc0b74d2bff2b88eb", "EGFR_COORDINATE_CONVENTION"),
    "SIGNOR-251094": ("12354693", 26674, "438776905671b869abc7d5e89c3abc77cfc1773997e0359e8742b077439f2126", "EGFR_ERBB2_Y1248"),
    "SIGNOR-277255": ("27345148", 34773, "0b0477ce252d0ceb2795fc9d096fb25542db075365282dc61af3f25ccd06c679", "BRAF_S614"),
    "SIGNOR-277498": ("31929109", 20802, "a396d54fef86558229c22908a9fd9ca6b0ac7872973822746e0fd747fa4651bc", "BRAF_P_LOOP"),
    "SIGNOR-277499": ("31929109", 2757, "8c5b49f3fd3e373d004e9fad836ac96b398059ee27a09c823aed4968a2025477", "BRAF_P_LOOP"),
    "SIGNOR-278308": ("25164010", 13267, "d94c342f8637986270308056c8cfc9fe94de69d42703b3675554f0804801100a", "EGFR_CTNNB1_Y654"),
    "SIGNOR-278309": ("22558232", 27650, "c07928cc4ff5c69d4f5c7efbd6a76554161f4464a729fc304d2d6854e1cb90b8", "EGFR_CTNNB1_Y142"),
    "SIGNOR-279368": ("23904266", 14513, "850a969194e1387d77fb891c89f54a2e9ff286f64c6d1f3f38b13eb7174bc965", "EGFR_GRK2_ORIGIN"),
    "SIGNOR-33633": ("26918608", 23285, "bae35a13f44efe6967aa52ed825a0976d2fa5d1e291437f61bb985e39eee87bc", "EGFR_PIK3R1_CITATION_CONTEXT"),
    # Phase 2: every row carrying one of the three exact CRC-model context IDs,
    # selected before inspecting claims. Reused papers remain shared evidence.
    "SIGNOR-235914": ("16293724", 6484, "862f86cd4a680af847272d971ce2ec2bb99a6bb3015bca28a1456387efa82748", "CRC_PIK3CA_AKT_SCOPE"),
    "SIGNOR-141814": ("16293724", 38958, "5d35eb7118e29febc8e1a54ae0ba09b0f0e65e1ab140724df78b3f5e4f4c8785", "CRC_PIK3CA_AKT_SCOPE"),
    "SIGNOR-273531": ("21779472", 8269, "9450067a0f2ebe8240923bed0b672db4451214e765c12a902077ba47938eab12", "CRC_MCC_UV_CHECKPOINT"),
    "SIGNOR-273530": ("21779472", 34422, "70fe4211ecacf33dca290b48bc7c88713c0889720a9f369ff18388b6e2bc0a13", "CRC_MCC_UV_CHECKPOINT"),
    "SIGNOR-60043": ("9734785", 29106, "817b9c85bec96325907600884cc60188b3f9e920aa616458eeea8417aa6c42d0", "CRC_AXIN_APC_SCOPE"),
}

_CASES = {
    "CRC_MCC_UV_CHECKPOINT": {
        "title": "MCC supports a UV checkpoint in colon cancer cell models",
        "status": "qualified_example", "useful_example": True,
        "summary": "The study implicates DNA-PK in UV-induced MCC phosphorylation and MCC phosphosites in a colorectal-model checkpoint; the exact kinase-to-site assignment remains qualified.",
        "conditions": ["In UV-treated HCT116 cells, a DNA-PK inhibitor partially reduced MCC phosphorylation; ATR knockdown also had a partial effect (Figure 3).",
            "In HCT15 cells, S118A/S120A MCC mutants impaired UV-induced G2/M arrest (Figure 6). These two source rows reuse one study."],
        "what_is_not_established": ["Purified PRKDC directly phosphorylating each site. The authors propose S118/S120 as the most likely targets and do not exclude other kinases.",
            "A novel relationship or independent new evidence: the saved STRING capture already reports a below-cutoff association; primary-study reuse remains unresolved.",
            "The same response in untreated cells or patients. Source DIRECT=t is retained as a database assertion, not upgraded to independent biochemical validation."],
        "sources": [{"url": "https://publications.garvan.org.au/research/publications/10755",
            "section": "Results and Figure 3 (pp.919–920); Figure 6 and Discussion (pp.922–924); Methods (p.925)", "material": "primary paper, institutional author manuscript"},
            {"url": "https://publications.gimr.garvan.org.au/open-access/10755",
             "section": "Author manuscript pp.919–925", "material": "inspected primary manuscript and figures",
             "inspected_sha256": "f4aca589ea13e3c09999c9fd0a666a14e61ac80a893c5f66e72feb6edc4faade"},
            {"url": "https://pubmed.ncbi.nlm.nih.gov/21779472/",
             "section": "Abstract; Figures 1, 3 and 6", "material": "official primary abstract and figure captions"}],
    },
    "CRC_PIK3CA_AKT_SCOPE": {
        "title": "A pathway result does not resolve each PI3K/Akt isoform",
        "status": "conditions_required", "useful_example": False,
        "summary": "The paper supports PGE2-responsive PI3K/Akt signaling, but this check did not establish isoform-specific PIK3CA→AKT1 and AKT2 experiments.",
        "conditions": ["The main PI3K/Akt perturbation uses wortmannin and Akt/phospho-Akt blots in HEK293T cells (Figure 4B); colon-cell growth assays include DLD-1.",
            "Both source rows report indirect regulation and reuse one paper. BTO:0000586 is a broad colonic-cancer context, not a named cell line."],
        "what_is_not_established": ["Isoform-specific causality from a generic PI3K inhibitor or an Akt readout.",
            "That every experiment in this paper was performed in colorectal cells; exact isoform support remains unconfirmed, rather than labeled false."],
        "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/16293724/",
            "section": "Abstract", "material": "official primary abstract"},
            {"url": "https://doi.org/10.1126/science.1116221",
             "section": "Main article pp.1505–1509; Figures 1 and 4B", "material": "primary article identity; supplementary methods not inspected"},
            {"url": "https://www.academia.edu/18842363/Prostaglandin_E2_Promotes_Colon_Cancer_Cell_Growth_Through_a_Gs_Axin_Catenin_Signaling_Axis",
             "section": "Main article text and Figure 4B caption (p.1508)", "material": "public primary-article copy; text inspected, figure images and supplement not inspected"}],
    },
    "CRC_AXIN_APC_SCOPE": {
        "title": "Axin–APC binding and pathway output have different scopes",
        "status": "limited_material_inspected", "useful_example": False,
        "summary": "The primary abstract reports Axin–APC association and reduced β-catenin after Axin overexpression in SW480 cells. That is more specific than a generic APC activity label.",
        "conditions": ["The reported SW480 result involves Axin overexpression and a β-catenin-level readout.",
            "This check inspected the primary abstract; the publisher's full text was unavailable."],
        "what_is_not_established": ["A separately measured increase in APC activity from the abstract alone.",
            "Universal effects outside the reported cell model; the source binding/effect literals remain unchanged."],
        "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/9734785/",
            "section": "Abstract: Results and Conclusion", "material": "official primary abstract"},
            {"url": "https://doi.org/10.1046/j.1365-2443.1998.00198.x",
             "section": "Primary article identity", "material": "publisher record; full text not inspected"}],
    },
    "BRAF_S614": {
        "title": "An inhibitory phosphorylation example",
        "status": "qualified_example", "useful_example": True,
        "summary": "The study supports inhibitory BRAF S614 autophosphorylation. Phosphorylation does not always mean activation.",
        "conditions": ["Tagged WT and V600E BRAF in HEK293T cells, with PC12 comparisons, isolated kinase assays and NIH3T3 transformation assays.",
            "S614A increased activity; the paper notes that S614D did not fully mimic phosphorylation."],
        "what_is_not_established": ["The same effect in colorectal tissue or patients.",
            "Equivalence between a phosphomimetic mutation and the phosphorylated protein."],
        "sources": [{"url": "https://doi.org/10.1016/j.cellsig.2016.06.016",
            "section": "Results 3.1–3.4; Figures 2–3", "material": "primary manuscript and figures"},
            {"url": "https://www.pure.ed.ac.uk/ws/portalfiles/portal/27024923/Dernayka_Rauch_etal_CellularSignalling_2016_Manuscript.pdf",
             "section": "Accepted manuscript pages 7–9, 11, 17–18", "material": "author manuscript"}],
    },
    "BRAF_P_LOOP": {
        "title": "BRAF inhibition depends on the experimental state",
        "status": "conditions_required", "useful_example": False,
        "summary": "WT BRAF P-loop autophosphorylation can inhibit activity; the cited study contrasts D594G:CRAF heterodimers that bypass this control.",
        "conditions": ["WT BRAF, MEK availability, dimer composition and ATP preincubation matter.",
            "The paper uses engineered HEK293/HEK293T cells and purified proteins; part of the WT mechanism cites earlier work."],
        "what_is_not_established": ["The same inhibition for every BRAF variant or in colorectal cancer.",
            "Independent experiments simply because Ser465 and Ser467 have separate source records."],
        "sources": [{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7039555/",
            "section": "Results: bypass of autoinhibitory phosphorylation; Figure 4; Methods", "material": "primary full text"}],
    },
    "EGFR_COORDINATE_CONVENTION": {
        "title": "EGFR sites use different numbering conventions",
        "status": "coordinate_qualification", "useful_example": False,
        "summary": "ProtMapper already documents the EGFR coordinate shift caused by removal of its 24-residue signal peptide.",
        "conditions": ["Keep the reported paper coordinates and canonical precursor coordinates distinguishable.",
            "Coordinate mapping is separate from whether a paper supports a particular regulatory claim."],
        "what_is_not_established": ["Direct experimental support for every site cited by this source record.",
            "Sequence, isoform or construct equivalence from an accession or coordinate match alone."],
        "sources": [{"url": "https://raw.githubusercontent.com/gyorilab/protmapper/master/protmapper/curated_site_map.csv",
            "section": "P00533 / EGFR curated mappings", "material": "official curated mapping table",
            "inspected_sha256": "78d7fa632a6f00dca93931d4973d48d5da3a11a437cf4c022c6f991f3d20a98f"},
            {"url": "https://reactome.org/content/detail/R-HSA-1247841",
             "section": "Y992/Y1016 signal-peptide explanation", "material": "official source annotation"}],
    },
    "KRAS_REVIEW": {
        "title": "Both KRAS records cite the same review",
        "status": "secondary_literature", "useful_example": False,
        "summary": "The article explicitly describes itself as a review, although its PubMed types list Journal Article without Review.",
        "conditions": ["The article surveys RAS-family effectors and earlier experiments.",
            "Both selected KRAS relations reuse this publication."],
        "what_is_not_established": ["Two independent primary experiments.",
            "CRC, isoform, variant or assay applicability from these source records."],
        "sources": [{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3128635/",
            "section": "Abstract; Introduction; RAS–PI3K discussion", "material": "review full text"}],
    },
    "EGFR_PIK3R1_CITATION_CONTEXT": {
        "title": "This citation needs a source-specific review",
        "status": "needs_review", "useful_example": False,
        "summary": "The cited experiments mainly study p85α regulation of EGFR expression, while this source row reports EGFR→PIK3R1 binding and MCF7/breast context.",
        "conditions": ["The paper uses mouse-derived p85α+/+ and p85α−/− cells, with 293T RNA-IP; the inspected text does not name MCF7.",
            "Upstream EGFR activation of p85 is discussed as prior knowledge, citing another review."],
        "what_is_not_established": ["Primary experimental verification of this row's binding, direction and cell context by this citation.",
            "That EGFR and PIK3R1 cannot interact; this flag identifies a citation/context support gap."],
        "sources": [{"url": "https://www.oncotarget.com/article/7674/text/",
            "section": "Results; Cell culture and transfection; Discussion; reference 41", "material": "primary full text"}],
    },
    "EGFR_PIK3R1_REVIEW": {
        "title": "The binding statement is cited through a review",
        "status": "secondary_literature", "useful_example": False,
        "summary": "The cited ErbB/HER signaling article is indexed as a review.",
        "conditions": ["A co-immunoprecipitation statement repeated in a review is not an additional assay."],
        "what_is_not_established": ["Direct primary experimental status until the underlying experimental citation is checked."],
        "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/14967450/",
            "section": "Abstract; Publication types", "material": "official citation metadata and abstract"}],
    },
    "EGFR_GRK2_ORIGIN": {
        "title": "The site mechanism refers to earlier work",
        "status": "primary_origin_qualification", "useful_example": False,
        "summary": "The selected 2013 sentence describes earlier EGFR→GRK2 work. A 2008 primary paper reports EGF-dependent association and Tyr13/86/92 mutational tests.",
        "conditions": ["Distinguish the earlier site study from the 2013 GRK2/MST2 centrosome study.",
            "Keep the original source PMID and the followed primary origin separate."],
        "what_is_not_established": ["An independent repeat of the site experiment merely because a later paper cites it."],
        "sources": [{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2441682/",
            "section": "EGFR-mediated GRK2 phosphorylation; Figure 4", "material": "followed primary full text"},
            {"url": "https://pubmed.ncbi.nlm.nih.gov/23904266/",
             "section": "Abstract and selected source sentence", "material": "original cited article"}],
    },
    "EGFR_CTNNB1_Y654": {
        "title": "Mutant EGFR and lung models limit this example",
        "status": "limited_material_inspected", "useful_example": False,
        "summary": "The primary abstract emphasizes mutant EGFR, including L858R/T790M, in lung cancer models; the source sentence also includes background WT/FLT3 information.",
        "conditions": ["The audit inspected the official abstract and source sentence, not exact full-text Y654 experiments."],
        "what_is_not_established": ["Exact conditional Y654 support from the abstract alone.",
            "A universal or CRC-specific EGFR→β-catenin effect."],
        "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/25164010/",
            "section": "Abstract", "material": "primary abstract"}],
    },
    "EGFR_CTNNB1_Y142": {
        "title": "A controlled biochemical phosphorylation example",
        "status": "qualified_example", "useful_example": True,
        "summary": "The primary paper reports EGFR-mediated β-catenin Y142 phosphorylation in a cell-free kinase assay.",
        "conditions": ["Recombinant EGFR and β-catenin, with ATP/kinase omission controls (Figure 7C).",
            "The assay used 400 ng of each protein, 50 µM ATP and 60 minutes at 30°C."],
        "what_is_not_established": ["The same downstream response in every cell or in colorectal tissue.",
            "Equivalence between this direct biochemical event and the separate ERK/LRP6/WNT pathway response."],
        "sources": [{"url": "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0035826",
            "section": "Figure 7C; Tyr142 Results section; recombinant RTK kinase Methods", "material": "primary full text"}],
    },
    "EGFR_ERBB2_Y1248": {
        "title": "A stimulated breast-cell model",
        "status": "conditions_required", "useful_example": False,
        "summary": "The cited study examines EGF-induced migration in breast cancer cells and engineered c-erbB-2/EGFR lines, including a Y1248-site mutant.",
        "conditions": ["Breast-cell context, receptor engineering and EGF stimulation are part of the experiment.",
            "This check used the official primary abstract and reported source context."],
        "what_is_not_established": ["The same mechanism or outcome in colorectal cancer."],
        "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/12354693/",
            "section": "Abstract", "material": "primary abstract"}],
    },
    "EGFR_ERBB2_CONSTRUCT": {
        "title": "Kinase-inactive EGFR is part of the experiment",
        "status": "conditions_required", "useful_example": False,
        "summary": "Experiments include EGFR K721M coexpressed with ErbB2 in ErbB-devoid 32D cells; signaling in this setup did not require EGFR kinase activity.",
        "conditions": ["Retain receptor construct, coexpression and EGF stimulation conditions.",
            "Participant taxon and experimental host are separate facts; this check used the primary abstract."],
        "what_is_not_established": ["A universal requirement for EGFR kinase activity to activate ERBB2.",
            "CRC applicability from the generic binding/up-regulation record."],
        "sources": [{"url": "https://pubmed.ncbi.nlm.nih.gov/11279155/",
            "section": "Abstract", "material": "primary abstract"}],
    },
}

_PROJECTED_FIELDS = {
    "effect_literal": "EFFECT", "mechanism_literal": "MECHANISM", "direct_literal": "DIRECT",
    "cell_context_raw": "CELL_DATA", "tissue_context_raw": "TISSUE_DATA", "residue_raw": "RESIDUE",
    "sequence_raw": "SEQUENCE", "supporting_sentence_raw": "SENTENCE",
}
_EGFR_MAPPINGS = {"Tyr1016": "Y992 → Y1016", "Tyr1197": "Y1173 → Y1197", "Tyr1069": "Y1045 → Y1069",
    "Tyr869": "Y845 → Y869", "Tyr1110": "Y1086 → Y1110", "Tyr1092": "Y1068 → Y1092"}


def _not_examined(reason):
    return {"format": FORMAT, "status": "not_examined", "reason": reason, "audit_kind": AUDIT_KIND,
        "human_reviewed": False, "novel_discovery": False, "biologically_validated": False,
        "notes": [], "interpretation": "No matching project literature check is attached; this is not a clearance or a judgment that the relation is false."}


def _binding(observation, pin):
    pmid, ordinal, row_sha, _ = pin
    raw, source = observation.get("source_row"), observation.get("source")
    if not (isinstance(raw, dict) and set(raw) == set(COLUMNS)
            and all(isinstance(value, str) for value in raw.values())
            and digest(raw) == row_sha and raw["SIGNOR_ID"] == observation.get("source_record_id")
            and raw["PMID"] == pmid and observation.get("publications") == ["PMID:" + pmid]
            and observation.get("source_kind") == "signor" and observation.get("source_release") == SOURCE_RELEASE
            and isinstance(source, dict) and source.get("kind") == "signor"
            and source.get("release") == SOURCE_RELEASE and source.get("url") == SOURCE_URL
            and type(observation.get("source_data_record_ordinal")) is int
            and observation["source_data_record_ordinal"] == ordinal
            and observation.get("products") == ["UniProtKB:" + raw["IDA"], "UniProtKB:" + raw["IDB"]]
            and all(observation.get(field) == raw[column] for field, column in _PROJECTED_FIELDS.items())
            and type(observation.get("source_reported_direct")) is bool
            and raw["DIRECT"] in {"t", "f"} and observation["source_reported_direct"] == (raw["DIRECT"] == "t")
            and type(observation.get("self_regulation")) is bool
            and observation["self_regulation"] == (raw["IDA"] == raw["IDB"])):
        return None
    locators = observation.get("source_locators")
    if not isinstance(locators, list):
        return None
    original = [item for item in locators if isinstance(item, dict)
                and item.get("role") == "original_source_data_record"]
    allowed = {prefix + "source/Oct2026_release.txt#data-record=" + str(ordinal)
               for prefix in ("", "extension_sources/signor/")}
    if not (len(original) == 1 and original[0].get("file_sha256") == SOURCE_SHA256
            and original[0].get("locator") in allowed):
        return None
    return {"source_release": SOURCE_RELEASE, "raw_source_sha256": SOURCE_SHA256,
        "source_record_id": raw["SIGNOR_ID"], "pmid": pmid,
        "source_data_record_ordinal": ordinal, "source_row_sha256": row_sha,
        "source_locator": original[0]["locator"]}


def case_notes(observation):
    """Return fresh project notes only for an exact inspected source observation.

    The caller's verified source observation is never edited. A matching source
    file digest and complete raw-row/literal agreement bind this annotation to
    the inspected release; this function does not authenticate a publication.
    """
    if not isinstance(observation, dict) or not isinstance(observation.get("source_record_id"), str):
        return _not_examined("No inspected source record identity.")
    pin = _ROW_PINS.get(observation["source_record_id"])
    if pin is None:
        return _not_examined("This source record is outside the fixed literature walkthrough.")
    binding = _binding(observation, pin)
    if binding is None:
        return _not_examined("Source version, publication or checked literals differ from the inspected record.")
    note = deepcopy(_CASES[pin[3]])
    note.update(qualification_flag=pin[3], audit_kind=AUDIT_KIND, audit_date=AUDIT_DATE,
        human_reviewed=False, novel_discovery=False, biologically_validated=False,
        source_binding=deepcopy(binding), paper_rights="Original publication rights are retained; this is a short project paraphrase.")
    note["audit_scope"] = ("all_exact_crc_model_context_matches.v1" if pin[3].startswith("CRC_")
        else "fixed_egfr_braf_kras_records.v1")
    if pin[3] == "EGFR_COORDINATE_CONVENTION":
        note["documented_mapping"] = _EGFR_MAPPINGS.get(observation["residue_raw"])
        if note["documented_mapping"] is None:
            note["mapping_scope"] = "No exact mapping for this row was confirmed in the inspected curated table; no coordinate is inferred."
        pmid, residue = binding["pmid"], observation["residue_raw"]
        note["sources"].append({"url": "https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/",
            "section": "Abstract and selected source sentence", "material": "original cited article"})
        if pmid == "10653583":
            note["site_support_scope"] = ("The abstract explicitly studies the corresponding Y992/Y1173 sites. This is not full experimental adjudication."
                if residue in {"Tyr1016", "Tyr1197"} else
                "This audit did not establish exact support for this additional site in the cited paper; coordinate agreement alone is insufficient.")
            note["sources"].append({"url": "https://pubmed.ncbi.nlm.nih.gov/28651473/",
                "section": "Linked 2017 corrigendum", "material": "publication notice"})
        else:
            note["site_support_scope"] = "The selected source sentence uses Y1045, mapped here to precursor Y1069; the paper's Cbl/downregulation context remains distinct from a generic activity label."
    return {"format": FORMAT, "status": "examined_with_qualifications", "audit_kind": AUDIT_KIND,
        "audit_date": AUDIT_DATE, "human_reviewed": False, "novel_discovery": False,
        "biologically_validated": False, "source_binding": binding, "notes": [note],
        "interpretation": "Project literature qualifications supplement the saved source claim. They are not an independent truth label or a local review decision."}
