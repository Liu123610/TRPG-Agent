"""LLM service with LangChain ChatOpenAI and native tool-calling support."""

from typing import Literal

from openai import APITimeoutError, APIConnectionError, BadRequestError
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config.settings import settings


LLMMode = Literal["narrative", "combat"]


class LLMService:
    def __init__(self) -> None:
        provider = settings.llm_provider.strip().lower()
        if provider != "openai":
            raise ValueError(f"Unsupported llm provider: {settings.llm_provider}")

        api_key = settings.llm_api_key.strip()
        if not api_key:
            raise ValueError("Missing LLM API key. Set TRPG_LLM_API_KEY in environment or .env")

        client_kwargs: dict[str, str] = {"api_key": api_key}
        base_url = settings.llm_base_url
        if base_url and base_url.strip():
            client_kwargs["base_url"] = base_url.strip()

        self._client = ChatOpenAI(
            **client_kwargs,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    # 中文注释：先保留单客户端实现，把 mode 作为稳定接口，后续可无痛分模型。
    def _get_client_for_mode(self, mode: LLMMode) -> ChatOpenAI:
        if mode not in {"narrative", "combat"}:
            raise ValueError(f"Unsupported LLM mode: {mode}")
        return self._client

    def invoke_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list,
        system_prompt: str,
        mode: LLMMode = "narrative",
    ) -> AIMessage:
        try:
            prompt_messages = [SystemMessage(content=system_prompt), *messages]
            client = self._get_client_for_mode(mode)

            # 仅在存在可用工具时启用 tool-calling，避免向上游发送空 tools 数组触发 400。
            if tools:
                runnable = client.bind_tools(tools)
                response = runnable.invoke(prompt_messages)
            else:
                response = client.invoke(prompt_messages)

            if isinstance(response, AIMessage):
                return response
            return AIMessage(content=str(getattr(response, "content", "") or ""))
        except BadRequestError as exc:
            raise ValueError(f"LLM bad request: {exc}") from exc
        except APITimeoutError as exc:
            raise RuntimeError(
                f"LLM request timed out after {settings.llm_timeout_seconds}s. "
                "Please check OPENAI_BASE_URL/network/model service status."
            ) from exc
        except APIConnectionError as exc:
            raise RuntimeError(
                "LLM connection failed. Please verify OPENAI_BASE_URL and network connectivity."
            ) from exc

