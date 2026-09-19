import json
import re
import unittest
from pathlib import Path

class TestWordPressSTS1Attribution(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).parent.parent
        self.js_path = self.repo_root / 'deploy' / 'wordpress' / 'budly-sales-agent' / 'assets' / 'budly-sales.js'
        self.tracking_php = self.repo_root / 'deploy' / 'wordpress' / 'budly-sales-agent' / 'includes' / 'tracking.php'
        self.decision_php = self.repo_root / 'deploy' / 'wordpress' / 'budly-sales-agent' / 'includes' / 'SecureMemory' / 'Decision' / 'DecisionService.php'

    def test_js_attribution_parameters_present(self):
        content = self.js_path.read_text(encoding='utf-8')
        for param in ['source', 'platform', 'content_id', 'campaign_id', 'cta_id', 'product_or_topic', 'published_post_id']:
            self.assertIn(f"'{param}'", content, f"Expected {param} in budly-sales.js query parser")
        self.assertIn("action:'budly_sales_track'", content)
        self.assertIn("attribution:state.attribution", content)
        self.assertIn("payload.attribution=state.attribution", content)

    def test_js_sanitization_rules(self):
        # Python mirror of sanitizeParam: val.trim().slice(0, maxLen).replace(/[^a-zA-Z0-9_\-\.:\/]/g, '')
        def sanitize_param(val, max_len=120):
            if not val or not isinstance(val, str):
                return ''
            val = val.strip()[:max_len]
            return re.sub(r'[^a-zA-Z0-9_\-\.:\/]', '', val)

        # Test length truncation
        long_val = 'a' * 200
        self.assertEqual(len(sanitize_param(long_val, 64)), 64)
        self.assertEqual(len(sanitize_param(long_val, 100)), 100)

        # Test character stripping (XSS / SQL injection attempt)
        malicious = "social'; DROP TABLE users; <script>alert(1)</script>"
        sanitized = sanitize_param(malicious)
        self.assertEqual(sanitized, 'socialDROPTABLEusersscriptalert1/script')

    def test_php_tracking_attribution_capture(self):
        content = self.tracking_php.read_text(encoding='utf-8')
        self.assertIn("$attr_fields = array('source', 'platform', 'content_id', 'campaign_id', 'cta_id', 'product_or_topic', 'published_post_id');", content)
        self.assertIn("$meta_arr['attribution'] = $clean_attr;", content)

    def test_php_decision_attribution_audit(self):
        content = self.decision_php.read_text(encoding='utf-8')
        self.assertIn("$inputs_data['attribution']=$clean_attribution;", content)
        self.assertIn("$audit_metadata['attribution']=$clean_attribution;", content)
        self.assertIn("$res['attribution']=$clean_attribution;", content)

if __name__ == '__main__':
    unittest.main()
