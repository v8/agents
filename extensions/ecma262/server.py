#!/usr/bin/env vpython3
# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""ECMA-262 Specification Research MCP server."""

from __future__ import annotations
import subprocess
import os
import json
import re
import sys
import importlib
from mcp.server import fastmcp

mcp = fastmcp.FastMCP('ecma262')

DATA_DIR = os.path.expanduser('~/.local/share/ecma262-mcp')
SPEC_PATH = os.path.join(DATA_DIR, 'ecma262', 'spec.html')
DATA_PATH = os.path.join(DATA_DIR, 'ecma262', 'spec_data.json')
TOOLS_SCRIPT = os.path.join(os.path.dirname(__file__), 'ecma262.js')


def ensure_spec_data():
  import filecmp
  import shutil
  import os
  npm_available = shutil.which('npm') is not None

  # Ensure base data directory exists
  if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

  spec_dir = os.path.dirname(SPEC_PATH)
  if not os.path.exists(spec_dir):
    os.makedirs(spec_dir, exist_ok=True)

  BIBLIO_PATH = os.path.join(spec_dir, 'biblio.json')
  TMP_SPEC_PATH = SPEC_PATH + '.tmp'

  def _install_node_modules():
    sys.stderr.write("Installing ecmarkup, jsdom, and @babel/parser...\n")
    try:
      subprocess.run([
          'npm', 'install', '--prefix', DATA_DIR, 'ecmarkup', 'jsdom',
          '@babel/parser'
      ],
                     check=True,
                     capture_output=True)
      sys.stderr.write("Installation successful.\n")
    except subprocess.CalledProcessError as e:
      sys.stderr.write(
          f"Error installing node modules: {e.stderr.decode() if e.stderr else str(e)}\n"
      )
      raise

  # Ensure node_modules exists in DATA_DIR
  node_modules_path = os.path.join(DATA_DIR, 'node_modules')
  if not os.path.exists(node_modules_path):
    if not npm_available:
      sys.stderr.write(
          "Error: 'npm' is not available in PATH and node_modules is missing.\n"
      )
      sys.stderr.write(
          "Please install npm or make it available in PATH to download dependencies.\n"
      )
      raise RuntimeError("npm not found")
    _install_node_modules()
  else:
    # Check if ecmarkup and jsdom are actually present
    if not os.path.exists(os.path.join(node_modules_path, 'ecmarkup')) or \
       not os.path.exists(os.path.join(node_modules_path, 'jsdom')) or \
       not os.path.exists(os.path.join(node_modules_path, '@babel/parser')):
      sys.stderr.write("Required node modules missing. Re-installing...\n")
      if not npm_available:
        sys.stderr.write(
            "Error: 'npm' is not available in PATH and required modules are missing.\n"
        )
        raise RuntimeError("npm not found")
      _install_node_modules()

    # Run npm update with --prefix to keep them fresh, but only once a day
    import time
    last_update_file = os.path.join(DATA_DIR, '.last_npm_update')
    need_update = True

    if os.path.exists(last_update_file):
      try:
        with open(last_update_file, 'r') as f:
          last_update_time = float(f.read().strip())
        # 1 day = 86400 seconds
        if time.time() - last_update_time < 86400:
          need_update = False
          sys.stderr.write(
              "Node modules were updated less than a day ago. Skipping update.\n"
          )
      except Exception as e:
        sys.stderr.write(f"Error reading last update time: {e}\n")

    if need_update:
      if not npm_available:
        sys.stderr.write(
            "Warning: 'npm' is not available in PATH. Skipping update.\n")
      else:
        sys.stderr.write("Updating node modules...\n")
        try:
          subprocess.run(['npm', 'update', '--prefix', DATA_DIR],
                         check=True,
                         capture_output=True)
          sys.stderr.write("Update successful.\n")
          try:
            with open(last_update_file, 'w') as f:
              f.write(str(time.time()))
          except Exception as e:
            sys.stderr.write(f"Error saving last update time: {e}\n")
        except subprocess.CalledProcessError as e:
          sys.stderr.write(
              f"Error updating node modules: {e.stderr.decode() if e.stderr else str(e)}\n"
          )
          # We don't raise here to allow offline usage if update fails but modules exist

  spec_changed = False

  # 1. Fetch spec.html and compare
  sys.stderr.write("Checking for spec updates from GitHub...\n")
  import urllib.request
  url = "https://raw.githubusercontent.com/tc39/ecma262/main/spec.html"
  try:
    urllib.request.urlretrieve(url, TMP_SPEC_PATH)

    if not os.path.exists(SPEC_PATH):
      os.rename(TMP_SPEC_PATH, SPEC_PATH)
      spec_changed = True
    else:
      if not filecmp.cmp(SPEC_PATH, TMP_SPEC_PATH, shallow=False):
        sys.stderr.write("Spec has changed. Updating...\n")
        os.rename(TMP_SPEC_PATH, SPEC_PATH)
        spec_changed = True
      else:
        sys.stderr.write("Spec is up to date.\n")
        os.remove(TMP_SPEC_PATH)
  except Exception as e:
    sys.stderr.write(f"Error checking/downloading spec: {e}\n")
    if not os.path.exists(SPEC_PATH):
      raise  # Fail if we don't even have a cached version

  # Download supporting files if spec changed or if they are missing
  supporting_files = [
      "table-nonbinary-unicode-properties.html",
      "table-binary-unicode-properties.html",
      "table-binary-unicode-properties-of-strings.html"
  ]

  for f in supporting_files:
    f_path = os.path.join(spec_dir, f)
    if spec_changed or not os.path.exists(f_path):
      sys.stderr.write(f"Downloading supporting file {f}...\n")
      f_url = f"https://raw.githubusercontent.com/tc39/ecma262/main/{f}"
      try:
        urllib.request.urlretrieve(f_url, f_path)
        sys.stderr.write(f"Downloaded {f} successfully.\n")
      except Exception as e:
        sys.stderr.write(f"Error downloading {f}: {e}\n")
        raise

  # 2. Check if we need to rebuild biblio.json
  need_biblio = spec_changed or not os.path.exists(BIBLIO_PATH)
  if not need_biblio and os.path.getmtime(SPEC_PATH) > os.path.getmtime(
      BIBLIO_PATH):
    need_biblio = True

  if need_biblio:
    sys.stderr.write("Running ecmarkup to generate biblio.json...\n")
    out_html_path = os.path.join(spec_dir, 'out.html')
    try:
      # Use npx to run ecmarkup from local node_modules in DATA_DIR
      subprocess.run([
          'npx', 'ecmarkup', '--write-biblio', BIBLIO_PATH, SPEC_PATH,
          out_html_path
      ],
                     cwd=DATA_DIR,
                     check=True,
                     capture_output=True)
      sys.stderr.write("biblio.json generated successfully.\n")
      if os.path.exists(out_html_path):
        os.remove(out_html_path)
    except subprocess.CalledProcessError as e:
      sys.stderr.write(
          f"Error running ecmarkup: {e.stderr.decode() if e.stderr else str(e)}\n"
      )
      raise

  # 3. Check if we need to run preparse_spec.js
  need_preparse = need_biblio or not os.path.exists(DATA_PATH)
  if not need_preparse and os.path.getmtime(BIBLIO_PATH) > os.path.getmtime(
      DATA_PATH):
    need_preparse = True

  if need_preparse:
    sys.stderr.write(
        "Running preparse step via ecma262.js to generate spec_data.json...\n")
    try:
      # Pass DATA_DIR and NODE_PATH to ecma262.js
      env = os.environ.copy()
      env['ECMABOT_DATA_DIR'] = DATA_DIR
      env['NODE_PATH'] = os.path.join(DATA_DIR, 'node_modules')
      input_data = json.dumps({"action": "preparse"})
      subprocess.run(['node', TOOLS_SCRIPT],
                     input=input_data,
                     text=True,
                     check=True,
                     capture_output=True,
                     env=env)
      sys.stderr.write("Regeneration successful.\n")
    except subprocess.CalledProcessError as e:
      sys.stderr.write(
          f"Error regenerating spec data: {e.stderr.decode() if e.stderr else str(e)}\n"
      )
      raise


ensure_spec_data()

with open(DATA_PATH, 'r') as f:
  SPEC_DATA = json.load(f)

OPS = SPEC_DATA.get('ops', {})
STEPS = SPEC_DATA.get('steps', {})


def _call_spec_tools(input_data: str, error_prefix: str) -> str:
  """Helper to call ecma262.js with proper environment."""
  script_path = os.path.join(os.path.dirname(__file__), 'ecma262.js')
  env = os.environ.copy()
  env['ECMABOT_DATA_DIR'] = DATA_DIR
  env['NODE_PATH'] = os.path.join(DATA_DIR, 'node_modules')
  try:
    result = subprocess.run(['node', script_path],
                            input=input_data,
                            text=True,
                            capture_output=True,
                            check=True,
                            env=env)
    return result.stdout
  except subprocess.CalledProcessError as e:
    return f"{error_prefix}: {e.stderr}"


@mcp.tool(name='ecma262_search')
def search_spec(query: str, type: str = None) -> str:
  """Searches the pre-computed biblio.json index for concepts in the specification.
    
    Arguments:
      query: The search term.
      type: Filter by type (e.g., 'clause', 'op', 'grammar').
    """
  input_data = json.dumps({
      "action": "searchSpec",
      "query": query,
      "type": type
  })
  return _call_spec_tools(input_data, "Error searching spec")


@mcp.tool(name='ecma262_section')
def get_section_content(id: str) -> str:
  """Fetches the full HTML content for a specific section ID from the rendered specification.
    
    Arguments:
      id: The section ID (e.g., 'sec-completion-ao').
    """
  input_data = json.dumps({"action": "getSectionContent", "id": id})
  return _call_spec_tools(input_data, "Error getting section content")


@mcp.tool(name='ecma262_sections')
def get_sections_content(ids: list[str]) -> str:
  """Fetches the full HTML content for multiple section IDs.
    
    Arguments:
      ids: A list of section IDs (e.g., ['sec-completion-ao', 'sec-tonumber']).
    """
  input_data = json.dumps({"action": "getSectionsContent", "ids": ids})
  result = _call_spec_tools(input_data, "Error getting sections content")
  if result.startswith("Error"):
    return result
  return result.strip()


@mcp.tool(name='ecma262_lookup')
def get_ancestry(id: str) -> str:
  """Resolves the ancestry (parent chain) of a given section ID, helping to understand its context in the specification hierarchy.
    
    Arguments:
      id: The section ID.
    """
  input_data = json.dumps({"action": "getAncestry", "id": id})
  return _call_spec_tools(input_data, "Error getting ancestry")


@mcp.tool(name='ecma262_signature')
def get_operation_signature(name: str) -> str:
  """Fetches the signature of an abstract operation from biblio.json.
    
    Arguments:
      name: The name of the abstract operation (e.g., 'Completion').
    """
  input_data = json.dumps({"action": "getOperationSignature", "name": name})
  return _call_spec_tools(input_data, "Error getting operation signature")


@mcp.tool(name='ecma262_get_operation')
def get_operation_algorithm(name: str) -> str:
  """Fetches the full HTML content for a specific abstract operation by name.
    
    Arguments:
      name: The name of the abstract operation (e.g., 'ToObject').
    """
  if name not in OPS:
    return f"Operation {name} not found in ops"

  op = OPS[name]
  ref_id = op.get('refId') or op.get('id')
  if not ref_id:
    return f"No ID found for operation {name}"

  if ref_id not in STEPS:
    return f"No steps found for operation {name} (ID: {ref_id})"

  steps = STEPS[ref_id]

  lines = []
  for step in steps:
    indent = " " * step.get('indent', 0)
    pos = step.get('position', '')
    content = step.get('content', '')
    lines.append(f"{indent}{pos}. {content}")

  return f"# Section: {ref_id}\n" + "\n".join(lines)


@mcp.tool(name='ecma262_get_evaluation')
def get_evaluation_algorithm(production_name: str) -> str:
  """Fetches the evaluation algorithm for a specific grammar production.
    
    Arguments:
      production_name: The name of the production (e.g., 'VariableStatement').
    """
  results = []
  for key, value in STEPS.items():
    if 'runtime-semantics-evaluation' in key and production_name in key:
      lines = []
      for step in value:
        indent = " " * step.get('indent', 0)
        pos = step.get('position', '')
        content = step.get('content', '')
        lines.append(f"{indent}{pos}. {content}")
      results.append(f"# Section: {key}\n" + "\n".join(lines))

  if not results:
    return f"No evaluation algorithm found for {production_name}"
  return "\n\n".join(results)


@mcp.tool(name='ecma262_parse')
def ecma262_parse(code: str) -> str:
  """Generates an Abstract Syntax Tree (AST) for the provided JavaScript code using @babel/parser.
    
    Arguments:
      code: The JavaScript code to parse.
    """
  input_data = json.dumps({"action": "parse", "code": code})
  return _call_spec_tools(input_data, "Error parsing JS")


if __name__ == '__main__':
  mcp.run()
