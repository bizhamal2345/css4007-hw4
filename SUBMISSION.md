# HW4 — submission

**AI assistance:** I used ChatGPT to help plan, implement, debug and explain the assignment. This workspace reconstructs an earlier attempt whose local Colab files and Git history were lost. The reconstructed plan will be committed before recreating the implementation files here. Experimental results will be generated anew.

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

| # | Step | What goes in (types) | What comes out (types) | When it goes wrong | Tool, loop, or model? |
|---|---|---|---|---|---|
| 1 | Understand the question | question: str | districts: list[str], fields: list[str], plan: str | Ask for clarification or mark unanswered if the question is unclear | Model |
| 2 | Validate a tool request | tool name: str, arguments: JSON string | validated arguments: dict or error: dict | Reject invalid JSON, unknown tools, wrong types, missing or extra fields | Loop |
| 3 | Retrieve a fact | district: str, field: str | value, unit, period and source IDs in a dict | Return explicit errors for unknown names, missing facts, unreadable numbers or unknown units | lookup tool |
| 4 | Construct a formula | facts: list[dict], plan: str | arithmetic expression: str | Obtain missing facts; do not guess numbers or conversions | Model |
| 5 | Calculate | expression: str | numeric result or error in a dict | Reject unsafe syntax, division by zero and excessive size or magnitude | calculate tool |
| 6 | Compare and answer | results: list[float], question: str | final answer: str | Mark unanswered if no valid answer is obtained within the round limit | Model; loop enforces limit |

**How the steps connect:**

Question -> model plan -> validated lookup requests -> facts with sources
-> model formula -> validated calculate request -> numeric result
-> comparison -> final answer.
Lookup and calculation steps may repeat when more facts or calculations are needed.

**What I am assuming:**

- Use 2025 population unless the question asks for 2020 or a projection.
- Budgets and household water use refer to 2025; pupils and schools use 2025/26.
- Ignore archived profiles NR-13 and NR-14.
- Corrections override profiles: Brightwater's area is 921.4 km2 according to NR-16.
- Match district names exactly, ignoring case and surrounding spaces.
- Suggest similar names for misspellings, but never silently choose one.
- Lookup returns water in cubic metres: 1 megalitre = 1000 cubic metres.
- Budgets remain in million tenge; calculations must include required conversions.
- Use 365 days for 2025 and 1000 litres per cubic metre.
- Use the 2025 tariff of 142.35 tenge per cubic metre.
- Preserve intermediate precision and round only the final result.
- Reference answers, values and source lists in questions.json are for evaluation only.
- The model never receives reference answers.
- The most sensitive assumption is authoritative source selection:
  correct arithmetic on an archived or uncorrected number still gives a wrong answer.

### A2 — The two tools

#### `lookup`

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Retrieve one authoritative fact about a Nine Rivers district. Use exact district names, ignoring case and surrounding spaces. Exclude archived profiles and apply correction notices. Return value, unit, period and source document IDs, not whole documents. Water is normalised to cubic metres; budgets remain in million tenge. Use district='REGION', field='water_tariff_2025' for the regional tariff.",
    "parameters": {
      "type": "object",
      "properties": {
        "district": {
          "type": "string",
          "description": "Exact district name, or REGION for the tariff.",
          "minLength": 1,
          "maxLength": 80
        },
        "field": {
          "type": "string",
          "enum": [
            "population_2025",
            "population_2020",
            "area_km2",
            "budget_million_tenge",
            "water_m3",
            "schools",
            "pupils",
            "road_km",
            "founded",
            "water_tariff_2025"
          ]
        }
      },
      "required": [
        "district",
        "field"
      ],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| Success | {"ok": true, "district": "Brightwater", "field": "area_km2", "value": 921.4, "unit": "km2", "period": "2025", "sources": ["NR-05", "NR-16"]} |
| Invalid inputs or unsupported field | INVALID_ARGUMENTS |
| Unknown or misspelled district | UNKNOWN_DISTRICT with suggestions; never silently choose one |
| Multiple current profiles matching the name | AMBIGUOUS_DISTRICT |
| Archived profile | Use the current profile; return NO_CURRENT_PROFILE if none exists |
| Wrong district-field combination | INVALID_FIELD_FOR_DISTRICT; the tariff field requires REGION |
| Missing fact or unreadable number | MISSING_FACT or INVALID_NUMBER |
| Unknown unit | UNKNOWN_UNIT |
| Missing or malformed corpus | DATA_ERROR |
| Unexpected failure | INTERNAL_ERROR without exposing secrets or internal paths |

Errors use {"ok": false, "error": {"code": "...", "message": "..."}}.
UNKNOWN_DISTRICT may include suggestions inside the error object.
Success returns one fact. Counts are integers; other values may be floats.
Population periods are 2020 or 2025. Schools and pupils use 2025/26.
Budget, water, tariff, area and road use 2025; founded uses historical.
Water conversions cite NR-15. Corrections cite the profile and correction notice.
Only the fixed corpus file is read; arguments cannot choose a file path.

**Worst thing it could do with strange or dangerous input:**

The main risk is returning the wrong district or an old or uncorrected value.
Exact matching, source IDs and correction precedence reduce this risk.
The tool does not execute input or access user-selected files.
Parsing mistakes remain possible and must be tested.

#### `calculate`

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Evaluate arithmetic using numbers, parentheses, +, -, *, / and unary + or -. Use this tool for calculations. Names, function calls, attributes, powers and other operators are forbidden. Return a numeric result without rounding, or a structured error.",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "Numbers and allowed arithmetic operators only.",
          "minLength": 1,
          "maxLength": 200
        }
      },
      "required": [
        "expression"
      ],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| Success | {"ok": true, "result": 7.0} for expression 3 + 4 |
| Empty, non-string or overlong input | INVALID_ARGUMENTS |
| Invalid syntax | INVALID_EXPRESSION |
| Names, calls, attributes, powers, strings, booleans or unsupported operators | UNSAFE_EXPRESSION |
| Division by zero | DIVISION_BY_ZERO |
| Excessive AST size or depth | EXPRESSION_TOO_COMPLEX |
| Non-finite or excessively large numbers | NUMBER_OUT_OF_RANGE |
| Unexpected failure | INTERNAL_ERROR |

Errors use the same envelope as lookup.
Limits: 200 input characters, 100 AST nodes and 20 levels of nesting.
The root Expression node is level 1.
Every numeric literal and intermediate result must be finite
and have absolute value at most 1e15. Zero is allowed.
Validate the entire AST before performing arithmetic.
Evaluate only explicitly allowed nodes; never use eval or exec.
Return floating-point results without final rounding.
The model handles unit conversions; calculate does not understand units.

**Worst thing it could do with strange or dangerous input:**

An unrestricted evaluator could execute commands or exhaust resources.
An AST allowlist and size limits block those operations.
Reject __import__('os').system('echo hi'), (1).__class__ and 9**9**9.
A permitted but incorrect formula can still produce the wrong answer.
The calculator cannot detect a wrong choice of facts or units.

### A3 — Q-09 by hand

This is a reconstructed illustrative conversation, not a new API run.
The arithmetic and example were checked during the earlier attempt.

```json
[
  {
    "role": "user",
    "content": "Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?"
  },
  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {
        "id": "call_1",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Brightwater\", \"field\": \"population_2025\"}"
        }
      },
      {
        "id": "call_2",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Brightwater\", \"field\": \"area_km2\"}"
        }
      },
      {
        "id": "call_3",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Millbrook\", \"field\": \"population_2025\"}"
        }
      },
      {
        "id": "call_4",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Millbrook\", \"field\": \"area_km2\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_1",
    "content": "{\"ok\": true, \"district\": \"Brightwater\", \"field\": \"population_2025\", \"value\": 44675, \"unit\": \"residents\", \"period\": \"2025\", \"sources\": [\"NR-05\"]}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_2",
    "content": "{\"ok\": true, \"district\": \"Brightwater\", \"field\": \"area_km2\", \"value\": 921.4, \"unit\": \"km2\", \"period\": \"2025\", \"sources\": [\"NR-05\", \"NR-16\"]}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_3",
    "content": "{\"ok\": true, \"district\": \"Millbrook\", \"field\": \"population_2025\", \"value\": 37203, \"unit\": \"residents\", \"period\": \"2025\", \"sources\": [\"NR-11\"]}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_4",
    "content": "{\"ok\": true, \"district\": \"Millbrook\", \"field\": \"area_km2\", \"value\": 758.6, \"unit\": \"km2\", \"period\": \"2025\", \"sources\": [\"NR-11\"]}"
  },
  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {
        "id": "call_5",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\": \"37203 / 758.6 - 44675 / 921.4\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_5",
    "content": "{\"ok\": true, \"result\": 0.5556561156405735}"
  },
  {
    "role": "assistant",
    "content": "Millbrook has the higher population density. The difference rounds to 0.6 residents per square kilometre.\nANSWER: Millbrook | 0.6"
  }
]
```

**My arithmetic:**

- Brightwater population: 44,675, from NR-05.
- Brightwater corrected area: 921.4 km2, from NR-16.
- Millbrook population: 37,203; area: 758.6 km2, from NR-11.
- Brightwater density = 44,675 / 921.4 ≈ 48.485999565878.
- Millbrook density = 37,203 / 758.6 ≈ 49.041655681519.
- Difference = (37,203 / 758.6) - (44,675 / 921.4)
  ≈ 0.555656115641 residents/km2.
- The difference is positive: Millbrook is denser.
- Round only the final difference to one decimal place: 0.6.

Every tool result includes the matching tool_call_id.
Tool arguments are JSON strings that the loop must parse and validate.

### A4 — Why I split it this way

An alternative is one large answer_question tool that retrieves facts,
chooses formulas, calculates and returns the answer.
It could reduce tool calls, but it would mix several responsibilities.

I chose two tools so that retrieval and arithmetic can be tested separately.
Lookup handles authoritative sources, archived profiles, corrections and units.
Calculate handles arithmetic and rejects unsafe expressions.
The model chooses the required facts and formulas.
The loop validates requests, returns results and limits the number of rounds.

This makes mistakes easier to locate: a wrong fact, a wrong formula
and a wrong calculation are different failures.
The trade-off is potentially more calls, tokens and time.
The new experiments will measure whether the benefit justifies that cost.

---

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

<!-- what changed in your plan, and why. "None" is an answer too. -->

### B2 — Tests

Command: `python -m pytest tests/test_tools.py -v --color=no`

```text
============================= test session starts ==============================
platform linux -- Python 3.13.16, pytest-8.4.2, pluggy-1.7.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /content/HW4
plugins: langsmith-0.14.11, typeguard-4.6.0, platformdirs-4.13.4, anyio-4.15.1
collecting ... collected 27 items

tests/test_tools.py::test_calculate_multiplication PASSED                [  3%]
tests/test_tools.py::test_calculate_parentheses PASSED                   [  7%]
tests/test_tools.py::test_calculate_negative_number PASSED               [ 11%]
tests/test_tools.py::test_calculate_division_by_zero PASSED              [ 14%]
tests/test_tools.py::test_calculate_rejects_unsafe_input[__import__('os').system('echo hi')] PASSED [ 18%]
tests/test_tools.py::test_calculate_rejects_unsafe_input[(1).__class__] PASSED [ 22%]
tests/test_tools.py::test_calculate_rejects_unsafe_input[9**9**9] PASSED [ 25%]
tests/test_tools.py::test_calculate_rejects_unsafe_input[True + 1] PASSED [ 29%]
tests/test_tools.py::test_calculate_number_limit[1e16] PASSED            [ 33%]
tests/test_tools.py::test_calculate_number_limit[1000000000 * 1000000000] PASSED [ 37%]
tests/test_tools.py::test_calculate_invalid_syntax PASSED                [ 40%]
tests/test_tools.py::test_calculate_invalid_argument[] PASSED            [ 44%]
tests/test_tools.py::test_calculate_invalid_argument[                                                                                                                                                                                                         ] PASSED [ 48%]
tests/test_tools.py::test_calculate_invalid_argument[None] PASSED        [ 51%]
tests/test_tools.py::test_calculate_depth_limit PASSED                   [ 55%]
tests/test_tools.py::test_lookup_current_population PASSED               [ 59%]
tests/test_tools.py::test_lookup_similar_names PASSED                    [ 62%]
tests/test_tools.py::test_lookup_misspelling PASSED                      [ 66%]
tests/test_tools.py::test_lookup_ignores_archived_profiles[Tarnvale-71388-NR-03] PASSED [ 70%]
tests/test_tools.py::test_lookup_ignores_archived_profiles[Kelmarsh-24117-NR-04] PASSED [ 74%]
tests/test_tools.py::test_lookup_correction PASSED                       [ 77%]
tests/test_tools.py::test_lookup_water_units PASSED                      [ 81%]
tests/test_tools.py::test_lookup_tariff PASSED                           [ 85%]
tests/test_tools.py::test_lookup_name_normalisation PASSED               [ 88%]
tests/test_tools.py::test_lookup_invalid_field PASSED                    [ 92%]
tests/test_tools.py::test_lookup_missing_corpus PASSED                   [ 96%]
tests/test_tools.py::test_lookup_only_archived_profile PASSED            [100%]

============================== 27 passed in 0.09s ==============================
```

### B3 — The loop

- Round limit: 12 model calls per question. This allows several rounds
  of fact retrieval, calculations and error recovery, while bounding
  the number of model calls. Reaching the limit is recorded as unanswered.
- Logs: `outputs/pilot/` for pilots. The new Q-09 log is
  `outputs/pilot/S3_Q-09_20261021T015809166119Z.json`. It records model responses, tool arguments,
  tool results, conversation messages, token usage and timing.
- Real Q-09 compared with A3: my manual plan used four lookup calls
  and one calculate call. The model used four lookup calls and three
  calculate calls: two densities separately, then their difference.
  It used the corrected Brightwater area of 921.4 km2, citing NR-16.
  The final difference was 0.5556561156405735 residents per km2,
  which rounds to 0.6. The answer was Millbrook.
- This new pilot used 4 successful API calls and
  7 tool calls, with 3786 input
  tokens and 229 output tokens.
  Total elapsed time: 11.77 seconds.
- Configuration: `reasoning_effort="none"`, temperature 1.0 and
  max_completion_tokens 4096. The reasoning setting accounts for
  the tools compatibility error observed in the earlier lost attempt.

### B4 — Three strategies

<!-- PREDECLARED_EVALUATION_RULES -->

**Rules fixed before the new full experiments**

All three strategies use gpt-5.6-luna, temperature 1.0,
reasoning_effort="none" and max_completion_tokens=4096.
They use the same 20 question texts and final-answer format.
The complete experiment is run twice.

S1 receives the full corpus and requests a direct answer in one call.
S2 receives the same corpus and requests step-by-step calculations
in five independent calls (k=5), followed by local voting.
S3 receives no corpus in its prompt and uses lookup and calculate,
with a limit of 12 model calls per question.

**Scoring**

Only the last non-empty line is parsed:
`ANSWER: <name or yes/no> | <number>`.

The name must match the reference exactly after trimming surrounding
spaces. Yes/no answers must use lowercase. The number must be finite.
Units, commas used as thousands separators, and ellipses are not
allowed on the final line.

Both the predicted and reference numbers are rounded to the question's
specified decimal places using Decimal and ROUND_HALF_UP.
An answer is correct when the name matches and the absolute difference
between these rounded numbers is at most 10**(-decimals), inclusive.
Thus, for decimals=1, the tolerance is 0.1.

A missing or invalid final answer is counted as unanswered and incorrect.
A valid but wrong answer is incorrect, but not unanswered.
API errors are reported separately and must be resolved before calling
an experimental run complete; they are not silently discarded.

**S2 voting**

Each valid sample votes for a pair:
(exact trimmed name, number rounded to the specified decimal places).
The most frequent pair wins. If pairs tie, the pair whose first vote
appeared earliest wins. Invalid samples do not vote. If there are no
valid votes, S2 is unanswered. All five calls count towards usage,
time and cost, including samples with invalid answers.

Reference answers, reference values and reference source IDs are never
passed to the model. Decimal precision is used locally for scoring
and voting.

**Measurements**

Count usage across every successful model call, including all S2
samples and all S3 rounds. Record calls without usage explicitly.
Report median elapsed time per question and summed elapsed time per
strategy. Calculate cost from recorded usage and explicitly documented
input/output prices; do not invent missing prices.

<!-- END_PREDECLARED_EVALUATION_RULES -->


**What I kept the same:**

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 3/20 | 0 | 46600 | 318 | 1.16 | 24.35 | pending |
| 1 | S2 think and vote (k = 5) | 14/20 | 0 | 233700 | 18533 | 11.77 | 224.63 | pending |
| 1 | S3 tools | 19/20 | 0 | 59597 | 4088 | 4.35 | 92.06 | pending |
| 2 | S1 direct | 3/20 | 2 | 46600 | 308 | 1.13 | 23.05 | pending |
| 2 | S2 think and vote (k = 5) | 15/20 | 0 | 233700 | 18419 | 11.93 | 227.25 | pending |
| 2 | S3 tools | 18/20 | 1 | 61851 | 4001 | 4.23 | 86.75 | pending |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | Wrong | Correct | Correct |
| Q-02 | Wrong | Correct | Correct |
| Q-03 | Wrong | Correct | Correct |
| Q-04 | Wrong | Correct | Correct |
| Q-05 | Wrong | Wrong | Correct |
| Q-06 | Correct | Correct | Correct |
| Q-07 | Wrong | Correct | Correct |
| Q-08 | Wrong | Correct | Correct |
| Q-09 | Wrong | Correct | Correct |
| Q-10 | Correct | Correct | Correct |
| Q-11 | Wrong | Correct | Wrong |
| Q-12 | Wrong | Wrong | Correct |
| Q-13 | Wrong | Correct | Correct |
| Q-14 | Wrong | Wrong | Correct |
| Q-15 | Wrong | Wrong | Correct |
| Q-16 | Correct | Correct | Correct |
| Q-17 | Wrong | Wrong | Correct |
| Q-18 | Wrong | Correct | Correct |
| Q-19 | Wrong | Correct | Correct |
| Q-20 | Wrong | Wrong | Correct |

---

U = unanswered; Wrong = a valid but incorrect answer. Both count as incorrect in the accuracy total.
Times and token counts cover the full experiments only; pilots and the description comparison are excluded. Dollar costs are pending documented model prices.

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

I compared the original S3 results from run 1 with new calls for
Q-01, Q-02, Q-03, Q-08 and Q-09. I changed only the lookup description
to `Looks things up.` The parameter schema, calculate description,
system prompt, model settings and round limit stayed the same.

The Calls columns below count tool calls, not model API calls.

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| Q-01 | 5 | 7 | Ossbridge: 4.57015387231975 | Ossbridge: 4.57015387231975 |
| Q-02 | 5 | 7 | Harrowfield: 1.687459381672536 | Harrowfield: 1.6874593816725367 |
| Q-03 | 7 | 7 | Lindenmoor: 5.34015866513721 | Lindenmoor: 5.34015866513721 |
| Q-08 | 6 | 4 | Brightwater: 72.45615 | Brightwater: 72.45615 |
| Q-09 | 7 | 7 | Millbrook: 0.5556561156405735 | Millbrook: 0.5556561156405735 |

Both versions answered 5/5 and 5/5 correctly,
respectively. The original description required 18 API calls
and 30 tool calls; the vague description required
19 API calls and 32 tool calls.

In this small comparison, the vague description did not reduce accuracy.
It used slightly more calls overall, but not on every question.
The unchanged parameter schema still supplied field names and argument
structure. These five questions and one sample per condition are not
enough to isolate the description's effect from generation variability
at temperature 1.0.

Logs: `outputs/vague/`. Comparison: `outputs/vague/comparison.json`.

### C2 — Three mistakes explained

#### S1: wrong district and value — Q-09, run 1

Log: `outputs/run_1/S1_Q-09.json`.

Actual response:

> ANSWER: Brightwater | 2.8018476351456355

The correct answer is Millbrook. Using the corrected Brightwater area, `37203 / 758.6 - 44675 / 921.4 = 0.5556561156405735`, which rounds to 0.6 residents per km2. Both the predicted name and value are wrong.

S1 provides no intermediate work. The log does not establish whether the model ignored the correction, selected wrong facts or calculated incorrectly. The exact cause cannot be identified from this output alone.

A possible improvement is to retrieve authoritative facts and use a calculator. This would change the strategy and should be tested separately.

#### S2: arithmetic errors and a five-way tie — Q-12, run 1

Log: `outputs/run_1/S2_Q-12.json`.

Sample 1 ended with:

> ANSWER: Tarnvale | 63.077488774

All five samples selected the correct district, used the correct budget and pupil counts, and stated the correct unit conversion. However, their divisions were inaccurate.

The correct expression is `12960.3 * 1000 / 10652 - 16021.7 * 1000 / 13904`. It gives approximately 64.39240085007577 thousand tenge per pupil, which rounds to 64.4.

The rounded predictions were 63.1, 63.7, 63.9, 63.4 and 64.0. Each received one vote. The predeclared tie rule selected the earliest pair, `Tarnvale | 63.1`. There was no numeric majority, and none of the five predictions met the scoring tolerance.

Voting cannot reliably repair arithmetic when all samples make errors. Calculator verification could help. Abstaining on ties is another option, but would increase unanswered results. These changes would require a new experiment.

#### S3: wrong maximum selected — Q-11, run 1

Log: `outputs/run_1/S3_Q-11.json`.

The tools returned Redfen = 314.7, Ashgrove = 368.2083333333333 and Millbrook = 370.8 pupils per school.

The model requested this calculation:

`{"expression": "(8837/24)-(3147/10)"}`

The calculator correctly returned 53.508333333333326 for that expression. But Millbrook, not Ashgrove, has the highest ratio. The required difference is `5562 / 15 - 3147 / 10 = 56.1`.

The model correctly identified Redfen as the lowest but chose the wrong maximum. This is a comparison/planning error, not a lookup or calculator error.

An explicit comparison of all candidates before selecting the minimum and maximum could help. A future structured comparison tool could perform this selection deterministically.

These observations do not change the original logs, scoring rules or reported experimental results.

### C3 — Which strategy I would use, and what would change it

For this numerical question-answering task, I would choose S3. Across two runs it answered 37/40 correctly (92.5%), compared with S2 at 29/40 (72.5%) and S1 at 6/40 (15%). These are repeated attempts on the same 20 questions, not 40 different questions.

S3 took approximately 178.81 seconds in total across both runs. S2 took 451.88 seconds and S1 took 47.40 seconds. S3 therefore offered the best observed accuracy and was faster than S2, although S1 was the fastest.

S3 used 121448 input tokens and 8089 output tokens across both runs. S2 used 467400 input tokens and 36952 output tokens; S1 used 93200 input tokens and 626 output tokens. Under the same positive input/output token prices, S3 has a lower nominal token cost than S2 and a higher one than S1. Dollar estimates require documented prices and do not by themselves establish the actual billed amount.

The logs make S3 errors easier to inspect: retrieved facts, source IDs, expressions and calculator results are visible. However, S3 still made planning, unit-conversion and final-format errors. Tools do not guarantee a correct answer.

Scenario 1: if latency and cost dominated, questions were simple fact lookups, and errors had low consequences, I would consider S1 after testing it on that simpler workload. Its accuracy in this experiment is too low for the present numerical task.

Scenario 2: if tools were unavailable and questions required qualitative judgments rather than precise arithmetic, I would consider S2 if the budget allowed five calls. Agreement would still need validation because repeated samples can share errors.

### C4 — How sure I can be

S1 scored 3/20 in both runs, but unanswered results increased from 0 to 2. Its correct/incorrect/unanswered outcome changed on Q-05 and Q-18 even though total accuracy stayed the same.

S2 changed from 14/20 to 15/20, with no unanswered results. Its outcomes changed on Q-14, Q-15 and Q-18. S3 changed from 19/20 to 18/20, with unanswered results increasing from 0 to 1. Its outcomes changed on Q-11, Q-12 and Q-14.

The ranking S3 > S2 > S1 held in both runs. This supports choosing S3 for this dataset and configuration, but two runs cannot establish a reliable probability of success on new tasks.

There are only 20 distinct questions from one small fictional corpus. Questions share documents and operations, so outcomes are not independent. The second run repeats the same questions and does not double the number of distinct test cases.

We tested one model with temperature 1.0 and one prompt design per strategy. S2 samples can share systematic arithmetic errors. The lookup implementation is specialised to the supplied corpus; performance on other formats or larger datasets is unknown.

Measured accuracy also depends on the declared tolerance and strict answer parser. For example, S3 run 2 Q-12 contained the right district and number but lacked the ANSWER prefix and was therefore counted as unanswered. The scoring rules were not changed after observing this failure.

Elapsed time can vary with network and service conditions. Runs were sequential rather than randomised, and the five-question description comparison is too small to establish causality.

A stronger study would use more independent questions, additional runs and models, varied corpora, randomised execution order, and separate reporting of factual, arithmetic, planning and format errors. Any prompt or tool improvements should be evaluated on held-out questions.


The accuracy gap between S3 and S2 was 5 questions in run 1 and 3 questions in run 2, larger than either strategy's one-question change in total accuracy between runs. This is encouraging but does not establish statistical significance.

There is no universal sample size that guarantees trust. As a next study, I would start with at least 200 distinct, held-out questions covering different operations and document formats, repeat the runs, and assess uncertainty in paired strategy differences before deciding whether more questions are needed.

### Final questions

1. The model has generated a request containing tool names and arguments; it has not executed our Python functions. Our application validates the request, runs the allowed function and returns its result with the corresponding tool_call_id.

2. Arguments arrive as a string because the API represents the generated function arguments as serialized JSON. Passing this string directly to our functions would not supply the required named arguments. We parse it, reject duplicate keys and invalid JSON, validate fields and types, then call the allowlisted function.

3. A paired API measurement used 11 input tokens without tools and 375 with both tool definitions, a difference of 364 tokens. This measures the definitions and associated request-format overhead for that probe, using tool_choice='none'. S3 uses tool_choice='auto', so 364 is a measured estimate rather than a guarantee of identical overhead in every S3 request; each round resends the definitions. Evidence: outputs/tool_definition_overhead.json.

4. Dollar costs and the S2/S1 cost ratio are pending documented input and output prices. Across both full runs, S1 used 93200 input and 626 output tokens, while S2 used 467400 input and 36952 output tokens. S2 sends the corpus five times per question and generates longer step-by-step answers, so its cost increase is not simply fivefold.

5. The maximum was four model rounds, shared by several questions; one example is Q-03 in run 1. It retrieved four facts, calculated two daily rates, calculated their difference, then produced the final answer. Input usage increased from 641 to 977 to 1092 to 1158 tokens because each request included the growing conversation and tool results. Evidence: outputs/run_1/S3_Q-03.json.

6. For 100000 documents, I would build an index instead of scanning and parsing the entire corpus on each lookup. Structured fields could be indexed by district, field and period, with correction precedence and source IDs preserved. For unstructured documents, retrieval would find candidates, followed by validation of the requested fact and its authoritative version.

7. The calculator parses an AST and permits only numeric literals and explicitly allowed arithmetic operations; it does not use eval or exec. It rejects names, calls, attributes and powers, and limits expression length, tree size, depth and numeric values. A model can still supply a mathematically valid but inappropriate expression: in Q-14 run 2 it omitted division by 365, and the calculator correctly evaluated the wrong formula.

8. Tools helped most with precise multi-step numerical comparisons and unit conversions: S3 scored 37/40 against S1's 6/40 across the repeated runs. Q-06, Q-10 and Q-16 were already correct for every strategy in both runs, so tools added no observed accuracy benefit there. Tools also did not prevent S3 from selecting the wrong maximum in Q-11 run 1 or omitting a time conversion in Q-14 run 2.

