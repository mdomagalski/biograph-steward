"""Optional NeMo Agent Toolkit registration; never imported by the core app."""
import asyncio
import json

from nat.plugin_api import Builder, FunctionBaseConfig, FunctionInfo, register_function
from pydantic import Field

from .portability import BoundedQuestionWorkflow


class BioGraphQuestionConfig(FunctionBaseConfig, name='biograph_question'):
    source_run: str = Field(description='Fixed saved BioGraph source run; users supply only a question.')
    max_results: int = Field(default=8, ge=1, le=30)
    max_paths: int = Field(default=3, ge=1, le=5)


@register_function(config_type=BioGraphQuestionConfig)
async def biograph_question(config: BioGraphQuestionConfig, builder: Builder):
    workflow = BoundedQuestionWorkflow(config.source_run, max_results=config.max_results, max_paths=config.max_paths)

    async def respond(input_message: str) -> str:
        """Answer one scoped evidence question with a validated read-only plan and source trace."""
        result = await asyncio.to_thread(workflow.run, input_message)
        return json.dumps(result, ensure_ascii=True, allow_nan=False)

    yield FunctionInfo.from_fn(respond, description=respond.__doc__)
