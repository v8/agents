#!/usr/bin/env vpython3
import unittest
import json
import os
import sys

# Ensure the current directory is in the path so we can import server
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import server

class TestEcma262Server(unittest.TestCase):
    def tearDown(self):
        server.ACTIVE_PROPOSAL = None

    def test_get_ast_simple(self):
        code = "const a = 1;"
        ast_json = server.ecma262_parse(code)
        
        # Verify it is valid JSON
        try:
            ast = json.loads(ast_json)
        except json.JSONDecodeError:
            self.fail(f"ecma262_parse did not return valid JSON. Output was: {ast_json}")
            
        # Verify expected structure (Babel returns File node at top level)
        self.assertEqual(ast.get('type'), 'File')
        self.assertIn('program', ast)
        program = ast['program']
        self.assertEqual(program.get('type'), 'Program')
        self.assertTrue(len(program.get('body', [])) > 0)
        
    def test_get_ast_error(self):
        code = "const a = ;" # Invalid JS
        result = server.ecma262_parse(code)
        self.assertTrue(result.startswith("Error parsing JS:"), f"Expected error message, got: {result}")

    def test_search_spec(self):
        result = server.search_spec("Completion")
        self.assertIsInstance(result, str)
        self.assertIn("# Search Results for \"Completion\"", result)
        self.assertIn("sec-completion-record", result)

    def test_get_section_content(self):
        result = server.get_section_content("sec-completion-ao")
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("# Completion"))
        self.assertIn("1. Assert: _completionRecord_ is a Completion Record.", result)
        # Ensure raw HTML tags are NOT present
        self.assertNotIn("<emu-clause", result)
        self.assertNotIn("<emu-alg>", result)

    def test_get_ancestry(self):
        result = server.get_ancestry("sec-completion-ao")
        self.assertIsInstance(result, str)
        self.assertIn("# Ancestry for `sec-completion-ao`", result)
        self.assertIn("sec-notational-conventions", result)

    def test_get_operation_signature(self):
        result = server.get_operation_signature("Completion")
        self.assertIsInstance(result, str)
        self.assertIn("# Signature: Completion", result)
        self.assertIn("Completion ( _completionRecord_: a Completion Record ): a Completion Record", result)

    def test_get_operation_algorithm(self):
        result = server.get_operation_algorithm("ToObject")
        self.assertIsInstance(result, str)
        self.assertIn("# ToObject", result)
        self.assertTrue("TypeError" in result)

    def test_get_operation_algorithm_host_defined(self):
        result = server.get_operation_algorithm("HostEnsureCanAddPrivateElement")
        self.assertIsInstance(result, str)
        self.assertTrue("HostEnsureCanAddPrivateElement" in result)
        self.assertTrue("host-defined exotic object" in result)
        self.assertIn(r"\~unused\~", result)
        # Verify rendered as markdown list
        self.assertIn("- If _obj_ is not a host-defined exotic object", result)

    def test_user_code_annotation(self):
        result = server.get_operation_algorithm("Get")
        self.assertIsInstance(result, str)
        self.assertIn("⚡", result)
        self.assertIn("_obj_.[[Get]]", result)

    def test_get_operation_callers(self):
        result = server.get_operation_callers("PrivateFieldAdd")
        self.assertIsInstance(result, str)
        self.assertIn("sec-definefield", result)
        self.assertIn("Perform ? PrivateFieldAdd", result)

    def test_section_hash_handling(self):
        res1 = server.get_section_content("#sec-completion-ao")
        self.assertIn("Completion", res1)

        res2 = server.get_operation_signature("ToObject")
        self.assertIn("ToObject ( _arg_:", res2)

    def test_all_spec_html_tags_handled(self):
        """Validates that every single HTML/Ecmarkup tag present in spec.html is explicitly handled."""
        HANDLED_TAGS = {
            'a', 'b', 'body', 'br', 'code', 'dd', 'dfn', 'div', 'dl', 'dt', 'em',
            'emu-alg', 'emu-annex', 'emu-clause', 'emu-concrete-method-dfns', 'emu-eqn',
            'emu-figure', 'emu-grammar', 'emu-import', 'emu-intro', 'emu-meta', 'emu-not-ref',
            'emu-note', 'emu-prodref', 'emu-table', 'emu-val', 'emu-xref', 'figure',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'head', 'html', 'i', 'img', 'ins', 'del',
            'li', 'link', 'meta', 'ol', 'p', 'pre', 'span', 'strong', 'style', 'sub',
            'sup', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul', 'var'
        }
        
        spec_path = server.SPEC_PATH
        self.assertTrue(os.path.exists(spec_path), f"spec.html not found at {spec_path}")
        
        import re
        with open(spec_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tags_in_doc = set(m.lower() for m in re.findall(r'<([a-zA-Z][a-zA-Z0-9-]*)[>\s/]', content))
        
        unhandled = tags_in_doc - HANDLED_TAGS
        self.assertEqual(len(unhandled), 0, f"Found unhandled tags in spec.html: {unhandled}")

    def test_sanitize_tc39_proposal_name(self):
        # Valid names
        self.assertEqual(server.sanitize_tc39_proposal_name("explicit-resource-management"), "explicit-resource-management")
        self.assertEqual(server.sanitize_tc39_proposal_name("proposal-temporal"), "temporal")
        self.assertEqual(server.sanitize_tc39_proposal_name("tc39/decorators"), "decorators")
        self.assertEqual(server.sanitize_tc39_proposal_name("https://tc39.es/proposal-float16array/"), "float16array")
        self.assertEqual(server.sanitize_tc39_proposal_name("https://github.com/tc39/proposal-shadowrealm"), "shadowrealm")

        # Invalid / non-TC39 names (security check)
        with self.assertRaises(ValueError):
            server.sanitize_tc39_proposal_name("")
        with self.assertRaises(ValueError):
            server.sanitize_tc39_proposal_name("../../etc/passwd")
        with self.assertRaises(ValueError):
            server.sanitize_tc39_proposal_name("evil.com/payload")
        with self.assertRaises(ValueError):
            server.sanitize_tc39_proposal_name("other-org/some-prop")

    def test_proposal_load_diff_and_query(self):
        # Load explicit-resource-management proposal
        load_res = server.load_proposal("explicit-resource-management")
        self.assertIn("# Loaded TC39 Proposal: `explicit-resource-management`", load_res)
        self.assertIn("Abstract Operations Indexed:", load_res)

        # List proposals
        list_res = server.list_proposals()
        self.assertIn("explicit-resource-management", list_res)
        self.assertIn("(ACTIVE)", list_res)

        # Query proposal-specific operation (NewDisposeCapability)
        op_res = server.get_operation_algorithm("NewDisposeCapability")
        self.assertIn("NewDisposeCapability", op_res)
        self.assertIn("**Context:** `explicit-resource-management`", op_res)

        # Diff an operation modified by the proposal
        diff_res = server.diff_operation("InitializeReferencedBinding")
        self.assertIn("Diff Comparison: `InitializeReferencedBinding`", diff_res)
        self.assertIn("Proposal Version", diff_res)
        self.assertIn("Base ECMA-262 Version", diff_res)

        # Switch back to base
        use_res = server.use_proposal("base")
        self.assertIn("# Active Context: Base ECMA-262", use_res)


if __name__ == '__main__':
    unittest.main()
