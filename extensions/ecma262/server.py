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
PROPOSALS_DIR = os.path.join(DATA_DIR, 'proposals')
TOOLS_SCRIPT = os.path.join(os.path.dirname(__file__), 'ecma262.js')

ACTIVE_PROPOSAL: str | None = None
LOADED_PROPOSALS: dict[str, dict] = {}


def sanitize_tc39_proposal_name(name: str) -> str:
  """Validates that a proposal name is strictly in the ECMA/TC39 namespace.
  
  Prevents directory traversal and disallows arbitrary non-TC39 domains/schemes.
  """
  if not name:
    raise ValueError("Proposal name cannot be empty")
  name = name.strip()

  # If user supplied a TC39 URL, extract the proposal slug
  m = re.match(
      r'^https?://(?:tc39\.es/proposal-|tc39\.es/|github\.com/tc39/proposal-|github\.com/tc39/|raw\.githubusercontent\.com/tc39/proposal-|raw\.githubusercontent\.com/tc39/)?([a-zA-Z0-9_-]+)/?.*$',
      name)
  if m:
    name = m.group(1)

  if name.startswith('tc39/'):
    name = name[5:]
  if name.startswith('proposal-'):
    name = name[9:]

  clean = name.lower()
  # Must be alphanumeric with hyphens / underscores
  if not re.match(r'^[a-z0-9]+([-_][a-z0-9]+)*$', clean):
    raise ValueError(
        f"Security Error: Invalid proposal name '{name}'. Only alphanumeric names in the TC39 namespace (e.g. 'temporal', 'decorators', 'explicit-resource-management') are allowed."
    )
  return clean


def _load_cached_proposal(clean_name: str) -> dict | None:
  prop_dir = os.path.join(PROPOSALS_DIR, clean_name)
  spec_path = os.path.join(prop_dir, 'spec.html')
  data_path = os.path.join(prop_dir, 'spec_data.json')

  if os.path.exists(spec_path) and os.path.exists(data_path):
    try:
      with open(data_path, 'r', encoding='utf-8') as f:
        p_data = json.load(f)
      return {
          'name': clean_name,
          'spec_path': spec_path,
          'data_path': data_path,
          'ops': p_data.get('ops', {}),
          'steps': p_data.get('steps', {}),
          'source_url': f"https://tc39.es/proposal-{clean_name}/",
      }
    except Exception:
      pass
  return None


def fetch_and_index_tc39_proposal(clean_name: str) -> dict:
  """Fetches a proposal strictly from the official TC39 domains and indexes its data."""
  import urllib.request
  import urllib.error

  candidate_urls = [
      f"https://tc39.es/proposal-{clean_name}/",
      f"https://tc39.es/{clean_name}/",
      f"https://raw.githubusercontent.com/tc39/proposal-{clean_name}/main/spec.html",
      f"https://raw.githubusercontent.com/tc39/proposal-{clean_name}/master/spec.html",
      f"https://raw.githubusercontent.com/tc39/proposal-{clean_name}/main/index.html",
      f"https://raw.githubusercontent.com/tc39/proposal-{clean_name}/master/index.html",
  ]

  html_content = None
  source_url = None
  errors = []

  for url in candidate_urls:
    try:
      req = urllib.request.Request(
          url,
          headers={
              'User-Agent': 'ecma262-mcp/1.0 (Google V8 Assistant)'
          })
      with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status == 200:
          data = resp.read()
          text = data.decode('utf-8', errors='replace')
          if '<emu-clause' in text or '<emu-alg' in text or '<html' in text:
            html_content = text
            source_url = url
            break
    except Exception as e:
      errors.append(f"{url}: {e}")

  if not html_content:
    raise RuntimeError(
        f"Could not fetch proposal '{clean_name}' from TC39 namespace. Tried:\n"
        + "\n".join(f"- {u}" for u in candidate_urls))

  prop_dir = os.path.join(PROPOSALS_DIR, clean_name)
  os.makedirs(prop_dir, exist_ok=True)
  spec_path = os.path.join(prop_dir, 'spec.html')
  data_path = os.path.join(prop_dir, 'spec_data.json')

  with open(spec_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

  # Preparse proposal HTML
  input_data = json.dumps({
      "action": "preparse",
      "specPath": spec_path,
      "outputPath": data_path
  })
  res = _call_spec_tools(input_data, f"Error preparsing proposal {clean_name}")

  with open(data_path, 'r', encoding='utf-8') as f:
    p_data = json.load(f)

  prop_info = {
      'name': clean_name,
      'spec_path': spec_path,
      'data_path': data_path,
      'ops': p_data.get('ops', {}),
      'steps': p_data.get('steps', {}),
      'source_url': source_url,
  }
  LOADED_PROPOSALS[clean_name] = prop_info
  return prop_info


def _get_spec_context(proposal: str | None = None) -> tuple[str, dict, dict, str]:
  """Resolves the active spec context (spec_path, ops, steps, context_name)."""
  prop_name = proposal or ACTIVE_PROPOSAL
  if prop_name and prop_name.lower() not in ('', 'base', 'ecma262'):
    clean = sanitize_tc39_proposal_name(prop_name)
    if clean in LOADED_PROPOSALS:
      p = LOADED_PROPOSALS[clean]
      return p['spec_path'], p['ops'], p['steps'], clean
    cached = _load_cached_proposal(clean)
    if cached:
      LOADED_PROPOSALS[clean] = cached
      return cached['spec_path'], cached['ops'], cached['steps'], clean
    p = fetch_and_index_tc39_proposal(clean)
    return p['spec_path'], p['ops'], p['steps'], clean
  return SPEC_PATH, OPS, STEPS, 'base'


def ensure_spec_data():
  import filecmp
  import shutil
  import os
  npm_available = shutil.which('npm') is not None

  # Ensure base data directory exists
  if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)
  if not os.path.exists(PROPOSALS_DIR):
    os.makedirs(PROPOSALS_DIR, exist_ok=True)

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
      sys.stderr.write("Checking for node module updates...\n")
      if not npm_available:
        sys.stderr.write("npm not found. Skipping update.\n")
      else:
        try:
          subprocess.run(['npm', 'update', '--prefix', DATA_DIR],
                         check=True,
                         capture_output=True)
          with open(last_update_file, 'w') as f:
            f.write(str(time.time()))
          sys.stderr.write("Node modules update check complete.\n")
        except subprocess.CalledProcessError as e:
          sys.stderr.write(
              f"Warning: npm update failed: {e.stderr.decode() if e.stderr else str(e)}\n"
          )

  # Check if spec.html and biblio.json exist
  import urllib.request
  import urllib.error

  spec_updated = False
  if not os.path.exists(SPEC_PATH) or not os.path.exists(BIBLIO_PATH):
    sys.stderr.write("Downloading ECMA-262 spec.html and biblio.json...\n")
    try:
      # Download spec.html
      urllib.request.urlretrieve(
          'https://raw.githubusercontent.com/tc39/ecma262/HEAD/spec.html',
          SPEC_PATH)
      # Download biblio.json
      urllib.request.urlretrieve(
          'https://raw.githubusercontent.com/tc39/ecma262/HEAD/biblio.json',
          BIBLIO_PATH)
      sys.stderr.write("Download complete.\n")
      spec_updated = True
    except Exception as e:
      sys.stderr.write(f"Error downloading ECMA-262 spec: {e}\n")
      raise
  else:
    # Check for spec updates, but at most once every 24 hours
    import time
    last_spec_update_file = os.path.join(DATA_DIR, '.last_spec_update')
    need_spec_check = True

    if os.path.exists(last_spec_update_file):
      try:
        with open(last_spec_update_file, 'r') as f:
          last_spec_time = float(f.read().strip())
        # 1 day = 86400 seconds
        if time.time() - last_spec_time < 86400:
          need_spec_check = False
      except Exception as e:
        sys.stderr.write(f"Error reading last spec update time: {e}\n")

    if need_spec_check:
      sys.stderr.write("Checking for spec updates from GitHub...\n")
      try:
        urllib.request.urlretrieve(
            'https://raw.githubusercontent.com/tc39/ecma262/HEAD/spec.html',
            TMP_SPEC_PATH)
        with open(last_spec_update_file, 'w') as f:
          f.write(str(time.time()))

        if not filecmp.cmp(SPEC_PATH, TMP_SPEC_PATH, shallow=False):
          sys.stderr.write("New spec version found. Updating...\n")
          shutil.move(TMP_SPEC_PATH, SPEC_PATH)
          # Also update biblio.json
          urllib.request.urlretrieve(
              'https://raw.githubusercontent.com/tc39/ecma262/HEAD/biblio.json',
              BIBLIO_PATH)
          spec_updated = True
        else:
          sys.stderr.write("Spec is up to date.\n")
          if os.path.exists(TMP_SPEC_PATH):
            os.remove(TMP_SPEC_PATH)
      except Exception as e:
        sys.stderr.write(f"Warning: Failed to check for spec updates: {e}\n")
        if os.path.exists(TMP_SPEC_PATH):
          os.remove(TMP_SPEC_PATH)

  # If spec_data.json doesn't exist or spec was updated, generate it
  if spec_updated or not os.path.exists(DATA_PATH):
    sys.stderr.write(
        "Running preparse step via ecma262.js to generate spec_data.json...\n")
    try:
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


@mcp.tool(name='ecma262_load_proposal')
def load_proposal(name: str) -> str:
  """Loads and indexes a TC39 proposal strictly from the official ECMA / TC39 namespace.
    
    Arguments:
      name: The proposal name or slug (e.g., 'explicit-resource-management', 'temporal', 'decorators', 'shadowrealm', 'float16array').
    """
  global ACTIVE_PROPOSAL
  try:
    clean = sanitize_tc39_proposal_name(name)
    prop = fetch_and_index_tc39_proposal(clean)
    ACTIVE_PROPOSAL = clean
    return (
        f"# Loaded TC39 Proposal: `{clean}`\n\n"
        f"- **Source URL:** {prop.get('source_url')}\n"
        f"- **Abstract Operations Indexed:** {len(prop.get('ops', {}))}\n"
        f"- **Algorithms Indexed:** {len(prop.get('steps', {}))}\n"
        f"- **Status:** Active (all subsequent queries will default to `{clean}`)\n\n"
        f"You can now query operations, sections, callers, or run `ecma262_diff` for this proposal."
    )
  except Exception as e:
    return f"Error loading TC39 proposal '{name}': {e}"


@mcp.tool(name='ecma262_list_proposals')
def list_proposals() -> str:
  """Lists all currently loaded TC39 proposals and indicates the active specification context."""
  lines = ["# Specification Contexts:\n"]
  is_base_active = " **(ACTIVE)**" if not ACTIVE_PROPOSAL else ""
  lines.append(
      f"- **Base ECMA-262** (`base`){is_base_active} — {len(OPS)} operations, {len(STEPS)} algorithms"
  )

  # Check disk cache for existing proposals
  if os.path.exists(PROPOSALS_DIR):
    for entry in os.listdir(PROPOSALS_DIR):
      if entry not in LOADED_PROPOSALS:
        cached = _load_cached_proposal(entry)
        if cached:
          LOADED_PROPOSALS[entry] = cached

  for name, prop in sorted(LOADED_PROPOSALS.items()):
    is_active = " **(ACTIVE)**" if ACTIVE_PROPOSAL == name else ""
    lines.append(
        f"- **Proposal `{name}`**{is_active} — {len(prop.get('ops', {}))} operations, {len(prop.get('steps', {}))} algorithms (`{prop.get('source_url')}`)"
    )

  return "\n".join(lines)


@mcp.tool(name='ecma262_use_proposal')
def use_proposal(name: str = "") -> str:
  """Switches the active specification context between Base ECMA-262 and a loaded TC39 proposal.
    
    Arguments:
      name: The proposal name (e.g., 'explicit-resource-management', 'temporal'), or 'base' / '' to switch back to standard ECMA-262.
    """
  global ACTIVE_PROPOSAL
  if not name or name.lower() in ('base', 'ecma262', 'none', 'default'):
    ACTIVE_PROPOSAL = None
    return "# Active Context: Base ECMA-262"

  try:
    clean = sanitize_tc39_proposal_name(name)
    if clean not in LOADED_PROPOSALS:
      cached = _load_cached_proposal(clean)
      if cached:
        LOADED_PROPOSALS[clean] = cached
      else:
        fetch_and_index_tc39_proposal(clean)
    ACTIVE_PROPOSAL = clean
    return f"# Active Context: TC39 Proposal `{clean}`"
  except Exception as e:
    return f"Error switching proposal: {e}"


@mcp.tool(name='ecma262_diff')
def diff_operation(name: str, proposal: str = None) -> str:
  """Compares an abstract operation or clause between base ECMA-262 and a TC39 proposal.
    
    Arguments:
      name: The name of the abstract operation or section ID (e.g., 'InitializeReferencedBinding', 'PrivateFieldAdd').
      proposal: Optional name of the TC39 proposal (e.g., 'explicit-resource-management', 'temporal'). Uses active proposal if omitted.
    """
  if not name:
    return "Error: Must provide operation name or section ID"

  target_prop = proposal or ACTIVE_PROPOSAL
  if not target_prop or target_prop.lower() in ('base', 'ecma262'):
    return "Error: Please specify a TC39 proposal name to diff against (e.g. proposal='explicit-resource-management')"

  try:
    prop_spec, prop_ops, prop_steps, prop_name = _get_spec_context(target_prop)
  except Exception as e:
    return f"Error loading proposal '{target_prop}': {e}"

  base_content = get_operation_algorithm(name=name, proposal="base")
  prop_content = get_operation_algorithm(name=name, proposal=prop_name)

  if base_content.startswith("Error:") and prop_content.startswith("Error:"):
    return f"Operation '{name}' not found in either base ECMA-262 or proposal '{prop_name}'"

  if base_content.startswith("Error:") or "not found in ops" in base_content:
    return f"# {name} (New in Proposal `{prop_name}`)\n\n" + prop_content

  if prop_content.startswith("Error:") or "not found in ops" in prop_content:
    return f"# {name} (Only in Base ECMA-262)\n\n" + base_content

  return (
      f"# Diff Comparison: `{name}` (Base ECMA-262 vs Proposal `{prop_name}`)\n\n"
      f"## Proposal Version (with <ins>/<del> markers):\n{prop_content}\n\n---\n\n"
      f"## Base ECMA-262 Version:\n{base_content}"
  )


@mcp.tool(name='ecma262_search')
def search_spec(query: str, type: str = None, proposal: str = None) -> str:
  """Searches for concepts across the specification or an active TC39 proposal.
    
    Arguments:
      query: The search term (e.g., 'Completion', 'Dispose', 'IsExtensible').
      type: Optional filter by type (e.g., 'clause', 'op', 'grammar', 'prose', 'abstract_op').
      proposal: Optional TC39 proposal context (e.g., 'explicit-resource-management'). Defaults to active context.
    """
  if not query:
    return "Error: Must provide search query"

  spec_path, ops, steps, context_name = _get_spec_context(proposal)

  # If querying a proposal context, search its indexed operations directly
  if context_name != 'base':
    q_lower = query.lower()
    matches = []
    for k, v in ops.items():
      if q_lower in k.lower() or (v.get('title') and
                                  q_lower in v['title'].lower()):
        matches.append(
            f"- **{v.get('title') or k}** (`{v.get('id') or k}`) — *{v.get('type', 'op')}*"
        )
    if matches:
      return f"# Search Results in Proposal `{context_name}` for \"{query}\" ({len(matches)} matches):\n" + "\n".join(
          matches)
    return f"# Search Results in Proposal `{context_name}` for \"{query}\"\n\nNo matches found in proposal."

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
def get_section_content(id: str, proposal: str = None) -> str:
  """Fetches the full content for a specific section ID from the specification or TC39 proposal as clean Markdown.
    
    Arguments:
      id: The section ID (e.g., 'sec-completion-ao', 'sec-hostensurecanaddprivateelement').
      proposal: Optional TC39 proposal context (e.g., 'explicit-resource-management'). Defaults to active context.
    """
  if not id:
    return "Error: Must provide section ID"
  if id.startswith('#'):
    id = id[1:]

  spec_path, ops, steps, context_name = _get_spec_context(proposal)
  input_data = json.dumps({
      "action": "getSectionContent",
      "id": id,
      "specPath": spec_path
  })
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
def get_sections_content(ids: list[str], proposal: str = None) -> str:
  """Fetches the full content for multiple section IDs as clean Markdown.
    
    Arguments:
      ids: A list of section IDs (e.g., ['sec-completion-ao', 'sec-tonumber']).
      proposal: Optional TC39 proposal context (e.g., 'explicit-resource-management'). Defaults to active context.
    """
  if not ids:
    return "Error: Must provide list of section IDs"
  cleaned_ids = [
      i[1:] if i.startswith('#') else i for i in ids if isinstance(i, str)
  ]
  spec_path, ops, steps, context_name = _get_spec_context(proposal)
  input_data = json.dumps({
      "action": "getSectionsContent",
      "ids": cleaned_ids,
      "specPath": spec_path
  })
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
def get_ancestry(id: str, proposal: str = None) -> str:
  """Resolves the ancestry (parent chain) of a given section ID in the specification hierarchy.
    
    Arguments:
      id: The section ID (e.g., 'sec-completion-ao').
      proposal: Optional TC39 proposal context. Defaults to active context.
    """
  if not id:
    return "Error: Must provide section ID"
  if id.startswith('#'):
    id = id[1:]
  spec_path, ops, steps, context_name = _get_spec_context(proposal)
  input_data = json.dumps({
      "action": "getAncestry",
      "id": id,
      "specPath": spec_path
  })
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
def get_operation_signature(name: str, proposal: str = None) -> str:
  """Fetches the signature of an abstract operation.
    
    Arguments:
      name: The name of the abstract operation (e.g., 'Completion', 'ToObject').
      proposal: Optional TC39 proposal context. Defaults to active context.
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
      # If not in base biblio, check if clause header in proposal has signature
      spec_path, ops, steps, context_name = _get_spec_context(proposal)
      if name in ops:
        ref_id = ops[name].get('refId') or ops[name].get('id')
        if ref_id:
          sec = get_section_content(id=ref_id, proposal=context_name)
          if not sec.startswith("Error:"):
            first_line = sec.split('\n')[0]
            return f"# Signature: {name}\n`{first_line.replace('# ', '')}`"
      return f"Error: {data['error']}"
  except Exception:
    pass
  return res


@mcp.tool(name='ecma262_get_operation')
def get_operation_algorithm(name: str, proposal: str = None) -> str:
  """Fetches the full algorithm steps or clause content for a specific abstract operation by name.
    
    Steps that can invoke JavaScript user code (e.g. getters, setters, Proxy traps, Symbol.toPrimitive) are annotated with ⚡.
    
    Arguments:
      name: The name of the abstract operation (e.g., 'ToObject', 'AddDisposableResource').
      proposal: Optional TC39 proposal context (e.g., 'explicit-resource-management'). Defaults to active context.
    """
  if not name:
    return "Error: Must provide operation name"

  spec_path, ops, steps, context_name = _get_spec_context(proposal)

  target = name
  if target not in ops:
    matched = None
    for k in ops:
      if k.lower() == target.lower():
        matched = k
        break
    if matched:
      target = matched
    else:
      # If not in OPS, try as section ID directly
      sec_result = get_section_content(id=target, proposal=context_name)
      if not sec_result.startswith("Error:"):
        return sec_result
      return f"Operation '{target}' not found in ops for context '{context_name}'"

  op_obj = ops[target]
  ref_id = op_obj.get('refId') or op_obj.get('id')
  if not ref_id:
    return f"No ID found for operation {target}"

  if ref_id in steps:
    step_list = steps[ref_id]
    lines = []
    for step in step_list:
      indent = " " * step.get('indent', 0)
      pos = step.get('position', '')
      content = re.sub(r'~([a-zA-Z0-9_-]+)~', r'\\~\1\\~', step.get('content', ''))
      lines.append(f"{indent}{pos}. {content}")
    ctx_str = f" | **Context:** `{context_name}`" if context_name != "base" else ""
    return f"# {target}\n**ID:** `{ref_id}` | **Type:** Abstract Operation{ctx_str}\n\n" + "\n".join(
        lines)

  # Fallback for host-defined operations, prose operations, or clauses without emu-alg
  sec_result = get_section_content(id=ref_id, proposal=context_name)
  if not sec_result.startswith("Error:"):
    return sec_result

  return f"No steps or content found for operation {target} (ID: {ref_id})"


@mcp.tool(name='ecma262_callers')
def get_operation_callers(name: str, proposal: str = None) -> str:
  """Finds all algorithm steps across the specification that call or reference a given abstract operation.
    
    Arguments:
      name: The name of the abstract operation (e.g., 'HostEnsureCanAddPrivateElement', 'AddDisposableResource').
      proposal: Optional TC39 proposal context. Defaults to active context.
    """
  if not name:
    return "Error: Must provide operation name"

  spec_path, ops, steps, context_name = _get_spec_context(proposal)

  pattern = re.compile(r'\b' + re.escape(name) + r'\b')
  results = []

  for sec_id, step_list in steps.items():
    matching_steps = []
    for step in step_list:
      raw_content = step.get('content', '')
      if pattern.search(raw_content):
        pos = step.get('position', '')
        content = re.sub(r'~([a-zA-Z0-9_-]+)~', r'\\~\1\\~', raw_content)
        matching_steps.append(f"{pos}: {content}")
    if matching_steps:
      title = sec_id
      if sec_id in ops and 'aoid' in ops[sec_id]:
        title = f"{ops[sec_id]['aoid']} ({sec_id})"
      elif sec_id in ops and 'title' in ops[sec_id]:
        title = f"{ops[sec_id]['title']} ({sec_id})"
      results.append(f"## {title}\n" + "\n".join(f"  - {s}" for s in matching_steps))

  if not results:
    return f"No callers found for '{name}' in algorithms (Context: `{context_name}`)"

  return f"# Callers of {name} ({len(results)} sections, Context: `{context_name}`):\n\n" + "\n\n".join(
      results)


@mcp.tool(name='ecma262_get_evaluation')
def get_evaluation_algorithm(production_name: str,
                             proposal: str = None) -> str:
  """Fetches the evaluation algorithm for a specific grammar production.
    
    Arguments:
      production_name: The name of the production (e.g., 'VariableStatement').
      proposal: Optional TC39 proposal context. Defaults to active context.
    """
  if not production_name:
    return "Error: Must provide production name"

  spec_path, ops, steps, context_name = _get_spec_context(proposal)

  results = []
  for key, value in steps.items():
    if 'runtime-semantics-evaluation' in key and production_name in key:
      lines = []
      for step in value:
        indent = " " * step.get('indent', 0)
        pos = step.get('position', '')
        content = re.sub(r'~([a-zA-Z0-9_-]+)~', r'\\~\1\\~', step.get('content', ''))
        lines.append(f"{indent}{pos}. {content}")
      results.append(f"## {key}\n" + "\n".join(lines))

  if not results:
    return f"No evaluation algorithm found for {production_name} (Context: `{context_name}`)"
  return f"# Runtime Semantics: Evaluation for {production_name} (Context: `{context_name}`)\n\n" + "\n\n".join(
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
