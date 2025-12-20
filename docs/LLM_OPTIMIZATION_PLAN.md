# PM1 Simulation LLM Analysis - Senior Expert Review

## Executive Summary

This document provides a comprehensive analysis of the PM1 simulation's LLM interactions, identifying optimization opportunities, quality improvements, and cost reduction strategies.

**Analysis Date**: December 2024
**Priority**: Quality Improvement (Pure LLM, Aggressive Batching)

---

## 1. CURRENT LLM USAGE PATTERNS

### 1.1 API Call Points (4 distinct LLM integration points)

| Call Point | Location | Model | Max Tokens | Frequency |
|------------|----------|-------|------------|-----------|
| Agent Actions | `simulation.py:971` | claude-sonnet-4 | 1024 | Every `event_frequency` seconds per agent |
| Meeting Turns | `meetings.py:1160` | claude-sonnet-4 | 500 | Per participant per round |
| Meeting Outcomes | `meetings.py:1246` | claude-sonnet-4 | 1500 | Once per completed meeting |
| Event Resolution | `simulation.py:1913` | claude-sonnet-4 | 1024 | Every 30 seconds (batch of 5) |

### 1.2 Token Consumption Analysis

**Estimated Per-Call Token Usage:**
- **Agent Action**: ~2,500-4,000 input tokens (system prompt + memory + context) + 200-400 output
- **Meeting Turn**: ~3,000-5,000 input (transcript + history) + 150-300 output
- **Event Resolution**: ~1,500-2,500 input (batch) + 500-800 output
- **Meeting Outcome**: ~4,000-8,000 input (full transcript) + 400-600 output

**Cost Drivers:**
1. System prompts recompiled but not cached effectively
2. Memory (20 entries) injected every call - often redundant
3. Meeting transcripts grow linearly with rounds
4. No token counting before submission

---

## 2. QUALITY ISSUES IDENTIFIED

### 2.1 Agent Decision Quality
| Issue | Impact | Root Cause |
|-------|--------|------------|
| Generic/repetitive actions | Low simulation depth | Prompts lack specificity, memory too shallow |
| Unrealistic timing | Immersion breaking | No temporal constraints in prompts |
| Missing inter-agent coordination | Isolated behaviors | Agents can't see pending actions of allies |
| Inconsistent action scope | Scale mismatch | "Prepare airstrike" vs "Win the war" in same format |

### 2.2 Memory System Weaknesses
- **Cap of 7 memories is too aggressive** - agents lose important context
- **No memory relevance scoring** - old trivial events equal to strategic ones
- **No semantic deduplication** - similar events consume slots
- **Linear format** - no hierarchy (strategic vs tactical)

### 2.3 Orchestration Gaps
- **No agent collaboration awareness** - agents act independently, can't coordinate
- **Fixed frequency scheduling** - doesn't adapt to situation urgency
- **No role-based action gating** - intel agent can propose military strikes
- **Missing chain-of-command** - subordinates don't defer to superiors

---

## 3. OPTIMIZATION RECOMMENDATIONS

### 3.1 Token Reduction Strategies

#### A. Implement Hierarchical Memory (Est. 40% token reduction)
```
Current: 20 flat memory entries (~800 tokens)
Proposed:
  - Strategic layer (3 entries): Major decisions, PM approvals
  - Operational layer (5 entries): Active operations, ongoing situations
  - Tactical layer (7 entries): Recent actions, immediate context
  - Summarization: Older tactical entries compressed into operational summaries
```

**Implementation:**
- Add `memory_layer` field to each memory entry
- Implement `compress_tactical_to_operational()` function
- Only inject relevant layers based on action_type being decided

#### B. System Prompt Caching (Est. 30% cost reduction)
```python
# Current: Full system prompt sent every call
# Proposed: Use Anthropic's prompt caching properly

# In compile_system_prompt():
static_parts = [identity, simulation_context, behavioral_rules]  # CACHE
dynamic_parts = [agenda, objectives, recent_situations]  # NO CACHE

# Use cache_control: {"type": "ephemeral"} on static_parts
```

#### C. Context Compression (Est. 25% token reduction)
- **Deduplicate memory entries** before injection
- **Abbreviate location lists** - only include zones relevant to agent role
- **Truncate resolved events** - don't repeat full summaries of completed actions
- **Use structured formats** - JSON/YAML more token-efficient than prose

#### D. Batch Optimization
```
Current: Resolver batches 5 events
Proposed: Dynamic batching based on event similarity
  - Group by action_type → single prompt per type
  - Group by entity → fewer context switches
  - Skip resolution for "none" actions entirely
```

### 3.2 Quality Improvements

#### A. Enhanced Agent Reasoning Prompts
```yaml
# Add to entity action prompt:
BEFORE_ACTING_CHECKLIST:
  - What is the current phase of the conflict?
  - What are my entity's most urgent needs?
  - What actions have colleagues taken in last hour?
  - What actions require coordination or sequencing?
  - What constraints does my role impose?
```

#### B. Role-Based Action Filtering
```python
ROLE_ACTION_MATRIX = {
    "Head-Of-Mossad": ["intelligence", "diplomatic"],
    "IDF-Commander": ["military", "intelligence"],
    "Treasury-Minister": ["economic", "internal"],
    "Foreign-Minister": ["diplomatic"],
    # Block agents from proposing out-of-role actions
}
```

#### C. Temporal Awareness
```python
# Add to prompt:
TEMPORAL_CONTEXT:
  - Hours since conflict start: {hours}
  - Current phase: {escalation|active_combat|negotiation|de-escalation}
  - Pending operations completing soon: {list}
  - Expected next major event: {prediction}
```

#### D. Coordination Protocol
```python
# New: Allies can see each other's pending actions
def get_allied_pending_actions(agent_id):
    entity = get_entity_for_agent(agent_id)
    allies = ENTITY_ALLIES[entity]  # e.g., Israel allies: USA, UK
    return [e for e in pending_events if e.agent_entity in allies]
```

### 3.3 Smarter Agent Orchestration

#### A. Adaptive Scheduling
```python
# Current: Fixed event_frequency per agent
# Proposed: Dynamic frequency based on:

def calculate_next_action_delay(agent_id, last_action):
    base = agent.event_frequency

    # Factors:
    urgency = get_situation_urgency()  # Crisis = faster
    action_type = last_action.action_type  # Military = slower cooldown
    pending_ops = count_pending_ops(agent_id)  # More ops = slower

    return base * urgency_multiplier * action_cooldown * pending_modifier
```

#### B. Priority Queue Instead of Round-Robin
```python
# Replace linear scheduling with priority-based:
agent_priority = calculate_priority(agent)
# Priority factors:
#   - Has pending approval response
#   - Mentioned in recent events
#   - Crisis relevance score
#   - Time since last action (decay)
```

#### C. Chain of Command Enforcement
```python
REPORTING_CHAIN = {
    "IDF-Commander": "Defense-Minister",
    "Head-Of-Mossad": "Defense-Minister",
    "Defense-Minister": "PM",
    # Major actions auto-escalate up chain
}
```

---

## 4. AGENT SKILLS ENHANCEMENT

### 4.1 Current Skills Gap
The codebase has a `skills` structure in agents.json but it's underutilized.

### 4.2 Proposed Skill System
```python
AGENT_SKILLS = {
    "Head-Of-Mossad": {
        "intelligence_gathering": 0.95,
        "asset_recruitment": 0.85,
        "covert_operations": 0.90,
        "diplomatic_insight": 0.70
    },
    "IDF-Commander": {
        "tactical_planning": 0.95,
        "force_coordination": 0.90,
        "precision_strikes": 0.85,
        "urban_warfare": 0.75
    }
}

# Skills affect:
# 1. Success rates in KPI_IMPACT_RULES
# 2. Action type restrictions
# 3. Information access (intel skills = more briefing data)
# 4. Coordination bonuses when skills complement
```

### 4.3 Skill-Based Prompting
```python
# Inject skill awareness into prompts:
YOUR_CAPABILITIES:
  - Strong: {high_skills} - actions in these areas more likely to succeed
  - Moderate: {mid_skills} - standard success rates
  - Limited: {low_skills} - consider delegating to specialists
```

---

## 5. MEMORY SYSTEM DEEP DIVE

### 5.1 Current Implementation Cost
- **Storage**: 7 memories × ~50 tokens = 350 tokens/agent × 20 agents = 7,000 tokens base
- **Injection**: 20 memories in decision prompts = ~800 tokens/call
- **Estimated monthly cost** (assuming 10 actions/agent/hour, 24h):
  - 20 agents × 10 actions × 24h × 800 tokens = 3.84M tokens/day = ~$11/day on input alone

### 5.2 Memory Quality Issues
1. **No importance weighting** - trivial events equal strategic ones
2. **No temporal decay** - week-old events same priority as hour-old
3. **No semantic clustering** - can't retrieve "all military events"
4. **Fixed cap loses context** - agent forgets early war decisions

### 5.3 Proposed: Tiered Memory Architecture
```
LONG-TERM MEMORY (persistent, summarized):
  - Key strategic decisions
  - PM approvals/rejections
  - Major outcome milestones

SHORT-TERM MEMORY (recent, detailed):
  - Last 10 actions
  - Recent events affecting agent
  - Active operation status

WORKING MEMORY (current context only):
  - Immediate pending actions
  - Current situation status
  - Last interaction context
```

### 5.4 Cost-Optimized Memory Retrieval
```python
def get_relevant_memories(agent_id, current_action_type):
    # Instead of injecting all 20 memories:

    memories = []

    # Always include: last 3 actions
    memories += get_recent_memories(agent_id, 3)

    # Relevant to action type:
    if current_action_type == "military":
        memories += get_memories_by_type(agent_id, "military", limit=5)

    # Semantic relevance (if embeddings available):
    memories += get_semantically_similar(agent_id, current_context, limit=3)

    return deduplicate(memories)[:10]  # Cap at 10, not 20
```

---

## 6. OUTPUT OPTIMIZATION MATRIX

| Output Type | Current | Optimized | Token Savings |
|-------------|---------|-----------|---------------|
| Agent action summary | 100 chars | 80 chars (tighter) | 5% |
| Memory entries | 20 per call | 10 relevant | 50% |
| System prompt | Full each time | Cached static parts | 30% |
| Meeting transcript | Full history | Last 5 turns + summary | 40% |
| Location context | All 15+ zones | Role-relevant 5 | 65% |
| KPI data in prompts | (already removed) | Rule-based | N/A |

### 6.1 Response Optimization
```python
# Current: LLM generates verbose outcomes
# Proposed: Structured minimal responses

OUTPUT_SCHEMA = {
    "action": "enum",  # Not free text
    "target": "zone_id",  # Not free text
    "intensity": "low|medium|high",  # Constrained
    "rationale": "50 chars max"  # Hard limit
}
```

---

## 7. IMPLEMENTATION PRIORITY

### Phase 1: Quick Wins
1. Implement proper prompt caching for static system prompt parts
2. Reduce memory injection from 20 to 10 relevant entries
3. Add role-based action filtering
4. Truncate location context to role-relevant zones

### Phase 2: Quality Improvements
1. Implement tiered memory architecture
2. Add coordination awareness (allies see pending actions)
3. Implement adaptive scheduling based on urgency
4. Add temporal context to prompts

### Phase 3: Advanced Features
1. Semantic memory retrieval (requires embeddings)
2. Full skill system integration
3. Chain-of-command enforcement
4. Dynamic event batching by similarity

---

## 8. ESTIMATED IMPACT

| Metric | Current | After Optimization |
|--------|---------|-------------------|
| Tokens per agent action | ~3,500 | ~2,000 (43% reduction) |
| Monthly API cost (estimated) | ~$350 | ~$180 (48% reduction) |
| Action quality score | Medium | High (better prompts) |
| Agent coordination | None | Cross-entity awareness |
| Memory relevance | Low | High (tiered + semantic) |
| Simulation realism | Medium | High (temporal + role constraints) |

---

## 9. CRITICAL FILES TO MODIFY

1. **[simulation.py](backend/simulation.py)** - Memory injection, prompt building, scheduling
2. **[app.py](backend/app.py)** - System prompt caching, memory architecture
3. **[meetings.py](backend/meetings.py)** - Transcript optimization
4. **[agents.json](data/agents.json)** - Skills structure, memory tiers

---

## 10. INCOMPLETE/UNWIRED FEATURES DISCOVERED

### Critical: Features Built But Never Used

#### 10.1 Skills System - DEAD CODE
**Location**: `app.py:296-305`, `app.py:611-612`
- `agent_skills` dictionary maintained and persisted
- Skills added to `interact_with_claude()` but **NOT to simulation's ENTITY_ACTION_PROMPT**
- Agents never reference their skills during autonomous decisions

**Fix**: Wire skills into `simulation.py:793` `ENTITY_ACTION_PROMPT`

**Status**: [x] COMPLETED - Skills added to ENTITY_ACTION_USER_PROMPT and injected in build_prompt()

---

#### 10.2 Prompt Caching - NOT UTILIZED
**Location**: `app.py:574-586`
- `prompt_caching()` function exists, stores cached prompts
- **NOT used in EventProcessor.build_prompt()**
- Only works for direct chat, not simulation

**Fix**: Integrate caching into simulation's LLM calls

**Status**: [x] COMPLETED - Added interact_with_caching() to app.py, split prompts into SYSTEM/USER pairs with cache_control

---

#### 10.3 Relocate Actions - NEVER PROCESSED
**Location**: `simulation.py:1001-1005`
- Agents can request `action_type: "relocate"` with `relocate_to` zone
- `parse_llm_response()` captures it but **never calls `start_entity_movement()`**
- Movement system is half-built

**Fix**: Wire relocate parsing to MapStateManager movement

**Status**: [x] COMPLETED - Added AGENT_TO_TRACKED_ENTITY mapping and wired relocate to start_entity_movement()

---

### High: Infrastructure Built But Starved of Input

#### 10.4 PM Approval Patterns - AGENTS DON'T TRIGGER
**Location**: `simulation.py:1736-1738`
- PM approval patterns defined but most Israeli agents have `event_frequency: 100`
- Defense-Minister, Treasury-Minister rarely act (~once per 100 game minutes)
- PM approval queue is empty because triggering agents are slow

**Fix**: Reduce event_frequency for government agents to ~30-60

**Status**: [x] COMPLETED - Defense-Minister: 100→40, Treasury-Minister: 100→50

---

#### 10.5 Scheduled Events - NEVER CREATED
**Location**: `simulation.py:536-593`
- Infrastructure complete, checked every resolver tick
- Since PM approvals are rare → scheduled events never created
- Downstream of issue #10.4

**Fix**: Fixing #10.4 will activate this

**Status**: [x] COMPLETED - Downstream of 10.4 fix, now activated

---

#### 10.6 Ongoing Situations - LIFECYCLE INCOMPLETE
**Location**: `simulation.py:400-426`
- `current_phase` never transitions after creation
- `cumulative_effects` list never appended to
- `update_situation()` method exists but **never called**

**Fix**: Add situation lifecycle processing to resolver loop

**Status**: [x] COMPLETED - Added _process_situation_lifecycles() method with phase transitions

---

#### 10.7 KPI Rules - 40% HAVE EMPTY IMPACTS
**Location**: `simulation.py:1272-1298`
- Intelligence actions: surveillance, infiltration, counter-intel → `on_success: {}`
- Diplomatic statements → empty impacts
- Economic/internal defaults → empty impacts

**Fix**: Populate missing KPI impacts for all action types

**Status**: [x] COMPLETED - Added ~15 KPI rules for intelligence, diplomatic, and other action types

---

### High: Fragmented Implementations

#### 10.8 Spatial Clash Detection - MISSING METHOD
**Location**: `simulation.py:1481-1483`
- `apply_spatial_clash()` calls `check_spatial_clash()`
- **This method doesn't exist in MapStateManager**
- Detection chance calculation incomplete

**Fix**: Implement `check_spatial_clash()` method

**Status**: [x] COMPLETED - Added check_spatial_clash() method to MapStateManager

---

#### 10.9 GeoEvents - CREATED BUT NOT PERSISTED
**Location**: `simulation.py:1543-1620`
- `create_geo_event_for_action()` builds GeoEvent objects
- **No call to `map_manager.add_geo_event()`**
- Map visualization never receives events

**Fix**: Wire GeoEvent creation to MapStateManager persistence

**Status**: [x] N/A - False positive, map_manager.create_geo_event() already saves via self._save()

---

#### 10.10 Meeting Auto-Triggers - MISSING RULES
**Location**: `simulation.py:2277`
- `check_auto_triggers()` called every resolver tick
- **`AUTO_TRIGGER_RULES` constant not found**
- Meeting auto-initiation is broken

**Fix**: Define AUTO_TRIGGER_RULES configuration

**Status**: [x] N/A - False positive, AUTO_TRIGGER_RULES already exists in meetings.py with 5 rules

---

## 11. QUALITY-FOCUSED IMPLEMENTATION PLAN

### Priority: User wants QUALITY improvement, pure LLM, aggressive batching

### Phase 1: Wire Missing Features (High Impact) ✅ COMPLETE
| Task | File | Lines | Impact | Status |
|------|------|-------|--------|--------|
| Wire skills into ENTITY_ACTION_PROMPT | simulation.py | 793+ | Agents use their capabilities | [x] |
| Process relocate actions → movement | simulation.py | 1001-1005 | Agents can move on map | [x] |
| Reduce govt agent event_frequency | agents.json | various | PM approvals actually trigger | [x] |
| Implement check_spatial_clash() | map_state.py | new | Spatial interactions work | [x] |
| Persist GeoEvents to map_manager | simulation.py | 1848 | Map shows events | [x] N/A |

### Phase 2: Complete Lifecycle Systems ✅ COMPLETE
| Task | File | Lines | Impact | Status |
|------|------|-------|--------|--------|
| Add situation phase transitions | simulation.py | 2240+ | Situations evolve over time | [x] |
| Call update_situation() in resolver | simulation.py | resolver loop | Cumulative effects applied | [x] |
| Populate empty KPI rules | simulation.py | 1272-1298 | Intel/diplomatic actions matter | [x] |
| Define AUTO_TRIGGER_RULES | meetings.py or simulation.py | new const | Meetings auto-start | [x] N/A |

### Phase 3: Optimization (Token Savings) ✅ COMPLETE
| Task | File | Impact | Status |
|------|------|--------|--------|
| Reduce memory injection 20→10 | simulation.py | 50% token savings on memory | [x] |
| Implement prompt caching for simulation | simulation.py | 30% cost reduction | [x] |
| Truncate location context by role | simulation.py | 65% location token savings | [x] |
| Batch resolver by action_type | simulation.py | Fewer LLM calls | [x] |

---

## 12. DETAILED FIX SPECIFICATIONS

### Fix 1: Wire Skills into Agent Decision Prompts
```python
# In simulation.py ENTITY_ACTION_PROMPT (line 793+):
# Add after objectives section:

YOUR_CAPABILITIES:
{{skills}}

Consider your skill levels when choosing actions.
Actions aligned with high skills are more likely to succeed.
```

```python
# In build_prompt() add:
skills = app.agent_skills.get(agent_id, {})
skills_text = ", ".join([f"{k}: {v}" for k,v in skills.items()]) if skills else "General capabilities"
```

---

### Fix 2: Process Relocate Actions
```python
# In parse_llm_response() after line 1005:
if action.get("action_type") == "relocate" and action.get("relocate_to"):
    target_zone = action["relocate_to"]
    if map_manager.is_valid_zone(target_zone):
        map_manager.start_entity_movement(
            entity_id=agent_id,
            target_zone=target_zone,
            duration_minutes=30  # or calculate based on distance
        )
```

---

### Fix 3: Reduce Government Agent Frequencies
```json
// In agents.json, change:
"Defense-Minister": { "event_frequency": 100 → 45 }
"Treasury-Minister": { "event_frequency": 100 → 60 }
"Foreign-Minister": { "event_frequency": 100 → 50 }
"IDF-Commander": { "event_frequency": 60 → 30 }
```

---

### Fix 4: Implement check_spatial_clash()
```python
# In map_state.py MapStateManager class:
def check_spatial_clash(self, zone_name: str, action_type: str) -> dict:
    """Check if action clashes with entities in zone"""
    entities_in_zone = self.get_entities_in_zone(zone_name)
    clash_info = {
        "has_clash": len(entities_in_zone) > 0,
        "entities": entities_in_zone,
        "entity_types": [e.entity_type for e in entities_in_zone],
        "detection_difficulty": self.get_zone_detection_difficulty(zone_name)
    }
    return clash_info
```

---

### Fix 5: Persist GeoEvents
```python
# In apply_resolutions() around line 1848:
geo_event = create_geo_event_for_action(event, resolution)
if geo_event:
    self.map_manager.add_geo_event(geo_event)  # ADD THIS LINE
```

---

### Fix 6: Situation Lifecycle Processing
```python
# In resolver loop (after processing events):
for situation in self.state.ongoing_situations:
    if situation.current_phase == "active":
        hours_active = (current_time - situation.started_at).hours
        if hours_active >= situation.expected_duration_minutes / 60:
            situation.current_phase = "resolving"
            # Check resolution conditions
            if self.check_situation_resolution(situation):
                situation.current_phase = "completed"
                self.apply_situation_outcome(situation)
```

---

### Fix 7: Populate Empty KPI Rules
```python
"surveillance|monitor": {
    "success_rate": 0.70,
    "on_success": {
        "Israel.intelligence.intel_accuracy": (2, 5),
        "Israel.intelligence.threat_detection": (1, 3)
    },
    "on_failure": {
        "Israel.intelligence.assets_compromised": (1, 2)
    }
},
```

---

## 13. FILES TO MODIFY

| File | Changes |
|------|---------|
| `backend/simulation.py` | Skills injection, relocate processing, GeoEvent persistence, situation lifecycle, KPI rules |
| `backend/map_state.py` | Implement check_spatial_clash(), get_zone_detection_difficulty() |
| `backend/meetings.py` | Define AUTO_TRIGGER_RULES |
| `data/agents.json` | Reduce event_frequency for government agents |

---

## 14. EXPECTED OUTCOMES

After implementation:
- **Skills actively influence agent decisions** (quality)
- **Agents physically move on map** (immersion)
- **PM approvals trigger regularly** (gameplay loop)
- **Scheduled events execute** (dynamic narrative)
- **Situations evolve over time** (strategic depth)
- **All actions have KPI consequences** (meaningful choices)
- **Map shows real-time events** (visualization)
- **Meetings auto-trigger on conditions** (emergent drama)

Token optimizations (Phase 3) will yield ~40-50% cost reduction while maintaining quality.

---

## 15. PROGRESS TRACKING

### Overall Progress ✅ ALL PHASES COMPLETE
- [x] Phase 1: Wire Missing Features (5/5)
- [x] Phase 2: Complete Lifecycle Systems (4/4)
- [x] Phase 3: Optimization (4/4)

### Completion Checklist
- [x] 10.1 Skills System wired
- [x] 10.2 Prompt Caching integrated
- [x] 10.3 Relocate Actions processed
- [x] 10.4 PM Approval frequencies fixed
- [x] 10.5 Scheduled Events working (downstream of 10.4)
- [x] 10.6 Ongoing Situations lifecycle
- [x] 10.7 KPI Rules populated
- [x] 10.8 Spatial Clash method implemented
- [x] 10.9 GeoEvents persisted (N/A - already working)
- [x] 10.10 Meeting Auto-Triggers defined (N/A - already exists)

---

## 16. IMPLEMENTATION SUMMARY

**Completed**: December 2024

### Key Changes Made:

#### Phase 1 - Wire Missing Features:
1. **Skills in prompts** - Added `ENTITY_ACTION_USER_PROMPT` with skills section, wired in `build_prompt()`
2. **Relocate actions** - Added `AGENT_TO_TRACKED_ENTITY` mapping, wired to `start_entity_movement()`
3. **Agent frequencies** - Defense-Minister: 100→40, Treasury-Minister: 100→50
4. **Spatial clash** - Implemented `check_spatial_clash()` in MapStateManager

#### Phase 2 - Lifecycle Systems:
1. **Situation lifecycle** - Added `_process_situation_lifecycles()` with phase transitions
2. **KPI rules** - Populated ~15 rules for intelligence, diplomatic, economic actions

#### Phase 3 - Token Optimization:
1. **Memory injection** - Reduced from 20 to 10 entries (50% savings)
2. **Prompt caching** - Split prompts into SYSTEM/USER pairs with `cache_control: ephemeral`
3. **Zone filtering** - Added `ROLE_ZONE_FILTERS` for role-based zone relevance (65% savings)
4. **Action batching** - Events grouped by action_type before batching

### New Functions Added:
- `app.py`: `interact_with_caching()` - LLM call with system prompt caching
- `simulation.py`: `get_role_relevant_zones()` - Role-based zone filtering
- `simulation.py`: `_process_situation_lifecycles()` - Situation phase management
- `map_state.py`: `check_spatial_clash()` - Spatial entity detection

### Estimated Impact:
| Metric | Before | After |
|--------|--------|-------|
| Tokens per agent action | ~3,500 | ~2,000 (43% reduction) |
| Memory tokens | ~800 | ~400 (50% reduction) |
| Zone tokens | ~150 | ~50 (65% reduction) |
| API cost reduction | - | ~40-50% estimated |
