"""Attribute, metric and operation names of the OpenTelemetry GenAI conventions.

Source: OpenTelemetry semantic conventions for GenAI spans and metrics v1.37.0
(status Development; ``gen_ai.provider.name`` replaced ``gen_ai.system``),
checked 2026-11-05.
"""

from __future__ import annotations

GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
SERVER_ADDRESS = "server.address"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_RESPONSE_ID = "gen_ai.response.id"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_TOOL_NAME = "gen_ai.tool.name"
GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call.id"
GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES = "gen_ai.output.messages"
ERROR_TYPE = "error.type"
GEN_AI_TOKEN_TYPE = "gen_ai.token.type"

TOKEN_TYPE_INPUT = "input"
TOKEN_TYPE_OUTPUT = "output"

METRIC_TOKEN_USAGE = "gen_ai.client.token.usage"
METRIC_OPERATION_DURATION = "gen_ai.client.operation.duration"
UNIT_TOKEN = "{token}"
UNIT_SECONDS = "s"

OPERATION_CHAT = "chat"
OPERATION_TEXT_COMPLETION = "text_completion"
OPERATION_EMBEDDINGS = "embeddings"
OPERATION_GENERATE_CONTENT = "generate_content"
OPERATION_EXECUTE_TOOL = "execute_tool"

LLM_OPERATIONS = frozenset(
    {
        OPERATION_CHAT,
        OPERATION_TEXT_COMPLETION,
        OPERATION_EMBEDDINGS,
        OPERATION_GENERATE_CONTENT,
    }
)
