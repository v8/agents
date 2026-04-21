# ECMA-262 State Machine Simulation MCP Server

This MCP server provides tools for simulating the ECMAScript abstract machine state.

## Tools

*   `ecma262_state_machine_init`: Initializes the state.
*   `ecma262_state_machine_push_context`: Pushes a new execution context.
*   `ecma262_state_machine_pop_context`: Pops the top execution context.
*   `ecma262_state_machine_update_context`: Updates a field in the running context.
*   `ecma262_state_machine_new_environment`: Creates a new environment record.
*   `ecma262_state_machine_set_binding`: Sets a binding in an environment record.
*   `ecma262_state_machine_env_op`: Performs operations on Environment Records.
*   `ecma262_state_machine_object_op`: Performs operations on the Heap / Object Model.
*   `ecma262_state_machine_enqueue_promise_job`: Enqueues a job in the Promise Job Queue.
*   `ecma262_state_machine_get_job_queue`: Returns the current list of pending jobs.
*   `ecma262_state_machine_dequeue_job`: Removes and returns the first job from the queue.
*   `ecma262_state_machine_get_history`: Returns the history of the state.

## Setup

The server stores state files in a subdirectory named `ecma262_states` relative to the server script.
