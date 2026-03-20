# RAFIQI Implementation Document

## Purpose

This document captures the current RAFIQI implementation in detail: what exists, how major files connect, what is currently working, what is unstable, and what remains to reach a true Jarvis-like assistant (proactive, reliable, low-latency, voice-first, and system-capable).

It is meant to be a living engineering reference for future development.

---

## Product Goal (Target State)

RAFIQI should behave like a local Jarvis:

- Always-available, voice-first interaction loop.
- Reliable wake word and natural conversation turn-taking.
- Immediate spoken acknowledgment after wake word.
- Fast, accurate, contextual responses with memory.
- Optional tool execution on the local machine with safe confirmations.
- Strong observability (status, logs, health checks, failure reasons visible).

Current codebase provides the foundational architecture for this, but still has critical integration gaps and reliability issues.

---

## High-Level Architecture

There are three runtime surfaces:

1. **Core Brain Runtime (Python local backend)**
   - LLM and agent logic
   - Memory
   - RAG
   - System/file tool wrappers
2. **Bridge Runtime (LiveKit agent participant)**
   - Connects LiveKit room to local brain API
   - Receives user messages from room data
   - Sends assistant replies back as room data
   - Publishes TTS audio track
3. **Frontend Runtime (Next.js + LiveKit components)**
   - Join room UI
   - Transcript and control bar
   - Aura visualizer
   - Token mint endpoint
   - Browser speech recognition + wake word handling (recently added)

Logical message flow:

`User speech -> frontend speech recognition -> room data message -> livekit_agent.py -> api_server.py /chat -> brain.py -> reply -> livekit_agent.py publishes chat + TTS audio -> frontend transcript + Aura`

---

## Repository Areas and Responsibilities

## 1) Python Entry and Modes

### `main.py`

Unified CLI entrypoint with explicit modes:

- `python main.py voice` -> local standalone wake-word voice loop
- `python main.py api` -> FastAPI endpoint for text chat
- `python main.py agent` -> LiveKit bridge participant

Why it matters:
- Prevents accidental microphone/device conflicts by not auto-running all loops at once.
- Provides clean separation for local-only mode vs UI/LiveKit mode.

---

## 2) API Layer

### `api_server.py`

FastAPI service exposing:

- `POST /chat`
  - Input: `{ "text": string }`
  - Output: `{ "reply": string }`

This currently delegates to `brain.chat()` (non-agent direct LLM helper), not to `agent.agent_chat()`.

Implication:
- LiveKit bridge currently uses a simpler conversational path than local `voice` mode (which uses tools through `agent_chat`).

---

## 3) Core Brain and Agent Logic

### `brain.py`

Provides:

- `chat(user_input)` -> non-streaming LLM request via Ollama.
- `chat_streaming_reply(user_input)` -> stream accumulation helper.
- `run_voice_loop()` -> standalone local Jarvis-like loop:
  - waits for wake word (`voice.wakeword.wait_for_wake_word`)
  - acknowledges with `speak('Yes?')`
  - records user utterance (`voice.listen.listen`)
  - uses `agent_chat` for tool-capable response
  - supports confirmation roundtrips for high-risk actions

Key note:
- `run_voice_loop()` is the most "Jarvis-like" path in behavior, but it is separate from LiveKit UI path.

### `agent.py`

LangChain tool-calling agent:

- LLM backend: `ChatOllama(model="llama3.2:3b")`
- Tools include:
  - web search
  - document retrieval
  - long-term memory read/write
  - system control
  - project-scoped file operations
- Maintains short-term history by converting memory messages into LangChain messages.

Key note:
- Strong capability foundation exists here.
- Not currently wired to `api_server.py` by default.

---

## 4) Memory Subsystem

### `memory/short_term.py`

- Deque-backed bounded memory (`DEFAULT_MAX_MESSAGES=32`)
- Singleton `memory` used by brain/agent.

### `memory/long_term.py`

- Chroma persistent DB in `data/chroma_db`
- Collection: `rafiqi_memory`
- Embeddings: `all-MiniLM-L6-v2`
- APIs:
  - `save_memory(text, metadata)`
  - `recall(query, n_results)`
  - `recall_texts(query, n_results)`

Current state:
- Functional semantic memory primitive is implemented.

---

## 5) RAG Subsystem

### `rag/loader.py`

- Ingests `.pdf`, `.txt`, `.docx`
- Chunks with `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)`
- Writes to shared vector store.

### `rag/retriever.py`

- Chroma collection `documents`
- Embeddings via Ollama `nomic-embed-text`
- APIs:
  - `retrieve_documents(question, k)`
  - `retrieve_context(question, k)`

Current state:
- Ingestion/retrieval pipeline exists; production quality depends on document curation and index lifecycle practices.

---

## 6) Voice Primitives (Local Standalone Path)

### `voice/wakeword.py`

- Uses `openwakeword` with default `WAKE_WORD = "hey jarvis"`.
- Streams from microphone with PyAudio at 16k.

### `voice/listen.py`

- Records microphone audio via `sounddevice`.
- Transcribes with `faster_whisper` (`base.en`, CPU int8).

### `voice/speak.py`

- TTS via `piper` CLI, optional config file.
- Plays generated wav via `sounddevice` (or `aplay` on Linux).

Current state:
- Local voice loop stack exists and is coherent.
- Separate from LiveKit-based conversation path.

---

## 7) LiveKit Bridge Agent

### `livekit_agent.py`

Primary responsibilities:

- Loads env vars (from `frontend/.env.local` and root `.env.local`).
- Connects to LiveKit room as agent participant.
- Publishes local audio track for TTS.
- Listens to data packets (`data_received`).
- Parses inbound message payloads.
- Calls local brain API (`POST /chat`).
- Publishes reply back into room data.
- Converts reply to TTS and streams PCM into room track.

Important implementation details:

- Retry/backoff on room connect.
- `_parse_chat_message()` now accepts multiple payload shapes:
  - `message`, `text`, `transcript`, `utterance`, `content`, `final`
  - also nested under `payload` or `data`
- Logs inbound packet metadata to aid debugging.

Current known behavior:

- If TTS stack fails, text response path still runs (chat can still work).
- TTS depends on:
  - `piper` executable available
  - voice model/config file present
  - Python dependencies required by pip-installed piper runtime

Recent production issue encountered:
- Missing `pathvalidate` caused runtime TTS failures (`ModuleNotFoundError`).
- Dependency has now been installed in the active venv.

---

## 8) Frontend (Next.js LiveKit UI)

### App Routing and Entry

- `frontend/src/app/page.tsx`: home page with "Open Rafiqi Interface".
- `frontend/src/app/rafiqi/page.tsx`: route that renders `RafiqiClient`.
- `frontend/src/app/layout.tsx`: root providers/theme/font setup.
- `frontend/src/app/api/token/route.ts`: mints room tokens using `livekit-server-sdk`.

### Session and Room Connection

### `frontend/src/app/rafiqi/RafiqiClient.tsx`

- Fetches token from `/api/token`.
- Connects via `LiveKitRoom`.
- Initializes session context via `SessionProvider`.
- Renders `AgentSessionView_01` with Aura visualizer enabled.

### Main Session UI

### `frontend/src/components/agent-session-block.tsx`

- Orchestrates top-level assistant session UI:
  - transcript panel
  - tile area
  - control bar
  - pre-connect shimmer message

### Visual Layer

- `audio-visualizer.tsx`
- `tile-view.tsx`
- `agent-audio-visualizer-*.tsx`
- hooks under `src/hooks/use-agent-audio-visualizer-*.ts`

These files render reactive visual states based on voice assistant tracks and state.

### Controls and Voice Triggering

### `frontend/src/components/agent-control-bar.tsx`

Core control logic:

- Mic/cam/screenshare toggles
- Chat input
- Disconnect
- LiveKit chat send path (`useChat().send`)

Recent additions:

- Browser speech recognition integration (`SpeechRecognition` / `webkitSpeechRecognition`)
- Wake word detection (`hey jarvis`)
- Wake window flow:
  - wake phrase detected -> status changes to "wake heard, speak command"
  - next utterance in window gets sent
- Direct greeting trigger when only wake word is spoken:
  - sends a short greeting prompt message automatically
- Basic speech status display in UI:
  - `unsupported | idle | listening | wake-armed | error`

Current caveat:
- Browser speech recognition support differs by browser and environment.
- This frontend wake-word approach is browser-dependent and not yet server-grade deterministic.

---

## 9) Tooling Surface (System + File)

### System tools

- `tools/system.py`: low-level operations (processes, apps, GUI automation, screenshots, system summary).
- `tools/system_control.py`: LangChain wrappers with confirmation protocols.

### File tools

- `tools/files.py`: path-restricted file operations locked to repo root.
- `tools/file_control.py`: LangChain wrappers with confirmation for write/move/copy.

### Search utility

- `tools/search.py`: web search via DuckDuckGo.

Security posture:

- Confirmation-first pattern for risky actions.
- Project-root lock for file manipulation.
- This is a good foundation but still needs stronger policy gating for "Jarvis mode" in production.

---

## Current Working State (As Implemented)

What currently works:

- Backend API starts and responds.
- LiveKit agent connects and receives data messages.
- Frontend connects to room and renders Aura UI.
- Wake word event in browser now updates status and can dispatch messages.
- Bridge payload parsing is more robust than before.

What is partially working:

- End-to-end voice turn from wake word to audible assistant response is inconsistent.
- TTS path had dependency/runtime failures in prior run; fixed in current venv but needs stability verification.

What is unstable:

- Frontend route intermittently 404s under some Next dev sessions (likely dev server state/cache issue).
- Build/lint commands appear slow/hanging in this environment, reducing confidence in dev feedback loop.

---

## Known Gaps vs Jarvis Target

1. **Single coherent voice architecture is not yet finalized**
   - Two pathways exist:
     - local standalone voice loop (`main.py voice`)
     - LiveKit/browser speech path
   - Behavior and capability are not fully unified.

2. **Wake-word acknowledgment contract is not centralized**
   - Greeting behavior is currently injected from frontend prompt.
   - Should be owned by a dedicated conversation policy layer.

3. **`/chat` uses `brain.chat`, not `agent_chat`**
   - LiveKit path may miss advanced tool routing available in local voice mode.

4. **TTS reliability and dependency hardening incomplete**
   - Need explicit startup health checks and actionable failure reporting.

5. **No explicit assistant state machine**
   - Should formalize: idle -> wake_detected -> listening -> thinking -> speaking -> followup_window.

6. **Observability is still log-centric**
   - Need health endpoint/status panel and metrics for:
     - STT events
     - wake detections
     - API latency
     - TTS synthesis latency/errors
     - room publish/subscribe status

7. **Conversation quality controls**
   - No interruption handling/barge-in strategy.
   - No robust endpointing/silence detection policy for live conversation.
   - No explicit persona policy layer for "Jarvis tone consistency."

8. **Frontend route/dev workflow reliability**
   - Intermittent `/rafiqi` 404 under dev must be stabilized.

---

## What Should Be Done Next (Priority Roadmap)

## Phase 1: Stabilize Current Stack (Must Do)

1. Add startup health checks:
   - verify piper binary, model, config, and synth test sentence
   - verify brain API reachability
   - print clear startup status summary
2. Add `/health` endpoint in API with dependency status.
3. Add frontend status panel:
   - connected/disconnected
   - wake listening state
   - last transcript sent
   - last agent response received
4. Fix/diagnose intermittent `/rafiqi` 404 in dev path.
5. Add integration smoke test script:
   - send synthetic room data message
   - assert bridge receives
   - assert API reply
   - assert data publish back

## Phase 2: Unify Intelligence Path (Very Important)

1. Decide whether `/chat` should call:
   - `brain.chat` (simple) or
   - `agent.agent_chat` (tool-capable Jarvis behavior)
2. If using `agent_chat`, enforce confirmation and safety policy for tool actions in voice mode.
3. Introduce a central "conversation policy" module:
   - wake-word greeting strategy
   - short responses by default
   - follow-up prompts
   - interruption/retry behavior

## Phase 3: Jarvis-Grade Voice Interaction

1. Implement explicit assistant state machine.
2. Add response interruption and barge-in handling.
3. Add low-latency streaming response option:
   - stream partial text and incremental TTS chunks where possible.
4. Add robust fallback STT strategy:
   - browser STT fallback to local/service STT when unsupported.

## Phase 4: Capability Expansion

1. Personal profile memory and preference learning.
2. Task and schedule abstraction layer.
3. Tool execution audit log and reversible actions where possible.
4. Optional "mission modes" (coding mode, research mode, system admin mode).

---

## Suggested Immediate Engineering Decisions

1. **Pick one primary conversational runtime for production:**
   - Option A: LiveKit UI as primary (recommended for modern UX)
   - Option B: local standalone `main.py voice` as primary
2. **Wire `/chat` to a single canonical orchestrator** so all channels share behavior.
3. **Define "Jarvis behavior contract" in code** (greeting style, brevity, confidence rules, escalation).

Without these decisions, features may keep diverging by runtime path.

---

## Operational Runbook (Current)

Typical startup:

1. `python main.py api`
2. `python main.py agent`
3. `cd frontend && npm run dev`
4. open `/rafiqi`, connect, enable mic, say wake word.

If no voice output:

1. Check agent logs for `[agent] recv` and `[agent] user`.
2. Check for `[agent] TTS failed`.
3. Validate piper model/config path and dependencies.
4. Confirm browser speech support and voice status in UI.

---

## Summary

RAFIQI now has a strong multi-layer foundation:

- local intelligence/runtime modules,
- memory and retrieval primitives,
- tool-calling infrastructure,
- LiveKit UI bridge with Aura.

The next critical step is not "more features" first; it is **system unification and reliability hardening** so every wake-word interaction consistently becomes an intelligent spoken response. Once that is stable, Jarvis-grade polish and capability scaling can be added with confidence.

# RAFIQI Implementation Document

## 1) Vision and Target Behavior

RAFIQI is being built as a local-first, Jarvis-style assistant with:

- Always-available voice interaction
- Wake-word activation ("Hey Jarvis")
- Conversational memory and context
- Tool execution (system + file operations) with safety controls
- Rich visual interface (LiveKit + Aura visualizer)
- Low-latency spoken responses

The end goal is not a generic chatbot UI, but a proactive, reliable, personality-driven assistant that can listen, reason, act, and speak naturally.

---

## 2) Current Architecture (High-Level)

The project currently has two main execution modes plus one bridge:

1. Local standalone voice loop (single process):
   - Wake-word -> local STT -> local agent -> local TTS
   - Entry: `python main.py voice`

2. Web Agent UI mode (multi-process):
   - Frontend (Next.js + LiveKit) for UI/mic/chat
   - Local brain API for model response
   - LiveKit bridge agent for room participation + TTS
   - Entry processes:
     - `python main.py api`
     - `python main.py agent`
     - `npm run dev` in `frontend`

3. LiveKit bridge process (critical in UI mode):
   - Joins room
   - Reads room data packets (chat-style payloads)
   - Calls local brain API
   - Publishes text reply + synthesized audio track

---

## 3) Repository File Map (Major Files and Their Roles)

## Core Entrypoints

- `main.py`
  - Unified CLI entrypoint with explicit modes:
    - `voice` -> local wake-word loop
    - `api` -> FastAPI server
    - `agent` -> LiveKit bridge agent
  - Prevents accidental microphone conflicts by separating modes.

- `api_server.py`
  - FastAPI app exposing `POST /chat`
  - Request format: `{ "text": "..." }`
  - Response format: `{ "reply": "..." }`
  - Calls `brain.chat()`.

- `livekit_agent.py`
  - LiveKit participant named `rafiqi-agent` (default identity).
  - Loads LiveKit credentials from env / `frontend/.env.local`.
  - Receives room data messages, parses user utterance text, queues messages.
  - Calls local brain API and publishes reply back to room as data.
  - Synthesizes speech with Piper and streams PCM frames into LiveKit audio track.

## Brain / Reasoning / Agent Layer

- `brain.py`
  - Defines system prompt and non-streaming model call (`ollama.chat`).
  - Maintains short-term memory.
  - Provides standalone voice loop path:
    - `wait_for_wake_word()` -> `listen()` -> `agent_chat()` -> `speak()`.
  - Handles a simple confirmation protocol (`CONFIRM_ACTION:`).

- `agent.py`
  - LangChain tool-calling agent (`create_tool_calling_agent`).
  - Uses `ChatOllama(model="llama3.2:3b")`.
  - Registers tools from:
    - web search
    - RAG retrieval
    - long-term memory
    - system control
    - file control
  - Converts short-term memory history into LangChain messages and executes.

## Voice Pipeline (Standalone Mode)

- `voice/wakeword.py`
  - Uses `openwakeword` + `pyaudio` to detect "hey jarvis".
  - Blocking loop waiting for threshold hit.

- `voice/listen.py`
  - Records audio via `sounddevice`.
  - Transcribes via `faster_whisper` (`base.en`, CPU int8).

- `voice/speak.py`
  - TTS via `piper` CLI into temp WAV.
  - Plays WAV with `sounddevice` on non-Linux.

## Memory and RAG

- `memory/short_term.py`
  - In-memory bounded deque (default 32 messages).
  - Singleton `memory` used across brain/agent flow.

- `memory/long_term.py`
  - Persistent semantic memory with ChromaDB.
  - Embeddings via `SentenceTransformerEmbeddingFunction` (`all-MiniLM-L6-v2`).

- `rag/retriever.py`
  - Document vector retrieval using LangChain Chroma + `OllamaEmbeddings` (`nomic-embed-text`).

- `rag/loader.py`
  - Document ingestion/chunking (`pdf`, `txt`, `docx`) into RAG store.

## Tooling (Agent Action Surface)

- `tools/system.py`
  - Low-level system/process/UI automation helpers (`psutil`, `pyautogui`, `subprocess`).

- `tools/system_control.py`
  - LangChain-safe wrappers over `tools/system.py`.
  - Adds confirmation-first behavior for high-risk actions.

- `tools/files.py`
  - Root-locked file operations (read/write/append/list/find/copy/move) under repo path.

- `tools/file_control.py`
  - LangChain tool wrappers over `tools/files.py` with confirm pattern.

- `tools/search.py`
  - DuckDuckGo search utility (`duckduckgo_search`).

## Frontend (Agent UI)

- `frontend/src/app/page.tsx`
  - Home page with "Open Rafiqi Interface" link to `/rafiqi`.

- `frontend/src/app/rafiqi/page.tsx`
  - Route entry rendering `RafiqiClient`.

- `frontend/src/app/rafiqi/RafiqiClient.tsx`
  - Connect form + LiveKit room setup.
  - Fetches token from `/api/token`.
  - Wraps session provider and renders `AgentSessionView_01`.

- `frontend/src/app/api/token/route.ts`
  - Mints LiveKit participant JWT using server env vars.
  - Grants publish/subscribe/data for room usage.

- `frontend/src/components/agent-session-block.tsx`
  - Main session shell:
    - transcript area
    - tile/visualizer layout
    - bottom control bar

- `frontend/src/components/agent-control-bar.tsx`
  - Mic/cam/share/chat/disconnect controls.
  - Text chat send using `useChat().send`.
  - Added wake-word speech recognition bridge (browser speech API):
    - listens when connected + mic enabled
    - detects "hey jarvis"
    - forwards utterances to chat channel
    - voice status indicator

- `frontend/src/components/audio-visualizer.tsx`
  - Visualizer variants (aura/wave/grid/radial/bar) driven by `useVoiceAssistant()`.

- `frontend/src/components/tile-view.tsx`
  - Layout logic for agent tile and local camera/screenshare tile.

---

## 4) Runtime Flows (How Pieces Connect)

## A) Standalone Voice Mode (`python main.py voice`)

1. `main.py` -> `brain.run_voice_loop()`
2. `wait_for_wake_word()` waits for "hey jarvis"
3. `listen()` captures command and transcribes text
4. `agent_chat()` invokes LangChain + tools + memory
5. `speak()` outputs response through Piper

This is the most direct Jarvis-like loop today.

## B) Agent UI Mode (multi-process)

Processes:
- Frontend (`npm run dev`)
- API (`python main.py api`)
- Bridge (`python main.py agent`)

Flow:
1. UI gets token from `/api/token` and joins LiveKit room.
2. User utterance is converted to text client-side (speech recognition path) or typed manually.
3. UI sends text via LiveKit chat/data.
4. `livekit_agent.py` receives data packet, parses payload, queues message.
5. Bridge calls `POST http://localhost:8000/chat`.
6. API calls `brain.chat()`, returns reply.
7. Bridge publishes reply as data packet and (if TTS available) streams synthesized audio into room.
8. UI transcript updates; Aura reacts to incoming assistant audio.

---

## 5) What Has Been Implemented Recently

1. LiveKit payload parsing hardening (`livekit_agent.py`)
   - Accepts multiple payload keys (`message`, `text`, `transcript`, etc.)
   - Accepts nested payload/data objects
   - Logs inbound packet topic/sender/message preview

2. Frontend wake-word bridge (`frontend/src/components/agent-control-bar.tsx`)
   - Added browser speech recognition integration
   - Wake phrase detection ("hey jarvis")
   - Wake-window behavior for follow-up command
   - Status display (`listening`, `wake-armed`, `error`, `unsupported`)

3. Wake-only greeting trigger
   - Saying only wake phrase now sends a greeting instruction to agent
   - Intended to mimic assistant acknowledgment behavior

4. TTS dependency issue identified and addressed
   - Piper failed due to missing `pathvalidate`
   - Installed in local virtualenv

---

## 6) Current Known Issues / Gaps

## Critical functional gaps

1. UI mode voice response reliability still unstable
   - Wake-word detection now works in UI, but end-to-end "speak back every time" is not yet consistently reliable.
   - Failure points can include browser speech-recognition behavior, packet timing, and TTS environment readiness.

2. No unified voice orchestration contract between modes
   - Standalone voice (`brain.run_voice_loop`) and LiveKit UI voice path are separate implementations.
   - Behavior parity is not guaranteed.

3. Browser STT is implementation-dependent
   - Current UI wake-word path depends on browser speech APIs.
   - Cross-browser behavior differs; this is weaker than backend-controlled STT.

## Product-level Jarvis gaps

1. No proactive assistant behavior engine
   - RAFIQI currently reacts to messages; it does not schedule, monitor, or proactively assist.

2. Limited dialogue state machine
   - Wake, intent, execution, confirmation, interruption, and cancellation are not yet modeled as explicit dialogue states in UI mode.

3. Personality consistency not enforced across all channels
   - System prompt exists, but no formal response policy layer for concise "Jarvis voice" output in every pathway.

4. No robust observability dashboard
   - Logs exist, but no structured event timeline for STT -> NLU -> tools -> TTS latency and failures.

5. No automated integration tests for voice pipeline
   - No deterministic tests simulating wake-word/session flow end-to-end.

---

## 7) Remaining Work to Reach "Jarvis-Level" RAFIQI

## Phase 1: Stabilize Current Pipeline (must-do first)

1. Unify utterance ingestion in UI mode
   - Decide canonical input contract for bridge (`topic`, JSON schema).
   - Enforce in `agent-control-bar.tsx` + `livekit_agent.py`.

2. Add deterministic ack on wake
   - Guarantee immediate short acknowledgment audio after wake.
   - Implement fallback if LLM or API stalls.

3. Harden TTS execution
   - Preflight Piper binary + voice model + Python deps at startup.
   - Add graceful fallback voice path if Piper fails.

4. Add structured logs
   - Correlation IDs per turn: wake -> transcript -> sent -> received -> replied -> spoken.
   - Persist logs for postmortem.

## Phase 2: Unify Voice Intelligence Across Modes

1. Move wake/STT logic from browser-dependent path to controllable backend path (optional LiveKit worker STT).
2. Create one conversation state machine shared by:
   - standalone local mode
   - LiveKit room mode
3. Ensure same confirmation/safety behavior regardless of channel.

## Phase 3: Jarvis Personality and Capability Upgrade

1. Response style policy layer
   - fast, concise, assistant-like replies by default
   - expandable depth on demand

2. Proactive features
   - reminders, periodic checks, event-driven notifications
   - context-sensitive suggestions (non-intrusive)

3. Tool confidence and guardrails
   - explicit capability declaration
   - intent confirmation templates
   - rollback/safe undo patterns where possible

## Phase 4: Quality, Testing, and Observability

1. Integration tests
   - mocked LiveKit data path
   - API/agent/TTS functional checks

2. Voice regression tests
   - scripted wake phrase and command sequences
   - verify transcript + spoken output

3. Latency budgets and monitoring
   - per-turn budget for:
     - transcription
     - model response
     - TTS generation
     - playback start

---

## 8) File-Level Task Backlog (Practical Next Steps)

## Backend / bridge

- `livekit_agent.py`
  - Add startup diagnostics endpoint/print block for TTS readiness.
  - Add strict turn IDs and latency timings.
  - Add guaranteed wake greeting path independent of model failures.

- `api_server.py`
  - Add health route (`/health`) and model readiness check.
  - Return structured error objects.

- `brain.py`
  - Centralize response style constraints for Jarvis persona.
  - Add lightweight intent classification for faster ack responses.

## Frontend

- `frontend/src/components/agent-control-bar.tsx`
  - Refactor wake-word + recognition into dedicated hook.
  - Add explicit UI controls:
    - wake mode on/off
    - sensitivity window
    - debug transcript panel

- `frontend/src/app/rafiqi/RafiqiClient.tsx`
  - Add session diagnostics panel (token/room/agent presence/round-trip check).

- `frontend/src/components/agent-session-block.tsx`
  - Add assistant state badges:
    - idle
    - listening
    - thinking
    - speaking

## Ops / docs

- `README.md`
  - Align commands with `main.py` modes consistently.
  - Add troubleshooting matrix with known errors and fixes.

- Add run scripts (`.ps1`) for one-command startup of 3 required services.

---

## 9) Current Success Criteria vs Target

Current:
- Interface renders
- LiveKit token and room join work
- Aura visualizer works
- Data messages can reach bridge
- Brain API is reachable
- TTS path exists and can be enabled

Target (Jarvis-like):
- Wake phrase always produces immediate spoken acknowledgment
- Natural continuous turn-taking
- Reliable spoken replies every turn
- Strong safety-confirmation for actions
- Persona-consistent concise voice responses
- Proactive assistance and contextual memory behaviors

RAFIQI is partway there: architecture is in place, but voice orchestration reliability and Jarvis-grade interaction polish still require focused stabilization and unification work.
