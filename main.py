"""
Unified entry point for RAFIQI.

This does NOT auto-start everything at once (to avoid conflicts like two
processes grabbing the microphone). Instead it gives you explicit modes:

    python main.py voice       # Local wake-word + voice-loop JARVIS
    python main.py api        # HTTP brain API (for external clients / LiveKit)
    python main.py agent      # LiveKit bridge agent (joins room, speaks)

If run with no args, it prints a short help message.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import NoReturn


def run_voice_mode() -> None:
  """Start the local wake-word + voice loop."""
  from brain import run_voice_loop

  run_voice_loop()


def run_api_mode(host: str, port: int) -> None:
  """Start the FastAPI HTTP brain API."""
  import uvicorn
  from api_server import app

  uvicorn.run(app, host=host, port=port)


def run_livekit_agent_mode() -> None:
  """Start the LiveKit bridge agent (async main)."""
  from livekit_agent import main as agent_main

  asyncio.run(agent_main())


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(prog="rafiqi", description="RAFIQI unified entry point")
  subparsers = parser.add_subparsers(dest="command")

  # voice
  subparsers.add_parser(
    "voice",
    help="Run local wake-word + voice-loop JARVIS",
  )

  # api
  api_parser = subparsers.add_parser(
    "api",
    help="Run HTTP brain API (FastAPI)",
  )
  api_parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
  api_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

  # livekit agent
  subparsers.add_parser(
    "agent",
    help="Run LiveKit bridge agent (connects to room, speaks replies)",
  )

  args = parser.parse_args(argv)

  if args.command == "voice":
    run_voice_mode()
    return 0
  if args.command == "api":
    run_api_mode(host=args.host, port=args.port)
    return 0
  if args.command == "agent":
    run_livekit_agent_mode()
    return 0

  parser.print_help()
  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv[1:]))