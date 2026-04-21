#!/usr/bin/env vpython3
# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""ECMA-262 State Machine Simulation MCP server."""

from __future__ import annotations
import subprocess
import os
import json
import difflib
import uuid
import sys
from mcp.server import fastmcp
from typing import Any

mcp = fastmcp.FastMCP('ecma262_state_machine')


class StateManager:

  def __init__(self, state_path):
    self.state_path = state_path

  def _read_state(self):
    if not os.path.exists(self.state_path):
      return {}
    with open(self.state_path, 'r') as f:
      return json.load(f)

  def _write_state(self, state):
    os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
    with open(self.state_path, 'w') as f:
      json.dump(state, f, indent=2)

    history_path = self.state_path + ".history"
    with open(history_path, 'a') as f:
      f.write(json.dumps(state) + "\n")

  def _check_value_warnings(self, value):
    warnings = []
    if isinstance(value, str):
      if value == "undefined":
        warnings.append(
            "Warning: passed the string with content undefined. did you maybe mean ~undefined~?"
        )
      elif value == "NaN":
        warnings.append(
            "Warning: passed the string with content NaN. did you maybe mean ~NaN~?"
        )
      elif value in ["Infinity", "-Infinity"]:
        warnings.append(
            f"Warning: passed the string with content {value}. did you maybe mean ~{value}~?"
        )
      elif value == "-0":
        warnings.append(
            "Warning: passed the string with content -0. did you maybe mean ~-0~?"
        )
      else:
        try:
          float(value)
          # It is a string that can be parsed as float!
          warnings.append(
              "Warning: passed a number as a string. is this intentional? ensure to pass ECMAScript numbers as raw numbers."
          )
        except ValueError:
          pass
    return warnings

  def ecma262_state_init(self):
    state = {
        "executionContextStack": [{
            "id": "global",
            "codeEvaluationState": "Executing global code",
            "function": None,
            "realm": "ref:Realm:1",
            "lexicalEnvironment": "ref:Env:Global",
            "variableEnvironment": "ref:Env:Global"
        }],
        "realms": {
            "ref:Realm:1": {
                "intrinsics": {},
                "globalObject": "ref:Obj:Global",
                "globalEnv": "ref:Env:Global",
                "[[TemplateMap]]": [],
                "[[LoadedModules]]": [],
                "[[AgentSignifier]]": "AgentSignifier",
                "[[HostDefined]]": {}
            }
        },
        "environmentRecords": {
            "ref:Env:Global": {
                "type": "Global",
                "outerEnv": None,
                "objectRecord": "ref:Env:GlobalObj",
                "declarativeRecord": "ref:Env:GlobalDecl",
                "[[GlobalThisValue]]": "ref:Obj:Global"
            },
            "ref:Env:GlobalObj": {
                "type": "Object",
                "outerEnv": None,
                "bindingObject": "ref:Obj:Global",
                "withEnvironment": False
            },
            "ref:Env:GlobalDecl": {
                "type": "Declarative",
                "outerEnv": None,
                "bindings": {}
            }
        },
        "heap": {
            "ref:Obj:Global": {
                "internalSlots": {
                    "[[Prototype]]": "ref:Obj:ObjectProto",
                    "[[Extensible]]": True
                },
                "properties": {}
            }
        },
        "privateEnvironmentRecords": {},
        "jobQueue": []
    }

    history_path = self.state_path + ".history"
    if os.path.exists(history_path):
      os.remove(history_path)

    self._write_state(state)
    return f"State initialized at ecma262_states/{os.path.basename(self.state_path)}"

  def ecma262_state_push_context(self,
                                 name,
                                 realm,
                                 lex_env,
                                 var_env,
                                 script_or_module=None,
                                 private_env=None,
                                 generator=None):
    state = self._read_state()
    if not state:
      return "Error: State not initialized. Call init first."

    context = {
        "id": name,
        "codeEvaluationState": "Executing",
        "function": None,
        "realm": realm,
        "ScriptOrModule": script_or_module,
        "lexicalEnvironment": lex_env,
        "variableEnvironment": var_env,
        "PrivateEnvironment": private_env,
        "Generator": generator
    }
    state["executionContextStack"].append(context)
    self._write_state(state)
    return f"Pushed context: {name}"

  def ecma262_state_pop_context(self):
    state = self._read_state()
    if not state:
      return "Error: State not initialized."

    if len(state["executionContextStack"]) <= 1:
      return "Error: Cannot pop global execution context."

    popped = state["executionContextStack"].pop()
    self._write_state(state)
    return f"Popped context: {popped['id']}"

  def ecma262_state_update_context(self, key, value):
    """Updates a field in the running execution context.

        Args:
            key: The field to update.
            value: The new value.
        """
    state = self._read_state()
    if not state:
      return "Error: State not initialized."

    if not state["executionContextStack"]:
      return "Error: Execution context stack is empty."

    top_context = state["executionContextStack"][-1]

    valid_keys = {
        "id", "codeEvaluationState", "function", "realm", "ScriptOrModule",
        "lexicalEnvironment", "variableEnvironment", "PrivateEnvironment",
        "Generator"
    }

    if key not in valid_keys:
      return f"Error: Invalid execution context key '{key}'"

    top_context[key] = value

    self._write_state(state)
    return f"Updated top context field '{key}' to {value}"

  def ecma262_state_enqueue_promise_job(self, job_name, callback_id, args):
    if not isinstance(job_name, str):
      return f"Error: ecma262_state_enqueue_promise_job argument job_name must be a string, got {type(job_name)}"
    if not isinstance(callback_id, str):
      return f"Error: ecma262_state_enqueue_promise_job argument callback_id must be a string, got {type(callback_id)}"
    if not isinstance(args, list):
      return f"Error: ecma262_state_enqueue_promise_job argument args must be a list, got {type(args)}"

    state = self._read_state()
    if not state:
      return "Error: State not initialized."
    if "jobQueue" not in state:
      state["jobQueue"] = []
    job = {"name": job_name, "callback": callback_id, "arguments": args}
    state["jobQueue"].append(job)
    self._write_state(state)
    return f"Enqueued job: {job_name}"

  def ecma262_state_get_job_queue(self):
    state = self._read_state()
    if not state:
      return "Error: State not initialized."
    return state.get("jobQueue", [])

  def ecma262_state_dequeue_job(self):
    state = self._read_state()
    if not state:
      return "Error: State not initialized."
    if not state.get("jobQueue"):
      return None
    job = state["jobQueue"].pop(0)
    self._write_state(state)
    return job

  def ecma262_state_new_environment(self, env_type, outer_env, bindings=None):
    """Creates a new environment record.

        Args:
            env_type: "Declarative", "Function", "Module", or "Private".
            outer_env: The outer environment reference.
            bindings: Optional initial bindings (for Declarative, Function, Module).
        """
    state = self._read_state()
    if not state:
      return "Error: State not initialized."

    if env_type == "Private":
      if "privateEnvironmentRecords" not in state:
        state["privateEnvironmentRecords"] = {}
      env_id = f"ref:PrivEnv:{len(state['privateEnvironmentRecords']) + 1}"
      state["privateEnvironmentRecords"][env_id] = {
          "outerPrivateEnvironment": outer_env,
          "names": []
      }
      self._write_state(state)
      return f"Created private environment {env_id}"

    elif env_type == "Object":
      binding_obj = bindings.get("bindingObject") if bindings else None
      if not binding_obj:
        return "Error: Object environment requires a bindingObject."

      env_id = f"ref:Env:{len(state['environmentRecords']) + 1}"
      state["environmentRecords"][env_id] = {
          "type": "Object",
          "outerEnv": outer_env,
          "bindingObject": binding_obj
      }
      self._write_state(state)
      return f"Created environment {env_id} of type Object"

    env_id = f"ref:Env:{len(state['environmentRecords']) + 1}"

    env_record = {
        "type": env_type,
        "outerEnv": outer_env,
        "bindings": bindings or {}
    }

    if env_type == "Function":
      env_record.update({
          "[[ThisValue]]": "~undefined~",
          "[[ThisBindingStatus]]": "uninitialized",
          "[[FunctionObject]]": None,
          "[[NewTarget]]": "~undefined~"
      })
    elif env_type == "Module":
      env_record["indirectBindings"] = {}

    state["environmentRecords"][env_id] = env_record
    self._write_state(state)
    return f"Created environment {env_id} of type {env_type}"

  def ecma262_state_set_binding(self, env_id, name, value):
    state = self._read_state()
    if not state:
      return "Error: State not initialized."

    if env_id not in state["environmentRecords"]:
      return f"Error: Environment {env_id} not found."

    env = state["environmentRecords"][env_id]
    if "bindings" not in env:
      env["bindings"] = {}

    if name in env["bindings"] and isinstance(
        env["bindings"][name], dict) and "value" in env["bindings"][name]:
      env["bindings"][name]["value"] = value
      env["bindings"][name]["initialized"] = True
    else:
      env["bindings"][name] = {
          "value": value,
          "strict": False,
          "mutable": True,
          "initialized": True,
          "deletable": True
      }

    self._write_state(state)
    return f"Set binding {name} = {value} in {env_id}"

  def ecma262_env_op(self,
                     env_id,
                     operation,
                     name=None,
                     value=None,
                     strict=False,
                     module_record=None,
                     binding_name=None):
    state = self._read_state()
    if not state:
      return "Error: State not initialized."

    if env_id not in state["environmentRecords"]:
      return f"Error: Environment {env_id} not found."

    env = state["environmentRecords"][env_id]
    if "bindings" not in env:
      env["bindings"] = {}

    if operation == "CreateMutableBinding":
      if not isinstance(name, str):
        return f"Error: CreateMutableBinding argument N (name) must be a string, got {type(name)}"
      if not isinstance(value, bool) and value is not None:
        return f"Error: CreateMutableBinding argument D (deletable) must be a boolean, got {type(value)}"
      deletable = value if isinstance(value, bool) else True

      if env.get("type") == "Object":
        binding_obj_id = env.get("bindingObject")
        if binding_obj_id in state["heap"]:
          res = self.ecma262_object_op(
              binding_obj_id,
              "OrdinaryDefineOwnProperty",
              name,
              descriptor={
                  "value": "~undefined~",
                  "writable": True,
                  "enumerable": True,
                  "configurable": deletable
              })
          if res is False:
            return f"Error: TypeError - Cannot define property {name} on Object environment binding."
          return res
        return f"Error: BindingObject {binding_obj_id} not found."

      elif env.get("type") == "Global":
        decl_rec_id = env.get("declarativeRecord")
        if decl_rec_id in state["environmentRecords"]:
          return self.ecma262_env_op(
              decl_rec_id, "CreateMutableBinding", name, value=deletable)
        return f"Error: DeclarativeRecord {decl_rec_id} not found."

      if name in env["bindings"]:
        return f"Error: Assertion failed - Binding {name} already exists."

      env["bindings"][name] = {
          "value": "~undefined~",
          "strict": False,
          "mutable": True,
          "initialized": False,
          "deletable": deletable
      }
      msg = f"Created mutable binding {name} in {env_id}"

    elif operation == "CreateImmutableBinding":
      if not isinstance(name, str):
        return f"Error: CreateImmutableBinding argument N (name) must be a string, got {type(name)}"
      strict = value if isinstance(value, bool) else False

      if env.get("type") == "Global":
        decl_rec_id = env.get("declarativeRecord")
        if decl_rec_id in state["environmentRecords"]:
          return self.ecma262_env_op(
              decl_rec_id, "CreateImmutableBinding", name, value=strict)
        return f"Error: DeclarativeRecord {decl_rec_id} not found."

      elif env.get("type") == "Object":
        return "Error: Object environment records do not support immutable bindings."

      if name in env["bindings"]:
        return f"Error: Assertion failed - Binding {name} already exists."

      env["bindings"][name] = {
          "value": "~undefined~",
          "strict": strict,
          "mutable": False,
          "initialized": False,
          "deletable": False
      }
      msg = f"Created immutable binding {name} in {env_id}"

    elif operation == "InitializeBinding":
      if not isinstance(name, str):
        return f"Error: InitializeBinding argument N (name) must be a string, got {type(name)}"

      if env.get("type") == "Object":
        return self.ecma262_env_op(
            env_id, "SetMutableBinding", name, value=value)

      elif env.get("type") == "Global":
        decl_rec_id = env.get("declarativeRecord")
        obj_rec_id = env.get("objectRecord")

        if decl_rec_id in state["environmentRecords"]:
          decl_env = state["environmentRecords"][decl_rec_id]
          if name in decl_env.get("bindings", {}):
            return self.ecma262_env_op(
                decl_rec_id, "InitializeBinding", name, value=value)

        if obj_rec_id in state["environmentRecords"]:
          return self.ecma262_env_op(
              obj_rec_id, "InitializeBinding", name, value=value)

        return f"Error: Binding {name} not found in Global environment."

      if name not in env["bindings"]:
        return f"Error: Binding {name} not created."
      if env["bindings"][name]["initialized"]:
        return f"Error: Assertion failed - Binding {name} is already initialized."
      env["bindings"][name]["value"] = value
      env["bindings"][name]["initialized"] = True
      msg = f"Initialized binding {name} to {value} in {env_id}"

    elif operation == "SetMutableBinding":
      if not isinstance(name, str):
        return f"Error: SetMutableBinding argument N (name) must be a string, got {type(name)}"

      if env.get("type") == "Object":
        binding_obj_id = env.get("bindingObject")
        if binding_obj_id in state["heap"]:
          has_prop = self.ecma262_object_op(binding_obj_id,
                                            "OrdinaryHasProperty", name)
          if isinstance(has_prop, str) and "requires_proxy_trap" in has_prop:
            return has_prop
          if not has_prop and strict:
            return f"Error: ReferenceError - Binding {name} not found in Object environment."

          res = self.ecma262_object_op(
              binding_obj_id, "OrdinarySet", name, value=value)
          res_data = json.loads(res)
          if res_data.get("status") == "failed" or (
              res_data.get("status") == "completed" and
              not res_data.get("success", True)):
            if strict:
              return f"Error: TypeError - Cannot set property {name} on Object environment binding."
            return json.dumps({"status": "completed", "success": False})
          return res
        return f"Error: BindingObject {binding_obj_id} not found."

      elif env.get("type") == "Global":
        decl_rec_id = env.get("declarativeRecord")
        obj_rec_id = env.get("objectRecord")

        if decl_rec_id in state["environmentRecords"]:
          decl_env = state["environmentRecords"][decl_rec_id]
          if name in decl_env.get("bindings", {}):
            return self.ecma262_env_op(
                decl_rec_id,
                "SetMutableBinding",
                name,
                value=value,
                strict=strict)

        if obj_rec_id in state["environmentRecords"]:
          return self.ecma262_env_op(
              obj_rec_id, "SetMutableBinding", name, value=value, strict=strict)

        return f"Error: Binding {name} not found in Global environment."

      if env.get(
          "type") == "Module" and "indirectBindings" in env and name in env[
              "indirectBindings"]:
        if strict:
          return f"Error: TypeError - Cannot set immutable binding {name} in {env_id}."
        return f"Ignored attempt to set immutable binding {name} in {env_id}"

      if name not in env["bindings"]:
        if strict:
          return f"Error: ReferenceError - Binding {name} not found in {env_id}."
        env["bindings"][name] = {
            "value": value,
            "strict": False,
            "mutable": True,
            "initialized": True,
            "deletable": True
        }
        msg = f"Created and set mutable binding {name} to {value} in {env_id}"
      else:
        if env["bindings"][name].get("strict", False):
          strict = True

        if not env["bindings"][name]["initialized"]:
          return f"Error: ReferenceError - Binding {name} not initialized (TDZ) in {env_id}."

        elif env["bindings"][name]["mutable"]:
          env["bindings"][name]["value"] = value
          msg = f"Set mutable binding {name} to {value} in {env_id}"
        else:
          if strict:
            return f"Error: TypeError - Cannot set immutable binding {name} in {env_id}."
          msg = f"Ignored attempt to set immutable binding {name} in {env_id}"
    elif operation == "DeleteBinding":
      if not isinstance(name, str):
        return f"Error: DeleteBinding argument N (name) must be a string, got {type(name)}"

      if env.get("type") == "Object":
        binding_obj_id = env.get("bindingObject")
        if binding_obj_id in state["heap"]:
          return self.ecma262_object_op(binding_obj_id, "OrdinaryDelete", name)
        return f"Error: BindingObject {binding_obj_id} not found."

      elif env.get("type") == "Global":
        decl_rec_id = env.get("declarativeRecord")
        obj_rec_id = env.get("objectRecord")

        if decl_rec_id in state["environmentRecords"]:
          decl_env = state["environmentRecords"][decl_rec_id]
          if name in decl_env.get("bindings", {}):
            return self.ecma262_env_op(decl_rec_id, "DeleteBinding", name)

        if obj_rec_id in state["environmentRecords"]:
          obj_env = state["environmentRecords"][obj_rec_id]
          binding_obj_id = obj_env.get("bindingObject")
          if binding_obj_id in state["heap"]:
            res = self.ecma262_object_op(binding_obj_id,
                                         "OrdinaryGetOwnProperty", name)
            if isinstance(res, str) and "requires_proxy_trap" in res:
              return res
            if res != "~undefined~":
              return self.ecma262_object_op(binding_obj_id, "OrdinaryDelete",
                                            name)

        return True

      if name not in env["bindings"]:
        result = True
      elif env["bindings"][name].get("deletable", True):
        del env["bindings"][name]
        result = True
      else:
        result = False

      self._write_state(state)
      return result
    elif operation == "HasBinding":
      if not isinstance(name, str):
        return f"Error: HasBinding argument N (name) must be a string, got {type(name)}"
      if env.get("type") in ["Declarative", "Function", "Module"]:
        if env.get(
            "type") == "Module" and "indirectBindings" in env and name in env[
                "indirectBindings"]:
          return json.dumps({
              "status":
                  "unsupported_feature",
              "reason":
                  f"Binding {name} is an import in Module environment",
              "instructions":
                  f"Please look up the binding in the target module {env['indirectBindings'][name]['module']} manually."
          })
        return name in env.get("bindings", {})
      elif env.get("type") == "Object":
        binding_obj_id = env.get("bindingObject")
        if binding_obj_id in state["heap"]:
          res = self.ecma262_object_op(binding_obj_id, "OrdinaryHasProperty",
                                       name)
          if isinstance(res, str) and "requires_proxy_trap" in res:
            return res
          return res is True
        return False
      elif env.get("type") == "Global":
        decl_rec_id = env.get("declarativeRecord")
        obj_rec_id = env.get("objectRecord")

        if decl_rec_id in state["environmentRecords"]:
          if name in state["environmentRecords"][decl_rec_id].get(
              "bindings", {}):
            return True

        if obj_rec_id in state["environmentRecords"]:
          obj_env = state["environmentRecords"][obj_rec_id]
          binding_obj_id = obj_env.get("bindingObject")
          if binding_obj_id in state["heap"]:
            res = self.ecma262_object_op(binding_obj_id, "OrdinaryHasProperty",
                                         name)
            if isinstance(res, str) and "requires_proxy_trap" in res:
              return res
            return res is True
        return False
    elif operation == "GetBindingValue":
      if not isinstance(name, str):
        return f"Error: GetBindingValue argument N (name) must be a string, got {type(name)}"

      if env.get("type") == "Object":
        binding_obj_id = env.get("bindingObject")
        if binding_obj_id in state["heap"]:
          # Spec: HasProperty(bindingObject, N)
          has_prop = self.ecma262_object_op(binding_obj_id,
                                            "OrdinaryHasProperty", name)
          if isinstance(has_prop, str) and "requires_proxy_trap" in has_prop:
            return has_prop
          if not has_prop:
            if strict:
              return f"Error: ReferenceError - Binding {name} not found in Object environment."
            return json.dumps("~undefined~")

          res = self.ecma262_object_op(binding_obj_id, "OrdinaryGet", name)
          res_data = json.loads(res)
          if res_data["status"] == "completed":
            return json.dumps(res_data["value"])
          else:
            return res
        return f"Error: BindingObject {binding_obj_id} not found."

      elif env.get("type") == "Global":
        decl_rec_id = env.get("declarativeRecord")
        obj_rec_id = env.get("objectRecord")

        if decl_rec_id in state["environmentRecords"]:
          decl_env = state["environmentRecords"][decl_rec_id]
          if name in decl_env.get("bindings", {}):
            if not decl_env["bindings"][name]["initialized"]:
              return f"Error: Binding {name} not initialized (TDZ)."
            return json.dumps(decl_env["bindings"][name]["value"])

        if obj_rec_id in state["environmentRecords"]:
          obj_env = state["environmentRecords"][obj_rec_id]
          binding_obj_id = obj_env.get("bindingObject")
          if binding_obj_id in state["heap"]:
            has_prop = self.ecma262_object_op(binding_obj_id,
                                              "OrdinaryHasProperty", name)
            if isinstance(has_prop, str) and "requires_proxy_trap" in has_prop:
              return has_prop
            if has_prop:
              res = self.ecma262_object_op(binding_obj_id, "OrdinaryGet", name)
              res_data = json.loads(res)
              if res_data["status"] == "completed":
                return json.dumps(res_data["value"])
              else:
                return res

        if strict:
          return f"Error: ReferenceError - Binding {name} not found in Global environment."
        return json.dumps("~undefined~")

      # Fallback to existing logic for Declarative, Function, Module
      if env.get(
          "type") == "Module" and "indirectBindings" in env and name in env[
              "indirectBindings"]:
        visited = set()
        current_env_id = env_id
        current_name = name

        while True:
          current_env = state["environmentRecords"][current_env_id]
          if current_env.get(
              "type"
          ) == "Module" and "indirectBindings" in current_env and current_name in current_env[
              "indirectBindings"]:
            if current_env_id in visited:
              return f"Error: Circular indirect binding detected for {name}."
            visited.add(current_env_id)

            indirect = current_env["indirectBindings"][current_name]
            current_env_id = indirect["module"]
            current_name = indirect["bindingName"]

            if current_env_id not in state["environmentRecords"]:
              return f"Error: Environment {current_env_id} not found for indirect binding."
            continue

          if current_name not in current_env.get("bindings", {}):
            return f"Error: Binding {current_name} not found in {current_env_id}."
          if not current_env["bindings"][current_name]["initialized"]:
            return f"Error: Binding {current_name} not initialized (TDZ) in {current_env_id}."
          return json.dumps(current_env["bindings"][current_name]["value"])

      if name not in env.get("bindings", {}):
        return f"Error: Binding {name} not found."
      if not env["bindings"][name]["initialized"]:
        return f"Error: Binding {name} not initialized (TDZ)."
      return json.dumps(env["bindings"][name]["value"])
    elif operation == "BindThisValue":
      if env.get("[[ThisBindingStatus]]") == "lexical":
        return "Error: Assertion failed - ThisBindingStatus is lexical in BindThisValue."
      if env.get("[[ThisBindingStatus]]") == "initialized":
        return "Error: ThisBindingStatus is already initialized."
      env["[[ThisValue]]"] = value
      env["[[ThisBindingStatus]]"] = "initialized"
      msg = f"Bound this value to {value} in {env_id}"
    elif operation == "HasThisBinding":
      if env.get("type") == "Function":
        has_this = env.get("[[ThisBindingStatus]]") != "lexical"
        return has_this
      if env.get("type") in ["Module", "Global"]:
        return True
      return False
    elif operation == "HasSuperBinding":
      if env.get("type") == "Function":
        has_this = env.get("[[ThisBindingStatus]]") != "lexical"
        if not has_this:
          return False
        func_obj_ref = env.get("[[FunctionObject]]")
        if func_obj_ref is None:
          return False
        if isinstance(func_obj_ref,
                      str) and func_obj_ref.startswith("ref:Obj:"):
          if func_obj_ref in state["heap"]:
            func_obj = state["heap"][func_obj_ref]
            home = func_obj.get("[[HomeObject]]")
            if home is None and "internalSlots" in func_obj:
              home = func_obj["internalSlots"].get("[[HomeObject]]")
            if home not in [None, "~undefined~"]:
              return True
        return False
      return False
    elif operation == "GetThisBinding":
      if env.get("type") == "Function":
        if env.get("[[ThisBindingStatus]]") == "lexical":
          return "Error: Assertion failed - ThisBindingStatus is lexical in GetThisBinding."
        if env.get("[[ThisBindingStatus]]") == "uninitialized":
          return "Error: ReferenceError - ThisBindingStatus is uninitialized."
        return json.dumps(env.get("[[ThisValue]]"))
      if env.get("type") == "Module":
        return json.dumps("~undefined~")
      if env.get("type") == "Global":
        return json.dumps(env.get("[[GlobalThisValue]]", "~undefined~"))
      return "Error: Not a function, module, or global environment."
    elif operation == "CreateImportBinding":
      if env.get("type") != "Module":
        return f"Error: Environment {env_id} is not a Module environment."
      if not isinstance(name, str):
        return f"Error: CreateImportBinding argument N (name) must be a string, got {type(name)}"
      if module_record is None or not isinstance(module_record, str):
        return f"Error: CreateImportBinding argument M (module_record) must be a string reference, got {type(module_record)}"
      if binding_name is None or not isinstance(binding_name, str):
        return f"Error: CreateImportBinding argument N2 (binding_name) must be a string, got {type(binding_name)}"

      if name in env.get("bindings", {}) or name in env.get(
          "indirectBindings", {}):
        return f"Error: Assertion failed - Binding {name} already exists in {env_id}."
      if module_record not in state["environmentRecords"]:
        return f"Error: Assertion failed - Module environment {module_record} not found."
      target_env = state["environmentRecords"][module_record]

      if binding_name not in target_env.get(
          "bindings", {}) and binding_name not in target_env.get(
              "indirectBindings", {}):
        return f"Error: Assertion failed - Module {module_record} does not contain binding {binding_name}."

      if "indirectBindings" not in env:
        env["indirectBindings"] = {}
      env["indirectBindings"][name] = {
          "module": module_record,
          "bindingName": binding_name
      }
      msg = f"Created import binding {name} in {env_id}"
    else:
      return f"Error: Unknown operation {operation}"

    self._write_state(state)
    warnings = self._check_value_warnings(value)
    if warnings:
      msg += "\n" + "\n".join(warnings)
    return msg

  def _same_value(self, x, y):
    if type(x) != type(y):
      return False
    if isinstance(x, float) and isinstance(y, float):
      if x != x and y != y:  # Both NaN
        return True
      if x == 0 and y == 0:
        import math
        return math.copysign(1, x) == math.copysign(1, y)
    return x == y

  def _validate_and_apply_property_descriptor(self, obj, p, extensible, desc,
                                              current):
    if current is None:
      if not extensible:
        return False
      is_accessor = "get" in desc or "set" in desc
      if is_accessor:
        obj["properties"][p] = {
            "get": desc.get("get", None),
            "set": desc.get("set", None),
            "enumerable": desc.get("enumerable", False),
            "configurable": desc.get("configurable", False)
        }
      else:
        obj["properties"][p] = {
            "value": desc.get("value", "~undefined~"),
            "writable": desc.get("writable", False),
            "enumerable": desc.get("enumerable", False),
            "configurable": desc.get("configurable", False)
        }
      return True

    if not desc:
      return True

    if not current.get("configurable", False):
      if desc.get("configurable", False):
        return False
      if "enumerable" in desc and desc["enumerable"] != current.get(
          "enumerable", False):
        return False

      is_new_accessor = "get" in desc or "set" in desc
      is_curr_accessor = "get" in current or "set" in current

      is_generic = "value" not in desc and "writable" not in desc and "get" not in desc and "set" not in desc
      if not is_generic and is_new_accessor != is_curr_accessor:
        return False

      if is_curr_accessor:
        if "get" in desc and not self._same_value(desc["get"],
                                                  current.get("get", None)):
          return False
        if "set" in desc and not self._same_value(desc["set"],
                                                  current.get("set", None)):
          return False
      elif not current.get("writable", False):
        if desc.get("writable", False):
          return False
        if "value" in desc:
          return self._same_value(desc["value"], current.get("value", None))

    is_new_accessor = "get" in desc or "set" in desc
    is_curr_accessor = "get" in current or "set" in current

    if is_curr_accessor and not is_new_accessor and ("value" in desc or
                                                     "writable" in desc):
      configurable = desc.get("configurable",
                              current.get("configurable", False))
      enumerable = desc.get("enumerable", current.get("enumerable", False))
      obj["properties"][p] = {
          "value": desc.get("value", "~undefined~"),
          "writable": desc.get("writable", False),
          "enumerable": enumerable,
          "configurable": configurable
      }
    elif not is_curr_accessor and is_new_accessor:
      configurable = desc.get("configurable",
                              current.get("configurable", False))
      enumerable = desc.get("enumerable", current.get("enumerable", False))
      obj["properties"][p] = {
          "get": desc.get("get", None),
          "set": desc.get("set", None),
          "enumerable": enumerable,
          "configurable": configurable
      }
    else:
      for field, val in desc.items():
        current[field] = val

    return True

  def _ordinary_set_prototype_of(self, state, object_id, v):
    obj = state["heap"][object_id]
    current = obj["internalSlots"].get("[[Prototype]]", None)
    if self._same_value(v, current):
      return True
    extensible = obj["internalSlots"].get("[[Extensible]]", True)
    if not extensible:
      return False
    p = v
    while p is not None:
      if p == object_id:
        return False
      if p not in state["heap"]:
        break
      p_obj = state["heap"][p]
      p = p_obj["internalSlots"].get("[[Prototype]]", None)
    obj["internalSlots"]["[[Prototype]]"] = v
    return True

  def _ordinary_own_property_keys(self, obj):
    keys = list(obj["properties"].keys())
    array_indices = []
    other_strings = []

    if "[[StringData]]" in obj["internalSlots"]:
      str_data = obj["internalSlots"]["[[StringData]]"]
      for i in range(len(str_data)):
        array_indices.append(str(i))

    for k in keys:
      if self._is_canonical_numeric_index(k):
        val = int(k)
        if val <= 2**32 - 2:
          if k not in array_indices:
            array_indices.append(k)
        else:
          other_strings.append(k)
      else:
        other_strings.append(k)
    array_indices.sort(key=int)

    strings = []
    symbols = []
    for k in other_strings:
      if k.startswith("Symbol("):
        symbols.append(k)
      else:
        strings.append(k)

    return array_indices + strings + symbols

  def _is_canonical_numeric_index(self, p):
    if not isinstance(p, str):
      return False
    if p == "-0":
      return True
    if p.isdigit() and str(int(p)) == p and int(p) <= 2**32 - 2:
      return True
    return False

  def ecma262_object_op(self,
                        object_id,
                        operation,
                        property_name=None,
                        value=None,
                        descriptor=None):
    state = self._read_state()
    if not state:
      return "Error: State not initialized."

    if operation == "MakeBasicObject":
      if not object_id:
        object_id = f"ref:Obj:{len(state['heap']) + 1}"

      internal_slots = []
      if descriptor and "internalSlots" in descriptor:
        internal_slots = list(descriptor["internalSlots"])

      if "[[PrivateElements]]" not in internal_slots:
        internal_slots.append("[[PrivateElements]]")

      state["heap"][object_id] = {
          "internalSlots": {
              slot: "~undefined~" for slot in internal_slots
          },
          "properties": {}
      }

      state["heap"][object_id]["internalSlots"]["[[PrivateElements]]"] = []
      if "[[Extensible]]" in internal_slots:
        state["heap"][object_id]["internalSlots"]["[[Extensible]]"] = True

      self._write_state(state)
      return f"MakeBasicObject {object_id}"

    elif operation == "OrdinaryObjectCreate":
      if value is not None and not (isinstance(value, str) and
                                    value.startswith("ref:")):
        return f"Error: OrdinaryObjectCreate argument proto (value) must be None or a string reference starting with 'ref:', got {type(value)}"
      if not object_id:
        object_id = f"ref:Obj:{len(state['heap']) + 1}"

      additional_slots = []
      if descriptor and "additionalSlots" in descriptor:
        additional_slots = descriptor["additionalSlots"]

      internal_slots = ["[[Prototype]]", "[[Extensible]]"]
      for slot in additional_slots:
        if slot not in internal_slots:
          internal_slots.append(slot)

      if "[[PrivateElements]]" not in internal_slots:
        internal_slots.append("[[PrivateElements]]")

      state["heap"][object_id] = {
          "internalSlots": {
              slot: "~undefined~" for slot in internal_slots
          },
          "properties": {}
      }

      state["heap"][object_id]["internalSlots"]["[[PrivateElements]]"] = []
      if "[[Extensible]]" in internal_slots:
        state["heap"][object_id]["internalSlots"]["[[Extensible]]"] = True

      proto = value
      state["heap"][object_id]["internalSlots"]["[[Prototype]]"] = proto

      self._write_state(state)
      return f"OrdinaryObjectCreate {object_id}"

    elif operation == "OrdinaryFunctionCreate":
      if not object_id:
        object_id = f"ref:Obj:{len(state['heap']) + 1}"

      internal_slots = [
          "[[Prototype]]", "[[Extensible]]", "[[Call]]", "[[FormalParameters]]",
          "[[ECMAScriptCode]]", "[[Realm]]", "[[ScriptOrModule]]",
          "[[ThisMode]]", "[[Strict]]", "[[HomeObject]]", "[[SourceText]]",
          "[[PrivateElements]]"
      ]

      state["heap"][object_id] = {
          "internalSlots": {
              slot: "~undefined~" for slot in internal_slots
          },
          "properties": {}
      }

      state["heap"][object_id]["internalSlots"]["[[PrivateElements]]"] = []
      state["heap"][object_id]["internalSlots"]["[[Extensible]]"] = True

      proto = value if value is not None else "ref:Obj:FunctionProto"
      state["heap"][object_id]["internalSlots"]["[[Prototype]]"] = proto
      state["heap"][object_id]["internalSlots"]["[[Call]]"] = True

      if descriptor:
        if "parameters" in descriptor:
          state["heap"][object_id]["internalSlots"][
              "[[FormalParameters]]"] = descriptor["parameters"]
        if "body" in descriptor:
          state["heap"][object_id]["internalSlots"][
              "[[ECMAScriptCode]]"] = descriptor["body"]
        if "homeObject" in descriptor:
          state["heap"][object_id]["internalSlots"][
              "[[HomeObject]]"] = descriptor["homeObject"]
        if "realm" in descriptor:
          state["heap"][object_id]["internalSlots"]["[[Realm]]"] = descriptor[
              "realm"]
        if "strict" in descriptor:
          state["heap"][object_id]["internalSlots"]["[[Strict]]"] = descriptor[
              "strict"]
        if "construct" in descriptor and descriptor["construct"]:
          state["heap"][object_id]["internalSlots"]["[[Construct]]"] = True

      self._write_state(state)
      return f"OrdinaryFunctionCreate {object_id}"

    elif operation == "CreatePrivateName":
      if "privateNameCounter" not in state:
        state["privateNameCounter"] = 0
      state["privateNameCounter"] += 1
      priv_id = f"ref:Priv:{state['privateNameCounter']}"

      desc = property_name if property_name else ""

      if "privateNames" not in state:
        state["privateNames"] = {}
      state["privateNames"][priv_id] = {"[[Description]]": desc}

      self._write_state(state)
      return priv_id

    elif operation == "ProxyCreate":
      target = value
      handler = descriptor.get("handler", None) if descriptor else None
      if not target or not handler:
        return "Error: ProxyCreate requires both target (value) and handler (descriptor.handler) references."

      if target not in state["heap"]:
        return f"Error: Target {target} not found in heap."
      if handler not in state["heap"]:
        return f"Error: Handler {handler} not found in heap."

      target_obj = state["heap"][target]

      if "objectCounter" not in state:
        state["objectCounter"] = 0
      state["objectCounter"] += 1
      proxy_id = f"ref:Obj:{state['objectCounter']}"

      slots = {
          "[[Prototype]]": None,
          "[[Extensible]]": True,
          "[[ProxyTarget]]": target,
          "[[ProxyHandler]]": handler
      }

      # Copy Call and Construct slots if present on target
      if "[[Call]]" in target_obj["internalSlots"]:
        slots["[[Call]]"] = True
      if "[[Construct]]" in target_obj["internalSlots"]:
        slots["[[Construct]]"] = True

      state["heap"][proxy_id] = {"properties": {}, "internalSlots": slots}
      self._write_state(state)
      return f"ProxyCreate {proxy_id}"

    elif operation == "ArrayCreate":
      length = value if value is not None else 0

      if not isinstance(length, int) or length < 0 or length > 2**32 - 1:
        return f"Error: RangeError: Invalid array length: {length}"

      proto = descriptor.get(
          "proto", "ref:Obj:ArrayProto") if descriptor else "ref:Obj:ArrayProto"

      if "objectCounter" not in state:
        state["objectCounter"] = 0
      state["objectCounter"] += 1
      array_id = f"ref:Obj:{state['objectCounter']}"

      state["heap"][array_id] = {
          "properties": {
              "length": {
                  "value": length,
                  "writable": True,
                  "enumerable": False,
                  "configurable": False
              }
          },
          "internalSlots": {
              "[[Prototype]]": proto,
              "[[Extensible]]": True,
              "[[ArrayLength]]": length
          }
      }
      self._write_state(state)
      return f"ArrayCreate {array_id}"

    elif operation == "StringCreate":
      if not isinstance(value, str):
        return f"Error: StringCreate requires a string value, got {type(value)}"

      if any(ord(c) > 0xFFFF for c in value):
        return json.dumps({
            "status":
                "unsupported_feature",
            "reason":
                "non-BMP characters (requiring surrogate pairs in UTF-16) are not supported in StringCreate",
            "instructions":
                "Please handle this string operation manually or avoid using non-BMP characters."
        })

      proto = descriptor.get(
          "proto",
          "ref:Obj:StringProto") if descriptor else "ref:Obj:StringProto"

      string_id = f"ref:Obj:{len(state['heap']) + 1}"

      state["heap"][string_id] = {
          "properties": {
              "length": {
                  "value": len(value),
                  "writable": False,
                  "enumerable": False,
                  "configurable": False
              }
          },
          "internalSlots": {
              "[[Prototype]]": proto,
              "[[Extensible]]": True,
              "[[StringData]]": value
          }
      }
      self._write_state(state)
      return f"StringCreate {string_id}"

    if object_id not in state["heap"]:
      return f"Error: Object {object_id} not found in heap."

    obj = state["heap"][object_id]

    if operation == "SetInternalSlot":
      if not isinstance(property_name, str):
        return f"Error: SetInternalSlot argument property_name must be a string, got {type(property_name)}"
      if property_name not in obj["internalSlots"]:
        return f"Error: Internal slot {property_name} was not declared during object creation."
      obj["internalSlots"][property_name] = value
      msg = f"Set internal slot {property_name} to {value} in {object_id}"
    elif operation == "OrdinaryDefineOwnProperty":
      if not isinstance(property_name, str):
        return f"Error: OrdinaryDefineOwnProperty argument property_name must be a string, got {type(property_name)}"
      if descriptor is not None and not isinstance(descriptor, dict):
        return f"Error: OrdinaryDefineOwnProperty argument descriptor must be a dictionary, got {type(descriptor)}"

      if "[[ProxyTarget]]" in obj["internalSlots"]:
        handler = obj["internalSlots"]["[[ProxyHandler]]"]
        target = obj["internalSlots"]["[[ProxyTarget]]"]
        return json.dumps({
            "status": "requires_proxy_trap",
            "trap": "defineProperty",
            "handler": handler,
            "target": target,
            "p": property_name,
            "desc": descriptor
        })

      is_string_index = False
      if "[[StringData]]" in obj[
          "internalSlots"] and self._is_canonical_numeric_index(property_name):
        str_data = obj["internalSlots"]["[[StringData]]"]
        idx = int(property_name)
        if 0 <= idx < len(str_data):
          is_string_index = True
          current = {
              "value": str_data[idx],
              "writable": False,
              "enumerable": True,
              "configurable": False
          }
        else:
          current = None
      else:
        current = obj["properties"].get(property_name, None)
      extensible = obj["internalSlots"].get("[[Extensible]]", True)

      if descriptor is None:
        descriptor = {
            "value": value,
            "enumerable": True,
            "configurable": True,
            "writable": True
        }

      # Task 8: ArraySetLength
      if "[[ArrayLength]]" in obj["internalSlots"] and property_name == "length":
        if descriptor.get("enumerable", False) is True or descriptor.get(
            "configurable", False) is True:
          return False

        if "value" in descriptor:
          new_len = descriptor["value"]
          if not isinstance(new_len, int) or new_len < 0 or new_len > 2**32 - 1:
            return f"Error: RangeError: Invalid array length: {new_len}"

          old_len = obj["internalSlots"]["[[ArrayLength]]"]
          if new_len != old_len and "length" in obj["properties"] and not obj[
              "properties"]["length"].get("writable", True):
            return False
          if new_len < old_len:
            keys_to_delete = []
            for k in obj["properties"].keys():
              if self._is_canonical_numeric_index(k) and k != "-0":
                idx = int(k)
                if idx >= new_len:
                  keys_to_delete.append(k)

            keys_to_delete.sort(key=int, reverse=True)
            for k in keys_to_delete:
              desc = obj["properties"].get(k, None)
              if desc and not desc.get("configurable", False):
                new_len = int(k) + 1
                obj["internalSlots"]["[[ArrayLength]]"] = new_len
                if "length" in obj["properties"]:
                  obj["properties"]["length"]["value"] = new_len
                  # Task 4: Apply writable false if requested
                  if descriptor.get("writable") is False:
                    obj["properties"]["length"]["writable"] = False
                self._write_state(state)
                return False
              del obj["properties"][k]

          obj["internalSlots"]["[[ArrayLength]]"] = new_len
          if "length" in obj["properties"]:
            obj["properties"]["length"]["value"] = new_len
            # Task 3: Apply writable attribute on success
            if "writable" in descriptor:
              obj["properties"]["length"]["writable"] = descriptor["writable"]

          self._write_state(state)
          return True

      # Task 4: Out-of-Bounds Array element insertion when length is non-writable
      if "[[ArrayLength]]" in obj[
          "internalSlots"] and self._is_canonical_numeric_index(property_name):
        idx = int(property_name)
        old_len = obj["internalSlots"]["[[ArrayLength]]"]
        if idx >= old_len:
          if "length" in obj["properties"] and not obj["properties"][
              "length"].get("writable", True):
            return False

      success = self._validate_and_apply_property_descriptor(
          obj, property_name, False if is_string_index else extensible,
          descriptor, current)

      if success:
        # Task 2: Array index additions updating length
        if "[[ArrayLength]]" in obj[
            "internalSlots"] and self._is_canonical_numeric_index(
                property_name):
          idx = int(property_name)
          old_len = obj["internalSlots"]["[[ArrayLength]]"]
          if idx >= old_len:
            new_len = idx + 1
            obj["internalSlots"]["[[ArrayLength]]"] = new_len
            if "length" in obj["properties"]:
              obj["properties"]["length"]["value"] = new_len

        self._write_state(state)
      return success

    elif operation == "CreateDataProperty":
      if not isinstance(property_name, str):
        return f"Error: CreateDataProperty argument property_name must be a string, got {type(property_name)}"

      if "[[ProxyTarget]]" in obj["internalSlots"]:
        handler = obj["internalSlots"]["[[ProxyHandler]]"]
        target = obj["internalSlots"]["[[ProxyTarget]]"]
        return json.dumps({
            "status": "requires_proxy_trap",
            "trap": "defineProperty",
            "handler": handler,
            "target": target,
            "p": property_name,
            "desc": {
                "value": value,
                "writable": True,
                "enumerable": True,
                "configurable": True
            }
        })

      current = obj["properties"].get(property_name, None)
      extensible = obj["internalSlots"].get("[[Extensible]]", True)
      descriptor = {
          "value": value,
          "enumerable": True,
          "configurable": True,
          "writable": True
      }
      success = self._validate_and_apply_property_descriptor(
          obj, property_name, extensible, descriptor, current)
      if success:
        self._write_state(state)
      return success

    elif operation == "PrivateFieldAdd":
      if not isinstance(property_name, str):
        return f"Error: PrivateFieldAdd argument property_name must be a string, got {type(property_name)}"
      priv_elements = obj["internalSlots"].get("[[PrivateElements]]", [])
      for elem in priv_elements:
        if elem["[[Key]]"] == property_name:
          return f"Error: Private field {property_name} already exists on object."
      priv_elements.append({"[[Key]]": property_name, "[[Value]]": value})
      obj["internalSlots"]["[[PrivateElements]]"] = priv_elements
      self._write_state(state)
      return True

    elif operation == "PrivateFieldGet":
      if not isinstance(property_name, str):
        return f"Error: PrivateFieldGet argument property_name must be a string, got {type(property_name)}"
      priv_elements = obj["internalSlots"].get("[[PrivateElements]]", [])
      for elem in priv_elements:
        if elem["[[Key]]"] == property_name:
          return elem["[[Value]]"]
      return f"Error: Private field {property_name} not found on object."

    elif operation == "PrivateFieldSet":
      if not isinstance(property_name, str):
        return f"Error: PrivateFieldSet argument property_name must be a string, got {type(property_name)}"
      priv_elements = obj["internalSlots"].get("[[PrivateElements]]", [])
      for elem in priv_elements:
        if elem["[[Key]]"] == property_name:
          elem["[[Value]]"] = value
          self._write_state(state)
          return True
      return f"Error: Private field {property_name} not found on object."

    elif operation == "OrdinaryGetPrototypeOf":
      if "[[ProxyTarget]]" in obj["internalSlots"]:
        handler = obj["internalSlots"]["[[ProxyHandler]]"]
        target = obj["internalSlots"]["[[ProxyTarget]]"]
        return json.dumps({
            "status": "requires_proxy_trap",
            "trap": "getPrototypeOf",
            "handler": handler,
            "target": target
        })
      return obj["internalSlots"].get("[[Prototype]]", None)

    elif operation == "OrdinarySetPrototypeOf":
      if "[[ProxyTarget]]" in obj["internalSlots"]:
        handler = obj["internalSlots"]["[[ProxyHandler]]"]
        target = obj["internalSlots"]["[[ProxyTarget]]"]
        return json.dumps({
            "status": "requires_proxy_trap",
            "trap": "setPrototypeOf",
            "handler": handler,
            "target": target,
            "v": value
        })
      if value is not None and not (isinstance(value, str) and
                                    value.startswith("ref:")):
        return f"Error: OrdinarySetPrototypeOf argument V (proto) must be None or a string reference starting with 'ref:', got {type(value)}"
      success = self._ordinary_set_prototype_of(state, object_id, value)
      if success:
        self._write_state(state)
      return success

    elif operation == "OrdinaryIsExtensible":
      if "[[ProxyTarget]]" in obj["internalSlots"]:
        handler = obj["internalSlots"]["[[ProxyHandler]]"]
        target = obj["internalSlots"]["[[ProxyTarget]]"]
        if target is None or target == "~null~":
          return f"Error: TypeError - Cannot perform isExtensible on revoked proxy."
        return json.dumps({
            "status": "requires_proxy_trap",
            "trap": "isExtensible",
            "handler": handler,
            "target": target
        })
      return obj["internalSlots"].get("[[Extensible]]", True)

    elif operation == "OrdinaryPreventExtensions":
      if "[[ProxyTarget]]" in obj["internalSlots"]:
        handler = obj["internalSlots"]["[[ProxyHandler]]"]
        target = obj["internalSlots"]["[[ProxyTarget]]"]
        if target is None or target == "~null~":
          return f"Error: TypeError - Cannot perform preventExtensions on revoked proxy."
        return json.dumps({
            "status": "requires_proxy_trap",
            "trap": "preventExtensions",
            "handler": handler,
            "target": target
        })
      obj["internalSlots"]["[[Extensible]]"] = False
      self._write_state(state)
      return True

    elif operation == "OrdinaryGetOwnProperty":
      if not isinstance(property_name, str):
        return f"Error: OrdinaryGetOwnProperty argument property_name must be a string, got {type(property_name)}"

      # Check for exotic objects
      standard_slots = {
          "[[Prototype]]", "[[Extensible]]", "[[PrivateElements]]", "[[Realm]]",
          "[[Environment]]", "[[FormalParameters]]", "[[ECMAScriptCode]]",
          "[[ConstructorKind]]", "[[SourceText]]", "[[IsClassConstructor]]",
          "[[HomeObject]]", "[[Fields]]", "[[PrivateMethods]]",
          "[[ArrayLength]]"
      }

      obj_slots = set(obj["internalSlots"].keys())
      non_standard_slots = obj_slots - standard_slots

      if non_standard_slots:
        if "[[ProxyTarget]]" in obj["internalSlots"]:
          handler = obj["internalSlots"]["[[ProxyHandler]]"]
          target = obj["internalSlots"]["[[ProxyTarget]]"]
          return json.dumps({
              "status": "requires_proxy_trap",
              "trap": "getOwnPropertyDescriptor",
              "handler": handler,
              "target": target,
              "p": property_name
          })
        elif "[[StringData]]" not in obj[
            "internalSlots"] and "[[ArrayLength]]" not in obj["internalSlots"]:
          return json.dumps({
              "status":
                  "unsupported_exotic_object",
              "slots":
                  list(non_standard_slots),
              "instructions":
                  f"Object {object_id} is an unsupported exotic object with slots {list(non_standard_slots)}. Please follow the spec for its [[GetOwnProperty]] method manually."
          })
      if "[[StringData]]" in obj["internalSlots"]:
        str_data = obj["internalSlots"]["[[StringData]]"]
        if self._is_canonical_numeric_index(property_name):
          idx = int(property_name)
          if 0 <= idx < len(str_data):
            return json.dumps({
                "value": str_data[idx],
                "writable": False,
                "enumerable": True,
                "configurable": False
            })

      desc = obj["properties"].get(property_name, None)
      if desc is None:
        return "~undefined~"
      return json.dumps(desc)

    elif operation == "OrdinaryHasProperty":
      if not isinstance(property_name, str):
        return f"Error: OrdinaryHasProperty argument property_name must be a string, got {type(property_name)}"

      standard_slots = {
          "[[Prototype]]", "[[Extensible]]", "[[PrivateElements]]", "[[Realm]]",
          "[[Environment]]", "[[FormalParameters]]", "[[ECMAScriptCode]]",
          "[[ConstructorKind]]", "[[SourceText]]", "[[IsClassConstructor]]",
          "[[HomeObject]]", "[[Fields]]", "[[PrivateMethods]]",
          "[[ArrayLength]]"
      }

      p = property_name
      curr_obj_id = object_id
      while curr_obj_id:
        curr_obj = state["heap"][curr_obj_id]

        obj_slots = set(curr_obj["internalSlots"].keys())
        non_standard_slots = obj_slots - standard_slots

        if non_standard_slots:
          if "[[ProxyTarget]]" in curr_obj["internalSlots"]:
            handler = curr_obj["internalSlots"]["[[ProxyHandler]]"]
            target = curr_obj["internalSlots"]["[[ProxyTarget]]"]
            return json.dumps({
                "status": "requires_proxy_trap",
                "trap": "has",
                "handler": handler,
                "target": target,
                "property": property_name
            })
          elif "[[StringData]]" not in curr_obj[
              "internalSlots"] and "[[ArrayLength]]" not in curr_obj[
                  "internalSlots"]:
            return json.dumps({
                "status":
                    "unsupported_exotic_object",
                "slots":
                    list(non_standard_slots),
                "instructions":
                    f"Object {curr_obj_id} is an unsupported exotic object with slots {list(non_standard_slots)}. Please follow the spec for its [[HasProperty]] method manually."
            })

        if p in curr_obj["properties"]:
          return True
        if "[[StringData]]" in curr_obj["internalSlots"]:
          str_data = curr_obj["internalSlots"]["[[StringData]]"]
          if self._is_canonical_numeric_index(p):
            idx = int(p)
            if 0 <= idx < len(str_data):
              return True

        curr_obj_id = curr_obj["internalSlots"].get("[[Prototype]]", None)
        if not curr_obj_id or curr_obj_id not in state["heap"]:
          break
      return False

    elif operation == "OrdinaryDelete":
      if not isinstance(property_name, str):
        return f"Error: OrdinaryDelete argument property_name must be a string, got {type(property_name)}"

      standard_slots = {
          "[[Prototype]]", "[[Extensible]]", "[[PrivateElements]]", "[[Realm]]",
          "[[Environment]]", "[[FormalParameters]]", "[[ECMAScriptCode]]",
          "[[ConstructorKind]]", "[[SourceText]]", "[[IsClassConstructor]]",
          "[[HomeObject]]", "[[Fields]]", "[[PrivateMethods]]",
          "[[ArrayLength]]"
      }

      obj_slots = set(obj["internalSlots"].keys())
      non_standard_slots = obj_slots - standard_slots

      if non_standard_slots:
        if "[[ProxyTarget]]" in obj["internalSlots"]:
          handler = obj["internalSlots"]["[[ProxyHandler]]"]
          target = obj["internalSlots"]["[[ProxyTarget]]"]
          return json.dumps({
              "status": "requires_proxy_trap",
              "trap": "deleteProperty",
              "handler": handler,
              "target": target,
              "property": property_name
          })
        elif "[[StringData]]" not in obj[
            "internalSlots"] and "[[ArrayLength]]" not in obj["internalSlots"]:
          return json.dumps({
              "status":
                  "unsupported_exotic_object",
              "slots":
                  list(non_standard_slots),
              "instructions":
                  f"Object {object_id} is an unsupported exotic object with slots {list(non_standard_slots)}. Please follow the spec for its [[Delete]] method manually."
          })

      if "[[StringData]]" in obj["internalSlots"]:
        if self._is_canonical_numeric_index(property_name):
          idx = int(property_name)
          str_data = obj["internalSlots"]["[[StringData]]"]
          if 0 <= idx < len(str_data):
            return False  # Cannot delete string indices

      desc = obj["properties"].get(property_name, None)
      if not desc:
        return True
      if desc.get("configurable", False):
        del obj["properties"][property_name]
        self._write_state(state)
        return True
      return False

    elif operation == "OrdinaryOwnPropertyKeys":
      if "[[ProxyTarget]]" in obj["internalSlots"]:
        handler = obj["internalSlots"]["[[ProxyHandler]]"]
        target = obj["internalSlots"]["[[ProxyTarget]]"]
        return json.dumps({
            "status": "requires_proxy_trap",
            "trap": "ownKeys",
            "handler": handler,
            "target": target
        })
      keys = self._ordinary_own_property_keys(obj)
      return json.dumps(keys)

    elif operation == "OrdinaryGet":
      if not isinstance(property_name, str):
        return f"Error: OrdinaryGet argument property_name must be a string, got {type(property_name)}"
      receiver = descriptor.get("receiver",
                                object_id) if descriptor else object_id

      standard_slots = {
          "[[Prototype]]", "[[Extensible]]", "[[PrivateElements]]", "[[Realm]]",
          "[[Environment]]", "[[FormalParameters]]", "[[ECMAScriptCode]]",
          "[[ConstructorKind]]", "[[SourceText]]", "[[IsClassConstructor]]",
          "[[HomeObject]]", "[[Fields]]", "[[PrivateMethods]]",
          "[[ArrayLength]]"
      }

      curr_obj_id = object_id
      while curr_obj_id:
        curr_obj = state["heap"][curr_obj_id]

        obj_slots = set(curr_obj["internalSlots"].keys())
        non_standard_slots = obj_slots - standard_slots

        if non_standard_slots:
          if "[[ProxyTarget]]" in curr_obj["internalSlots"]:
            handler = curr_obj["internalSlots"]["[[ProxyHandler]]"]
            target = curr_obj["internalSlots"]["[[ProxyTarget]]"]
            return json.dumps({
                "status": "requires_proxy_trap",
                "trap": "get",
                "handler": handler,
                "target": target,
                "property": property_name,
                "receiver": receiver
            })
          elif "[[StringData]]" in curr_obj["internalSlots"]:
            str_data = curr_obj["internalSlots"]["[[StringData]]"]
            if self._is_canonical_numeric_index(property_name):
              idx = int(property_name)
              if 0 <= idx < len(str_data):
                return json.dumps({
                    "status": "completed",
                    "value": str_data[idx]
                })
          else:
            return json.dumps({
                "status":
                    "unsupported_exotic_object",
                "slots":
                    list(non_standard_slots),
                "instructions":
                    f"Object {curr_obj_id} is an unsupported exotic object with slots {list(non_standard_slots)}. Please follow the spec for its [[Get]] method manually."
            })

        desc = curr_obj["properties"].get(property_name, None)
        if desc is not None:
          if "get" in desc or "set" in desc:
            getter = desc.get("get", None)
            if getter is None or getter == "~undefined~":
              return json.dumps({"status": "completed", "value": "~undefined~"})
            return json.dumps({
                "status": "requires_getter_invocation",
                "getter": getter,
                "receiver": receiver
            })
          else:
            return json.dumps({
                "status": "completed",
                "value": desc.get("value", "~undefined~")
            })

        curr_obj_id = curr_obj["internalSlots"].get("[[Prototype]]", None)
        if not curr_obj_id or curr_obj_id not in state["heap"]:
          break

      return json.dumps({"status": "completed", "value": "~undefined~"})

    elif operation == "OrdinarySet":
      if not isinstance(property_name, str):
        return f"Error: OrdinarySet argument property_name must be a string, got {type(property_name)}"
      receiver_id = descriptor.get("receiver",
                                   object_id) if descriptor else object_id
      if not isinstance(receiver_id, str) or not receiver_id.startswith("ref:"):
        return json.dumps({"status": "completed", "success": False})
      if receiver_id not in state["heap"]:
        return f"Error: Receiver {receiver_id} not found in heap."
      receiver_obj = state["heap"][receiver_id]

      # Prevent setting indexed properties on Strings
      if "[[StringData]]" in receiver_obj["internalSlots"]:
        if self._is_canonical_numeric_index(property_name):
          idx = int(property_name)
          str_data = receiver_obj["internalSlots"]["[[StringData]]"]
          if 0 <= idx < len(str_data):
            return json.dumps({
                "status": "failed",
                "reason": "cannot set indexed property on string"
            })

      standard_slots = {
          "[[Prototype]]", "[[Extensible]]", "[[PrivateElements]]", "[[Realm]]",
          "[[Environment]]", "[[FormalParameters]]", "[[ECMAScriptCode]]",
          "[[ConstructorKind]]", "[[SourceText]]", "[[IsClassConstructor]]",
          "[[HomeObject]]", "[[Fields]]", "[[PrivateMethods]]",
          "[[ArrayLength]]"
      }

      curr_obj_id = object_id
      found_desc = None
      while curr_obj_id:
        curr_obj = state["heap"][curr_obj_id]

        obj_slots = set(curr_obj["internalSlots"].keys())
        non_standard_slots = obj_slots - standard_slots

        if non_standard_slots:
          if "[[ProxyTarget]]" in curr_obj["internalSlots"]:
            handler = curr_obj["internalSlots"]["[[ProxyHandler]]"]
            target = curr_obj["internalSlots"]["[[ProxyTarget]]"]
            return json.dumps({
                "status": "requires_proxy_trap",
                "trap": "set",
                "handler": handler,
                "target": target,
                "property": property_name,
                "value": value,
                "receiver": receiver_id
            })
          elif "[[StringData]]" not in curr_obj[
              "internalSlots"] and "[[ArrayLength]]" not in curr_obj[
                  "internalSlots"]:
            return json.dumps({
                "status":
                    "unsupported_exotic_object",
                "slots":
                    list(non_standard_slots),
                "instructions":
                    f"Object {curr_obj_id} is an unsupported exotic object with slots {list(non_standard_slots)}. Please follow the spec for its [[Set]] method manually."
            })

        if "[[StringData]]" in curr_obj[
            "internalSlots"] and self._is_canonical_numeric_index(
                property_name):
          str_data = curr_obj["internalSlots"]["[[StringData]]"]
          idx = int(property_name)
          if 0 <= idx < len(str_data):
            desc = {
                "value": str_data[idx],
                "writable": False,
                "enumerable": True,
                "configurable": False
            }
          else:
            desc = None
        else:
          desc = curr_obj["properties"].get(property_name, None)

        if desc is not None:
          found_desc = desc
          break

        curr_obj_id = curr_obj["internalSlots"].get("[[Prototype]]", None)
        if not curr_obj_id or curr_obj_id not in state["heap"]:
          break

      if found_desc:
        if "get" in found_desc or "set" in found_desc:
          setter = found_desc.get("set", None)
          if setter is None or setter == "~undefined~":
            return json.dumps({"status": "failed", "reason": "no setter"})
          return json.dumps({
              "status": "requires_setter_invocation",
              "setter": setter,
              "receiver": receiver_id,
              "value": value
          })
        elif not found_desc.get("writable", False):
          return json.dumps({
              "status": "failed",
              "reason": "non-writable in prototype"
          })

      res = self.ecma262_object_op(receiver_id, "OrdinaryGetOwnProperty",
                                   property_name)
      if isinstance(res, str) and "requires_proxy_trap" in res:
        return res

      existing_desc = None
      if res != "~undefined~":
        existing_desc = json.loads(res)

      if existing_desc:
        if "get" in existing_desc or "set" in existing_desc:
          return json.dumps({
              "status": "failed",
              "reason": "receiver has accessor"
          })
        if not existing_desc.get("writable", False):
          return json.dumps({
              "status": "failed",
              "reason": "receiver property is non-writable"
          })

        res = self.ecma262_object_op(
            receiver_id,
            "OrdinaryDefineOwnProperty",
            property_name,
            descriptor={"value": value})
        if isinstance(res, str) and "requires_proxy_trap" in res:
          return res
        return json.dumps({"status": "completed", "success": res})
      else:
        res = self.ecma262_object_op(
            receiver_id,
            "OrdinaryDefineOwnProperty",
            property_name,
            value=value)
        if isinstance(res, str) and "requires_proxy_trap" in res:
          return res
        return json.dumps({"status": "completed", "success": res})

    elif operation == "OrdinaryCall":
      if "[[ProxyTarget]]" in obj["internalSlots"]:
        handler = obj["internalSlots"]["[[ProxyHandler]]"]
        target = obj["internalSlots"]["[[ProxyTarget]]"]

        if handler in state["heap"]:
          handler_obj = state["heap"][handler]
          trap = handler_obj["properties"].get("apply", None)
          if not trap or trap.get("value") == "~undefined~":
            return json.dumps({
                "status":
                    "unsupported_feature",
                "reason":
                    "Proxy apply trap is undefined, falling back to target is not supported in tool",
                "instructions":
                    f"Please call the target object {target} directly instead of the proxy."
            })

        return json.dumps({
            "status":
                "requires_proxy_trap",
            "trap":
                "apply",
            "handler":
                handler,
            "target":
                target,
            "thisValue":
                value,
            "argumentsList":
                descriptor.get("argumentsList", []) if descriptor else []
        })
      return json.dumps({
          "status":
              "requires_execution",
          "type":
              "call",
          "function":
              object_id,
          "thisValue":
              value,
          "argumentsList":
              descriptor.get("argumentsList", []) if descriptor else []
      })

    elif operation == "OrdinaryConstruct":
      if "[[ProxyTarget]]" in obj["internalSlots"]:
        handler = obj["internalSlots"]["[[ProxyHandler]]"]
        target = obj["internalSlots"]["[[ProxyTarget]]"]
        return json.dumps({
            "status":
                "requires_proxy_trap",
            "trap":
                "construct",
            "handler":
                handler,
            "target":
                target,
            "newTarget":
                descriptor.get("newTarget", object_id)
                if descriptor else object_id,
            "argumentsList":
                descriptor.get("argumentsList", []) if descriptor else []
        })
      return json.dumps({
          "status":
              "requires_execution",
          "type":
              "construct",
          "function":
              object_id,
          "newTarget":
              descriptor.get("newTarget", object_id)
              if descriptor else object_id,
          "argumentsList":
              descriptor.get("argumentsList", []) if descriptor else []
      })

    else:
      return f"Error: Unknown operation {operation}"

    self._write_state(state)
    warnings = self._check_value_warnings(value)
    if warnings:
      msg += "\n" + "\n".join(warnings)
    return msg

  def ecma262_state_get_history(self, format_type="full"):
    history_path = self.state_path + ".history"
    if not os.path.exists(history_path):
      return "No history available."

    with open(history_path, 'r') as f:
      lines = f.readlines()

    states = [json.loads(line) for line in lines]

    if format_type == "full":
      output = []
      for i, state in enumerate(states):
        output.append(f"=== State {i} ===")
        output.append(json.dumps(state, indent=2))
      return "\n".join(output)

    elif format_type == "diff":
      output = []
      for i in range(len(states)):
        if i == 0:
          output.append(f"=== State 0 (Initial) ===")
          output.append(json.dumps(states[0], indent=2))
        else:
          output.append(f"=== Diff State {i-1} -> State {i} ===")
          prev_str = json.dumps(
              states[i - 1], indent=2).splitlines(keepends=True)
          curr_str = json.dumps(states[i], indent=2).splitlines(keepends=True)
          diff = difflib.unified_diff(
              prev_str, curr_str, fromfile=f"State {i-1}", tofile=f"State {i}")
          output.extend(diff)
      return "".join(output)
    else:
      return f"Unknown format: {format_type}"


CURRENT_STATE_FILE = os.path.join(
    os.path.dirname(__file__), 'ecma262_states', 'current_state.txt')


def _get_state_path(state_id=None):
  if state_id is None:
    if os.path.exists(CURRENT_STATE_FILE):
      with open(CURRENT_STATE_FILE, 'r') as f:
        state_id = f.read().strip()
    else:
      state_id = "state.json"
  path = os.path.join(os.path.dirname(__file__), 'ecma262_states', state_id)
  os.makedirs(os.path.dirname(path), exist_ok=True)
  return path


def _set_current_state(state_id):
  os.makedirs(os.path.dirname(CURRENT_STATE_FILE), exist_ok=True)
  with open(CURRENT_STATE_FILE, 'w') as f:
    f.write(state_id)


# Tool definitions
# ... (keep existing tools)
@mcp.tool(name='ecma262_state_machine_init')
def ecma262_state_machine_init() -> str:
  """Initializes the abstract machine state.
    
    Returns the full path to the created state file.
    """
  state_id = f"state_{uuid.uuid4().hex}.json"
  _set_current_state(state_id)
  sm = StateManager(_get_state_path(state_id))
  res = sm.ecma262_state_init()
  return json.dumps({
      "status": "initialized",
      "state_id": state_id,
      "state_file": _get_state_path(state_id),
      "result": res
  })


@mcp.tool(name='ecma262_state_machine_push_context')
def ecma262_state_machine_push_context(name: str,
                                       realm: str,
                                       lexEnv: str,
                                       varEnv: str,
                                       state_id: str = None) -> str:
  """Pushes a new execution context onto the stack."""
  sm = StateManager(_get_state_path(state_id))
  return sm.ecma262_state_push_context(name, realm, lexEnv, varEnv)


@mcp.tool(name='ecma262_state_machine_pop_context')
def ecma262_state_machine_pop_context(state_id: str = None) -> str:
  """Pops the top execution context from the stack."""
  sm = StateManager(_get_state_path(state_id))
  return sm.ecma262_state_pop_context()


@mcp.tool(name='ecma262_state_machine_update_context')
def ecma262_state_machine_update_context(key: str,
                                         value: Any,
                                         state_id: str = None) -> str:
  """Updates a field in the running execution context."""
  sm = StateManager(_get_state_path(state_id))
  return sm.ecma262_state_update_context(key, value)


@mcp.tool(name='ecma262_state_machine_new_environment')
def ecma262_state_machine_new_environment(type: str,
                                          outerEnv: str,
                                          bindings: dict = None,
                                          state_id: str = None) -> str:
  """Creates a new environment record."""
  sm = StateManager(_get_state_path(state_id))
  return sm.ecma262_state_new_environment(type, outerEnv, bindings)


@mcp.tool(name='ecma262_state_machine_set_binding')
def ecma262_state_machine_set_binding(envId: str,
                                      name: str,
                                      value: Any,
                                      state_id: str = None) -> str:
  """Sets a binding in an environment record."""
  sm = StateManager(_get_state_path(state_id))
  return sm.ecma262_state_set_binding(envId, name, value)


@mcp.tool(name='ecma262_state_machine_env_op')
def ecma262_state_machine_env_op(env_id: str,
                                 operation: str,
                                 name: str,
                                 value: Any = None,
                                 module_record: str = None,
                                 binding_name: str = None,
                                 state_id: str = None) -> Any:
  """Performs operation on Environment Record."""
  sm = StateManager(_get_state_path(state_id))
  return sm.ecma262_env_op(
      env_id,
      operation,
      name,
      value,
      module_record=module_record,
      binding_name=binding_name)


@mcp.tool(name='ecma262_state_machine_object_op')
def ecma262_state_machine_object_op(object_id: str,
                                    operation: str,
                                    property_name: str = None,
                                    value: Any = None,
                                    descriptor: dict = None,
                                    state_id: str = None) -> str:
  """Performs operation on Heap / Object Model."""
  sm = StateManager(_get_state_path(state_id))
  return sm.ecma262_object_op(object_id, operation, property_name, value,
                              descriptor)


@mcp.tool(name='ecma262_state_machine_enqueue_promise_job')
def ecma262_state_machine_enqueue_promise_job(job_name: str,
                                              callback_id: str,
                                              args: list,
                                              state_id: str = None) -> str:
  """Enqueues a job in the Promise Job Queue."""
  sm = StateManager(_get_state_path(state_id))
  return sm.ecma262_state_enqueue_promise_job(job_name, callback_id, args)


@mcp.tool(name='ecma262_state_machine_get_job_queue')
def ecma262_state_machine_get_job_queue(state_id: str = None) -> str:
  """Returns the current list of pending jobs."""
  sm = StateManager(_get_state_path(state_id))
  return json.dumps(sm.ecma262_state_get_job_queue())


@mcp.tool(name='ecma262_state_machine_dequeue_job')
def ecma262_state_machine_dequeue_job(state_id: str = None) -> str:
  """Removes and returns the first job from the queue."""
  sm = StateManager(_get_state_path(state_id))
  return json.dumps(sm.ecma262_state_dequeue_job())


@mcp.tool(name='ecma262_state_machine_get_history')
def ecma262_state_machine_get_history(format_type: str = "full",
                                      state_id: str = None) -> str:
  """Returns the history of the state."""
  sm = StateManager(_get_state_path(state_id))
  return sm.ecma262_state_get_history(format_type)


if __name__ == '__main__':
  mcp.run()
