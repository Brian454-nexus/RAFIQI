# RAFIQI Jarvis Specification

## Objective

Define the target behavior and technical contract for evolving RAFIQI from a functional local assistant into a Jarvis-like system.

This spec is grounded in the current RAFIQI architecture and is intended to guide implementation, testing, and release decisions.

---

## 1. Product Identity

RAFIQI is a local-first, voice-first personal AI operator.

Jarvis-like expectations:

- Natural, confident, concise speech.
- Immediate responsiveness after wake phrase.
- Context continuity across turns.
- Safe but capable local action execution.
- Reliable operation over long sessions.

RAFIQI is not a generic chatbot UI; it is an always-ready assistant runtime.

---

## 2. Supported Interaction Modes

RAFIQI currently has multiple paths. Target behavior requires unifying them under one conversation contract.

### A. LiveKit UI Mode (primary target mode)

- User joins room through `frontend`.
- Wake phrase and command are captured.
- User utterance reaches bridge agent as text message.
- Bridge calls local brain API and speaks response into room.
- Aura visualizer reflects assistant speaking activity.

### B. Local Standalone Voice Mode (secondary / fallback)

- Wake phrase detection and local recording loop.
- Brain response spoken via local audio output.
- Should share behavior contract with LiveKit mode.

---

## 3. Assistant State Machine (Canonical)

All runtime modes should implement this same logical state machine:

1. **idle**
   - waiting for wake phrase
2. **wake_detected**
   - instant acknowledgment (<= 400 ms target)
3. **listening_for_command**
   - captures user request
4. **thinking**
   - reasoning/tool planning/LLM generation
5. **responding**
   - text response emitted + TTS started
6. **followup_window**
   - accepts brief follow-up without repeating wake phrase
7. **error_recovery**
   - user-safe fallback + clear apology + retry guidance

Transitions must be explicit and observable in logs/telemetry.

---

## 4. Wake Word and Greeting Contract

Wake phrase: `"hey jarvis"` (case-insensitive)

Required behavior:

- On wake phrase alone:
  - respond with a short greeting prompt (example: "Yes? What can I do for you?")
  - open a follow-up command window
- On wake phrase + command in same utterance:
  - execute command immediately
  - do not ask redundant "What can I do for you?"
- If no command arrives before window timeout:
  - return to idle silently

Target timings:

- wake detection to ack initiation: <= 400 ms
- command acceptance window: 6-10 s (default 8 s)

---

## 5. Voice UX Requirements

### Input

- Must support microphone permission denial gracefully.
- Must display clear voice status:
  - listening
  - wake heard
  - thinking
  - speaking
  - error

### Output

- Spoken responses are mandatory in voice mode.
- If TTS fails:
  - still provide text response
  - notify user in plain language once, not repeatedly.

### Turn-taking

- No long robotic monologues by default.
- 1-3 sentence responses unless user asks for depth.
- Follow-up question when ambiguity is high.

---

## 6. Personality and Speech Style Contract

RAFIQI tone:

- Calm, competent, focused.
- Friendly and slightly playful.
- No excessive hype or generic assistant filler.

Speech rules:

- Start with the answer.
- Keep default responses compact.
- Use actionable next step language.
- Admit uncertainty quickly and propose verification.

Forbidden patterns:

- Overly formal legalistic wording for normal tasks.
- Repetitive "As an AI..." phrasing.
- Unrequested long disclaimers.

---

## 7. Intelligence Orchestration Contract

The system needs one canonical orchestrator across channels.

Requirements:

- Same reasoning/tool policy for:
  - LiveKit/UI requests
  - standalone voice requests
  - API requests
- Memory handling must be consistent across channels.
- Tool confirmation policy must be identical regardless of entrypoint.

Decision needed:

- Canonical brain path should be tool-capable (`agent_chat`) with strict safety controls, or equivalent orchestrator abstraction that wraps it.

---

## 8. Tool Safety Policy

Risk classes:

- **Low-risk read actions**
  - status queries, process list, read-only retrieval
  - can run immediately
- **Medium/high-risk actions**
  - file writes/moves, app launch, process kill, GUI automation
  - require explicit user confirmation

Confirmation behavior:

- Assistant must summarize intended action in plain language.
- Require explicit "yes"/equivalent.
- Log user approval and executed action.

Emergency behavior:

- Any tool exception should not crash conversation loop.
- Assistant should apologize briefly and offer next action.

---

## 9. Memory and Context Contract

### Short-term memory

- Maintain bounded recent chat context for continuity.
- Preserve role ordering and recent user intent.

### Long-term memory

- Store user preferences and durable facts only.
- Do not auto-store every message.
- Mark source and timestamp.

### Retrieval behavior

- Prefer relevant memory when confidence is high.
- If uncertain, ask user rather than hallucinating.

---

## 10. Performance Targets

User-perceived goals (voice path):

- Wake ack start: <= 400 ms
- Command-to-first-text token (or response start): <= 1.8 s typical
- Command-to-TTS audio start: <= 2.5 s typical

Operational goals:

- 60+ minute stable session without restart
- graceful reconnect behavior when room/network fluctuates

---

## 11. Reliability and Observability Requirements

Must-have visibility:

- startup diagnostics:
  - env config
  - API reachability
  - TTS readiness
  - voice model readiness
- runtime event logs:
  - wake detected
  - transcript sent
  - response received
  - tts started/failed

Recommended endpoints:

- `/health` (API and dependencies)
- `/ready` (can process user request now)

Frontend status panel should expose core live state to user.

---

## 12. Error Handling Contract

Error classes and responses:

- **STT unavailable**
  - inform user voice mode is unavailable
  - offer text fallback
- **Brain/API failure**
  - short spoken apology + retry suggestion
- **TTS failure**
  - display text response, attempt next turn normally
- **Room disconnect**
  - attempt reconnect with backoff and status updates

No silent failure states are allowed for core turn flow.

---

## 13. Security and Privacy

Principles:

- Local-first by default.
- Explicit consent before state-changing actions.
- Minimal retention of sensitive content.
- No hidden outbound calls beyond configured providers/components.

Auditability:

- Action log for tool executions (what, why, when, confirmed by whom).

---

## 14. Definition of Done (Jarvis Milestone)

RAFIQI can be considered "Jarvis-ready" when all are true:

1. Saying "Hey Jarvis" reliably triggers spoken acknowledgment.
2. Same-turn and next-turn command capture both work reliably.
3. Assistant replies are spoken and reflected in Aura for >95% of turns.
4. One canonical orchestrator handles all channels consistently.
5. Tool confirmations are safe, clear, and logged.
6. Runtime provides clear status and non-silent failure reporting.
7. 30-minute conversational session runs without manual restarts.

---

## 15. Implementation Priorities (Next)

1. Stabilize voice response reliability (STT -> bridge -> TTS).
2. Add startup health + runtime status visibility.
3. Unify orchestrator path used by `/chat` and voice loops.
4. Formalize state machine and follow-up window behavior.
5. Add integration tests for wake -> response spoken loop.

---

## 16. Out of Scope (for current milestone)

- Multi-user personalization at scale.
- Mobile app parity.
- Full autonomous task scheduling engine.
- Enterprise policy management.

These can be layered after core Jarvis loop reliability is achieved.

