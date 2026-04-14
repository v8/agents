# Prompt Evaluation

This directory is intended for running prompt evaluation tests on the V8 code
base using extensions under `extensions/`.

Currently, the testing infrastructure is not fully implemented in this
repository.

## Adding Tests

Test configurations should use [promptfoo](https://www.promptfoo.dev/). Each
independent test case should have its own promptfoo yaml config file.

Config files should be placed in a subdirectory of the relevant extension
directory.
