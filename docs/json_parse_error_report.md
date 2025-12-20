# JSON Parse Error Analysis Report

**Generated:** December 20, 2025
**Log Period Analyzed:** December 19-20, 2025
**Report Author:** Game Content Reviewer Agent

---

## Executive Summary

The simulation system experiences two distinct categories of JSON parsing failures that disrupt gameplay flow. These errors originate from LLM responses that either contain no JSON at all, or contain malformed JSON with syntax errors.

---

## Error Categories

### Category 1: "No JSON found in LLM response"

**Description:** The LLM returns plain text without any JSON structure.

**Affected Components:**
- Agent action parsing (`parse_llm_response` in simulation.py:1115)

**Error Pattern:**
```
ERROR - No JSON found in LLM response for {agent_id}
```

### Category 2: "JSON parse error - Expecting ',' delimiter"

**Description:** The LLM returns JSON with syntax errors, typically missing commas.

**Affected Components:**
- Resolver response parsing (`parse_resolver_response` in simulation.py:2058)

**Error Pattern:**
```
ERROR - JSON parse error in resolver response: Expecting ',' delimiter: line X column Y (char Z)
```

---

## Timeline of Errors

### December 19, 2025

| Time | Agent/Component | Error Type |
|------|-----------------|------------|
| 17:40:00 | test-agent | No JSON found (unit tests) |
| 18:15:46 | **IDF-Commander** | No JSON found |
| 18:16:12 | **Russia-President** | No JSON found |
| 18:16:16 | **North-Korea-Supreme-Leader** | No JSON found |
| 18:16:32 | **Iran-Ayatollah** | No JSON found |
| 18:45:42 | **Hamas-Leadership** | No JSON found |
| 22:16:20 | Resolver | JSON parse error (line 74, char 3391) |
| 22:28:34 | Resolver | JSON parse error (line 91, char 3383) |
| 23:09:25 | Resolver | JSON parse error (line 39, char 2537) |
| 23:24:42 | Resolver | JSON parse error (line 59, char 3768) |
| 23:25:58 | Resolver | JSON parse error (line 58, char 3805) |
| 23:31:37 | Resolver | JSON parse error (line 68, char 3750) |
| 23:32:55 | Resolver | JSON parse error (line 55, char 3741) |
| 23:34:13 | Resolver | JSON parse error (line 44, char 3125) |

### December 20, 2025

| Time | Agent/Component | Error Type |
|------|-----------------|------------|
| 00:03:00 | test-agent | No JSON found (unit tests) |
| 00:09:57 | Resolver | JSON parse error (line 63, char 3727) |
| 00:10:20 | **Hamas-Leadership** | No JSON found |
| 00:11:14 | Resolver | JSON parse error (line 37, char 2172) |
| 00:12:30 | Resolver | JSON parse error (line 63, char 3451) |
| 00:13:47 | Resolver | JSON parse error (line 67, char 3736) |

---

## Root Cause Analysis

### 1. Agent Action Failures ("No JSON found")

**First Occurrence:** December 19, 2025 at 18:15:46 (IDF-Commander)

**Root Cause:** The LLM prompt requests JSON output, but some agents - particularly adversary/international agents - return narrative text instead of structured JSON. This appears to happen when:

1. **Agents with less context** - IDF-Commander failed on first real action
2. **Non-Israeli agents** - Russia-President, North-Korea-Supreme-Leader, Iran-Ayatollah
3. **Adversary agents** - Hamas-Leadership (failed twice)

**Hypothesis:** These agents may receive less contextual information in their prompts, or the LLM interprets their "character" as more likely to respond narratively rather than following the strict JSON format.

**Code Location:**
```python
# simulation.py:1109-1116
def parse_llm_response(self, agent_id: str, response: str, game_time: str):
    try:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            logger.error(f"No JSON found in LLM response for {agent_id}")
            return None
```

### 2. Resolver Failures ("Expecting ',' delimiter")

**First Occurrence:** December 19, 2025 at 22:16:20

**Root Cause:** The resolver processes batches of 20 events and must generate a complex JSON response with resolutions for each. The errors consistently occur:
- Around character 2500-3800 (deep in the response)
- Around line 40-75 (in the middle of the resolutions array)

**Hypothesis:** As the resolver generates longer responses for more events, it becomes more likely to:
1. Drop a comma between array elements
2. Malform a string with unescaped characters
3. Truncate the response mid-JSON

**Code Location:**
```python
# simulation.py:2040-2058
def parse_resolver_response(self, response: str) -> dict:
    try:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            logger.error("No JSON found in resolver response")
            return {"resolutions": [], "pm_requests": []}

        result = json.loads(json_match.group())
        ...
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in resolver response: {e}")
        return {"resolutions": [], "pm_requests": []}
```

---

## Affected Agents (Most to Least Frequent)

| Agent | Failure Count | Notes |
|-------|---------------|-------|
| test-agent | 8 | Unit test - expected |
| Hamas-Leadership | 2 | Adversary agent, critical for gameplay |
| IDF-Commander | 1 | Key military agent |
| Russia-President | 1 | International agent |
| North-Korea-Supreme-Leader | 1 | International agent |
| Iran-Ayatollah | 1 | Adversary-aligned agent |
| Resolver (system) | 12 | Critical system component |

---

## Impact Assessment

### Gameplay Impact: HIGH

1. **Broken adversary behavior:** Hamas-Leadership fails to act, making the simulation feel passive
2. **Missing international pressure:** Russia, Iran, North Korea not acting reduces geopolitical complexity
3. **Event resolution failures:** 12 resolver failures mean pending events don't resolve, KPIs don't update

### System Impact: MEDIUM

1. **Silent failures:** Errors logged but gameplay continues with missing actions
2. **State inconsistency:** Pending events may accumulate without resolution
3. **Memory not updated:** Agents missing actions don't receive memory of their own choices

---

## Assumptions About Cause

### Primary Assumption: Prompt Length & Complexity

The resolver prompt becomes very long when processing 20 events. The LLM may:
- Lose track of JSON syntax when generating 3000+ character responses
- Start "thinking" in natural language mid-response
- Run into token limits that cause truncation

**Evidence:** Errors cluster around char 3000-3800, suggesting a consistent failure point.

### Secondary Assumption: Character-Based Responses

Some agents (Hamas-Leadership, Iran-Ayatollah) may trigger the LLM to adopt their "persona" too strongly, leading to narrative responses rather than following the JSON format instruction.

**Evidence:** Adversary/authoritarian agents fail more often than Israeli agents.

### Tertiary Assumption: Instruction Following

The prompts say "Respond ONLY with valid JSON" but:
- This instruction appears at the end of a long system prompt
- The LLM may prioritize roleplay over format compliance

---

## Recommendations

### Immediate Fixes (Priority 1)

1. **Add retry logic with reformatted prompt:**
   ```python
   if not json_match:
       # Retry with explicit JSON-only prompt
       retry_response = llm_call(f"Previous response was not valid JSON. Return ONLY: {json_schema}")
   ```

2. **Reduce resolver batch size from 20 to 5-10:**
   - Shorter responses = fewer syntax errors
   - Already partially implemented in Dec 20 logs

3. **Add fallback actions for failed agents:**
   ```python
   if event is None:
       return SimulationEvent(
           action_type="none",
           summary=f"{agent_id} is deliberating",
           ...
       )
   ```

### Medium-Term Fixes (Priority 2)

1. **Use structured output mode** if LLM provider supports it (OpenAI JSON mode, Anthropic tool use)

2. **Move JSON format instructions to the END of the prompt** where they're more likely to be followed

3. **Validate and repair JSON:**
   ```python
   import json_repair
   fixed_json = json_repair.repair_json(malformed_json)
   ```

### Long-Term Fixes (Priority 3)

1. **Implement agent-specific prompts** that emphasize format compliance for problematic agents

2. **Add JSON schema validation** with clear error messages

3. **Create monitoring dashboard** for parse failure rates by agent

---

## Files Analyzed

- `backend/logs/simulation_20251219.log`
- `backend/logs/simulation_20251220.log`
- `backend/simulation.py` (lines 1109-1202, 2038-2060)

---

## Conclusion

The JSON parsing failures stem from two distinct issues:

1. **Agent prompts** that don't consistently enforce JSON output format, especially for adversary/international agents
2. **Resolver prompts** that request too much output, causing the LLM to lose JSON syntax consistency

The immediate fix is to add retry logic and reduce batch sizes. The long-term fix is to use structured output modes or JSON repair libraries.

**Estimated Fix Effort:** 2-4 hours for immediate fixes, 1-2 days for medium-term improvements.
