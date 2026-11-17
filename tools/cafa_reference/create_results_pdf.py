"""Render a short delivery addendum from sealed aggregate results only."""
from pathlib import Path
import hashlib
import json

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                               TableStyle, PageBreak, Image)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf/BioGraph_Steward_Scientific_Update_20261114.pdf'
NAVY = colors.HexColor('#143449')
TEAL = colors.HexColor('#237576')
GRAY = colors.HexColor('#4b5b65')
PALE = colors.HexColor('#edf5f5')
RULE = colors.HexColor('#d7e1e6')
styles = {
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=23,
                            leading=27, textColor=NAVY, spaceAfter=8),
    'sub': ParagraphStyle('sub', fontName='Helvetica', fontSize=10,
                          leading=14, textColor=GRAY, spaceAfter=13),
    'h': ParagraphStyle('h', fontName='Helvetica-Bold', fontSize=12.5,
                        leading=16, textColor=NAVY, spaceBefore=13, spaceAfter=7),
    'p': ParagraphStyle('p', fontName='Helvetica', fontSize=9.5,
                        leading=13.1, textColor=NAVY, spaceAfter=7),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8,
                            leading=10.7, textColor=GRAY, spaceAfter=6),
    'cell': ParagraphStyle('cell', fontName='Helvetica', fontSize=8.5,
                           leading=11, textColor=NAVY),
    'head': ParagraphStyle('head', fontName='Helvetica-Bold', fontSize=8,
                           leading=10, textColor=NAVY),
}


def p(text, style='p'):
    return Paragraph(text, styles[style])


def table(rows, widths):
    prepared = [[p(str(cell), 'head' if i == 0 else 'cell') for cell in row]
                for i, row in enumerate(rows)]
    result = Table(prepared, colWidths=widths, hAlign='LEFT', repeatRows=1)
    result.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PALE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, 0), .6, RULE),
        ('LINEBELOW', (0, 1), (-1, -1), .3, RULE),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return result


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.line(40, 35, 572, 35)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(40, 23, 'BioGraph Steward | Scientific delivery addendum | 14 November 2026')
    canvas.drawRightString(572, 23, str(doc.page))
    canvas.restoreState()


def main():
    source = ROOT / 'docs/evaluations/biored_source_relations_20261114_summary.json'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == '25cbdf3de5b621b70867065a59bff7cb8c2865a00ce7d748c6e098d3c3ba016c'
    agent = json.loads(source.read_text())
    primary = agent['reports']['primary']['report']
    gene = agent['reports']['gene']['report']
    assert primary['test_cases'] == 128 and gene['cases'] == 16489
    labels = {
        'always_None': 'Always no relation',
        'typed_co_mention': 'Typed co-mention',
        'specialist_native': 'Published specialist',
        'specialist_type_guard': 'Specialist + type guard',
        'flat_context_LLM': 'Flat-context NVIDIA LLM',
        'source_audit_agent': 'NVIDIA source-audit agent',
    }
    rows = [['Source-relation method', 'Exact accuracy', 'Positive relation F1', 'Unresolved']]
    for key, label in labels.items():
        m = primary['metrics'][key]
        rows.append([label, f"{m['exact_accuracy']:.1%}",
                     f"{m['exact_positive_relation']['f1']:.3f}", m['unresolved']])
    story = [
        p('Measured gains, qualified evidence', 'title'),
        p('BioGraph Steward | A public-reference evaluation and an inspectable product increment', 'sub'),
        p('<b>What improved:</b> restoring historical Pharos context lost by the earlier scoped retrieval improved recovery of later curated protein functions. The resulting model context is now available for source inspection in the app. A published specialist also gives us a stronger baseline for checking literature claims.'),
        p('Controlled protein-function comparison', 'h'),
        p('Official CAFA5 v2 future GO annotations; unchanged published evaluator and prediction methods. Biological process: 833 eligible proteins, or 832 for the information-weighted readout. Predictions were sealed before the future term labels were decoded. Newer GOA had previously been inspected: historical inputs were enforced, but this is not wholly developer-blind.'),
        table([
            ['Historical source / method', 'Micro Fmax', 'IA micro', 'Macro', 'IA macro'],
            ['Original scoped LocalPlus', '0.121787', '0.110311', '0.156162', '0.157396'],
            ['Original FastSinkSource+ (primary)', '0.116413', '0.109560', '0.147643', '0.145631'],
            ['Original GeneMANIA+ (secondary)', '0.129942', '0.120481', '0.157908', '0.155240'],
            ['Full historical LocalPlus, strict source', '0.135290', '0.130017', '0.157304', '0.155505'],
        ], [220, 78, 78, 78, 78]),
        Spacer(1, 10),
        p('<b>Two bounded positive results.</b> Same-graph GeneMANIA+ improves micro-Fmax by <b>0.00816</b> (paired 95% interval 0.00106 to 0.01540). Fuller strict-source LocalPlus improves it by <b>0.01350</b>, about <b>11.1% relative</b> (0.00727 to 0.02121). The primary FSS candidate did not win. These are secondary, descriptive comparisons, without portfolio-wide multiplicity adjustment.'),
        p('The context comparison changes available training seeds, source coverage and source qualification. It repairs our scoped retrieval; it does not show superiority over the complete original Pharos graph. IA-macro declines slightly. At fixed cutoff 0.5, precision rises from 0.172 to 0.300, but recall falls from 0.037 to 0.027 and F1 from 0.061 to 0.050.'),
        p('Transfer and pruning: limits that change the decision', 'h'),
        p('<b>Additional protein cohort:</b> 2,826 eligible proteins outside the old scope; full LocalPlus reaches 0.139968, above full FSS (0.131961), ProtT5 neighbors (0.066423) and the non-experimental annotation control (0.091528). All three paired difference intervals exclude zero. Strict-source sensitivity is 0.139966. This is same-study transductive transfer.'),
        p('<b>Lower-prior-knowledge checks:</b> across the six no-/limited-knowledge GO tasks, strong native controls lead five point estimates. Neither graph method establishes a BPO gain over the non-experimental control. Three fixed pruning views show no reliable BPO improvement; automatic biological pruning is not promoted.'),
        p('<b>Metric key.</b> Fmax is the best F1 on the official threshold grid, not percent scientific accuracy. IA weights informative terms; micro pools annotations, macro averages proteins. Intervals resample proteins and are conditional on shared source data. Missing curator support is not a biological negative.', 'small'),
        p('Methods and reference: <link href="https://zenodo.org/records/22381862" color="#237576">CAFA5 v2</link>; <link href="https://doi.org/10.1093/bioadv/vbae043" color="#237576">CAFA evaluator</link>; <link href="https://doi.org/10.1093/bioinformatics/btaa885" color="#237576">FastSinkSource / published baselines</link>. Full denominators, failures, 240 PK outcome slots and separate NK/LK results are retained in the linked repository report.', 'small'),
        PageBreak(),
        p('Evidence accuracy and actual agent use', 'title'),
        p('A source-relative test with expert BioRED / BioCreative VIII relation labels', 'sub'),
        p('A fixed 128-publication sample tests one candidate pair per publication. All predictions were sealed before its labels were opened. The NVIDIA agent could read the abstract, entity mentions and published specialist output through three bounded tools. The flat LLM received the same information. Unresolved answers count as errors. None means no qualifying relation in the abstract.'),
        table(rows, [252, 95, 110, 75]),
        Spacer(1, 9),
        p('<b>Decision:</b> keep the agent experimental. It made 512 model calls versus 128 for flat context, always reading the same three tools in the same order. Its small advantage over flat context is uncertain; its exact-accuracy difference from the specialist is -20.3 percentage points (95% interval -28.1 to -12.5). Valid tool calls did not produce better factual judgments.'),
        p('<b>Larger specialist check:</b> 16,489 gene-involving pairs from 374 publications yield 85.97% exact accuracy and positive-relation F1 0.600 (publication-cluster interval 0.570 to 0.628). Pair-detection F1 is 0.788. Errors include 924 unsupported pair calls, 678 misses and 711 wrong types. Native Bind recall is 38/124; Bind need not mean direct physical binding. The agent sample has no positive Bind cases. Gold entity mentions are supplied. This measures source-relative agreement, not whole-Pharos truth; checkpoint training membership is not independently audited.'),
        p('What reviewers can now inspect', 'h'),
    ]
    screenshot = ROOT / 'docs/images/HOSTED_FUNCTION_CONTEXT_20261114.png'
    width, height = ImageReader(str(screenshot)).getSize()
    picture = Image(str(screenshot), width=171, height=171*height/width)
    right = [
        p('<b>Saved historical context:</b> six queries, 36 displayed hypotheses, raw STRING pair weights, neighbor contributions and training terms. The strict model uses 20,412 proteins and 985,863 qualified weighted pairs.'),
        p('<b>Interpretation safeguards:</b> 12 displayed concepts already occur literally in the broader pre-t0 control; four historical terms are now obsolete. Separate ontology versions and record-level reuse stay visible. Scores are hypotheses, not accepted GO annotations or physical interactions.'),
        p('<b>Operational use:</b> private AWS reviewer site; saved inspection needs no Brev model or GPU. The historical model stays separate from the 99-target source workspace. Original answers can take one to two minutes on a cold load.'),
        p('Actual hosted function inspector at left. Full tables, methods, sources and reproduction instructions: <b>docs/evaluations/SCIENTIFIC_RESULTS_20261114.md</b>.', 'small'),
    ]
    grid = Table([[picture, right]], colWidths=[187, 345], hAlign='LEFT')
    grid.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),0), ('RIGHTPADDING',(0,0),(0,0),16)]))
    story += [grid]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=(612, 792), rightMargin=40,
                            leftMargin=40, topMargin=37, bottomMargin=45,
                            title='BioGraph Steward - Scientific Update, 14 November 2026',
                            author='BioGraph Steward team', pageCompression=1)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == '__main__':
    main()
