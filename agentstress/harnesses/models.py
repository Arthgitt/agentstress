"""Model clients for each framework, for both backends.

The Ollama branches construct exactly what the harnesses built before Phase 1d,
so Phase 1 runs are unchanged. The OpenAI branches use the same temperature and
the Chat Completions API for all three frameworks, keeping the transport
identical across frameworks as it was on Ollama.
"""
from __future__ import annotations

import os

import agentstress.run_config as rc


def model_label() -> str:
    return rc.OPENAI_MODEL if rc.PROVIDER == "openai" else rc.OLLAMA_MODEL


def langchain_chat_model():
    if rc.PROVIDER == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=rc.OPENAI_MODEL, temperature=rc.TEMPERATURE,
                          base_url=rc.OPENAI_BASE_URL, api_key=os.environ["OPENAI_API_KEY"])
    from langchain_ollama import ChatOllama

    return ChatOllama(model=rc.OLLAMA_MODEL, temperature=rc.TEMPERATURE, base_url=rc.OLLAMA_BASE_URL)


def crewai_llm():
    from crewai import LLM

    if rc.PROVIDER == "openai":
        return LLM(model=f"openai/{rc.OPENAI_MODEL}", temperature=rc.TEMPERATURE,
                   base_url=rc.OPENAI_BASE_URL, api_key=os.environ["OPENAI_API_KEY"])
    return LLM(model=f"ollama/{rc.OLLAMA_MODEL}", base_url=rc.OLLAMA_BASE_URL, temperature=rc.TEMPERATURE)


_clients: dict = {}


def openai_agents_model():
    from agents import AsyncOpenAI, OpenAIChatCompletionsModel

    if rc.PROVIDER == "openai":
        base, key, name = rc.OPENAI_BASE_URL, os.environ["OPENAI_API_KEY"], rc.OPENAI_MODEL
    else:
        # Ollama ignores the key but the client requires a non-empty one.
        base, key, name = rc.OLLAMA_OPENAI_BASE_URL, "ollama", rc.OLLAMA_MODEL
    if base not in _clients:
        _clients[base] = AsyncOpenAI(base_url=base, api_key=key)
    return OpenAIChatCompletionsModel(model=name, openai_client=_clients[base])
