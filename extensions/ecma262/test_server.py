#!/usr/bin/env vpython3
import unittest
import json
import os
import sys

# Ensure the current directory is in the path so we can import server
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import server

class TestEcma262Server(unittest.TestCase):
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
        results_json = server.search_spec("Completion")
        try:
            results = json.loads(results_json)
        except json.JSONDecodeError:
            self.fail(f"search_spec did not return valid JSON. Output was: {results_json}")
            
        self.assertTrue(len(results) > 0)
        # Verify first result has expected fields
        first = results[0]
        self.assertIn('id', first)
        self.assertIn('title', first)
        self.assertIn('type', first)

    def test_get_section_content(self):
        result_json = server.get_section_content("sec-completion-ao")
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            self.fail(f"get_section_content did not return valid JSON. Output was: {result_json}")
            
        self.assertIn('content', result)
        self.assertTrue(result['content'].startswith("<emu-clause id=\"sec-completion-ao\""))

    def test_get_ancestry(self):
        result_json = server.get_ancestry("sec-completion-ao")
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            self.fail(f"get_ancestry did not return valid JSON. Output was: {result_json}")
            
        self.assertIn('ancestry', result)
        self.assertTrue(len(result['ancestry']) > 0)
        # Verify structure
        first = result['ancestry'][0]
        self.assertIn('id', first)
        self.assertIn('title', first)

    def test_get_operation_signature(self):
        result_json = server.get_operation_signature("Completion")
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            self.fail(f"get_operation_signature did not return valid JSON. Output was: {result_json}")
            
        self.assertIn('signature', result)
        self.assertIn('parameters', result['signature'])

    def test_get_operation_algorithm(self):
        result = server.get_operation_algorithm("ToObject")
        self.assertIsInstance(result, str)
        self.assertTrue("TypeError" in result)

if __name__ == '__main__':
    unittest.main()
