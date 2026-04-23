# ECMA-262 State Machine Simulation MCP Server

This MCP server provides tools for simulating the ECMAScript abstract machine state.

## Tools

*   `init`: Initializes the state.
*   `push_context`: Pushes a new execution context.
*   `pop_context`: Pops the top execution context.
*   `update_context`: Updates a field in the running context.
*   `new_environment`: Creates a new environment record.
*   `set_binding`: Sets a binding in an environment record.
*   `env_op`: Performs operations on Environment Records.
*   `object_op`: Performs operations on the Heap / Object Model.
*   `enqueue_promise_job`: Enqueues a job in the Promise Job Queue.
*   `get_job_queue`: Returns the current list of pending jobs.
*   `dequeue_job`: Removes and returns the first job from the queue.
*   `get_history`: Returns the history of the state.

## Setup

The server stores state files in a subdirectory named `ecma262_states` relative to the server script.
