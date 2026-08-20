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
      query: The search term (e.g., 'Completion', 'IsExtensible').
      type: Optional filter by type (e.g., 'clause', 'op', 'grammar', 'prose', 'abstract_op').
    """
  if not query:
    return "Error: Must provide search query"
  input_data = json.dumps({
      "action": "searchSpec",
      "query": query,
      "type": type
  })
  res = _call_spec_tools(input_data, "Error searching spec")
  try:
    items = json.loads(res)
    if isinstance(items, list):
      if not items:
        return f"# Search Results for \"{query}\"\n\nNo matches found."
      lines = [f"# Search Results for \"{query}\" ({len(items)} matches):\n"]
      for it in items:
        num = f"[{it.get('number')}] " if it.get('number') else ""
        lines.append(
            f"- **{num}{it.get('title')}** (`{it.get('id')}`) — *{it.get('type')}*"
        )
      return "\n".join(lines)
  except Exception:
    pass
  return res


@mcp.tool(name='ecma262_section')
def get_section_content(id: str) -> str:
  """Fetches the full content for a specific section ID from the specification as clean Markdown.
    
    Arguments:
      id: The section ID (e.g., 'sec-completion-ao', 'sec-hostensurecanaddprivateelement').
    """
  if not id:
    return "Error: Must provide section ID"
  if id.startswith('#'):
    id = id[1:]
  input_data = json.dumps({"action": "getSectionContent", "id": id})
  res = _call_spec_tools(input_data, "Error getting section content")
  try:
    data = json.loads(res)
    if 'content' in data:
      return data['content']
    if 'error' in data:
      return f"Error: {data['error']}"
  except Exception:
    pass
  return res


@mcp.tool(name='ecma262_sections')
def get_sections_content(ids: list[str]) -> str:
  """Fetches the full content for multiple section IDs as clean Markdown.
    
    Arguments:
      ids: A list of section IDs (e.g., ['sec-completion-ao', 'sec-tonumber']).
    """
  if not ids:
    return "Error: Must provide list of section IDs"
  cleaned_ids = [
      i[1:] if i.startswith('#') else i for i in ids if isinstance(i, str)
  ]
  input_data = json.dumps({"action": "getSectionsContent", "ids": cleaned_ids})
  res = _call_spec_tools(input_data, "Error getting sections content")
  try:
    data = json.loads(res)
    if isinstance(data, dict):
      sections = []
      for sec_id, sec_val in data.items():
        if isinstance(sec_val, dict) and 'content' in sec_val:
          sections.append(sec_val['content'])
        elif isinstance(sec_val, dict) and 'error' in sec_val:
          sections.append(f"## {sec_id}\nError: {sec_val['error']}")
      return "\n\n---\n\n".join(sections)
  except Exception:
    pass
  return res


@mcp.tool(name='ecma262_lookup')
def get_ancestry(id: str) -> str:
  """Resolves the ancestry (parent chain) of a given section ID in the specification hierarchy.
    
    Arguments:
      id: The section ID (e.g., 'sec-completion-ao').
    """
  if not id:
    return "Error: Must provide section ID"
  if id.startswith('#'):
    id = id[1:]
  input_data = json.dumps({"action": "getAncestry", "id": id})
  res = _call_spec_tools(input_data, "Error getting ancestry")
  try:
    data = json.loads(res)
    if 'ancestry' in data and isinstance(data['ancestry'], list):
      lines = [f"# Ancestry for `{id}`:\n"]
      for i, item in enumerate(data['ancestry']):
        indent = "  " * i
        lines.append(f"{indent}- **{item.get('title')}** (`{item.get('id')}`)")
      return "\n".join(lines)
    if 'error' in data:
      return f"Error: {data['error']}"
  except Exception:
    pass
  return res


@mcp.tool(name='ecma262_signature')
def get_operation_signature(name: str) -> str:
  """Fetches the signature of an abstract operation from biblio.json.
    
    Arguments:
      name: The name of the abstract operation (e.g., 'Completion', 'ToObject').
    """
  if not name:
    return "Error: Must provide operation name"
  input_data = json.dumps({
      "action": "getOperationSignature",
      "name": name
  })
  res = _call_spec_tools(input_data, "Error getting operation signature")
  try:
    data = json.loads(res)
    if 'formatted' in data:
      return f"# Signature: {name}\n`{data['formatted']}`"
    if 'error' in data:
      return f"Error: {data['error']}"
  except Exception:
    pass
  return res


@mcp.tool(name='ecma262_get_operation')
def get_operation_algorithm(name: str) -> str:
  """Fetches the full algorithm steps or clause content for a specific abstract operation by name.
    
    Arguments:
      name: The name of the abstract operation (e.g., 'ToObject', 'HostEnsureCanAddPrivateElement').
    """
  if not name:
    return "Error: Must provide operation name"

  target = name
  if target not in OPS:
    matched = None
    for k in OPS:
      if k.lower() == target.lower():
        matched = k
        break
    if matched:
      target = matched
    else:
      # If not in OPS, try as section ID directly
      sec_result = get_section_content(id=target)
      if not sec_result.startswith("Error:"):
        return sec_result
      return f"Operation '{target}' not found in ops"

  op_obj = OPS[target]
  ref_id = op_obj.get('refId') or op_obj.get('id')
  if not ref_id:
    return f"No ID found for operation {target}"

  if ref_id in STEPS:
    steps = STEPS[ref_id]
    lines = []
    for step in steps:
      indent = " " * step.get('indent', 0)
      pos = step.get('position', '')
      content = re.sub(r'~([a-zA-Z0-9_-]+)~', r'\\~\1\\~', step.get('content', ''))
      lines.append(f"{indent}{pos}. {content}")
    return f"# {target}\n**ID:** `{ref_id}` | **Type:** Abstract Operation\n\n" + "\n".join(
        lines)

  # Fallback for host-defined operations, prose operations, or clauses without emu-alg
  sec_result = get_section_content(id=ref_id)
  if not sec_result.startswith("Error:"):
    return sec_result

  return f"No steps or content found for operation {target} (ID: {ref_id})"


@mcp.tool(name='ecma262_callers')
def get_operation_callers(name: str) -> str:
  """Finds all algorithm steps across the specification that call or reference a given abstract operation.
    
    Arguments:
      name: The name of the abstract operation (e.g., 'HostEnsureCanAddPrivateElement', 'PrivateFieldAdd', 'IsExtensible').
    """
  if not name:
    return "Error: Must provide operation name"

  pattern = re.compile(r'\b' + re.escape(name) + r'\b')
  results = []

  for sec_id, step_list in STEPS.items():
    matching_steps = []
    for step in step_list:
      raw_content = step.get('content', '')
      if pattern.search(raw_content):
        pos = step.get('position', '')
        content = re.sub(r'~([a-zA-Z0-9_-]+)~', r'\\~\1\\~', raw_content)
        matching_steps.append(f"{pos}: {content}")
    if matching_steps:
      title = sec_id
      if sec_id in OPS and 'aoid' in OPS[sec_id]:
        title = f"{OPS[sec_id]['aoid']} ({sec_id})"
      elif sec_id in OPS and 'title' in OPS[sec_id]:
        title = f"{OPS[sec_id]['title']} ({sec_id})"
      results.append(f"## {title}\n" + "\n".join(f"  - {s}" for s in matching_steps))

  if not results:
    return f"No callers found for '{name}' in specification algorithms"

  return f"# Callers of {name} ({len(results)} sections):\n\n" + "\n\n".join(results)


@mcp.tool(name='ecma262_get_evaluation')
def get_evaluation_algorithm(production_name: str) -> str:
  """Fetches the evaluation algorithm for a specific grammar production.
    
    Arguments:
      production_name: The name of the production (e.g., 'VariableStatement').
    """
  if not production_name:
    return "Error: Must provide production name"

  results = []
  for key, value in STEPS.items():
    if 'runtime-semantics-evaluation' in key and production_name in key:
      lines = []
      for step in value:
        indent = " " * step.get('indent', 0)
        pos = step.get('position', '')
        content = re.sub(r'~([a-zA-Z0-9_-]+)~', r'\\~\1\\~', step.get('content', ''))
        lines.append(f"{indent}{pos}. {content}")
      results.append(f"## {key}\n" + "\n".join(lines))

  if not results:
    return f"No evaluation algorithm found for {production_name}"
  return f"# Runtime Semantics: Evaluation for {production_name}\n\n" + "\n\n".join(
      results)


@mcp.tool(name='ecma262_parse')
def ecma262_parse(code: str) -> str:
  """Generates an Abstract Syntax Tree (AST) for the provided JavaScript code using @babel/parser.
    
    Arguments:
      code: The JavaScript code to parse.
    """
  if not code:
    return "Error: Must provide JavaScript code"
  input_data = json.dumps({"action": "parse", "code": code})
  return _call_spec_tools(input_data, "Error parsing JS")


if __name__ == '__main__':
  mcp.run()
