# Main brain module for Rafiqi, integrating LLM, RAG, voice and conversation logic
import ollama
from voice.listen import listen
from voice.speak import speak
from voice.wakeword import wait_for_wake_word
from memory.short_term import memory as short_term_memory
from agent import agent_chat
 
MODEL = 'llama3.2:3b'
 
SYSTEM_PROMPT = """
IDENTITY
You are Rafiqi, an intelligent personal AI assistant running locally on the user's computer.
You are fast-thinking, highly capable, and designed to help with technical tasks, learning, and problem solving.

PERSONALITY
You are:
- Intelligent and resourceful
- Friendly and approachable
- Slightly playful and curious, like a clever guide
- Calm, confident, and efficient

You never sound robotic or overly formal.

COMMUNICATION STYLE
- You are a voice assistant, so keep responses concise and natural.
- Prefer short explanations unless the user asks for more detail.
- Speak clearly and conversationally.
- Avoid unnecessary filler words.

INTELLIGENCE GUIDELINES
When answering:
1. Prioritize accuracy.
2. Use logical reasoning when solving problems.
3. If unsure, say so instead of guessing.
4. Ask clarifying questions when needed.
5. Break complex problems into simple steps.

CONTEXT AWARENESS
- You remember the conversation history and use it to improve responses.
- You adapt to the user's goals and preferences.
- You remain focused on the user's request.

SYSTEM CONTEXT
- You run locally on the user's machine.
- You respect privacy and do not assume internet access unless told.
- Your purpose is to assist quickly and intelligently.

CORE GOAL
Help the user accomplish tasks efficiently while making the interaction feel natural, intelligent, and enjoyable.
"""
def chat(user_input: str) -> str:
    """Non-streaming chat helper using the configured model."""
    short_term_memory.add('user', user_input)

    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                *short_term_memory.get_messages(),
            ],
        )
    except ollama.ResponseError as e:
        reply = f"Sorry, I ran into an error talking to the model: {e.error}"
        short_term_memory.add('assistant', reply)
        return reply
    except Exception:
        # Fallback for unexpected errors
        reply = "Sorry, something went wrong while generating a response."
        short_term_memory.add('assistant', reply)
        return reply

    reply = response['message']['content']
    short_term_memory.add('assistant', reply)
    return reply


def chat_streaming_reply(user_input: str) -> str:
    """
    Streaming chat helper.

    Uses Ollama's stream=True API, accumulates chunks into a single reply
    so callers (like voice) can keep using a simple string response.
    """
    short_term_memory.add('user', user_input)

    try:
        stream = ollama.chat(
            model=MODEL,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                *short_term_memory.get_messages(),
            ],
            stream=True,
        )

        reply_chunks = []
        for chunk in stream:
            content = chunk.get('message', {}).get('content', '')
            if content:
                reply_chunks.append(content)

        reply = ''.join(reply_chunks).strip()

    except ollama.ResponseError as e:
        reply = f"Sorry, I ran into an error talking to the model: {e.error}"
    except Exception:
        reply = "Sorry, something went wrong while generating a response."

    short_term_memory.add('assistant', reply)
    return reply
 
def run_voice_loop():
    """Main voice interaction loop."""
    speak('Rafiqi online. Ready.')

    while True:
        wait_for_wake_word()      # Wait for 'Hey JARVIS'
        speak('Yes?')             # Acknowledge
        user_text = listen(5)     # Record 5 seconds

        if not user_text:
            continue
        if 'goodbye' in user_text.lower():
            speak('Goodbye.')
            break

        # Let the LangChain agent decide which tools to use.
        response = agent_chat(user_text)

        # Simple confirmation handler for high‑risk actions.
        # If a tool response starts with the special CONFIRM prefix, ask
        # the user for explicit approval before continuing the dialogue.
        if response.startswith('CONFIRM_ACTION:'):
            speak('I need your confirmation before doing that.')
            speak(response.removeprefix('CONFIRM_ACTION:').strip())
            speak('Should I proceed? Say yes or no.')
            answer = listen(4) or ''
            answer_lower = answer.lower()
            if any(word in answer_lower for word in ('yes', 'yeah', 'sure', 'go ahead', 'do it')):
                # The actual execution is done by the tools when called
                # with confirm=True. The agent will see this confirmation
                # and can recall the same tool with confirm=True.
                confirm_msg = (
                    'The user explicitly confirmed the last action. '
                    'If you proposed a system action requiring confirmation, '
                    're‑invoke the same tool with confirm=True.'
                )
                follow_up = agent_chat(confirm_msg)
                speak(follow_up)
                continue
            else:
                speak('Okay, I will not perform that action.')
                continue

        speak(response)