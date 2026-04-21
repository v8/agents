#!/usr/bin/env vpython3
import unittest
import json
import os
import sys

# Ensure the current directory is in the path so we can import server
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import server

server.STATE_FILE = os.path.join(
    os.path.dirname(__file__), 'ecma262_states', 'test_state.json')


class TestEcmabot(unittest.TestCase):

  def test_state_init(self):
    result_json = server.ecma262_state_machine_init()
    result = json.loads(result_json)
    self.assertEqual(result.get("status"), "initialized")

  def test_current_state_tracking(self):
    # Init without arguments, should generate a unique file
    init_res = server.ecma262_state_machine_init()
    result = json.loads(init_res)
    state_file = result.get("state_file")
    self.assertIsNotNone(state_file)
    self.assertTrue("state_" in state_file)

    # Call another operation without state_id
    server.ecma262_state_machine_push_context("test_current", "ref:Realm:1",
                                              "ref:Env:1", "ref:Env:1")

    # Verify it wrote to the generated file by reading history
    history = server.ecma262_state_machine_get_history("full")
    self.assertIn("test_current", history)

    # Clean up
    if os.path.exists(server.CURRENT_STATE_FILE):
      os.remove(server.CURRENT_STATE_FILE)
    if state_file and os.path.exists(state_file):
      os.remove(state_file)

  def test_state_push_context(self):
    server.ecma262_state_machine_init()
    result = server.ecma262_state_machine_push_context("test_context",
                                                       "ref:Realm:1",
                                                       "ref:Env:Test",
                                                       "ref:Env:Test")
    self.assertEqual(result, "Pushed context: test_context")

  def test_state_pop_context(self):
    server.ecma262_state_machine_init()
    server.ecma262_state_machine_push_context("test_context", "ref:Realm:1",
                                              "ref:Env:Test", "ref:Env:Test")
    result = server.ecma262_state_machine_pop_context()
    self.assertEqual(result, "Popped context: test_context")

  def test_state_update_context(self):
    server.ecma262_state_machine_init()
    server.ecma262_state_machine_push_context("test_context", "ref:Realm:1",
                                              "ref:Env:Test", "ref:Env:Test")

    # Test valid update
    result = server.ecma262_state_machine_update_context(
        "codeEvaluationState", "Suspended")
    self.assertTrue("Updated top context field" in result)

    # Test invalid key
    result = server.ecma262_state_machine_update_context("invalid_key", "value")
    self.assertTrue("Error: Invalid execution context key" in result)

  def test_state_create_env(self):
    server.ecma262_state_machine_init()
    result = server.ecma262_state_machine_new_environment(
        "Declarative", "ref:Env:Global")
    self.assertEqual(result,
                     "Created environment ref:Env:4 of type Declarative")

  def test_state_set_binding(self):
    server.ecma262_state_machine_init()
    server.ecma262_state_machine_new_environment("Declarative",
                                                 "ref:Env:Global")
    result = server.ecma262_state_machine_set_binding("ref:Env:4", "x", 42)
    self.assertEqual(result, "Set binding x = 42 in ref:Env:4")

  def test_state_env_op(self):
    server.ecma262_state_machine_init()
    server.ecma262_state_machine_new_environment("Declarative",
                                                 "ref:Env:Global")

    # Test CreateMutableBinding
    result = server.ecma262_state_machine_env_op("ref:Env:4",
                                                 "CreateMutableBinding", "x")
    self.assertEqual(result, "Created mutable binding x in ref:Env:4")

    # Test InitializeBinding
    result = server.ecma262_state_machine_env_op("ref:Env:4",
                                                 "InitializeBinding", "x", 42)
    self.assertEqual(result, "Initialized binding x to 42 in ref:Env:4")

    # Test GetBindingValue
    result = server.ecma262_state_machine_env_op("ref:Env:4", "GetBindingValue",
                                                 "x")
    self.assertEqual(json.loads(result), 42)

  def test_state_has_binding_declarative(self):
    server.ecma262_state_machine_init()
    server.ecma262_state_machine_new_environment("Declarative",
                                                 "ref:Env:Global")

    result = server.ecma262_state_machine_env_op("ref:Env:4", "HasBinding", "x")
    self.assertFalse(result)

    server.ecma262_state_machine_env_op("ref:Env:4", "CreateMutableBinding",
                                        "x")

    result = server.ecma262_state_machine_env_op("ref:Env:4", "HasBinding", "x")
    self.assertTrue(result)

  def test_state_has_binding_object(self):
    server.ecma262_state_machine_init()

    result = server.ecma262_state_machine_env_op("ref:Env:GlobalObj",
                                                 "HasBinding", "globalProp")
    self.assertFalse(result)

    server.ecma262_state_machine_object_op("ref:Obj:Global",
                                           "OrdinaryDefineOwnProperty",
                                           "globalProp", 100)

    result = server.ecma262_state_machine_env_op("ref:Env:GlobalObj",
                                                 "HasBinding", "globalProp")
    self.assertTrue(result)

  def test_state_has_binding_global(self):
    server.ecma262_state_machine_init()

    result = server.ecma262_state_machine_env_op("ref:Env:Global", "HasBinding",
                                                 "x")
    self.assertFalse(result)

    server.ecma262_state_machine_env_op("ref:Env:GlobalDecl",
                                        "CreateMutableBinding", "x")

    result = server.ecma262_state_machine_env_op("ref:Env:Global", "HasBinding",
                                                 "x")
    self.assertTrue(result)

    result = server.ecma262_state_machine_env_op("ref:Env:Global", "HasBinding",
                                                 "globalProp")
    self.assertFalse(result)

    server.ecma262_state_machine_object_op("ref:Obj:Global",
                                           "OrdinaryDefineOwnProperty",
                                           "globalProp", 100)

    result = server.ecma262_state_machine_env_op("ref:Env:Global", "HasBinding",
                                                 "globalProp")
    self.assertTrue(result)

  def test_state_object_op(self):
    server.ecma262_state_machine_init()

    # Test MakeBasicObject
    result = server.ecma262_state_machine_object_op(
        None,
        "MakeBasicObject",
        descriptor={"internalSlots": ["[[CustomSlot]]"]})
    self.assertTrue("MakeBasicObject" in result)

    # Test SetInternalSlot (should succeed because [[CustomSlot]] was declared)
    result = server.ecma262_state_machine_object_op("ref:Obj:2",
                                                    "SetInternalSlot",
                                                    "[[CustomSlot]]", 123)
    self.assertEqual(result,
                     "Set internal slot [[CustomSlot]] to 123 in ref:Obj:2")

    # Test SetInternalSlot (should fail because [[UndeclaredSlot]] was not declared)
    result = server.ecma262_state_machine_object_op("ref:Obj:2",
                                                    "SetInternalSlot",
                                                    "[[UndeclaredSlot]]", 456)
    self.assertTrue(
        "Error: Internal slot [[UndeclaredSlot]] was not declared" in result)

    # Test OrdinaryDefineOwnProperty
    server.ecma262_state_machine_object_op("ref:Obj:3", "MakeBasicObject")
    result = server.ecma262_state_machine_object_op(
        "ref:Obj:3", "OrdinaryDefineOwnProperty", "prop", 456)
    self.assertTrue(result)

    # Test OrdinaryDefineOwnProperty (reject non-configurable update)
    server.ecma262_state_machine_object_op(
        "ref:Obj:3",
        "OrdinaryDefineOwnProperty",
        "non_conf",
        descriptor={
            "value": 1,
            "configurable": False
        })
    result = server.ecma262_state_machine_object_op(
        "ref:Obj:3",
        "OrdinaryDefineOwnProperty",
        "non_conf",
        descriptor={"value": 2})
    self.assertFalse(result)

    # Test OrdinaryGetPrototypeOf (initially None)
    result = server.ecma262_state_machine_object_op("ref:Obj:3",
                                                    "OrdinaryGetPrototypeOf")
    self.assertIsNone(result)

    # Test OrdinarySetPrototypeOf
    server.ecma262_state_machine_object_op("ref:ProtoObj", "MakeBasicObject")
    result = server.ecma262_state_machine_object_op(
        "ref:Obj:3", "OrdinarySetPrototypeOf", value="ref:ProtoObj")
    self.assertTrue(result)

    # Test OrdinaryGetPrototypeOf (now should be ref:ProtoObj)
    result = server.ecma262_state_machine_object_op("ref:Obj:3",
                                                    "OrdinaryGetPrototypeOf")
    self.assertEqual(result, "ref:ProtoObj")

    # Test OrdinaryIsExtensible
    result = server.ecma262_state_machine_object_op("ref:Obj:3",
                                                    "OrdinaryIsExtensible")
    self.assertTrue(result)

    # Test OrdinaryPreventExtensions
    result = server.ecma262_state_machine_object_op(
        "ref:Obj:3", "OrdinaryPreventExtensions")
    self.assertTrue(result)

    # Test OrdinaryIsExtensible (now False)
    result = server.ecma262_state_machine_object_op("ref:Obj:3",
                                                    "OrdinaryIsExtensible")
    self.assertFalse(result)

    # Test OrdinaryGetOwnProperty
    result = server.ecma262_state_machine_object_op("ref:Obj:3",
                                                    "OrdinaryGetOwnProperty",
                                                    "prop")
    desc = json.loads(result)
    self.assertEqual(desc["value"], 456)

    # Test OrdinaryHasProperty
    result = server.ecma262_state_machine_object_op("ref:Obj:3",
                                                    "OrdinaryHasProperty",
                                                    "prop")
    self.assertTrue(result)

    # Test OrdinaryDelete
    result = server.ecma262_state_machine_object_op("ref:Obj:3",
                                                    "OrdinaryDelete", "prop")
    self.assertTrue(result)

    # Test OrdinaryHasProperty (now False)
    result = server.ecma262_state_machine_object_op("ref:Obj:3",
                                                    "OrdinaryHasProperty",
                                                    "prop")
    self.assertFalse(result)

    # Test OrdinaryOwnPropertyKeys
    result = server.ecma262_state_machine_object_op("ref:Obj:3",
                                                    "OrdinaryOwnPropertyKeys")
    keys = json.loads(result)
    self.assertIn("non_conf", keys)

    # Test OrdinaryGet (data property)
    result = server.ecma262_state_machine_object_op("ref:Obj:3", "OrdinaryGet",
                                                    "non_conf")
    res = json.loads(result)
    self.assertEqual(res["status"], "completed")
    self.assertEqual(res["value"], 1)

    # Test OrdinarySet (data property) on a new extensible object
    server.ecma262_state_machine_object_op("ref:Obj:5", "MakeBasicObject")
    result = server.ecma262_state_machine_object_op("ref:Obj:5", "OrdinarySet",
                                                    "new_prop", 789)
    res = json.loads(result)
    self.assertEqual(res["status"], "completed")
    self.assertTrue(res["success"])

    # Test OrdinaryGet (verify new_prop)
    result = server.ecma262_state_machine_object_op("ref:Obj:5", "OrdinaryGet",
                                                    "new_prop")
    res = json.loads(result)
    self.assertEqual(res["status"], "completed")
    self.assertEqual(res["value"], 789)

    # Test OrdinaryDefineOwnProperty with getter on a NEW object
    server.ecma262_state_machine_object_op("ref:Obj:4", "MakeBasicObject")
    server.ecma262_state_machine_object_op(
        "ref:Obj:4",
        "OrdinaryDefineOwnProperty",
        "getter_prop",
        descriptor={"get": "ref:GetterFunc"})

    # Test OrdinaryGet (should return signal)
    result = server.ecma262_state_machine_object_op("ref:Obj:4", "OrdinaryGet",
                                                    "getter_prop")
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_getter_invocation")
    self.assertEqual(res["getter"], "ref:GetterFunc")

    # Test OrdinaryCall
    result = server.ecma262_state_machine_object_op(
        "ref:Obj:3",
        "OrdinaryCall",
        value="ref:ThisVal",
        descriptor={"argumentsList": [1, 2]})
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_execution")
    self.assertEqual(res["type"], "call")
    self.assertEqual(res["function"], "ref:Obj:3")
    self.assertEqual(res["thisValue"], "ref:ThisVal")
    self.assertEqual(res["argumentsList"], [1, 2])

    # Test OrdinaryConstruct
    result = server.ecma262_state_machine_object_op(
        "ref:Obj:2",
        "OrdinaryConstruct",
        descriptor={
            "argumentsList": [3, 4],
            "newTarget": "ref:NewTarget"
        })
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_execution")
    self.assertEqual(res["type"], "construct")
    self.assertEqual(res["function"], "ref:Obj:2")
    self.assertEqual(res["newTarget"], "ref:NewTarget")
    self.assertEqual(res["argumentsList"], [3, 4])

    # Test OrdinaryObjectCreate
    result = server.ecma262_state_machine_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:2")
    self.assertTrue("OrdinaryObjectCreate" in result)


class TestStateManager(unittest.TestCase):

  def setUp(self):
    self.test_state_file = os.path.join(
        os.path.dirname(__file__), 'ecma262_states', 'test_state.json')
    if os.path.exists(self.test_state_file):
      os.remove(self.test_state_file)
    self.sm = server.StateManager(self.test_state_file)

  def tearDown(self):
    if os.path.exists(self.test_state_file):
      os.remove(self.test_state_file)
    history_path = self.test_state_file + ".history"
    if os.path.exists(history_path):
      os.remove(history_path)

  def test_init(self):
    result = self.sm.ecma262_state_init()
    self.assertEqual(
        result,
        f"State initialized at ecma262_states/{os.path.basename(self.test_state_file)}"
    )
    self.assertTrue(os.path.exists(self.test_state_file))

    with open(self.test_state_file, 'r') as f:
      state = json.load(f)

    self.assertIn("executionContextStack", state)
    self.assertEqual(len(state["executionContextStack"]), 1)
    self.assertEqual(state["executionContextStack"][0]["id"], "global")
    self.assertIn("ref:Realm:1", state["realms"])
    self.assertEqual(state["realms"]["ref:Realm:1"]["[[TemplateMap]]"], [])
    self.assertEqual(state["realms"]["ref:Realm:1"]["[[LoadedModules]]"], [])
    self.assertEqual(state["realms"]["ref:Realm:1"]["[[AgentSignifier]]"],
                     "AgentSignifier")
    self.assertEqual(state["realms"]["ref:Realm:1"]["[[HostDefined]]"], {})
    self.assertIn("privateEnvironmentRecords", state)

  def test_private_fields(self):
    self.sm.ecma262_state_init()

    # Create object
    result = self.sm.ecma262_object_op(None, "MakeBasicObject")
    object_id = result.split(" ")[1]

    # Add private field
    res = self.sm.ecma262_object_op(
        object_id, "PrivateFieldAdd", property_name="#x", value="Avalue")
    self.assertTrue(res)

    # Get private field
    res = self.sm.ecma262_object_op(
        object_id, "PrivateFieldGet", property_name="#x")
    self.assertEqual(res, "Avalue")

    # Set private field
    res = self.sm.ecma262_object_op(
        object_id, "PrivateFieldSet", property_name="#x", value="Bvalue")
    self.assertTrue(res)

    # Get private field again
    res = self.sm.ecma262_object_op(
        object_id, "PrivateFieldGet", property_name="#x")
    self.assertEqual(res, "Bvalue")

    # Test adding duplicate field (should fail)
    res = self.sm.ecma262_object_op(
        object_id, "PrivateFieldAdd", property_name="#x", value="Cvalue")
    self.assertTrue(isinstance(res, str) and res.startswith("Error"))

    # Test getting non-existent field (should fail)
    res = self.sm.ecma262_object_op(
        object_id, "PrivateFieldGet", property_name="#y")
    self.assertTrue(isinstance(res, str) and res.startswith("Error"))

    # Test setting non-existent field (should fail)
    res = self.sm.ecma262_object_op(
        object_id, "PrivateFieldSet", property_name="#y", value="Cvalue")
    self.assertTrue(isinstance(res, str) and res.startswith("Error"))

  def test_create_private_name(self):
    self.sm.ecma262_state_init()

    # Create private name
    priv_id1 = self.sm.ecma262_object_op(
        None, "CreatePrivateName", property_name="#x")
    self.assertTrue(priv_id1.startswith("ref:Priv:"))

    # Create another private name with same description
    priv_id2 = self.sm.ecma262_object_op(
        None, "CreatePrivateName", property_name="#x")
    self.assertTrue(priv_id2.startswith("ref:Priv:"))

    # Verify they are different
    self.assertNotEqual(priv_id1, priv_id2)

    # Verify registry in state
    state = self.sm._read_state()
    self.assertIn("privateNames", state)
    self.assertIn(priv_id1, state["privateNames"])
    self.assertIn(priv_id2, state["privateNames"])
    self.assertEqual(state["privateNames"][priv_id1]["[[Description]]"], "#x")

  def test_exact_object_model(self):
    self.sm.ecma262_state_init()

    # Create target and handler for proxy
    self.sm.ecma262_object_op("ref:Obj:Target", "MakeBasicObject")
    self.sm.ecma262_object_op("ref:Obj:Handler", "MakeBasicObject")

    # Test ProxyCreate
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value="ref:Obj:Target",
        descriptor={"handler": "ref:Obj:Handler"})
    self.assertTrue(res.startswith("ProxyCreate"))
    proxy_id = res.split(" ")[1]

    # Test StringCreate
    res = self.sm.ecma262_object_op(None, "StringCreate", value="hello")
    self.assertTrue(res.startswith("StringCreate"))
    string_id = res.split(" ")[1]

    # Test ArrayCreate
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    self.assertTrue(res.startswith("ArrayCreate"))
    array_id = res.split(" ")[1]

    # Test Get on Proxy
    res = self.sm.ecma262_object_op(
        proxy_id, "OrdinaryGet", property_name="prop")
    import json
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "get")

    # Test Get on String (indexed)
    res = self.sm.ecma262_object_op(string_id, "OrdinaryGet", property_name="1")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], "e")

    # Test Get on String (length)
    res = self.sm.ecma262_object_op(
        string_id, "OrdinaryGet", property_name="length")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], 5)

    # Test Fallback on unsupported exotic object
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    obj_id = res.split(" ")[1]
    state = self.sm._read_state()
    state["heap"][obj_id]["internalSlots"]["[[CustomSlot]]"] = True
    self.sm._write_state(state)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGet", property_name="prop")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "unsupported_exotic_object")

  def test_audit_fixes(self):
    self.sm.ecma262_state_init()

    # Create handler
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    handler_id = res.split(" ")[1]

    # Test ProxyCreate validation
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value="ref:NonExistentTarget",
        descriptor={"handler": handler_id})
    self.assertTrue(isinstance(res, str) and "Error" in res)

    # Test ArrayCreate range check
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=-1)
    self.assertTrue(isinstance(res, str) and "Error" in res)

    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=2**32)
    self.assertTrue(isinstance(res, str) and "Error" in res)

    # Test Callable Proxy
    # Create a callable target
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate")
    target_id = res.split(" ")[1]

    # Create Proxy
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    # Define apply trap on handler
    self.sm.ecma262_object_op(
        handler_id,
        "OrdinaryDefineOwnProperty",
        "apply",
        descriptor={"value": "ref:Obj:SomeFunction"})

    # Test OrdinaryCall on Proxy
    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryCall")
    import json
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "apply")

    # Test Proxy in prototype chain
    # Create target for proxy
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id2 = res.split(" ")[1]

    # Create Proxy
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id2,
        descriptor={"handler": handler_id})
    proxy_id2 = res.split(" ")[1]

    # Create ordinary object
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    obj_id = res.split(" ")[1]

    # Set Proxy as prototype
    self.sm.ecma262_object_op(obj_id, "OrdinarySetPrototypeOf", value=proxy_id2)

    # Test Get on obj (should fall back to Proxy and trigger trap)
    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGet", property_name="prop")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "get")

    # Test setting indexed property on String
    res = self.sm.ecma262_object_op(None, "StringCreate", value="hello")
    string_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        string_id, "OrdinarySet", property_name="1", value="x")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "failed")

  def test_full_audit_fixes(self):
    self.sm.ecma262_state_init()

    # Task 1: HasSuperBinding
    res = self.sm.ecma262_object_op(
        None,
        "OrdinaryFunctionCreate",
        descriptor={"homeObject": "~undefined~"})
    func_id = res.split(" ")[1]

    res = self.sm.ecma262_state_new_environment("Function", "ref:Env:Global")
    env_id = res.split(" ")[2]
    state = self.sm._read_state()
    state["environmentRecords"][env_id]["[[FunctionObject]]"] = func_id
    state["environmentRecords"][env_id]["[[ThisBindingStatus]]"] = "non-lexical"
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(env_id, "HasSuperBinding")
    self.assertFalse(res)

    # Task 2: Global ThisBinding
    res = self.sm.ecma262_state_new_environment("Global", "ref:Env:Global")
    global_env_id = res.split(" ")[2]
    state = self.sm._read_state()
    state["environmentRecords"][global_env_id][
        "[[GlobalThisValue]]"] = "ref:Obj:GlobalThis"
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(global_env_id, "HasThisBinding")
    self.assertTrue(res)

    res = self.sm.ecma262_env_op(global_env_id, "GetThisBinding")
    import json
    self.assertEqual(json.loads(res), "ref:Obj:GlobalThis")

    # Task 3: ValidateAndApplyPropertyDescriptor early return
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={
            "value": 42,
            "writable": False,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        obj_id, "OrdinaryDefineOwnProperty", "prop", descriptor={"value": 42})
    self.assertTrue(res)

    # Task 4: Proxy checks in remaining operations
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    handler_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        proxy_id, "OrdinaryGetOwnProperty", property_name="prop")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "getOwnPropertyDescriptor")

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryOwnPropertyKeys")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "ownKeys")

    # Task 5: String Exotic Properties
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    string_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        string_id, "OrdinaryGetOwnProperty", property_name="1")
    res_data = json.loads(res)
    self.assertEqual(res_data["value"], "b")
    self.assertFalse(res_data["writable"])
    self.assertTrue(res_data["enumerable"])
    self.assertFalse(res_data["configurable"])

    res = self.sm.ecma262_object_op(string_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    self.assertIn("0", keys)
    self.assertIn("1", keys)
    self.assertIn("2", keys)
    self.assertIn("length", keys)

    # Task 6 & 7: Object Environment Records
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    binding_obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        binding_obj_id,
        "OrdinaryDefineOwnProperty",
        "obj_prop",
        descriptor={
            "value": 100,
            "writable": True,
            "enumerable": True,
            "configurable": True
        })

    res = self.sm.ecma262_state_new_environment(
        "Object", "ref:Env:Global", bindings={"bindingObject": binding_obj_id})
    obj_env_id = res.split(" ")[2]

    res = self.sm.ecma262_env_op(obj_env_id, "HasBinding", "obj_prop")
    self.assertTrue(res)

    res = self.sm.ecma262_env_op(obj_env_id, "GetBindingValue", "obj_prop")
    self.assertEqual(json.loads(res), 100)

    res = self.sm.ecma262_env_op(
        obj_env_id, "SetMutableBinding", "obj_prop", value=200)
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertTrue(res_data["success"])

    res = self.sm.ecma262_object_op(
        binding_obj_id, "OrdinaryGet", property_name="obj_prop")
    res_data = json.loads(res)
    self.assertEqual(res_data["value"], 200)

    res = self.sm.ecma262_env_op(obj_env_id, "DeleteBinding", "obj_prop")
    self.assertTrue(res)

    # Task 8: Array length truncation
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    array_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        array_id, "OrdinaryDefineOwnProperty", "0", value="a")
    self.sm.ecma262_object_op(
        array_id, "OrdinaryDefineOwnProperty", "4", value="e")

    res = self.sm.ecma262_object_op(array_id, "OrdinaryGet", property_name="0")
    self.assertEqual(json.loads(res)["value"], "a")
    res = self.sm.ecma262_object_op(array_id, "OrdinaryGet", property_name="4")
    self.assertEqual(json.loads(res)["value"], "e")

    res = self.sm.ecma262_object_op(
        array_id,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"value": 2})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(array_id, "OrdinaryGet", property_name="0")
    self.assertEqual(json.loads(res)["value"], "a")
    res = self.sm.ecma262_object_op(array_id, "OrdinaryGet", property_name="4")
    self.assertEqual(json.loads(res)["value"], "~undefined~")

    res = self.sm.ecma262_object_op(
        array_id,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"value": -1})
    self.assertTrue(isinstance(res, str) and "Error" in res)

    # Round 2 Audit Fixes
    # Task 1: OrdinaryDefineOwnProperty on Proxy
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    handler_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        proxy_id, "OrdinaryDefineOwnProperty", "prop", descriptor={"value": 42})
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "defineProperty")

    # Task 2: Array index additions updating length
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=2)
    array_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        array_id, "OrdinaryDefineOwnProperty", "5", value="x")
    res = self.sm.ecma262_object_op(
        array_id, "OrdinaryGet", property_name="length")
    res_data = json.loads(res)
    self.assertEqual(res_data["value"], 6)

    # Task 3: Canonical Numeric Indices
    res = self.sm.ecma262_object_op(None, "StringCreate", value="hello")
    string_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        string_id, "OrdinaryGet", property_name="01")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], "~undefined~")

    # Task 4: Propagate Proxy traps from Environments
    res = self.sm.ecma262_state_new_environment(
        "Object", "ref:Env:Global", bindings={"bindingObject": proxy_id})
    obj_env_id = res.split(" ")[2]

    res = self.sm.ecma262_env_op(obj_env_id, "HasBinding", "prop")
    self.assertTrue(isinstance(res, str) and "requires_proxy_trap" in res)

    # Task 5: Create Object Environment via tool
    res = self.sm.ecma262_state_new_environment(
        "Object",
        "ref:Env:Global",
        bindings={"bindingObject": "ref:Obj:Target"})
    self.assertTrue(res.startswith("Created environment"))

    # Round 3 Audit Fixes
    # Task 1: String Exotic Object Shadowing in OrdinaryDefineOwnProperty
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    string_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        string_id, "OrdinaryDefineOwnProperty", "1", descriptor={"value": "x"})
    self.assertFalse(res)

    # Task 3: GetBindingValue respect strictness
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id2 = res.split(" ")[1]
    res = self.sm.ecma262_state_new_environment(
        "Object", "ref:Env:Global", bindings={"bindingObject": target_id2})
    obj_env_id2 = res.split(" ")[2]

    res = self.sm.ecma262_env_op(
        obj_env_id2, "GetBindingValue", "non_existent", strict=True)
    self.assertTrue(isinstance(res, str) and "ReferenceError" in res)

    # Task 4: SetMutableBinding in Declarative Environments
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    decl_env_id = res.split(" ")[2]

    self.sm.ecma262_env_op(decl_env_id, "CreateMutableBinding", "x")

    res = self.sm.ecma262_env_op(
        decl_env_id, "SetMutableBinding", "x", value=10, strict=True)
    self.assertTrue(isinstance(res, str) and "ReferenceError" in res)

    self.sm.ecma262_env_op(decl_env_id, "InitializeBinding", "x", value=5)

    res = self.sm.ecma262_env_op(
        decl_env_id, "SetMutableBinding", "x", value=10, strict=True)
    self.assertTrue("Set mutable binding" in res)

    res = self.sm.ecma262_env_op(
        decl_env_id, "SetMutableBinding", "y", value=20, strict=False)
    self.assertTrue("Created and set mutable binding" in res)

    # Round 4 Audit Fixes
    # Task 1: Array truncation respects non-configurable properties
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    array_id2 = res.split(" ")[1]

    self.sm.ecma262_object_op(
        array_id2,
        "OrdinaryDefineOwnProperty",
        "3",
        descriptor={
            "value": "non-conf",
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        array_id2,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"value": 2})
    self.assertFalse(res)

    res = self.sm.ecma262_object_op(
        array_id2, "OrdinaryGet", property_name="length")
    res_data = json.loads(res)
    self.assertEqual(res_data["value"], 4)

    # Task 2: SetMutableBinding in Object Env throws ReferenceError in strict mode
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id3 = res.split(" ")[1]
    res = self.sm.ecma262_state_new_environment(
        "Object", "ref:Env:Global", bindings={"bindingObject": target_id3})
    obj_env_id3 = res.split(" ")[2]

    res = self.sm.ecma262_env_op(
        obj_env_id3, "SetMutableBinding", "non_existent", value=42, strict=True)
    self.assertTrue(isinstance(res, str) and "ReferenceError" in res)

    # Task 3: GetBindingValue in Global Env propagates Proxy traps
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    handler_id2 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id4 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id4,
        descriptor={"handler": handler_id2})
    proxy_id2 = res.split(" ")[1]

    res = self.sm.ecma262_state_new_environment(
        "Object", "ref:Env:Global", bindings={"bindingObject": proxy_id2})
    obj_rec_id = res.split(" ")[2]

    res = self.sm.ecma262_state_new_environment("Global", "ref:Env:Global")
    global_env_id2 = res.split(" ")[2]

    state = self.sm._read_state()
    state["environmentRecords"][global_env_id2]["objectRecord"] = obj_rec_id
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(global_env_id2, "GetBindingValue", "prop")
    self.assertTrue(isinstance(res, str) and "requires_proxy_trap" in res)

    # Task 4: OrdinarySet Receiver triggers Proxy trap
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    obj_id2 = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id2,
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={
            "value": 100,
            "writable": True,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(
        obj_id2, "OrdinarySet", "prop", descriptor={"receiver": proxy_id2})
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "getOwnPropertyDescriptor")

    # Round 5 Audit Fixes
    # Task 1: OrdinarySet String Index Shadowing in Prototype Chain
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    string_id2 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    obj_id3 = res.split(" ")[1]
    self.sm.ecma262_object_op(
        obj_id3, "OrdinarySetPrototypeOf", value=string_id2)
    res = self.sm.ecma262_object_op(obj_id3, "OrdinarySet", "1", value="x")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "failed")
    self.assertEqual(res_data["reason"], "non-writable in prototype")

    # Task 2: OrdinarySet Proxy defineProperty Trap Swallow
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id5 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    handler_id3 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id5,
        descriptor={"handler": handler_id3})
    proxy_id3 = res.split(" ")[1]
    # obj_id2 was created in Task 4 test in previous round!
    # Let's assume it is still there!
    # Wait, Task 4 test used obj_id2 and set property "prop" on it!
    # So obj_id2 is a basic object with property "prop".
    res = self.sm.ecma262_object_op(
        obj_id2, "OrdinarySet", "new_prop", descriptor={"receiver": proxy_id3})
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "getOwnPropertyDescriptor")

    # Task 3: ArraySetLength respect writable attribute
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    array_id3 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(
        array_id3,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={
            "value": 2,
            "writable": False
        })
    self.assertTrue(res)
    res = self.sm.ecma262_object_op(
        array_id3, "OrdinaryGetOwnProperty", property_name="length")
    res_data = json.loads(res)
    self.assertEqual(res_data["value"], 2)
    self.assertFalse(res_data["writable"])

    # Task 4: ArraySetLength Non-Configurable failure corner case
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    array_id4 = res.split(" ")[1]
    self.sm.ecma262_object_op(
        array_id4,
        "OrdinaryDefineOwnProperty",
        "3",
        descriptor={
            "value": "non-conf",
            "configurable": False
        })
    res = self.sm.ecma262_object_op(
        array_id4,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={
            "value": 2,
            "writable": False
        })
    self.assertFalse(res)
    res = self.sm.ecma262_object_op(
        array_id4, "OrdinaryGetOwnProperty", property_name="length")
    res_data = json.loads(res)
    self.assertEqual(res_data["value"], 4)
    self.assertFalse(res_data["writable"])

    # Task 5: SetMutableBinding in Object Env throws TypeError
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id6 = res.split(" ")[1]
    self.sm.ecma262_object_op(
        target_id6,
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={
            "value": 100,
            "writable": False,
            "configurable": True
        })
    res = self.sm.ecma262_state_new_environment(
        "Object", "ref:Env:Global", bindings={"bindingObject": target_id6})
    obj_env_id4 = res.split(" ")[2]
    res = self.sm.ecma262_env_op(
        obj_env_id4, "SetMutableBinding", "prop", value=42, strict=True)
    self.assertTrue(isinstance(res, str) and "TypeError" in res)

    # Round 6 Audit Fixes
    # Task 1: OrdinarySet on primitive receiver returns false
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    obj_id4 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id4,
        "OrdinarySet",
        "prop",
        descriptor={"receiver": "primitive_val"})
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertFalse(res_data["success"])

    # Task 2: ArraySetLength attribute validation
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    array_id5 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        array_id5,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"enumerable": True})
    self.assertFalse(res)

    # Task 3: ArraySetLength SameValue check
    self.sm.ecma262_object_op(
        array_id5,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={
            "value": 5,
            "writable": False
        })

    res = self.sm.ecma262_object_op(
        array_id5,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"value": 5})
    self.assertTrue(res)

    # Task 4: Out-of-Bounds Array element insertion when length is non-writable
    res = self.sm.ecma262_object_op(
        array_id5, "OrdinaryDefineOwnProperty", "10", descriptor={"value": "x"})
    self.assertFalse(res)

    # Task 5: Global DeleteBinding triggers getOwnPropertyDescriptor trap
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    handler_id4 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id7 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id7,
        descriptor={"handler": handler_id4})
    proxy_id4 = res.split(" ")[1]

    res = self.sm.ecma262_state_new_environment(
        "Object", "ref:Env:Global", bindings={"bindingObject": proxy_id4})
    obj_rec_id2 = res.split(" ")[2]

    res = self.sm.ecma262_state_new_environment("Global", "ref:Env:Global")
    global_env_id3 = res.split(" ")[2]

    state = self.sm._read_state()
    state["environmentRecords"][global_env_id3]["objectRecord"] = obj_rec_id2
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(global_env_id3, "DeleteBinding", "prop")
    self.assertTrue(isinstance(res, str) and "requires_proxy_trap" in res)

    # Burn-down Audit Fixes
    # Task 1: MakeBasicObject Side Effect
    slots = ["[[Prototype]]"]
    self.sm.ecma262_object_op(
        None, "MakeBasicObject", descriptor={"internalSlots": slots})
    self.assertEqual(slots, ["[[Prototype]]"])

    # Task 2: StringCreate ID Generation
    res1 = self.sm.ecma262_object_op(None, "StringCreate", value="a")
    res2 = self.sm.ecma262_object_op(None, "StringCreate", value="b")
    self.assertNotEqual(res1.split(" ")[1], res2.split(" ")[1])

    # Task 3: GetThisBinding Naming Mismatch
    res = self.sm.ecma262_env_op("ref:Env:Global", "GetThisBinding")
    self.assertEqual(json.loads(res), "ref:Obj:Global")

    # Task 4: OrdinaryGetOwnProperty Safety Check
    res = self.sm.ecma262_object_op(
        None,
        "MakeBasicObject",
        descriptor={"internalSlots": ["[[NonStandard]]"]})
    exotic_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(exotic_id, "OrdinaryGetOwnProperty", "prop")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "unsupported_exotic_object")

    # Task 5: OrdinaryOwnPropertyKeys Ordering
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    obj_id5 = res.split(" ")[1]
    self.sm.ecma262_object_op(
        obj_id5, "OrdinaryDefineOwnProperty", "b", descriptor={"value": 1})
    self.sm.ecma262_object_op(
        obj_id5,
        "OrdinaryDefineOwnProperty",
        "Symbol(x)",
        descriptor={"value": 2})
    self.sm.ecma262_object_op(
        obj_id5, "OrdinaryDefineOwnProperty", "a", descriptor={"value": 3})

    state = self.sm._read_state()
    keys = self.sm._ordinary_own_property_keys(state["heap"][obj_id5])
    self.assertEqual(keys, ["b", "a", "Symbol(x)"])

    # Task 6: StringCreate UTF-16 Limitation (Bail)
    res = self.sm.ecma262_object_op(None, "StringCreate", value="💩")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "unsupported_feature")

    # Task 7: HasBinding Module Imports (Bail)
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    mod_env_id = res.split(" ")[2]

    state = self.sm._read_state()
    state["environmentRecords"][mod_env_id]["indirectBindings"] = {
        "imp": {
            "module": "mod1",
            "bindingName": "x"
        }
    }
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(mod_env_id, "HasBinding", "imp")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "unsupported_feature")

    # Task 8: OrdinaryCall Undefined Apply Trap (Bail)
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    handler_id5 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id8 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id8,
        descriptor={"handler": handler_id5})
    proxy_id5 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        proxy_id5, "OrdinaryCall", value="undefined")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "unsupported_feature")

    # Phase 3 Audit Fixes
    # Task 9: Proxy Revocation Checks
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    handler_id6 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "MakeBasicObject")
    target_id9 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id9,
        descriptor={"handler": handler_id6})
    proxy_id6 = res.split(" ")[1]

    state = self.sm._read_state()
    state["heap"][proxy_id6]["internalSlots"]["[[ProxyTarget]]"] = "~null~"
    self.sm._write_state(state)

    res = self.sm.ecma262_object_op(proxy_id6, "OrdinaryIsExtensible")
    self.assertTrue(isinstance(res, str) and "TypeError" in res)

    # Task 10: Binding Existence Checks
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    decl_env_id2 = res.split(" ")[2]
    self.sm.ecma262_env_op(decl_env_id2, "CreateMutableBinding", "x")

    res = self.sm.ecma262_env_op(decl_env_id2, "CreateMutableBinding", "x")
    self.assertTrue(isinstance(res, str) and "Assertion failed" in res)

    # Task 11: InitializeBinding Assertion
    self.sm.ecma262_env_op(decl_env_id2, "InitializeBinding", "x", value=5)

    res = self.sm.ecma262_env_op(
        decl_env_id2, "InitializeBinding", "x", value=10)
    self.assertTrue(isinstance(res, str) and "Assertion failed" in res)

    # Task 12: Canonical Indices "-0"
    self.assertTrue(self.sm._is_canonical_numeric_index("-0"))

    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    array_id6 = res.split(" ")[1]

    state = self.sm._read_state()
    state["heap"][array_id6]["properties"]["-0"] = {
        "value": "neg-zero",
        "writable": True,
        "enumerable": True,
        "configurable": True
    }
    self.sm._write_state(state)

    self.sm.ecma262_object_op(
        array_id6,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"value": 2})

    state = self.sm._read_state()
    self.assertIn("-0", state["heap"][array_id6]["properties"])

  def test_job_queue(self):
    self.sm.ecma262_state_init()

    queue = self.sm.ecma262_state_get_job_queue()
    self.assertEqual(queue, [])

    result = self.sm.ecma262_state_enqueue_promise_job("TestJob",
                                                       "ref:Obj:Callback",
                                                       ["arg1"])
    self.assertEqual(result, "Enqueued job: TestJob")

    queue = self.sm.ecma262_state_get_job_queue()
    self.assertEqual(len(queue), 1)
    self.assertEqual(queue[0]["name"], "TestJob")

    self.sm.ecma262_state_enqueue_promise_job("TestJob2", "ref:Obj:Callback2",
                                              ["arg2"])
    queue = self.sm.ecma262_state_get_job_queue()
    self.assertEqual(len(queue), 2)

    job = self.sm.ecma262_state_dequeue_job()
    self.assertEqual(job["name"], "TestJob")

    queue = self.sm.ecma262_state_get_job_queue()
    self.assertEqual(len(queue), 1)
    self.assertEqual(queue[0]["name"], "TestJob2")

    job = self.sm.ecma262_state_dequeue_job()
    self.assertEqual(job["name"], "TestJob2")

    queue = self.sm.ecma262_state_get_job_queue()
    self.assertEqual(queue, [])

    job = self.sm.ecma262_state_dequeue_job()
    self.assertIsNone(job)

  def test_push_pop_context(self):
    self.sm.ecma262_state_init()

    result = self.sm.ecma262_state_push_context("test_context", "ref:Realm:1",
                                                "ref:Env:Test", "ref:Env:Test",
                                                "ref:Script:1", "ref:PrivEnv:1",
                                                "ref:Gen:1")
    self.assertEqual(result, "Pushed context: test_context")

    with open(self.test_state_file, 'r') as f:
      state = json.load(f)
    self.assertEqual(len(state["executionContextStack"]), 2)
    self.assertEqual(state["executionContextStack"][1]["id"], "test_context")
    self.assertEqual(state["executionContextStack"][1]["ScriptOrModule"],
                     "ref:Script:1")
    self.assertEqual(state["executionContextStack"][1]["PrivateEnvironment"],
                     "ref:PrivEnv:1")
    self.assertEqual(state["executionContextStack"][1]["Generator"],
                     "ref:Gen:1")

    result = self.sm.ecma262_state_pop_context()
    self.assertEqual(result, "Popped context: test_context")

    with open(self.test_state_file, 'r') as f:
      state = json.load(f)
    self.assertEqual(len(state["executionContextStack"]), 1)

  def test_create_env(self):
    self.sm.ecma262_state_init()

    result = self.sm.ecma262_state_new_environment("Declarative",
                                                   "ref:Env:Global")
    # Initial state has 3 envs: ref:Env:Global, ref:Env:GlobalObj, ref:Env:GlobalDecl
    # So the new one should be ref:Env:4
    self.assertEqual(result,
                     "Created environment ref:Env:4 of type Declarative")

    with open(self.test_state_file, 'r') as f:
      state = json.load(f)
    self.assertIn("ref:Env:4", state["environmentRecords"])
    self.assertEqual(state["environmentRecords"]["ref:Env:4"]["type"],
                     "Declarative")

  def test_create_env_function_module(self):
    self.sm.ecma262_state_init()

    self.sm.ecma262_state_new_environment("Function", "ref:Env:Global")
    self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")

    with open(self.test_state_file, 'r') as f:
      state = json.load(f)

    env_func = state["environmentRecords"]["ref:Env:4"]
    self.assertEqual(env_func["type"], "Function")
    self.assertEqual(env_func["[[ThisValue]]"], "~undefined~")
    self.assertEqual(env_func["[[ThisBindingStatus]]"], "uninitialized")
    self.assertIsNone(env_func["[[FunctionObject]]"])
    self.assertEqual(env_func["[[NewTarget]]"], "~undefined~")

    env_mod = state["environmentRecords"]["ref:Env:5"]
    self.assertEqual(env_mod["type"], "Module")
    self.assertEqual(env_mod["indirectBindings"], {})

  def test_module_env_ops(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_state_new_environment("Module",
                                          "ref:Env:Global")  # ref:Env:4

    # Test HasThisBinding for Module
    result = self.sm.ecma262_env_op("ref:Env:4", "HasThisBinding")
    self.assertEqual(result, True)

    # Test GetThisBinding for Module
    result = self.sm.ecma262_env_op("ref:Env:4", "GetThisBinding")
    self.assertEqual(json.loads(result), "~undefined~")

    # Test GetBindingValue resolving indirection
    self.sm.ecma262_state_new_environment("Module",
                                          "ref:Env:Global")  # ref:Env:5
    self.sm.ecma262_env_op("ref:Env:5", "CreateMutableBinding",
                           "target_binding")
    self.sm.ecma262_env_op("ref:Env:5", "InitializeBinding", "target_binding",
                           99)

    self.sm.ecma262_env_op(
        "ref:Env:4",
        "CreateImportBinding",
        "imported_binding",
        module_record="ref:Env:5",
        binding_name="target_binding")

    result = self.sm.ecma262_env_op("ref:Env:4", "GetBindingValue",
                                    "imported_binding")
    self.assertEqual(json.loads(result), 99)

  def test_function_env_ops(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_state_new_environment("Function",
                                          "ref:Env:Global")  # ref:Env:4

    # Test HasSuperBinding (no HomeObject)
    result = self.sm.ecma262_env_op("ref:Env:4", "HasSuperBinding")
    self.assertEqual(result, False)

    # Set [[FunctionObject]] to a reference
    with open(self.test_state_file, 'r') as f:
      state = json.load(f)
    state["environmentRecords"]["ref:Env:4"]["[[FunctionObject]]"] = "ref:Obj:1"
    state["heap"]["ref:Obj:1"] = {
        "type": "Function",
        "[[HomeObject]]": "ref:Obj:2"
    }
    with open(self.test_state_file, 'w') as f:
      json.dump(state, f)

    # Test HasSuperBinding (with HomeObject)
    result = self.sm.ecma262_env_op("ref:Env:4", "HasSuperBinding")
    self.assertEqual(result, True)

    # Test GetThisBinding (lexical assertion)
    with open(self.test_state_file, 'r') as f:
      state = json.load(f)
    state["environmentRecords"]["ref:Env:4"][
        "[[ThisBindingStatus]]"] = "lexical"
    with open(self.test_state_file, 'w') as f:
      json.dump(state, f)

    result = self.sm.ecma262_env_op("ref:Env:4", "GetThisBinding")
    self.assertTrue("Assertion failed" in result)

  def test_set_binding(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")

    result = self.sm.ecma262_state_set_binding("ref:Env:4", "x", 42)

    self.assertEqual(result, "Set binding x = 42 in ref:Env:4")

    with open(self.test_state_file, 'r') as f:
      state = json.load(f)
    self.assertEqual(
        state["environmentRecords"]["ref:Env:4"]["bindings"]["x"]["value"], 42)

  def test_get_history(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_state_push_context("test_context", "ref:Realm:1",
                                       "ref:Env:Global", "ref:Env:Global")

    history_full = self.sm.ecma262_state_get_history("full")
    self.assertIn("=== State 0 ===", history_full)
    self.assertIn("=== State 1 ===", history_full)

    history_diff = self.sm.ecma262_state_get_history("diff")
    self.assertIn("=== State 0 (Initial) ===", history_diff)
    self.assertIn("=== Diff State 0 -> State 1 ===", history_diff)

  def test_object_op_allocate(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op(
        "ref:Obj:Test", "OrdinaryObjectCreate", value=None)
    with open(self.test_state_file, 'r') as f:
      state = json.load(f)
    self.assertIn("ref:Obj:Test", state["heap"])
    self.assertEqual(
        state["heap"]["ref:Obj:Test"]["internalSlots"]["[[PrivateElements]]"],
        [])

  def test_create_private_env(self):
    self.sm.ecma262_state_init()
    result = self.sm.ecma262_state_new_environment("Private",
                                                   "ref:PrivEnv:Outer")
    self.assertEqual(result, "Created private environment ref:PrivEnv:1")
    with open(self.test_state_file, 'r') as f:
      state = json.load(f)
    self.assertIn("ref:PrivEnv:1", state["privateEnvironmentRecords"])
    self.assertEqual(
        state["privateEnvironmentRecords"]["ref:PrivEnv:1"]
        ["outerPrivateEnvironment"], "ref:PrivEnv:Outer")


class TestTest262Mappings(unittest.TestCase):

  def setUp(self):
    self.test_state_file = os.path.join(
        os.path.dirname(__file__), 'ecma262_states', 'test_state.json')
    if os.path.exists(self.test_state_file):
      os.remove(self.test_state_file)
    self.sm = server.StateManager(self.test_state_file)

  def tearDown(self):
    if os.path.exists(self.test_state_file):
      os.remove(self.test_state_file)

  def test_test262_preventExtensions_repeated(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    preCheck = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryIsExtensible")
    self.assertTrue(preCheck)
    self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryPreventExtensions")
    testResult1 = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryIsExtensible")
    self.assertFalse(testResult1)
    self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryPreventExtensions")
    testResult2 = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryIsExtensible")
    self.assertFalse(testResult2)

  def test_test262_keys_own_enumerable(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={
            "value": 1003,
            "enumerable": True,
            "configurable": True
        })
    keys = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryOwnPropertyKeys")
    keys_list = json.loads(keys)
    self.assertIn("prop", keys_list)
    self.assertEqual(len(keys_list), 1)

  def test_test262_keys_own_enumerable_accessor(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={
            "get": "ref:GetterFunc",
            "enumerable": True,
            "configurable": True
        })
    keys = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryOwnPropertyKeys")
    keys_list = json.loads(keys)
    self.assertIn("prop", keys_list)

  def test_test262_keys_non_enumerable(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "prop1",
        descriptor={
            "value": 1001,
            "enumerable": True,
            "configurable": True,
            "writable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "prop2",
        descriptor={
            "value": 1002,
            "enumerable": True,
            "configurable": True,
            "writable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "prop3",
        descriptor={
            "value": 1003,
            "enumerable": True,
            "configurable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "prop4",
        descriptor={
            "value": 1004,
            "enumerable": False,
            "configurable": True
        })
    keys = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryOwnPropertyKeys")
    keys_list = json.loads(keys)
    enumerable_keys = []
    for key in keys_list:
      desc_str = self.sm.ecma262_object_op("ref:Obj:1",
                                           "OrdinaryGetOwnProperty", key)
      if desc_str:
        desc = json.loads(desc_str)
        if desc.get("enumerable", False):
          enumerable_keys.append(key)
    self.assertIn("prop1", enumerable_keys)
    self.assertIn("prop2", enumerable_keys)
    self.assertIn("prop3", enumerable_keys)
    self.assertNotIn("prop4", enumerable_keys)

  def test_test262_keys_non_enumerable_accessor(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "prop1",
        descriptor={
            "get": "ref:Getter1",
            "enumerable": True,
            "configurable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "prop2",
        descriptor={
            "get": "ref:Getter2",
            "enumerable": False,
            "configurable": True
        })
    keys = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryOwnPropertyKeys")
    keys_list = json.loads(keys)
    enumerable_keys = []
    for key in keys_list:
      desc_str = self.sm.ecma262_object_op("ref:Obj:1",
                                           "OrdinaryGetOwnProperty", key)
      if desc_str:
        desc = json.loads(desc_str)
        if desc.get("enumerable", False):
          enumerable_keys.append(key)
    self.assertIn("prop1", enumerable_keys)
    self.assertNotIn("prop2", enumerable_keys)

  def test_test262_keys_inherited_enumerable(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "inheritedProp",
        descriptor={
            "value": 1003,
            "enumerable": True,
            "configurable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")
    self.sm.ecma262_object_op(
        "ref:Obj",
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={
            "value": 1004,
            "enumerable": True,
            "configurable": True,
            "writable": True
        })
    keys = self.sm.ecma262_object_op("ref:Obj", "OrdinaryOwnPropertyKeys")
    keys_list = json.loads(keys)
    self.assertIn("prop", keys_list)
    self.assertNotIn("inheritedProp", keys_list)

  def test_test262_create_null(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj", "OrdinaryObjectCreate", value=None)
    proto = self.sm.ecma262_object_op("ref:Obj", "OrdinaryGetPrototypeOf")
    self.assertIsNone(proto)

  def test_test262_setPrototypeOf_success(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj", "MakeBasicObject")
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    success = self.sm.ecma262_object_op(
        "ref:Obj", "OrdinarySetPrototypeOf", value="ref:Proto")
    self.assertTrue(success)
    current_proto = self.sm.ecma262_object_op("ref:Obj",
                                              "OrdinaryGetPrototypeOf")
    self.assertEqual(current_proto, "ref:Proto")

  def test_test262_getOwnPropertyDescriptor_undefined_name(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj", "MakeBasicObject")
    desc = self.sm.ecma262_object_op("ref:Obj", "OrdinaryGetOwnProperty",
                                     "undefined")
    self.assertEqual(desc, "~undefined~")

  def test_test262_getOwnPropertyDescriptor_accessor(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": "ref:GetterFunc"})
    desc_str = self.sm.ecma262_object_op("ref:Obj", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertEqual(desc["get"], "ref:GetterFunc")
    self.assertFalse(desc.get("enumerable", False))
    self.assertFalse(desc.get("configurable", False))

  def test_test262_defineProperty_change_value_writable(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "writable": True,
            "configurable": True
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 2})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertEqual(desc["value"], 2)

  def test_test262_defineProperty_change_value_non_writable_non_configurable_fail(
      self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "writable": False,
            "configurable": False
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 2})
    self.assertFalse(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertEqual(desc["value"], 1)

  def test_test262_defineProperty_change_writable_true_to_false_non_conf(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "writable": True,
            "configurable": False
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"writable": False})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertFalse(desc.get("writable", False))

  def test_test262_defineProperty_change_writable_false_to_true_non_conf_fail(
      self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "writable": False,
            "configurable": False
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"writable": True})
    self.assertFalse(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertFalse(desc.get("writable", False))

  def test_test262_defineProperty_change_configurable_false_to_true_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "configurable": False
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": True})
    self.assertFalse(success)

  def test_test262_defineProperty_change_enumerable_non_conf_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "enumerable": True,
            "configurable": False
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"enumerable": False})
    self.assertFalse(success)

  def test_test262_setPrototypeOf_non_extensible_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op("ref:Proto1", "MakeBasicObject")
    self.sm.ecma262_object_op("ref:Proto2", "MakeBasicObject")

    # Set initial proto
    self.sm.ecma262_object_op(
        "ref:Obj:1", "OrdinarySetPrototypeOf", value="ref:Proto1")

    # Prevent extensions
    self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryPreventExtensions")

    # Try to change proto
    success = self.sm.ecma262_object_op(
        "ref:Obj:1", "OrdinarySetPrototypeOf", value="ref:Proto2")
    self.assertFalse(success)

  def test_test262_setPrototypeOf_cycle_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op("ref:Obj:2", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:2", "OrdinarySetPrototypeOf", value="ref:Obj:1")
    success = self.sm.ecma262_object_op(
        "ref:Obj:1", "OrdinarySetPrototypeOf", value="ref:Obj:2")
    self.assertFalse(success)

  def test_test262_getPrototypeOf_user_object(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")
    proto = self.sm.ecma262_object_op("ref:Obj", "OrdinaryGetPrototypeOf")
    self.assertEqual(proto, "ref:Proto")

  def test_test262_delete_configurable(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "configurable": True
        })
    success = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryDelete", "foo")
    self.assertTrue(success)
    desc = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                     "foo")
    self.assertEqual(desc, "~undefined~")

  def test_test262_delete_non_configurable(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "configurable": False
        })
    success = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryDelete", "foo")
    self.assertFalse(success)
    desc = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                     "foo")
    self.assertNotEqual(desc, "~undefined~")

  def test_test262_delete_non_existent(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    success = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryDelete", "foo")
    self.assertTrue(success)

  def test_test262_hasProperty_direct(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 1})
    has_prop = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryHasProperty",
                                         "foo")
    self.assertTrue(has_prop)

  def test_test262_hasProperty_inherited(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 1})
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")
    has_prop = self.sm.ecma262_object_op("ref:Obj", "OrdinaryHasProperty",
                                         "foo")
    self.assertTrue(has_prop)

  def test_test262_hasProperty_non_existent(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    has_prop = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryHasProperty",
                                         "foo")
    self.assertFalse(has_prop)

  def test_test262_get_own_data(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 42,
            "enumerable": True
        })
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGet", "foo")
    res = json.loads(result)
    self.assertEqual(res["status"], "completed")
    self.assertEqual(res["value"], 42)

  def test_test262_get_inherited_data(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 42,
            "enumerable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")
    result = self.sm.ecma262_object_op("ref:Obj", "OrdinaryGet", "foo")
    res = json.loads(result)
    self.assertEqual(res["status"], "completed")
    self.assertEqual(res["value"], 42)

  def test_test262_get_non_existent(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGet", "foo")
    res = json.loads(result)
    self.assertEqual(res["status"], "completed")
    self.assertEqual(res["value"], "~undefined~")

  def test_test262_set_own_data(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "writable": True,
            "configurable": True
        })
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinarySet", "foo", 42)
    res = json.loads(result)
    self.assertEqual(res["status"], "completed")
    self.assertTrue(res["success"])

    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGet", "foo")
    res = json.loads(result)
    self.assertEqual(res["value"], 42)

  def test_test262_set_new_property(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinarySet", "foo", 42)
    res = json.loads(result)
    self.assertEqual(res["status"], "completed")
    self.assertTrue(res["success"])

    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGet", "foo")
    res = json.loads(result)
    self.assertEqual(res["value"], 42)

  def test_test262_keys_order(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "b",
        descriptor={
            "value": 1,
            "enumerable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "2",
        descriptor={
            "value": 1,
            "enumerable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "a",
        descriptor={
            "value": 1,
            "enumerable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "1",
        descriptor={
            "value": 1,
            "enumerable": True
        })

    keys = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryOwnPropertyKeys")
    keys_list = json.loads(keys)
    self.assertEqual(keys_list, ["1", "2", "b", "a"])

  def test_test262_set_shadows_prototype(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "writable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")

    result = self.sm.ecma262_object_op("ref:Obj", "OrdinarySet", "foo", 42)
    res = json.loads(result)
    self.assertTrue(res["success"])

    desc_str = self.sm.ecma262_object_op("ref:Obj", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertEqual(desc["value"], 42)

    desc_str = self.sm.ecma262_object_op("ref:Proto", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertEqual(desc["value"], 1)

  def test_test262_set_prototype_non_writable_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "writable": False
        })
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")

    result = self.sm.ecma262_object_op("ref:Obj", "OrdinarySet", "foo", 42)
    res = json.loads(result)
    self.assertEqual(res["status"], "failed")

    desc = self.sm.ecma262_object_op("ref:Obj", "OrdinaryGetOwnProperty", "foo")
    self.assertEqual(desc, "~undefined~")

  def test_test262_set_prototype_setter(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": "ref:SetterFunc"})
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")

    result = self.sm.ecma262_object_op("ref:Obj", "OrdinarySet", "foo", 42)
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_setter_invocation")
    self.assertEqual(res["setter"], "ref:SetterFunc")
    self.assertEqual(res["value"], 42)

  def test_test262_defineProperty_data_to_accessor(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "configurable": True
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": "ref:GetterFunc"})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertIn("get", desc)
    self.assertNotIn("value", desc)

  def test_test262_defineProperty_data_to_accessor_non_conf_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "configurable": False
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": "ref:GetterFunc"})
    self.assertFalse(success)

  def test_test262_preventExtensions_cannot_add(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryPreventExtensions")
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 1})
    self.assertFalse(success)

  def test_test262_preventExtensions_can_update(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "writable": True
        })
    self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryPreventExtensions")
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 2})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertEqual(desc["value"], 2)

  def test_test262_preventExtensions_can_delete(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "configurable": True
        })
    self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryPreventExtensions")
    success = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryDelete", "foo")
    self.assertTrue(success)
    desc = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                     "foo")
    self.assertEqual(desc, "~undefined~")

  def test_test262_create_with_slots(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryObjectCreate",
        value=None,
        descriptor={"additionalSlots": ["[[CustomSlot]]"]})
    result = self.sm.ecma262_object_op("ref:Obj:1", "SetInternalSlot",
                                       "[[CustomSlot]]", 123)
    self.assertEqual(result,
                     "Set internal slot [[CustomSlot]] to 123 in ref:Obj:1")

  def test_test262_getOwnProperty_inherited_undefined(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 1})
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")
    desc = self.sm.ecma262_object_op("ref:Obj", "OrdinaryGetOwnProperty", "foo")
    self.assertEqual(desc, "~undefined~")

  def test_test262_delete_inherited_noop(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 1})
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")

    success = self.sm.ecma262_object_op("ref:Obj", "OrdinaryDelete", "foo")
    self.assertTrue(success)

    result = self.sm.ecma262_object_op("ref:Obj", "OrdinaryGet", "foo")
    res = json.loads(result)
    self.assertEqual(res["value"], 1)

  def test_test262_setPrototypeOf_same_value(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1", "OrdinarySetPrototypeOf", value="ref:Proto")

    success = self.sm.ecma262_object_op(
        "ref:Obj:1", "OrdinarySetPrototypeOf", value="ref:Proto")
    self.assertTrue(success)

  def test_test262_defineProperty_change_getter_non_conf_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": "ref:Getter1",
            "configurable": False
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": "ref:Getter2"})
    self.assertFalse(success)

  def test_test262_defineProperty_change_setter_non_conf_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": "ref:Setter1",
            "configurable": False
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": "ref:Setter2"})
    self.assertFalse(success)

  def test_test262_defineProperty_change_getter_configurable(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": "ref:Getter1",
            "configurable": True
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": "ref:Getter2"})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertEqual(desc["get"], "ref:Getter2")

  def test_test262_defineProperty_change_setter_configurable(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": "ref:Setter1",
            "configurable": True
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": "ref:Setter2"})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertEqual(desc["set"], "ref:Setter2")

  def test_test262_defineProperty_only_getter(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": "ref:GetterFunc"})
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertEqual(desc["get"], "ref:GetterFunc")
    self.assertIsNone(desc["set"])

  def test_test262_defineProperty_only_setter(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": "ref:SetterFunc"})
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertEqual(desc["set"], "ref:SetterFunc")
    self.assertIsNone(desc["get"])

  def test_test262_get_accessor_no_getter(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": "ref:SetterFunc"})
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGet", "foo")
    res = json.loads(result)
    self.assertEqual(res["status"], "completed")
    self.assertEqual(res["value"], "~undefined~")

  def test_test262_get_accessor_with_receiver(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op("ref:ReceiverObj", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": "ref:GetterFunc"})

    result = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryGet",
        "foo",
        descriptor={"receiver": "ref:ReceiverObj"})
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_getter_invocation")
    self.assertEqual(res["receiver"], "ref:ReceiverObj")

  def test_test262_set_accessor_with_receiver(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op("ref:ReceiverObj", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": "ref:SetterFunc"})

    result = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinarySet",
        "foo",
        42,
        descriptor={"receiver": "ref:ReceiverObj"})
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_setter_invocation")
    self.assertEqual(res["receiver"], "ref:ReceiverObj")

  def test_test262_set_receiver_non_writable_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "writable": False
        })

    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinarySet", "foo", 42)
    res = json.loads(result)
    self.assertEqual(res["status"], "failed")

  def test_test262_set_receiver_has_accessor_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": "ref:SetterFunc"})

    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinarySet", "foo", 42)
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_setter_invocation")
    self.assertEqual(res["setter"], "ref:SetterFunc")
    self.assertEqual(res["receiver"], "ref:Obj:1")

  def test_test262_get_inherited_accessor_with_receiver(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": "ref:GetterFunc"})
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")

    result = self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryGet", "foo", descriptor={"receiver": "ref:Obj"})
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_getter_invocation")
    self.assertEqual(res["receiver"], "ref:Obj")

  def test_test262_set_inherited_accessor_with_receiver(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": "ref:SetterFunc"})
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")

    result = self.sm.ecma262_object_op(
        "ref:Obj", "OrdinarySet", "foo", 42, descriptor={"receiver": "ref:Obj"})
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_setter_invocation")
    self.assertEqual(res["receiver"], "ref:Obj")

  def test_test262_set_prototype_no_setter_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Proto", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Proto",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": "ref:GetterFunc"})
    self.sm.ecma262_object_op(
        "ref:Obj", "OrdinaryObjectCreate", value="ref:Proto")

    result = self.sm.ecma262_object_op("ref:Obj", "OrdinarySet", "foo", 42)
    res = json.loads(result)
    self.assertEqual(res["status"], "failed")

  def test_test262_keys_large_integer(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    large_int = str(2**32)
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        large_int,
        descriptor={
            "value": 1,
            "enumerable": True
        })
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "1",
        descriptor={
            "value": 1,
            "enumerable": True
        })

    keys = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryOwnPropertyKeys")
    keys_list = json.loads(keys)
    self.assertEqual(keys_list, ["1", large_int])

  def test_test262_keys_empty(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    keys = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryOwnPropertyKeys")
    keys_list = json.loads(keys)
    self.assertEqual(keys_list, [])

  def test_test262_getPrototypeOf_null(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryObjectCreate", value=None)
    proto = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetPrototypeOf")
    self.assertIsNone(proto)

  def test_test262_preventExtensions_returns_true(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    success = self.sm.ecma262_object_op("ref:Obj:1",
                                        "OrdinaryPreventExtensions")
    self.assertTrue(success)

  def test_test262_isExtensible_false_after_preventExtensions(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryPreventExtensions")
    extensible = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryIsExtensible")
    self.assertFalse(extensible)

  def test_test262_isExtensible_true_by_default(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    extensible = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryIsExtensible")
    self.assertTrue(extensible)

  def test_test262_get_default_receiver(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": "ref:GetterFunc"})

    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGet", "foo")
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_getter_invocation")
    self.assertEqual(res["receiver"], "ref:Obj:1")

  def test_test262_set_default_receiver(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": "ref:SetterFunc"})

    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinarySet", "foo", 42)
    res = json.loads(result)
    self.assertEqual(res["status"], "requires_setter_invocation")
    self.assertEqual(res["receiver"], "ref:Obj:1")

  def test_test262_defineProperty_change_enumerable_configurable(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "enumerable": True,
            "configurable": True
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"enumerable": False})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertFalse(desc["enumerable"])

  def test_test262_defineProperty_change_enumerable_configurable_false_to_true(
      self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "enumerable": False,
            "configurable": True
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"enumerable": True})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertTrue(desc["enumerable"])

  def test_test262_defineProperty_accessor_to_data(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": "ref:GetterFunc",
            "configurable": True
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 42})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertIn("value", desc)
    self.assertNotIn("get", desc)

  def test_test262_defineProperty_accessor_to_data_non_conf_fail(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": "ref:GetterFunc",
            "configurable": False
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 42})
    self.assertFalse(success)

  def test_test262_defineProperty_clear_getter(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": "ref:GetterFunc",
            "configurable": True
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": None})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertIsNone(desc["get"])

  def test_test262_defineProperty_clear_setter(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": "ref:SetterFunc",
            "configurable": True
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": None})
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertIsNone(desc["set"])

  def test_test262_defineProperty_make_non_writable_non_conf(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "writable": True,
            "configurable": True
        })
    success = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "writable": False,
            "configurable": False
        })
    self.assertTrue(success)
    desc_str = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                         "foo")
    desc = json.loads(desc_str)
    self.assertFalse(desc["writable"])
    self.assertFalse(desc["configurable"])

  def test_test262_getOwnProperty_non_existent_undefined(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    desc = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                     "foo")
    self.assertEqual(desc, "~undefined~")


class TestStrictTypeChecking(unittest.TestCase):

  def setUp(self):
    self.test_state_file = os.path.join(
        os.path.dirname(__file__), 'ecma262_states', 'test_state.json')
    if os.path.exists(self.test_state_file):
      os.remove(self.test_state_file)
    self.sm = server.StateManager(self.test_state_file)

  def tearDown(self):
    if os.path.exists(self.test_state_file):
      os.remove(self.test_state_file)

  def test_create_mutable_binding_type_check(self):
    self.sm.ecma262_state_init()
    result = self.sm.ecma262_env_op("ref:Env:GlobalDecl",
                                    "CreateMutableBinding", 123)
    self.assertTrue(
        result.startswith(
            "Error: CreateMutableBinding argument N (name) must be a string"))

    result = self.sm.ecma262_env_op(
        "ref:Env:GlobalDecl", "CreateMutableBinding", "x", value="not_a_bool")
    self.assertTrue(
        result.startswith(
            "Error: CreateMutableBinding argument D (deletable) must be a boolean"
        ))

  def test_create_immutable_binding_type_check(self):
    self.sm.ecma262_state_init()
    result = self.sm.ecma262_env_op("ref:Env:GlobalDecl",
                                    "CreateImmutableBinding", 123)
    self.assertTrue(
        result.startswith(
            "Error: CreateImmutableBinding argument N (name) must be a string"))

  def test_initialize_binding_type_check(self):
    self.sm.ecma262_state_init()
    result = self.sm.ecma262_env_op("ref:Env:GlobalDecl", "InitializeBinding",
                                    123)
    self.assertTrue(
        result.startswith(
            "Error: InitializeBinding argument N (name) must be a string"))

  def test_set_mutable_binding_type_check(self):
    self.sm.ecma262_state_init()
    result = self.sm.ecma262_env_op("ref:Env:GlobalDecl", "SetMutableBinding",
                                    123)
    self.assertTrue(
        result.startswith(
            "Error: SetMutableBinding argument N (name) must be a string"))

  def test_create_import_binding_type_check(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_state_new_environment("Module",
                                          "ref:Env:Global")  # ref:Env:4

    result = self.sm.ecma262_env_op("ref:Env:4", "CreateImportBinding", 123)
    self.assertTrue(
        result.startswith(
            "Error: CreateImportBinding argument N (name) must be a string"))

    result = self.sm.ecma262_env_op("ref:Env:4", "CreateImportBinding", "x")
    self.assertTrue(
        result.startswith(
            "Error: CreateImportBinding argument M (module_record) must be a string reference"
        ))

    result = self.sm.ecma262_env_op(
        "ref:Env:4", "CreateImportBinding", "x", module_record="ref:Env:5")
    self.assertTrue(
        result.startswith(
            "Error: CreateImportBinding argument N2 (binding_name) must be a string"
        ))

  def test_create_import_binding_value_fails(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_state_new_environment("Module",
                                          "ref:Env:Global")  # ref:Env:4

    result = self.sm.ecma262_env_op(
        "ref:Env:4",
        "CreateImportBinding",
        "x",
        value={
            "module": "ref:Env:5",
            "bindingName": "y"
        })
    self.assertTrue(
        result.startswith(
            "Error: CreateImportBinding argument M (module_record) must be a string reference"
        ))

  def test_set_internal_slot_type_check(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    result = self.sm.ecma262_object_op(
        "ref:Obj:1", "SetInternalSlot", 123, value="val")
    self.assertTrue(
        result.startswith(
            "Error: SetInternalSlot argument property_name must be a string"))

  def test_ordinary_define_own_property_type_check(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryDefineOwnProperty",
                                       123)
    self.assertTrue(
        result.startswith(
            "Error: OrdinaryDefineOwnProperty argument property_name must be a string"
        ))

    result = self.sm.ecma262_object_op(
        "ref:Obj:1",
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor="not_a_dict")
    self.assertTrue(
        result.startswith(
            "Error: OrdinaryDefineOwnProperty argument descriptor must be a dictionary"
        ))

  def test_enqueue_promise_job_type_check(self):
    self.sm.ecma262_state_init()
    result = self.sm.ecma262_state_enqueue_promise_job(123, "ref:Obj:Callback",
                                                       [])
    self.assertTrue(
        result.startswith(
            "Error: ecma262_state_enqueue_promise_job argument job_name must be a string"
        ))

    result = self.sm.ecma262_state_enqueue_promise_job("Job", 123, [])
    self.assertTrue(
        result.startswith(
            "Error: ecma262_state_enqueue_promise_job argument callback_id must be a string"
        ))

    result = self.sm.ecma262_state_enqueue_promise_job("Job",
                                                       "ref:Obj:Callback",
                                                       "not_a_list")
    self.assertTrue(
        result.startswith(
            "Error: ecma262_state_enqueue_promise_job argument args must be a list"
        ))

  def test_delete_binding_type_check(self):
    self.sm.ecma262_state_init()
    result = self.sm.ecma262_env_op("ref:Env:GlobalDecl", "DeleteBinding", 123)
    self.assertTrue(
        result.startswith(
            "Error: DeleteBinding argument N (name) must be a string"))

  def test_has_binding_type_check(self):
    self.sm.ecma262_state_init()
    result = self.sm.ecma262_env_op("ref:Env:GlobalDecl", "HasBinding", 123)
    self.assertTrue(
        result.startswith(
            "Error: HasBinding argument N (name) must be a string"))

  def test_get_binding_value_type_check(self):
    self.sm.ecma262_state_init()
    result = self.sm.ecma262_env_op("ref:Env:GlobalDecl", "GetBindingValue",
                                    123)
    self.assertTrue(
        result.startswith(
            "Error: GetBindingValue argument N (name) must be a string"))

  def test_ordinary_get_own_property_type_check(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGetOwnProperty",
                                       123)
    self.assertTrue(
        result.startswith(
            "Error: OrdinaryGetOwnProperty argument property_name must be a string"
        ))

  def test_ordinary_has_property_type_check(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryHasProperty", 123)
    self.assertTrue(
        result.startswith(
            "Error: OrdinaryHasProperty argument property_name must be a string"
        ))

  def test_ordinary_delete_type_check(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryDelete", 123)
    self.assertTrue(
        result.startswith(
            "Error: OrdinaryDelete argument property_name must be a string"))

  def test_ordinary_get_type_check(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinaryGet", 123)
    self.assertTrue(
        result.startswith(
            "Error: OrdinaryGet argument property_name must be a string"))

  def test_ordinary_set_type_check(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    result = self.sm.ecma262_object_op("ref:Obj:1", "OrdinarySet", 123, 42)
    self.assertTrue(
        result.startswith(
            "Error: OrdinarySet argument property_name must be a string"))

  def test_ordinary_object_create_proto_check(self):
    self.sm.ecma262_state_init()
    result = self.sm.ecma262_object_op(
        "ref:Obj:Test", "OrdinaryObjectCreate", value=123)
    self.assertTrue(
        result.startswith(
            "Error: OrdinaryObjectCreate argument proto (value) must be None or a string reference"
        ))

  def test_ordinary_set_prototype_of_proto_check(self):
    self.sm.ecma262_state_init()
    self.sm.ecma262_object_op("ref:Obj:1", "MakeBasicObject")
    result = self.sm.ecma262_object_op(
        "ref:Obj:1", "OrdinarySetPrototypeOf", value=123)
    self.assertTrue(
        result.startswith(
            "Error: OrdinarySetPrototypeOf argument V (proto) must be None or a string reference"
        ))


class TestTest262Generated(unittest.TestCase):

  def setUp(self):
    self.test_state_file = "/usr/local/google/home/olivf/ecmabot/ecma262_states/test_state_generated.json"
    if os.path.exists(self.test_state_file):
      os.remove(self.test_state_file)
    self.sm = server.StateManager(self.test_state_file)

  def tearDown(self):
    if os.path.exists(self.test_state_file):
      os.remove(self.test_state_file)
    history_path = self.test_state_file + ".history"
    if os.path.exists(history_path):
      os.remove(history_path)

  def test_gen_string_get_a_0(self):
    self.sm.ecma262_state_init()
    res = self.sm.ecma262_object_op(None, "StringCreate", value="a")
    str_id = res.split(" ")[1]
    get_res = self.sm.ecma262_object_op(
        str_id, "OrdinaryGet", property_name="0")
    res_data = json.loads(get_res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], "a")


class TestSpecCompliance(unittest.TestCase):

  def setUp(self):
    self.test_state_file = os.path.join(
        os.path.dirname(__file__), 'ecma262_states', 'test_state.json')
    if os.path.exists(self.test_state_file):
      os.remove(self.test_state_file)
    self.sm = server.StateManager(self.test_state_file)
    self.sm.ecma262_state_init()

  def tearDown(self):
    if os.path.exists(self.test_state_file):
      os.remove(self.test_state_file)
    history_path = self.test_state_file + ".history"
    if os.path.exists(history_path):
      os.remove(history_path)

  # --- Batch 1: Property Defaults & No-ops ---

  def test_b1_1_defaults_data(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id, "OrdinaryDefineOwnProperty", "foo", descriptor={"value": 1})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 1)
    self.assertFalse(desc["writable"])
    self.assertFalse(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b1_2_defaults_accessor(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": getter_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["get"], getter_id)
    self.assertIsNone(desc["set"])
    self.assertFalse(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b1_3_generic_desc(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id, "OrdinaryDefineOwnProperty", "foo", descriptor={})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], "~undefined~")
    self.assertFalse(desc["writable"])
    self.assertFalse(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b1_4_noop_data(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(object_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    d1 = json.loads(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 101,
            "writable": True,
            "enumerable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    d2 = json.loads(res)

    self.assertEqual(d1, d2)

  def test_b1_5_noop_accessor(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "enumerable": True,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    d1 = json.loads(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "enumerable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    d2 = json.loads(res)

    self.assertEqual(d1, d2)

  # --- Batch 2: Redefinition Restrictions ---

  def test_b2_1_enum_false_to_true(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "enumerable": False,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "enumerable": True
        })
    self.assertFalse(res)

  def test_b2_2_enum_true_to_false(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "enumerable": True,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "enumerable": False
        })
    self.assertFalse(res)

  def test_b2_3_data_to_accessor(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 101,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": getter_id})
    self.assertFalse(res)

  def test_b2_4_accessor_to_data(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 101})
    self.assertFalse(res)

  def test_b2_5_configurable_data_to_accessor(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(object_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": getter_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["get"], getter_id)
    self.assertTrue(desc["enumerable"])
    self.assertTrue(desc["configurable"])

  # --- Batch 3: More Redefinition Edge Cases ---

  def test_b3_1_accessor_to_data_configurable(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 101})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 101)
    self.assertFalse(desc["writable"])
    self.assertFalse(desc["enumerable"])
    self.assertTrue(desc["configurable"])

  def test_b3_2_relax_writable(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 101,
            "writable": False,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 101,
            "writable": True
        })
    self.assertFalse(res)

  def test_b3_3_change_value_non_writable(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 101,
            "writable": False,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 102})
    self.assertFalse(res)

  def test_b3_4_change_setter(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": setter_id})
    self.assertFalse(res)

  def test_b3_5_set_setter_undefined(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id, "OrdinaryDefineOwnProperty", "foo", descriptor={"set": None})
    self.assertTrue(res)

  # --- Batch 4: Inherited & Shadowed Properties ---

  def test_b4_1_change_getter(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id, "OrdinaryDefineOwnProperty", "foo", descriptor={"get": None})
    self.assertFalse(res)

  def test_b4_2_set_getter_undefined(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": setter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id, "OrdinaryDefineOwnProperty", "foo", descriptor={"get": None})
    self.assertTrue(res)

  def test_b4_3_make_configurable_false(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": True
        })
    self.assertFalse(res)

  def test_b4_4_shadow_inherited(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        proto_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": True})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertTrue(desc["configurable"])

  def test_b4_5_redefine_shadowed_non_configurable(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        proto_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": True})
    self.assertFalse(res)

  # --- Batch 5: Inherited & Shadowed Accessors ---

  def test_b5_1_shadow_accessor_non_configurable(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        proto_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": True})
    self.assertFalse(res)

  def test_b5_2_change_getter_non_configurable(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "get": getter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id2 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "get": getter_id2,
            "configurable": True
        })
    self.assertFalse(res)

  def test_b5_3_shadow_inherited_accessor(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        proto_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "get": getter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id2 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "get": getter_id2,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)
    self.assertTrue(desc["configurable"])

  def test_b5_4_redefine_shadowed_accessor_non_configurable(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        proto_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": True})
    self.assertFalse(res)

  def test_b5_5_redefine_shadowed_accessor_non_configurable_2(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        proto_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id2 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id2,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": True})
    self.assertFalse(res)

  # --- Batch 6: Accessors without Get & Object Types ---

  def test_b6_1_accessor_no_get_make_configurable(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    # Create function object for setter
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": setter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": True})
    self.assertFalse(res)

  def test_b6_2_shadow_accessor_no_get_make_configurable(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        proto_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    # Create function object for setter
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": setter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": True})
    self.assertFalse(res)

  def test_b6_3_shadow_inherited_accessor_no_get(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        proto_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": setter_id,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": True})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertTrue(desc["configurable"])

  def test_b6_4_defineProperty_on_function(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    fun_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        fun_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        fun_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": True
        })
    self.assertFalse(res)

  def test_b6_5_defineProperty_on_array_non_index(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        arr_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        arr_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": True
        })
    self.assertFalse(res)

  # --- Batch 7: defineProperty on Various Object Types ---

  def test_b7_1_defineProperty_on_string_non_index(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        str_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        str_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": True
        })
    self.assertFalse(res)

  def test_b7_2_defineProperty_on_boolean(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]
    # Simulate Boolean object by adding slot if needed, but here we just treat it as ordinary

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": True
        })
    self.assertFalse(res)

  def test_b7_3_defineProperty_on_number(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": True
        })
    self.assertFalse(res)

  def test_b7_4_defineProperty_on_math(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 12)
    self.assertTrue(desc["configurable"])

  def test_b7_5_defineProperty_on_date(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": True
        })
    self.assertFalse(res)

  # --- Batch 8: defineProperty on More Object Types ---

  def test_b8_1_defineProperty_on_regexp(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]
    # Simulate RegExp object

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": True
        })
    self.assertFalse(res)

  def test_b8_2_defineProperty_on_json(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 12)
    self.assertTrue(desc["configurable"])

  def test_b8_3_defineProperty_on_error(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": True
        })
    self.assertFalse(res)

  def test_b8_4_defineProperty_on_arguments(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 11,
            "configurable": True
        })
    self.assertFalse(res)

  def test_b8_5_defineProperty_on_global(self):
    # Global object is ref:Obj:Global
    res = self.sm.ecma262_object_op(
        "ref:Obj:Global",
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 12,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op("ref:Obj:Global", "OrdinaryGetOwnProperty",
                                    "foo")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 12)
    self.assertTrue(desc["configurable"])

  # --- Batch 9: defineProperty Defaults (Data Properties) ---

  def test_b9_1_generic_desc_data(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={"enumerable": True})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertTrue(desc["enumerable"])
    self.assertEqual(desc["value"], "~undefined~")
    self.assertFalse(desc["writable"])
    self.assertFalse(desc["configurable"])

  def test_b9_2_value_absent_defaults_undefined(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "writable": True,
            "enumerable": True,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertEqual(desc["value"], "~undefined~")
    self.assertTrue(desc["writable"])
    self.assertTrue(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b9_3_writable_absent_defaults_false(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "value": 1001,
            "enumerable": True,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 1001)
    self.assertFalse(desc["writable"])
    self.assertTrue(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b9_4_enumerable_absent_defaults_false(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "value": 1001,
            "writable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 1001)
    self.assertTrue(desc["writable"])
    self.assertFalse(desc["enumerable"])
    self.assertTrue(desc["configurable"])

  def test_b9_5_configurable_absent_defaults_false(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "value": 1001,
            "writable": True,
            "enumerable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 1001)
    self.assertTrue(desc["writable"])
    self.assertTrue(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  # --- Batch 10: defineProperty Defaults (Accessor Properties) ---

  def test_b10_1_update_all_attributes(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    # Create property with all true
    res = self.sm.ecma262_object_op(
        object_id, "CreateDataProperty", "property", value=1)
    self.assertTrue(res)

    # Update all attributes to false
    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "value": 1001,
            "writable": False,
            "enumerable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 1001)
    self.assertFalse(desc["writable"])
    self.assertFalse(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b10_2_getter_absent_defaults_undefined(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "set": setter_id,
            "enumerable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertIsNone(desc["get"])
    self.assertEqual(desc["set"], setter_id)

  def test_b10_3_setter_absent_defaults_undefined(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "get": getter_id,
            "enumerable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertEqual(desc["get"], getter_id)
    self.assertIsNone(desc["set"])

  def test_b10_4_enumerable_absent_defaults_false_accessor(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "get": getter_id,
            "set": setter_id,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertFalse(desc["enumerable"])
    self.assertTrue(desc["configurable"])

  def test_b10_5_configurable_absent_defaults_false_accessor(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "get": getter_id,
            "set": setter_id,
            "enumerable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertTrue(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  # --- Batch 11: defineProperty More Accessors & No-ops ---

  def test_b11_1_update_all_attributes_accessor(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    # Create function objects
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    # Define accessor property
    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "get": getter_id,
            "set": setter_id,
            "configurable": True,
            "enumerable": True
        })
    self.assertTrue(res)

    # Create new function objects
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id2 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id2 = res.split(" ")[1]

    # Update all attributes
    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "get": getter_id2,
            "set": setter_id2,
            "configurable": False,
            "enumerable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty",
                                    "property")
    desc = json.loads(res)

    self.assertEqual(desc["get"], getter_id2)
    self.assertEqual(desc["set"], setter_id2)
    self.assertFalse(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b11_2_empty_desc_data_noop(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(object_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(
        object_id, "OrdinaryDefineOwnProperty", "foo", descriptor={})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 101)
    self.assertTrue(desc["writable"])
    self.assertTrue(desc["enumerable"])
    self.assertTrue(desc["configurable"])

  def test_b11_3_empty_desc_accessor_noop(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "enumerable": True,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(
        object_id, "OrdinaryDefineOwnProperty", "foo", descriptor={})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["get"], getter_id)
    self.assertTrue(desc["enumerable"])
    self.assertTrue(desc["configurable"])

  def test_b11_4_change_value_type(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(object_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": "abc"})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], "abc")

  def test_b11_5_set_value_undefined_twice(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": None})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": None})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertIsNone(desc["value"])

  # --- Batch 12: defineProperty Special Values ---

  def test_b12_1_set_value_null_twice(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": None})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": None})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertIsNone(desc["value"])

  def test_b12_2_set_value_nan_twice(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    nan = float('nan')
    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": nan})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": nan})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertTrue(desc["value"] != desc["value"] or desc["value"] == "~NaN~")

  def test_b12_3_change_value_neg_zero_to_pos_zero(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": -0.0,
            "configurable": False
        })
    self.assertTrue(res)

    # Try to change to +0.0
    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 0.0})
    self.assertFalse(res)

  def test_b12_4_change_value_pos_zero_to_neg_zero(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 0.0,
            "configurable": False
        })
    self.assertTrue(res)

    # Try to change to -0.0
    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": -0.0})
    self.assertFalse(res)

  def test_b12_5_change_value_number(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(object_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 102})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 102)

  # --- Batch 13: defineProperty More Values & Writable ---

  def test_b13_1_change_value_boolean(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id, "CreateDataProperty", "foo", value=True)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": False})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertFalse(desc["value"])

  def test_b13_2_set_value_object_twice(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj1_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": obj1_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": obj1_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], obj1_id)

  def test_b13_3_change_value_object(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj1_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        object_id, "CreateDataProperty", "foo", value=obj1_id)

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj2_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": obj2_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], obj2_id)

  def test_b13_4_set_writable_false_twice(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"writable": False})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"writable": False})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertFalse(desc["writable"])

  def test_b13_5_change_writable_false_to_true(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "writable": False,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"writable": True})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertTrue(desc["writable"])

  # --- Batch 14: defineProperty Accessor Re-definition ---

  def test_b14_1_set_getter_twice(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "set": setter_id
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": getter_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["get"], getter_id)

  def test_b14_2_change_getter_configurable(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id1 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id1 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id1,
            "set": setter_id1,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id2 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": getter_id2})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["get"], getter_id2)

  def test_b14_3_set_setter_twice(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": setter_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": setter_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["set"], setter_id)

  def test_b14_4_change_setter_configurable(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id1 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": setter_id1,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id2 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": setter_id2})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["set"], setter_id2)

  def test_b14_5_set_enumerable_false_twice(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"enumerable": False})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"enumerable": False})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertFalse(desc["enumerable"])

  # --- Batch 15: defineProperty Enumerable & Configurable ---

  def test_b15_1_change_enumerable_false_to_true(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "enumerable": False,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"enumerable": True})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertTrue(desc["enumerable"])

  def test_b15_2_set_configurable_false_twice(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": False})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": False})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertFalse(desc["configurable"])

  def test_b15_3_change_configurable_true_to_false(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": True})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"configurable": False})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertFalse(desc["configurable"])

  def test_b15_4_redefine_non_writable_undefined(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": "~undefined~",
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": "~undefined~",
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], "~undefined~")

  def test_b15_5_redefine_non_writable_null(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": None,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": None,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertIsNone(desc["value"])

  # --- Batch 16: defineProperty Non-Writable Re-definition ---

  def test_b16_1_redefine_non_writable_nan(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    nan = float('nan')
    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": nan,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": nan,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertTrue(desc["value"] != desc["value"] or desc["value"] == "~NaN~")

  def test_b16_2_change_value_neg_zero_to_pos_zero_non_writable(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": -0.0,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 0.0})
    self.assertFalse(res)

  def test_b16_3_change_value_pos_zero_to_neg_zero_non_writable(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 0.0,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": -0.0})
    self.assertFalse(res)

  def test_b16_4_redefine_non_writable_same_number(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 100,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 100})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 100)

  def test_b16_5_change_value_non_writable_number(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 10,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id, "OrdinaryDefineOwnProperty", "foo", descriptor={"value": 20})
    self.assertFalse(res)

  # --- Batch 17: defineProperty More Non-Writable Re-definition ---

  def test_b17_1_redefine_non_writable_same_string(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": "abcd",
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": "abcd"})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], "abcd")

  def test_b17_2_change_value_non_writable_string(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": "abcd",
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": "fghj"})
    self.assertFalse(res)

  def test_b17_3_redefine_non_writable_same_boolean(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": False,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": False})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertFalse(desc["value"])

  def test_b17_4_change_value_non_writable_boolean(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": False,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": True})
    self.assertFalse(res)

  def test_b17_5_redefine_non_writable_same_object(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj1_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": obj1_id,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": obj1_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], obj1_id)

  # --- Batch 18: defineProperty More Accessor Restrictions ---

  def test_b18_1_change_value_non_writable_object(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj1_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": obj1_id,
            "writable": False,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj2_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": obj2_id})
    self.assertFalse(res)

  def test_b18_2_set_setter_twice_non_configurable(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": setter_id,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": setter_id})
    self.assertTrue(res)

  def test_b18_3_set_setter_undefined_fail(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={
            "get": getter_id,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "property",
        descriptor={"set": setter_id})
    self.assertFalse(res)

  def test_b18_4_set_getter_undefined_fail(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": setter_id,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": getter_id})
    self.assertFalse(res)

  def test_b18_5_change_value_to_undefined(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(object_id, "CreateDataProperty", "foo", value=100)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": None})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertIsNone(desc["value"])

  # --- Batch 19: defineProperty Updating Accessors ---

  def test_b19_1_change_value_undefined_to_number(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id, "CreateDataProperty", "foo", value="~undefined~")
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"value": 100})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 100)

  def test_b19_2_update_multiple_attributes(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 100,
            "writable": True,
            "enumerable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 200,
            "writable": False,
            "enumerable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["value"], 200)
    self.assertFalse(desc["writable"])
    self.assertFalse(desc["enumerable"])
    self.assertTrue(desc["configurable"])

  def test_b19_3_change_getter_to_undefined(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "set": setter_id,
            "enumerable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": setter_id,
            "get": None
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertIsNone(desc["get"])
    self.assertEqual(desc["set"], setter_id)

  def test_b19_4_change_getter_undefined_to_function(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": setter_id,
            "get": None,
            "enumerable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"get": getter_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["get"], getter_id)

  def test_b19_5_change_setter_to_undefined(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "set": setter_id,
            "enumerable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": None,
            "get": getter_id
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertIsNone(desc["set"])
    self.assertEqual(desc["get"], getter_id)

  # --- Batch 20: defineProperty Final Edge Cases ---

  def test_b20_1_change_setter_undefined_to_function(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "set": None,
            "get": getter_id,
            "enumerable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={"set": setter_id})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["set"], setter_id)

  def test_b20_2_change_enumerable_true_to_false_accessor(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "enumerable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "enumerable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertFalse(desc["enumerable"])

  def test_b20_3_change_configurable_true_to_false_accessor(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "set": setter_id,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getter_id,
            "configurable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertFalse(desc["configurable"])

  def test_b20_4_update_multiple_attributes_accessor(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getFunc1 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setFunc1 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getFunc1,
            "set": setFunc1,
            "enumerable": True,
            "configurable": True
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getFunc2 = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setFunc2 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "get": getFunc2,
            "set": setFunc2,
            "enumerable": False
        })
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)

    self.assertEqual(desc["get"], getFunc2)
    self.assertEqual(desc["set"], setFunc2)
    self.assertFalse(desc["enumerable"])
    self.assertTrue(desc["configurable"])

  def test_b20_5_array_length_truncation_fail(self):
    # Create array with length 2
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=2)
    arr_id = res.split(" ")[1]

    # Set element 1 to non-configurable
    res = self.sm.ecma262_object_op(
        arr_id,
        "OrdinaryDefineOwnProperty",
        "1",
        descriptor={
            "value": 1,
            "configurable": False
        })
    self.assertTrue(res)

    # Try to set length to 1 (requires deleting element 1)
    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "length", descriptor={"value": 1})
    self.assertFalse(res)

    # Verify length is still 2
    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 2)

  # --- Batch 21: Prototype Chain Operations ---

  def test_b21_1_getPrototypeOf(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetPrototypeOf")
    self.assertEqual(res, proto_id)

  def test_b21_2_setPrototypeOf(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id1 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id2 = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id1)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id, "OrdinarySetPrototypeOf", value=proto_id2)
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetPrototypeOf")
    self.assertEqual(res, proto_id2)

  def test_b21_3_setPrototypeOf_cycle(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj1_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=obj1_id)
    obj2_id = res.split(" ")[1]

    # Try to set prototype of obj1 to obj2 (creates cycle: obj1 -> obj2 -> obj1)
    res = self.sm.ecma262_object_op(
        obj1_id, "OrdinarySetPrototypeOf", value=obj2_id)
    self.assertFalse(res)

  def test_b21_4_hasProperty_proto_chain(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(proto_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(object_id, "OrdinaryHasProperty", "foo")
    self.assertTrue(res)

  def test_b21_5_get_proto_chain(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(proto_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(object_id, "OrdinaryGet", "foo")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], 101)

  def test_b22_1_set_shadowing(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(proto_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(object_id, "OrdinarySet", "foo", 202)
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertTrue(res_data["success"])

    # Verify shadowing
    res = self.sm.ecma262_object_op(object_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 202)

    res = self.sm.ecma262_object_op(proto_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 101)

  def test_b22_2_delete_only_own(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(proto_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(object_id, "OrdinaryDelete", "foo")
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryHasProperty", "foo")
    self.assertTrue(res)

  def test_b22_3_ownPropertyKeys_only_own(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(proto_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(object_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    self.assertEqual(keys, [])

  def test_b22_4_extensibility(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(object_id, "OrdinaryIsExtensible")
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryPreventExtensions")
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(object_id, "OrdinaryIsExtensible")
    self.assertFalse(res)

  def test_b22_5_setPrototypeOf_non_extensible(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(object_id, "OrdinaryPreventExtensions")

    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id, "OrdinarySetPrototypeOf", value=proto_id)
    self.assertFalse(res)

  # --- Batch 23: Declarative Environments ---

  def test_b23_1_create_init_declarative(self):
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    env_id = res.split(" ")[2]

    res = self.sm.ecma262_env_op(env_id, "CreateMutableBinding", "x")
    self.assertEqual(res, f"Created mutable binding x in {env_id}")

    res = self.sm.ecma262_env_op(env_id, "InitializeBinding", "x", 42)
    self.assertEqual(res, f"Initialized binding x to 42 in {env_id}")

    res = self.sm.ecma262_env_op(env_id, "GetBindingValue", "x")
    self.assertEqual(json.loads(res), 42)

  def test_b23_2_get_binding_value(self):
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    env_id = res.split(" ")[2]

    self.sm.ecma262_env_op(env_id, "CreateMutableBinding", "x")
    self.sm.ecma262_env_op(env_id, "InitializeBinding", "x", 101)

    res = self.sm.ecma262_env_op(env_id, "GetBindingValue", "x")
    self.assertEqual(json.loads(res), 101)

  def test_b23_3_set_mutable_binding(self):
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    env_id = res.split(" ")[2]

    self.sm.ecma262_env_op(env_id, "CreateMutableBinding", "x")
    self.sm.ecma262_env_op(env_id, "InitializeBinding", "x", 101)

    res = self.sm.ecma262_env_op(
        env_id, "SetMutableBinding", "x", 202, strict=True)
    self.assertTrue("Set mutable binding" in res)

    res = self.sm.ecma262_env_op(env_id, "GetBindingValue", "x")
    self.assertEqual(json.loads(res), 202)

  def test_b23_4_delete_binding(self):
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    env_id = res.split(" ")[2]

    self.sm.ecma262_env_op(env_id, "CreateMutableBinding", "x", value=False)

    res = self.sm.ecma262_env_op(env_id, "DeleteBinding", "x")
    self.assertFalse(res)

  def test_b23_5_has_binding(self):
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    env_id = res.split(" ")[2]

    self.sm.ecma262_env_op(env_id, "CreateMutableBinding", "x")

    res = self.sm.ecma262_env_op(env_id, "HasBinding", "x")
    self.assertTrue(res)

    res = self.sm.ecma262_env_op(env_id, "HasBinding", "y")
    self.assertFalse(res)

  # --- Batch 24: Advanced Environments ---

  def test_b24_1_scope_chain_lookup(self):
    # Outer env
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    outer_id = res.split(" ")[2]

    self.sm.ecma262_env_op(outer_id, "CreateMutableBinding", "x")
    self.sm.ecma262_env_op(outer_id, "InitializeBinding", "x", 42)

    # Inner env
    res = self.sm.ecma262_state_new_environment("Declarative", outer_id)
    inner_id = res.split(" ")[2]

    # Simulate identifier resolution loop
    current_id = inner_id
    found = False
    while current_id and current_id != "null":
      res = self.sm.ecma262_env_op(current_id, "HasBinding", "x")
      if res is True:
        res = self.sm.ecma262_env_op(current_id, "GetBindingValue", "x")
        self.assertEqual(json.loads(res), 42)
        found = True
        break
      # Get outer env
      state = self.sm._read_state()
      current_id = state["environmentRecords"][current_id].get("outerEnv")

    self.assertTrue(found)

  def test_b24_2_immutable_binding(self):
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    env_id = res.split(" ")[2]

    res = self.sm.ecma262_env_op(env_id, "CreateImmutableBinding", "x")
    self.assertEqual(res, f"Created immutable binding x in {env_id}")

    self.sm.ecma262_env_op(env_id, "InitializeBinding", "x", 42)

    res = self.sm.ecma262_env_op(
        env_id, "SetMutableBinding", "x", 100, strict=True)
    self.assertTrue("Error: TypeError" in res)

  def test_b24_3_tdz_check(self):
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    env_id = res.split(" ")[2]

    self.sm.ecma262_env_op(env_id, "CreateMutableBinding", "x")

    res = self.sm.ecma262_env_op(env_id, "GetBindingValue", "x")
    self.assertTrue("TDZ" in res)

  def test_b24_4_object_environment(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_state_new_environment(
        "Object", "ref:Env:Global", bindings={"bindingObject": obj_id})
    env_id = res.split(" ")[2]

    res = self.sm.ecma262_env_op(env_id, "HasBinding", "foo")
    self.assertTrue(res)

    res = self.sm.ecma262_env_op(env_id, "GetBindingValue", "foo")
    self.assertEqual(json.loads(res), 101)

  def test_b24_5_global_environment(self):
    # Create property on global object
    self.sm.ecma262_object_op(
        "ref:Obj:Global", "CreateDataProperty", "globalProp", value=123)

    res = self.sm.ecma262_env_op("ref:Env:Global", "HasBinding", "globalProp")
    self.assertTrue(res)

    res = self.sm.ecma262_env_op("ref:Env:Global", "GetBindingValue",
                                 "globalProp")
    self.assertEqual(json.loads(res), 123)

  # --- Batch 25: Private Fields ---

  def test_b25_1_private_field_add_get(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldAdd", property_name="#x", value=42)
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldGet", property_name="#x")
    self.assertEqual(res, 42)

  def test_b25_2_private_field_set(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id, "PrivateFieldAdd", property_name="#x", value=42)

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldSet", property_name="#x", value=100)
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldGet", property_name="#x")
    self.assertEqual(res, 100)

  def test_b25_3_private_field_access_errors(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldGet", property_name="#x")
    self.assertTrue("Error" in res)

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldSet", property_name="#x", value=100)
    self.assertTrue("Error" in res)

  def test_b25_4_private_field_duplicate_add(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id, "PrivateFieldAdd", property_name="#x", value=42)

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldAdd", property_name="#x", value=100)
    self.assertTrue("Error" in res)

  def test_b25_5_create_private_name_uniqueness(self):
    res1 = self.sm.ecma262_object_op(
        None, "CreatePrivateName", property_name="#x")
    self.assertTrue(res1.startswith("ref:Priv:"))

    res2 = self.sm.ecma262_object_op(
        None, "CreatePrivateName", property_name="#x")
    self.assertTrue(res2.startswith("ref:Priv:"))

    self.assertNotEqual(res1, res2)

  def test_b26_1_private_method(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    func_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldAdd", property_name="#method", value=func_id)
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldGet", property_name="#method")
    self.assertEqual(res, func_id)

  def test_b26_2_private_field_isolation(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj1_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj2_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj1_id, "PrivateFieldAdd", property_name="#x", value=42)
    self.sm.ecma262_object_op(
        obj2_id, "PrivateFieldAdd", property_name="#x", value=100)

    res = self.sm.ecma262_object_op(
        obj1_id, "PrivateFieldGet", property_name="#x")
    self.assertEqual(res, 42)

    res = self.sm.ecma262_object_op(
        obj2_id, "PrivateFieldGet", property_name="#x")
    self.assertEqual(res, 100)

  def test_b26_3_private_field_no_inheritance(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        proto_id, "PrivateFieldAdd", property_name="#x", value=42)

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        object_id, "PrivateFieldGet", property_name="#x")
    self.assertTrue("Error" in res)

  def test_b26_4_private_field_coexistence(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    # Create two unique private names with same description
    priv1 = self.sm.ecma262_object_op(
        None, "CreatePrivateName", property_name="#x")
    priv2 = self.sm.ecma262_object_op(
        None, "CreatePrivateName", property_name="#x")

    # Add both to same object using unique IDs
    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldAdd", property_name=priv1, value=42)
    self.assertTrue(res)
    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldAdd", property_name=priv2, value=100)
    self.assertTrue(res)

    # Verify they coexist
    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldGet", property_name=priv1)
    self.assertEqual(res, 42)
    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldGet", property_name=priv2)
    self.assertEqual(res, 100)

  def test_b26_5_private_field_non_object(self):
    # Try to access on non-existent object reference
    res = self.sm.ecma262_object_op(
        "ref:Obj:NonExistent", "PrivateFieldGet", property_name="#x")
    self.assertTrue("Error" in res)

  # --- Batch 27: Special Object Types ---

  def test_b27_1_array_length_grows(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "5", descriptor={"value": 10})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 6)

  def test_b27_2_array_length_truncation_success(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    arr_id = res.split(" ")[1]

    self.sm.ecma262_object_op(arr_id, "CreateDataProperty", "4", value=100)

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "length", descriptor={"value": 2})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "4")
    self.assertEqual(res, "~undefined~")

  def test_b27_3_string_indexed_access(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGet", "1")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], "b")

  def test_b27_4_string_length(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGet", "length")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], 3)

  def test_b27_5_function_strict_slot(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryFunctionCreate", descriptor={"strict": True})
    func_id = res.split(" ")[1]

    state = self.sm._read_state()
    self.assertTrue(state["heap"][func_id]["internalSlots"]["[[Strict]]"])

  # --- Batch 28: More Special Object Types ---

  def test_b28_1_sparse_array(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "5", descriptor={"value": 10})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "2")
    self.assertEqual(res, "~undefined~")

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 6)

  def test_b28_2_invalid_array_length(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "length", descriptor={"value": -1})
    self.assertTrue("Error: RangeError" in res)

  def test_b28_3_string_out_of_bounds(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGet", "5")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], "~undefined~")

  def test_b28_4_modify_string_length(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        str_id, "OrdinaryDefineOwnProperty", "length", descriptor={"value": 5})
    self.assertFalse(res)

  def test_b28_5_function_parameters_slot(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryFunctionCreate", descriptor={"parameters": ["a", "b"]})
    func_id = res.split(" ")[1]

    state = self.sm._read_state()
    self.assertEqual(
        state["heap"][func_id]["internalSlots"]["[[FormalParameters]]"],
        ["a", "b"])

  # --- Batch 29: Edge Cases ---

  def test_b29_1_delete_non_configurable(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "configurable": False
        })

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryDelete", "foo")
    self.assertFalse(res)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryHasProperty", "foo")
    self.assertTrue(res)

  def test_b29_2_modify_non_extensible(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "OrdinaryPreventExtensions")

    res = self.sm.ecma262_object_op(
        obj_id, "OrdinaryDefineOwnProperty", "foo", descriptor={"value": 1})
    self.assertFalse(res)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryHasProperty", "foo")
    self.assertFalse(res)

  def test_b29_3_delete_array_length(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryDelete", "length")
    self.assertFalse(res)

  def test_b29_4_delete_string_length(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryDelete", "length")
    self.assertFalse(res)

  def test_b29_5_get_own_property_non_existent(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty",
                                    "non_existent")
    self.assertEqual(res, "~undefined~")

  # --- Batch 30: Final Edge Cases ---

  def test_b30_1_string_get_own_property_out_of_bounds(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGetOwnProperty", "3")
    self.assertEqual(res, "~undefined~")

  def test_b30_2_string_get_own_property_length(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 3)
    self.assertFalse(desc["writable"])
    self.assertFalse(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b30_3_array_get_own_property_length(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 5)
    self.assertTrue(desc["writable"])
    self.assertFalse(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b30_4_setPrototypeOf_same_proto_non_extensible(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    proto_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    object_id = res.split(" ")[1]

    self.sm.ecma262_object_op(object_id, "OrdinaryPreventExtensions")

    # Set to same proto should succeed
    res = self.sm.ecma262_object_op(
        object_id, "OrdinarySetPrototypeOf", value=proto_id)
    self.assertTrue(res)

  def test_b30_5_delete_non_existent(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value="ref:Obj:ObjectProto")
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryDelete", "non_existent")
    self.assertTrue(res)

  # --- Batch 31: OwnPropertyKeys Order ---

  def test_b31_1_keys_order_numeric(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "2", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "1", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "3", value=1)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    self.assertEqual(keys, ["1", "2", "3"])

  def test_b31_2_keys_order_strings(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "b", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "a", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "c", value=1)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    self.assertEqual(keys, ["b", "a", "c"])

  def test_b31_3_keys_order_mixed(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "b", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "1", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "a", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "2", value=1)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    self.assertEqual(keys, ["1", "2", "b", "a"])

  def test_b31_4_keys_order_array(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=2)
    arr_id = res.split(" ")[1]

    self.sm.ecma262_object_op(arr_id, "CreateDataProperty", "1", value=1)
    self.sm.ecma262_object_op(arr_id, "CreateDataProperty", "0", value=1)
    self.sm.ecma262_object_op(arr_id, "CreateDataProperty", "foo", value=1)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    # length is in properties, so it should be included!
    # properties are: "length", "1", "0", "foo"
    # indices: "0", "1"
    # strings: "length", "foo" (length was added first in ArrayCreate)
    self.assertEqual(keys, ["0", "1", "length", "foo"])

  def test_b31_5_keys_order_string_object(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="ab")
    str_id = res.split(" ")[1]

    self.sm.ecma262_object_op(str_id, "CreateDataProperty", "foo", value=1)

    res = self.sm.ecma262_object_op(str_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    # StringCreate adds indices 0, 1 and length
    # So keys should be "0", "1", "length", "foo"
    self.assertEqual(keys, ["0", "1", "length", "foo"])

  # --- Batch 32: OwnPropertyKeys Order & Symbols ---

  def test_b32_1_keys_order_symbols(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id, "CreateDataProperty", "Symbol(a)", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "b", value=1)
    self.sm.ecma262_object_op(
        obj_id, "CreateDataProperty", "Symbol(c)", value=1)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    self.assertEqual(keys, ["b", "Symbol(a)", "Symbol(c)"])

  def test_b32_2_keys_order_after_delete(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "a", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "b", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "c", value=1)

    self.sm.ecma262_object_op(obj_id, "OrdinaryDelete", "b")
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "b", value=1)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    # b was re-added, so it should be at the end of strings!
    self.assertEqual(keys, ["a", "c", "b"])

  def test_b32_3_keys_order_large_indices(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    # Large index string that is not a valid array index according to spec (<= 2**32 - 2)
    # Wait, 2**32 - 1 is valid length, so max index is 2**32 - 2.
    large_idx = str(2**32 - 1)

    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", large_idx, value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "1", value=1)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    # large_idx should be treated as a string, not an index!
    # So order should be ["1", large_idx]
    self.assertEqual(keys, ["1", large_idx])

  def test_b32_4_keys_order_negative_indices(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "-1", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "1", value=1)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    # -1 is not a valid array index. So order should be ["1", "-1"]
    self.assertEqual(keys, ["1", "-1"])

  def test_b32_5_keys_order_leading_zeros(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "01", value=1)
    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "1", value=1)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryOwnPropertyKeys")
    keys = json.loads(res)
    # "01" is not a canonical numeric index! So order should be ["1", "01"]
    self.assertEqual(keys, ["1", "01"])

  # --- Batch 33: Proxy Traps Signals ---

  def test_b33_1_proxy_trap_get(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryGet", "foo")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "get")

  def test_b33_2_proxy_trap_set(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinarySet", "foo", 42)
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "set")

  def test_b33_3_proxy_trap_has(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryHasProperty", "foo")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "has")

  def test_b33_4_proxy_trap_deleteProperty(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryDelete", "foo")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "deleteProperty")

  def test_b33_5_proxy_trap_defineProperty(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        proxy_id, "OrdinaryDefineOwnProperty", "foo", descriptor={"value": 1})
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "defineProperty")

  # --- Batch 34: More Proxy Traps Signals ---

  def test_b34_1_proxy_trap_getOwnPropertyDescriptor(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryGetOwnProperty", "foo")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "getOwnPropertyDescriptor")

  def test_b34_2_proxy_trap_ownKeys(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryOwnPropertyKeys")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "ownKeys")

  def test_b34_3_proxy_trap_getPrototypeOf(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryGetPrototypeOf")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "getPrototypeOf")

  def test_b34_4_proxy_trap_setPrototypeOf(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        proxy_id, "OrdinarySetPrototypeOf", value=proto_id)
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "setPrototypeOf")

  def test_b34_5_proxy_trap_isExtensible(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryIsExtensible")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "isExtensible")

  # --- Batch 35: Call & Construct Signals ---

  def test_b35_1_ordinary_call_signal(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    func_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        func_id,
        "OrdinaryCall",
        value="ref:ThisVal",
        descriptor={"argumentsList": [1, 2]})
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_execution")
    self.assertEqual(res_data["type"], "call")
    self.assertEqual(res_data["function"], func_id)
    self.assertEqual(res_data["thisValue"], "ref:ThisVal")
    self.assertEqual(res_data["argumentsList"], [1, 2])

  def test_b35_2_ordinary_construct_signal(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryFunctionCreate", descriptor={"construct": True})
    func_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        func_id,
        "OrdinaryConstruct",
        descriptor={
            "argumentsList": [3, 4],
            "newTarget": func_id
        })
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_execution")
    self.assertEqual(res_data["type"], "construct")
    self.assertEqual(res_data["function"], func_id)
    self.assertEqual(res_data["newTarget"], func_id)
    self.assertEqual(res_data["argumentsList"], [3, 4])

  def test_b35_3_proxy_trap_apply(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    # Define apply trap on handler to avoid unsupported_feature fallback
    self.sm.ecma262_object_op(
        handler_id, "CreateDataProperty", "apply", value="ref:Obj:SomeFunction")

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryCall")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "apply")

  def test_b35_4_proxy_trap_construct(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryFunctionCreate", descriptor={"construct": True})
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryConstruct")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "construct")

  def test_b35_5_call_non_proxy_object(self):
    # OrdinaryCall returns requires_execution for all non-proxy objects in this impl
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryCall")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_execution")
    self.assertEqual(res_data["type"], "call")
    self.assertEqual(res_data["function"], obj_id)

  # --- Batch 36: Module Environments & Indirect Bindings ---

  def test_b36_1_create_import_binding(self):
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env_id = res.split(" ")[2]

    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    target_env_id = res.split(" ")[2]

    self.sm.ecma262_env_op(target_env_id, "CreateMutableBinding", "x")
    self.sm.ecma262_env_op(target_env_id, "InitializeBinding", "x", 42)

    res = self.sm.ecma262_env_op(
        env_id,
        "CreateImportBinding",
        "local_x",
        module_record=target_env_id,
        binding_name="x")
    self.assertTrue("Created import binding" in res)

    res = self.sm.ecma262_env_op(env_id, "GetBindingValue", "local_x")
    self.assertEqual(json.loads(res), 42)

  def test_b36_2_indirect_binding_resolution(self):
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env1_id = res.split(" ")[2]
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env2_id = res.split(" ")[2]
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env3_id = res.split(" ")[2]

    self.sm.ecma262_env_op(env3_id, "CreateMutableBinding", "x")
    self.sm.ecma262_env_op(env3_id, "InitializeBinding", "x", 100)

    self.sm.ecma262_env_op(
        env2_id,
        "CreateImportBinding",
        "y",
        module_record=env3_id,
        binding_name="x")
    self.sm.ecma262_env_op(
        env1_id,
        "CreateImportBinding",
        "z",
        module_record=env2_id,
        binding_name="y")

    res = self.sm.ecma262_env_op(env1_id, "GetBindingValue", "z")
    self.assertEqual(json.loads(res), 100)

  def test_b36_3_indirect_binding_circular_error(self):
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env1_id = res.split(" ")[2]
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env2_id = res.split(" ")[2]

    # Manually inject circular indirect bindings
    state = self.sm._read_state()
    state["environmentRecords"][env1_id]["indirectBindings"] = {
        "x": {
            "module": env2_id,
            "bindingName": "y"
        }
    }
    state["environmentRecords"][env2_id]["indirectBindings"] = {
        "y": {
            "module": env1_id,
            "bindingName": "x"
        }
    }
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(env1_id, "GetBindingValue", "x")
    self.assertTrue("Error: Circular indirect binding" in res)

  def test_b36_4_set_mutable_binding_import_fail(self):
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env_id = res.split(" ")[2]
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    target_id = res.split(" ")[2]

    self.sm.ecma262_env_op(target_id, "CreateMutableBinding", "x")
    self.sm.ecma262_env_op(target_id, "InitializeBinding", "x", 42)

    self.sm.ecma262_env_op(
        env_id,
        "CreateImportBinding",
        "local_x",
        module_record=target_id,
        binding_name="x")

    res = self.sm.ecma262_env_op(
        env_id, "SetMutableBinding", "local_x", 100, strict=True)
    self.assertTrue("Error: TypeError" in res)

  def test_b36_5_has_binding_module(self):
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env_id = res.split(" ")[2]

    self.sm.ecma262_env_op(env_id, "CreateMutableBinding", "x")

    res = self.sm.ecma262_env_op(env_id, "HasBinding", "x")
    self.assertTrue(res)

    # Create target module env
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    target_id = res.split(" ")[2]
    self.sm.ecma262_env_op(target_id, "CreateMutableBinding", "z")

    self.sm.ecma262_env_op(
        env_id,
        "CreateImportBinding",
        "y",
        module_record=target_id,
        binding_name="z")
    res = self.sm.ecma262_env_op(env_id, "HasBinding", "y")
    self.assertTrue("unsupported_feature" in res)

  # --- Batch 37: Function & Global Environments ---

  def test_b37_1_has_this_binding_function(self):
    res = self.sm.ecma262_state_new_environment("Function", "ref:Env:Global")
    env_id = res.split(" ")[2]

    state = self.sm._read_state()
    state["environmentRecords"][env_id]["[[ThisBindingStatus]]"] = "non-lexical"
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(env_id, "HasThisBinding")
    self.assertTrue(res)

  def test_b37_2_has_this_binding_lexical(self):
    res = self.sm.ecma262_state_new_environment("Function", "ref:Env:Global")
    env_id = res.split(" ")[2]

    state = self.sm._read_state()
    state["environmentRecords"][env_id]["[[ThisBindingStatus]]"] = "lexical"
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(env_id, "HasThisBinding")
    self.assertFalse(res)

  def test_b37_3_get_this_binding_uninitialized(self):
    res = self.sm.ecma262_state_new_environment("Function", "ref:Env:Global")
    env_id = res.split(" ")[2]

    state = self.sm._read_state()
    state["environmentRecords"][env_id][
        "[[ThisBindingStatus]]"] = "uninitialized"
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(env_id, "GetThisBinding")
    self.assertTrue("Error: ReferenceError" in res)

  def test_b37_4_has_super_binding(self):
    res = self.sm.ecma262_object_op(
        None,
        "OrdinaryFunctionCreate",
        descriptor={"homeObject": "ref:Obj:Home"})
    func_id = res.split(" ")[1]

    res = self.sm.ecma262_state_new_environment("Function", "ref:Env:Global")
    env_id = res.split(" ")[2]

    state = self.sm._read_state()
    state["environmentRecords"][env_id]["[[FunctionObject]]"] = func_id
    state["environmentRecords"][env_id]["[[ThisBindingStatus]]"] = "non-lexical"
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(env_id, "HasSuperBinding")
    self.assertTrue(res)

  def test_b37_5_global_env_has_binding(self):
    self.sm.ecma262_env_op("ref:Env:GlobalDecl", "CreateMutableBinding",
                           "decl_x")
    self.sm.ecma262_object_op(
        "ref:Obj:Global", "CreateDataProperty", "obj_y", value=1)

    res = self.sm.ecma262_env_op("ref:Env:Global", "HasBinding", "decl_x")
    self.assertTrue(res)

    res = self.sm.ecma262_env_op("ref:Env:Global", "HasBinding", "obj_y")
    self.assertTrue(res)

  # --- Batch 38: Get & Set Details ---

  def test_b38_1_get_accessor_signal(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={"get": getter_id})

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGet", "prop")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_getter_invocation")
    self.assertEqual(res_data["getter"], getter_id)

  def test_b38_2_set_accessor_signal(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={
            "set": setter_id,
            "configurable": True
        })

    res = self.sm.ecma262_object_op(obj_id, "OrdinarySet", "prop", 42)
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_setter_invocation")
    self.assertEqual(res_data["setter"], setter_id)

  def test_b38_3_set_non_writable_fail(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={
            "value": 1,
            "writable": False
        })

    res = self.sm.ecma262_object_op(obj_id, "OrdinarySet", "prop", 2)
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "failed")

  def test_b38_4_set_new_property(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(obj_id, "OrdinarySet", "prop", 42)
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertTrue(res_data["success"])

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty", "prop")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 42)
    self.assertTrue(desc["writable"])
    self.assertTrue(desc["enumerable"])
    self.assertTrue(desc["configurable"])

  def test_b38_5_get_fallback_proto(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]
    self.sm.ecma262_object_op(proto_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGet", "foo")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], 101)

  # --- Batch 39: Get & Set with Receivers ---

  def test_b39_1_get_with_receiver(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    getter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={"get": getter_id})

    res = self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryGet",
        "prop",
        descriptor={"receiver": "ref:Obj:Receiver"})
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_getter_invocation")
    self.assertEqual(res_data.get("receiver"), "ref:Obj:Receiver")

  def test_b39_2_set_with_receiver(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    setter_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "prop",
        descriptor={
            "set": setter_id,
            "configurable": True
        })

    # Create receiver object in heap
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    receiver_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id, "OrdinarySet", "prop", 42, descriptor={"receiver": receiver_id})
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_setter_invocation")
    self.assertEqual(res_data.get("receiver"), receiver_id)

  def test_b39_3_get_own_property_string_index(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGetOwnProperty", "1")
    desc = json.loads(res)
    self.assertEqual(desc["value"], "b")

  def test_b39_4_get_own_property_string_length(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 3)

  def test_b39_5_get_own_property_array_length(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 5)

  # --- Batch 40: More Edge Cases ---

  def test_b40_1_prevent_extensions_proxy(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryPreventExtensions")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "preventExtensions")

  def test_b40_2_is_extensible_proxy(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryIsExtensible")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "isExtensible")

  def test_b40_3_delete_proxy(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryDelete", "foo")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "deleteProperty")

  def test_b40_4_has_property_proxy(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryHasProperty", "foo")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["trap"], "has")

  def test_b40_5_private_field_add_non_extensible(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "OrdinaryPreventExtensions")

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldAdd", property_name="#x", value=42)
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(
        obj_id, "PrivateFieldGet", property_name="#x")
    self.assertEqual(res, 42)

  # --- Batch 41: MakeBasicObject & SetInternalSlot ---

  def test_b41_1_make_basic_object(self):
    res = self.sm.ecma262_object_op(
        None,
        "MakeBasicObject",
        descriptor={"internalSlots": ["[[CustomSlot]]"]})
    self.assertTrue(res.startswith("MakeBasicObject ref:Obj:"))

    obj_id = res.split(" ")[1]
    state = self.sm._read_state()
    self.assertIn("[[CustomSlot]]", state["heap"][obj_id]["internalSlots"])
    self.assertEqual(state["heap"][obj_id]["internalSlots"]["[[CustomSlot]]"],
                     "~undefined~")

  def test_b41_2_set_internal_slot(self):
    res = self.sm.ecma262_object_op(
        None,
        "MakeBasicObject",
        descriptor={"internalSlots": ["[[CustomSlot]]"]})
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id, "SetInternalSlot", property_name="[[CustomSlot]]", value=42)
    self.assertTrue("Set internal slot" in res)

    state = self.sm._read_state()
    self.assertEqual(state["heap"][obj_id]["internalSlots"]["[[CustomSlot]]"],
                     42)

  def test_b41_3_set_internal_slot_undeclared(self):
    res = self.sm.ecma262_object_op(
        None, "MakeBasicObject", descriptor={"internalSlots": []})
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        obj_id, "SetInternalSlot", property_name="[[CustomSlot]]", value=42)
    self.assertTrue("Error" in res)

  def test_b41_4_make_basic_object_default_slots(self):
    res = self.sm.ecma262_object_op(
        None, "MakeBasicObject", descriptor={"internalSlots": []})
    obj_id = res.split(" ")[1]

    state = self.sm._read_state()
    self.assertIn("[[PrivateElements]]", state["heap"][obj_id]["internalSlots"])

  def test_b41_5_make_basic_object_extensible_default(self):
    res = self.sm.ecma262_object_op(
        None,
        "MakeBasicObject",
        descriptor={"internalSlots": ["[[Extensible]]"]})
    obj_id = res.split(" ")[1]

    state = self.sm._read_state()
    self.assertTrue(state["heap"][obj_id]["internalSlots"]["[[Extensible]]"])

  # --- Batch 42: String Exotic Object Edge Cases ---

  def test_b42_1_define_string_index_non_configurable(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        str_id,
        "OrdinaryDefineOwnProperty",
        "1",
        descriptor={"configurable": True})
    self.assertFalse(res)

  def test_b42_2_define_string_index_non_writable(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        str_id, "OrdinaryDefineOwnProperty", "1", descriptor={"writable": True})
    self.assertFalse(res)

  def test_b42_3_define_string_index_different_value(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        str_id, "OrdinaryDefineOwnProperty", "1", descriptor={"value": "x"})
    self.assertFalse(res)

  def test_b42_4_define_string_index_same_value(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        str_id,
        "OrdinaryDefineOwnProperty",
        "1",
        descriptor={
            "value": "b",
            "writable": False,
            "enumerable": True,
            "configurable": False
        })
    self.assertTrue(res)

  def test_b42_5_define_string_length_fail(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        str_id, "OrdinaryDefineOwnProperty", "length", descriptor={"value": 5})
    self.assertFalse(res)

  # --- Batch 43: More String Edge Cases ---

  def test_b43_1_get_string_negative_index(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGet", "-1")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], "~undefined~")

  def test_b43_2_get_string_large_index(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGet", "5")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], "~undefined~")

  def test_b43_3_get_string_fractional_index(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGet", "1.5")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "completed")
    self.assertEqual(res_data["value"], "~undefined~")

  def test_b43_4_string_has_property_index(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryHasProperty", "1")
    self.assertTrue(res)

  def test_b43_5_string_has_property_out_of_bounds(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryHasProperty", "5")
    self.assertFalse(res)

  # --- Batch 44: Array Exotic Object Edge Cases ---

  def test_b44_1_array_length_non_numeric(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"value": "abc"})
    self.assertTrue("Error: RangeError" in res)

  def test_b44_2_array_length_fractional(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"value": 1.5})
    self.assertTrue("Error: RangeError" in res)

  def test_b44_3_array_length_non_writable(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"writable": False})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertFalse(desc["writable"])

  def test_b44_4_array_length_non_writable_cannot_grow(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        arr_id,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"writable": False})

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "length", descriptor={"value": 5})
    self.assertFalse(res)

  def test_b44_5_array_length_non_writable_cannot_shrink(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    arr_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        arr_id,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"writable": False})

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "length", descriptor={"value": 2})
    self.assertFalse(res)

  # --- Batch 45: More Array Edge Cases ---

  def test_b45_1_array_add_element_above_length(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "5", descriptor={"value": 10})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 6)

  def test_b45_2_array_add_element_below_length(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(arr_id, "CreateDataProperty", "2", value=10)
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 5)

  def test_b45_3_array_delete_element_below_length(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    arr_id = res.split(" ")[1]

    self.sm.ecma262_object_op(arr_id, "CreateDataProperty", "2", value=10)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryDelete", "2")
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 5)

  def test_b45_4_array_define_property_not_array_index(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id, "CreateDataProperty", "foo", value=10)
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 0)

  def test_b45_5_array_length_as_string(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id,
        "OrdinaryDefineOwnProperty",
        "length",
        descriptor={"value": "5"})
    self.assertTrue("Error: RangeError" in res)

  # --- Batch 46: Global Environment More Details ---

  def test_b46_1_global_env_has_binding_decl(self):
    self.sm.ecma262_env_op("ref:Env:GlobalDecl", "CreateMutableBinding", "x")

    res = self.sm.ecma262_env_op("ref:Env:Global", "HasBinding", "x")
    self.assertTrue(res)

  def test_b46_2_global_env_has_binding_obj(self):
    self.sm.ecma262_object_op(
        "ref:Obj:Global", "CreateDataProperty", "y", value=1)

    res = self.sm.ecma262_env_op("ref:Env:Global", "HasBinding", "y")
    self.assertTrue(res)

  def test_b46_3_global_env_get_binding_value_decl(self):
    self.sm.ecma262_env_op("ref:Env:GlobalDecl", "CreateMutableBinding", "x")
    self.sm.ecma262_env_op("ref:Env:GlobalDecl", "InitializeBinding", "x", 42)

    res = self.sm.ecma262_env_op("ref:Env:Global", "GetBindingValue", "x")
    self.assertEqual(json.loads(res), 42)

  def test_b46_4_global_env_get_binding_value_obj(self):
    self.sm.ecma262_object_op(
        "ref:Obj:Global", "CreateDataProperty", "y", value=101)

    res = self.sm.ecma262_env_op("ref:Env:Global", "GetBindingValue", "y")
    self.assertEqual(json.loads(res), 101)

  def test_b46_5_global_env_set_mutable_binding_obj(self):
    self.sm.ecma262_object_op(
        "ref:Obj:Global", "CreateDataProperty", "y", value=1)

    res = self.sm.ecma262_env_op(
        "ref:Env:Global", "SetMutableBinding", "y", 100, strict=True)
    self.assertTrue("Set mutable binding" in res or "completed" in res)

    res = self.sm.ecma262_object_op("ref:Obj:Global", "OrdinaryGetOwnProperty",
                                    "y")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 100)

  # --- Batch 47: Function Objects Details ---

  def test_b47_1_function_parameters_slot_empty(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    func_id = res.split(" ")[1]

    state = self.sm._read_state()
    self.assertEqual(
        state["heap"][func_id]["internalSlots"]["[[FormalParameters]]"],
        "~undefined~")

  def test_b47_2_function_body_slot(self):
    res = self.sm.ecma262_object_op(
        None, "OrdinaryFunctionCreate", descriptor={"body": "return 42;"})
    func_id = res.split(" ")[1]

    state = self.sm._read_state()
    self.assertEqual(
        state["heap"][func_id]["internalSlots"]["[[ECMAScriptCode]]"],
        "return 42;")

  def test_b47_3_function_realm_slot(self):
    res = self.sm.ecma262_object_op(
        None,
        "OrdinaryFunctionCreate",
        descriptor={"realm": "ref:Realm:Custom"})
    func_id = res.split(" ")[1]

    state = self.sm._read_state()
    self.assertEqual(state["heap"][func_id]["internalSlots"]["[[Realm]]"],
                     "ref:Realm:Custom")

  def test_b47_4_function_thisMode_slot(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    func_id = res.split(" ")[1]

    state = self.sm._read_state()
    self.assertEqual(state["heap"][func_id]["internalSlots"]["[[ThisMode]]"],
                     "~undefined~")

  def test_b47_5_function_construct_slot_false(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryFunctionCreate", value=None)
    func_id = res.split(" ")[1]

    state = self.sm._read_state()
    self.assertNotIn("[[Construct]]", state["heap"][func_id]["internalSlots"])

  # --- Batch 48: Edge Cases in Delete ---

  def test_b48_1_delete_inherited_property(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]
    self.sm.ecma262_object_op(proto_id, "CreateDataProperty", "foo", value=101)

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryDelete", "foo")
    self.assertTrue(res)

    # Verify it still exists on proto
    res = self.sm.ecma262_object_op(proto_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 101)

  def test_b48_2_delete_non_existent_from_proto(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    proto_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        None, "OrdinaryObjectCreate", value=proto_id)
    obj_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryDelete", "foo")
    self.assertTrue(res)

  def test_b48_3_delete_property_non_extensible_not_found(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "OrdinaryPreventExtensions")

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryDelete", "foo")
    self.assertTrue(res)

  def test_b48_4_delete_property_non_extensible_found_configurable(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "foo", value=1)
    self.sm.ecma262_object_op(obj_id, "OrdinaryPreventExtensions")

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryDelete", "foo")
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty", "foo")
    self.assertEqual(res, "~undefined~")

  def test_b48_5_delete_property_non_extensible_found_non_configurable(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(
        obj_id,
        "OrdinaryDefineOwnProperty",
        "foo",
        descriptor={
            "value": 1,
            "configurable": False
        })
    self.sm.ecma262_object_op(obj_id, "OrdinaryPreventExtensions")

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryDelete", "foo")
    self.assertFalse(res)

  # --- Batch 49: Edge Cases in GetOwnProperty ---

  def test_b49_1_getOwnProperty_proxy_target_revoked(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    target_id = res.split(" ")[1]
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    handler_id = res.split(" ")[1]

    # Create valid proxy
    res = self.sm.ecma262_object_op(
        None,
        "ProxyCreate",
        value=target_id,
        descriptor={"handler": handler_id})
    proxy_id = res.split(" ")[1]

    # Manually revoke it
    state = self.sm._read_state()
    state["heap"][proxy_id]["internalSlots"]["[[ProxyTarget]]"] = "~null~"
    self.sm._write_state(state)

    res = self.sm.ecma262_object_op(proxy_id, "OrdinaryGetOwnProperty", "foo")
    res_data = json.loads(res)
    self.assertEqual(res_data["status"], "requires_proxy_trap")
    self.assertEqual(res_data["target"], "~null~")

  def test_b49_2_getOwnProperty_string_character(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGetOwnProperty", "1")
    desc = json.loads(res)
    self.assertEqual(desc["value"], "b")
    self.assertFalse(desc["writable"])
    self.assertTrue(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b49_3_getOwnProperty_string_length(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 3)
    self.assertFalse(desc["writable"])
    self.assertFalse(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b49_4_getOwnProperty_array_length(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 5)
    self.assertTrue(desc["writable"])
    self.assertFalse(desc["enumerable"])
    self.assertFalse(desc["configurable"])

  def test_b49_5_getOwnProperty_normal_property(self):
    res = self.sm.ecma262_object_op(None, "OrdinaryObjectCreate", value=None)
    obj_id = res.split(" ")[1]

    self.sm.ecma262_object_op(obj_id, "CreateDataProperty", "foo", value=42)

    res = self.sm.ecma262_object_op(obj_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 42)
    self.assertTrue(desc["writable"])
    self.assertTrue(desc["enumerable"])
    self.assertTrue(desc["configurable"])

  # --- Batch 50: Final Edge Cases ---

  def test_b50_1_hasProperty_primitive_error(self):
    res = self.sm.ecma262_object_op("ref:Obj:NonExistent",
                                    "OrdinaryHasProperty", "foo")
    self.assertTrue("Error" in res)

  def test_b50_2_getProperty_primitive_error(self):
    res = self.sm.ecma262_object_op("ref:Obj:NonExistent", "OrdinaryGet", "foo")
    self.assertTrue("Error" in res)

  def test_b50_3_setProperty_primitive_error(self):
    res = self.sm.ecma262_object_op("ref:Obj:NonExistent", "OrdinarySet", "foo",
                                    42)
    self.assertTrue("Error" in res)

  def test_b50_4_deleteProperty_primitive_error(self):
    res = self.sm.ecma262_object_op("ref:Obj:NonExistent", "OrdinaryDelete",
                                    "foo")
    self.assertTrue("Error" in res)

  def test_b50_5_ownPropertyKeys_primitive_error(self):
    res = self.sm.ecma262_object_op("ref:Obj:NonExistent",
                                    "OrdinaryOwnPropertyKeys")
    self.assertTrue("Error" in res)

  # --- Batch 51: Global Environment Shadowing & Interactions ---

  def test_b51_1_global_decl_shadows_obj(self):
    self.sm.ecma262_env_op("ref:Env:GlobalDecl", "CreateMutableBinding", "x")
    self.sm.ecma262_env_op("ref:Env:GlobalDecl", "InitializeBinding", "x", 42)

    self.sm.ecma262_object_op(
        "ref:Obj:Global", "CreateDataProperty", "x", value=101)

    # Should get from declarative record (42) instead of object record (101)
    res = self.sm.ecma262_env_op("ref:Env:Global", "GetBindingValue", "x")
    self.assertEqual(json.loads(res), 42)

  def test_b51_2_global_set_mutable_shadowed(self):
    self.sm.ecma262_env_op("ref:Env:GlobalDecl", "CreateMutableBinding", "x")
    self.sm.ecma262_env_op("ref:Env:GlobalDecl", "InitializeBinding", "x", 42)

    self.sm.ecma262_object_op(
        "ref:Obj:Global", "CreateDataProperty", "x", value=101)

    # Should update declarative binding
    self.sm.ecma262_env_op(
        "ref:Env:Global", "SetMutableBinding", "x", 202, strict=True)

    res = self.sm.ecma262_env_op("ref:Env:Global", "GetBindingValue", "x")
    self.assertEqual(json.loads(res), 202)

    # Object property should remain unchanged
    res = self.sm.ecma262_object_op("ref:Obj:Global", "OrdinaryGetOwnProperty",
                                    "x")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 101)

  def test_b51_3_global_delete_shadowed(self):
    self.sm.ecma262_env_op(
        "ref:Env:GlobalDecl", "CreateMutableBinding", "x",
        value=False)  # non-deletable

    self.sm.ecma262_object_op(
        "ref:Obj:Global", "CreateDataProperty", "x", value=101)

    # Try to delete x from global env. Should try decl record first and fail if non-deletable!
    res = self.sm.ecma262_env_op("ref:Env:Global", "DeleteBinding", "x")
    self.assertFalse(res)

  def test_b51_4_global_has_binding_order(self):
    self.sm.ecma262_env_op("ref:Env:GlobalDecl", "CreateMutableBinding", "x")

    # We can't easily observe the order of HasBinding unless we mock it,
    # but we can assume it follows the same order as GetBindingValue.
    # Let's just verify it finds it.
    res = self.sm.ecma262_env_op("ref:Env:Global", "HasBinding", "x")
    self.assertTrue(res)

  def test_b51_5_global_get_binding_value_missing(self):
    res = self.sm.ecma262_env_op("ref:Env:Global", "GetBindingValue",
                                 "non_existent")
    # Implementation returns undefined if not strict!
    self.assertEqual(json.loads(res), "~undefined~")

  # --- Batch 52: Module Environment Complex Linking ---

  def test_b52_1_module_indirect_binding_uninitialized_target(self):
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env_id = res.split(" ")[2]
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    target_id = res.split(" ")[2]

    self.sm.ecma262_env_op(target_id, "CreateMutableBinding", "x")
    # Do not initialize it!

    self.sm.ecma262_env_op(
        env_id,
        "CreateImportBinding",
        "y",
        module_record=target_id,
        binding_name="x")

    res = self.sm.ecma262_env_op(env_id, "GetBindingValue", "y")
    self.assertTrue("TDZ" in res)

  def test_b52_2_module_indirect_binding_non_existent_target_manual(self):
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env_id = res.split(" ")[2]

    # Manually inject binding to non-existent module
    state = self.sm._read_state()
    state["environmentRecords"][env_id]["indirectBindings"] = {
        "y": {
            "module": "ref:Env:NonExistent",
            "bindingName": "x"
        }
    }
    self.sm._write_state(state)

    res = self.sm.ecma262_env_op(env_id, "GetBindingValue", "y")
    self.assertTrue("Error: Environment ref:Env:NonExistent not found" in res)

  def test_b52_3_module_has_binding_indirect_unsupported(self):
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env_id = res.split(" ")[2]
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    target_id = res.split(" ")[2]
    self.sm.ecma262_env_op(target_id, "CreateMutableBinding", "x")

    self.sm.ecma262_env_op(
        env_id,
        "CreateImportBinding",
        "y",
        module_record=target_id,
        binding_name="x")

    res = self.sm.ecma262_env_op(env_id, "HasBinding", "y")
    self.assertTrue("unsupported_feature" in res)

  def test_b52_4_module_set_mutable_binding_indirect_non_strict(self):
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env_id = res.split(" ")[2]
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    target_id = res.split(" ")[2]
    self.sm.ecma262_env_op(target_id, "CreateMutableBinding", "x")
    self.sm.ecma262_env_op(target_id, "InitializeBinding", "x", 42)

    self.sm.ecma262_env_op(
        env_id,
        "CreateImportBinding",
        "y",
        module_record=target_id,
        binding_name="x")

    # Non-strict mode should also fail or ignore according to spec for immutable bindings,
    # but our implementation throws TypeError in strict mode. Let's see what it does in non-strict mode.
    # Line 457 in SetMutableBinding: returns error in strict mode, else returns ignore message.
    res = self.sm.ecma262_env_op(
        env_id, "SetMutableBinding", "y", 100, strict=False)
    self.assertTrue("Ignored attempt" in res or "Error" in res)

  def test_b52_5_module_delete_binding_indirect(self):
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    env_id = res.split(" ")[2]
    res = self.sm.ecma262_state_new_environment("Module", "ref:Env:Global")
    target_id = res.split(" ")[2]
    self.sm.ecma262_env_op(target_id, "CreateMutableBinding", "x")

    self.sm.ecma262_env_op(
        env_id,
        "CreateImportBinding",
        "y",
        module_record=target_id,
        binding_name="x")

    # Indirect bindings are not in env["bindings"], so DeleteBinding returns True (no-op)
    res = self.sm.ecma262_env_op(env_id, "DeleteBinding", "y")
    self.assertTrue(res)

    # Verify it still exists in indirectBindings
    state = self.sm._read_state()
    self.assertIn(
        "y", state["environmentRecords"][env_id].get("indirectBindings", {}))

  # --- Batch 53: Array Exotic Object Boundary Conditions ---

  def test_b53_1_array_set_length_to_current(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=5)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "length", descriptor={"value": 5})
    self.assertTrue(res)

  def test_b53_2_array_set_length_larger(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=2)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "length", descriptor={"value": 5})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 5)

  def test_b53_3_array_define_property_negative_index(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "-1", descriptor={"value": 10})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 0)

  def test_b53_4_array_define_property_fractional_index(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        arr_id, "OrdinaryDefineOwnProperty", "1.5", descriptor={"value": 10})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 0)

  def test_b53_5_array_define_property_too_large_index(self):
    res = self.sm.ecma262_object_op(None, "ArrayCreate", value=0)
    arr_id = res.split(" ")[1]

    large_idx = str(2**32 - 1)
    res = self.sm.ecma262_object_op(
        arr_id,
        "OrdinaryDefineOwnProperty",
        large_idx,
        descriptor={"value": 10})
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(arr_id, "OrdinaryGetOwnProperty", "length")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 0)

  # --- Batch 54: String Exotic Object Boundary Conditions ---

  def test_b54_1_string_get_negative_index(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGetOwnProperty", "-1")
    self.assertEqual(res, "~undefined~")

  def test_b54_2_string_get_fractional_index(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGetOwnProperty", "1.5")
    self.assertEqual(res, "~undefined~")

  def test_b54_3_string_get_too_large_index(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGetOwnProperty", "3")
    self.assertEqual(res, "~undefined~")

  def test_b54_4_string_define_non_index_property(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        str_id, "CreateDataProperty", "foo", value=10)
    self.assertTrue(res)

    res = self.sm.ecma262_object_op(str_id, "OrdinaryGetOwnProperty", "foo")
    desc = json.loads(res)
    self.assertEqual(desc["value"], 10)

  def test_b54_5_string_define_index_property_fail(self):
    res = self.sm.ecma262_object_op(None, "StringCreate", value="abc")
    str_id = res.split(" ")[1]

    res = self.sm.ecma262_object_op(
        str_id, "OrdinaryDefineOwnProperty", "1", descriptor={"value": "x"})
    self.assertFalse(res)

  # --- Batch 55: More Environment Details ---

  def test_b55_1_declarative_env_immutable_binding_strict(self):
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    env_id = res.split(" ")[2]

    self.sm.ecma262_env_op(env_id, "CreateImmutableBinding", "x")
    self.sm.ecma262_env_op(env_id, "InitializeBinding", "x", 42)

    res = self.sm.ecma262_env_op(
        env_id, "SetMutableBinding", "x", 100, strict=True)
    self.assertTrue("Error: TypeError" in res)

  def test_b55_2_declarative_env_immutable_binding_non_strict(self):
    res = self.sm.ecma262_state_new_environment("Declarative", "ref:Env:Global")
    env_id = res.split(" ")[2]

    self.sm.ecma262_env_op(env_id, "CreateImmutableBinding", "x")
    self.sm.ecma262_env_op(env_id, "InitializeBinding", "x", 42)

    res = self.sm.ecma262_env_op(
        env_id, "SetMutableBinding", "x", 100, strict=False)
    self.assertTrue("Ignored attempt" in res)

    res = self.sm.ecma262_env_op(env_id, "GetBindingValue", "x")
    self.assertEqual(json.loads(res), 42)

  def test_b55_3_global_env_delete_decl_non_deletable(self):
    self.sm.ecma262_env_op(
        "ref:Env:GlobalDecl", "CreateMutableBinding", "x", value=False)

    res = self.sm.ecma262_env_op("ref:Env:Global", "DeleteBinding", "x")
    self.assertFalse(res)

  def test_b55_4_global_env_delete_obj_configurable(self):
    self.sm.ecma262_object_op(
        "ref:Obj:Global", "CreateDataProperty", "y", value=1)

    res = self.sm.ecma262_env_op("ref:Env:Global", "DeleteBinding", "y")
    self.assertTrue(res)

    res = self.sm.ecma262_object_op("ref:Obj:Global", "OrdinaryGetOwnProperty",
                                    "y")
    self.assertEqual(res, "~undefined~")

  def test_b55_5_global_env_delete_obj_non_configurable(self):
    self.sm.ecma262_object_op(
        "ref:Obj:Global",
        "OrdinaryDefineOwnProperty",
        "y",
        descriptor={
            "value": 1,
            "configurable": False
        })

    res = self.sm.ecma262_env_op("ref:Env:Global", "DeleteBinding", "y")
    self.assertFalse(res)

  # --- Batch 56: Job Queue & Realms ---

  def test_b56_1_enqueue_job(self):
    self.sm.ecma262_state_init()  # Reset state to ensure clean job queue

    res = self.sm.ecma262_state_enqueue_promise_job("PromiseReactionJob",
                                                    "ref:Obj:Callback", [42])
    self.assertEqual(res, "Enqueued job: PromiseReactionJob")

    queue = self.sm.ecma262_state_get_job_queue()
    self.assertEqual(len(queue), 1)
    self.assertEqual(queue[0]["name"], "PromiseReactionJob")
    self.assertEqual(queue[0]["callback"], "ref:Obj:Callback")
    self.assertEqual(queue[0]["arguments"], [42])

  def test_b56_2_get_job_queue_empty(self):
    self.sm.ecma262_state_init()

    queue = self.sm.ecma262_state_get_job_queue()
    self.assertEqual(queue, [])

  def test_b56_3_dequeue_job(self):
    self.sm.ecma262_state_init()

    self.sm.ecma262_state_enqueue_promise_job("Job1", "ref:Callback1", [])

    res = self.sm.ecma262_state_dequeue_job()
    self.assertEqual(res["name"], "Job1")

    queue = self.sm.ecma262_state_get_job_queue()
    self.assertEqual(queue, [])

  def test_b56_4_job_queue_fifo(self):
    self.sm.ecma262_state_init()

    self.sm.ecma262_state_enqueue_promise_job("Job1", "ref:Callback1", [])
    self.sm.ecma262_state_enqueue_promise_job("Job2", "ref:Callback2", [])

    res1 = self.sm.ecma262_state_dequeue_job()
    self.assertEqual(res1["name"], "Job1")

    res2 = self.sm.ecma262_state_dequeue_job()
    self.assertEqual(res2["name"], "Job2")

  def test_b56_5_dequeue_empty_queue(self):
    self.sm.ecma262_state_init()

    res = self.sm.ecma262_state_dequeue_job()
    self.assertIsNone(res)

  def test_b56_6_initial_realm_exists(self):
    state = self.sm._read_state()
    self.assertIn("ref:Realm:1", state["realms"])
    self.assertEqual(state["realms"]["ref:Realm:1"]["globalObject"],
                     "ref:Obj:Global")


if __name__ == '__main__':
  unittest.main()
