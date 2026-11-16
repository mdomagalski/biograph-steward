"""Production review keeps real graph changes while excluding development controls."""
from html.parser import HTMLParser
import unittest

from biograph_steward.webapp import report_html


class Panels(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.parents = []
        self.development = set()
        self.ids = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        dev = 'data-development-view' in attrs or any(self.parents)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
            if dev:
                self.development.add(attrs['id'])
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.parents.append(dev)

    def handle_endtag(self, tag):
        if self.parents:
            self.parents.pop()


class ProductReviewViewsTests(unittest.TestCase):
    def test_saved_review_hides_only_development_controls_and_keeps_product_tasks(self):
        html = report_html(saved_data_only=True)
        panels = Panels(html)
        self.assertIn('body[data-saved-data-only="true"] [data-development-view]', html)
        self.assertTrue({'comparisonResearchHistory', 'comparisonPruningControls',
                         'scientificAssessmentHistory', 'neptunePanel'} <= panels.development)
        for item in ('workspaceTabCompare', 'appliedQualificationPanel', 'scientificAssessmentBody',
                     'sourceAgentPanel', 'sourceGuide', 'workspaceProvenance', 'savedWorkPanel', 'constructionPublication',
                     'workspaceDownloads', 'downloadZip'):
            self.assertIn(item, panels.ids)
            self.assertNotIn(item, panels.development)
        self.assertIn('Graph changes and assessment', html)
        self.assertIn('initializeWorkspaceAssessments();', html)

    def test_operator_page_retains_research_controls_without_saved_mode_hiding(self):
        html = report_html()
        self.assertNotIn('body[data-saved-data-only="true"] [data-development-view]', html)
        self.assertIn('Research history &amp; earlier methods', html)
        self.assertIn('id="comparisonPruningControls"', html)
        self.assertIn('id="scientificAssessmentHistory"', html)


if __name__ == '__main__':
    unittest.main()
