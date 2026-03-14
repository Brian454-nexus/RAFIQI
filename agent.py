from __future__ import annotations

"""LangChain agent that routes between tools (memory, RAG, web search)."""

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from memory.long_term import recall_texts, save_memory
from memory.short_term import memory as short_term_memory
from rag.retriever import retrieve_context
from tools.search import search_web as search_web_utility
from tools.system_control import SYSTEM_TOOLS
from tools.file_control import FILE_TOOLS


llm = ChatOllama(model="llama3.2:3b")


@tool
def search_web(query: str) -> str:
    """Search the web for up‑to‑date information using DuckDuckGo."""
    return search_web_utility(query)


@tool
def search_documents(question: str) -> str:
    """Search the user's loaded documents for relevant context."""
    if not question:
        return "No question provided."
    context = retrieve_context(question)
    return context or "No relevant document content found."


@tool
def search_long_term_memory(question: str) -> str:
    """Search long‑term vector memory for facts about the user or past context."""
    memories = recall_texts(question, n_results=5)
    if not memories:
        return "No relevant memories found."
    return "\n".join(f"- {m}" for m in memories)


@tool
def remember_fact(fact: str) -> str:
    """Store a fact about the user or environment into long‑term memory."""
    if not fact:
        return "No fact provided."
    memory_id = save_memory(fact)
    return f"Stored memory with id: {memory_id}"


TOOLS = [
    search_web,
    search_documents,
    search_long_term_memory,
    remember_fact,
    *SYSTEM_TOOLS,
    *FILE_TOOLS,
]


SYSTEM_INSTRUCTIONS = """You are Rafiqi, a local AI assistant.
You have access to tools for:
- Searching the web (search_web)
- Searching the user's documents (search_documents)
- Searching and updating long‑term memory (search_long_term_memory, remember_fact)
- System control (launch apps, open URLs/paths, processes, GUI, screenshot)
- Files: read_file, write_file, append_to_file, list_directory, find_files, copy_file, move_file (all paths are inside the project; write/copy/move require confirm=True when the user agrees)

Decide when to call tools based on the user's request. For file or system actions that change state, ask for confirmation first, then call the tool again with confirm=True once the user agrees.
When responding, be concise and conversational."""


prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_INSTRUCTIONS),
        MessagesPlaceholder("messages"),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)

agent = create_tool_calling_agent(llm, TOOLS, prompt)
agent_executor = AgentExecutor(agent=agent, tools=TOOLS)


def agent_chat(user_input: str) -> str:
    """Run the LangChain agent on the given user input."""
    # Build history from short‑term memory
    history_msgs = []
    for m in short_term_memory.get_messages():
        role = m.get("role")
        content = m.get("content", "")
        if not content:
            continue
        if role == "user":
            history_msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            history_msgs.append(AIMessage(content=content))

    # Add the new user message
    history_msgs.append(HumanMessage(content=user_input))

    try:
        result = agent_executor.invoke({"messages": history_msgs})
        reply = result.get("output", "")
    except Exception as e:
        reply = f"Sorry, something went wrong while running the agent: {e}"

    # Update short‑term memory
    short_term_memory.add("user", user_input)
    short_term_memory.add("assistant", reply)

    return reply

