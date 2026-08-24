---
# TODO:
# Provide name as unit-converter;
# Provide description: Write when the agent should activate this skill. Cover: what unit categories it handles and what user actions trigger it.
# License is Apache-2.0
# Metadata: 
#    - Author is ai-powered-apps-development-expert
#    - version is 1.0
# And allowed tools is execute_code
name: unit-converter
description: >
  Converts numeric values between units of measurement — length, weight, volume, area, speed,
  time, data, pressure, energy, and temperature. Use this skill whenever the user asks to
  convert, translate, or find the equivalent of a measurement in different units (e.g. "convert
  100 km to miles," "how many MB is 1.5 TB?," "98.6°F in Celsius").
license: Apache-2.0
metadata:
  author: ai-powered-apps-development-expert
  version: "1.0"
allowed-tools: execute_code
---

# Unit Converter

<!--
TODO: Fill in the workflow for the agent. The script is at scripts/convert.py.
See references/how-code-execution-works.md to understand how execute_code works.
See examples.md for invocation examples and supported units.

## Workflow

### Step 1: Load the script (first call, session_id = "")
Call execute_code with script_path, the conversion code, and session_id = "".
Save the returned session_id for reuse.

### Step 2: Write the conversion call
Pass as code: call convert_units(value, from_unit, to_unit) and print Category, Input, Result.

### Step 3: Return output
Return the printed output as-is.

### Step 4: Reuse session
On follow-up conversions skip Step 1 — pass only code + saved session_id.

### Step 5: Error handling
Unknown unit / incompatible categories: report the error and list supported units from examples.md.
Invalid number: ask to clarify. Expired session: silently restart from Step 1.
-->

## Workflow

### Step 1: Load the script (first call, session_id = "")

Call `execute_code` with:
- `script_path`: `/unit-converter/scripts/convert.py` — the tool reads this file and prepends its
  content to `code` before execution, so the functions below become available
- `code`: the conversion call for this request (see Step 2)
- `session_id`: `""`

Save the `session_id` returned in `session_info` — you'll reuse it for every later conversion in
this conversation.

### Step 2: Write the conversion call

Map the user's request to `value`, `from_unit`, `to_unit` (see examples.md for the mapping
pattern and the exact unit spellings to use). Append this to the executed code:

```python
result, category = convert_units(value, from_unit, to_unit)
print(f"Category: {category}")
print(f"Input:    {value} {from_unit}")
print(f"Result:   {fmt(result)} {to_unit}")
```

### Step 3: Return output

Return the printed output as-is — don't reformat or recompute the numbers yourself.

### Step 4: Reuse session

On follow-up conversions in the same conversation, skip Step 1 (the functions already live in
the kernel). Call `execute_code` with only the Step 2 code and the saved `session_id`.

### Step 5: Error handling

- **Unknown unit / incompatible categories**: `convert_units` raises `ValueError`, which comes
  back as `error` in the tool result. Report that error message to the user and list the
  supported units for the relevant category from examples.md.
- **Invalid number**: if the user's value isn't a clear number, ask them to clarify before
  calling the tool.
- **Expired session** (`SessionExpiredError`): silently restart from Step 1 — reload the script
  with a fresh `session_id` and retry the same conversion — don't surface this as an error to
  the user.