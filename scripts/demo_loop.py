import asyncio
import json
from pathlib import Path

from agents import Agent, WebSearchTool, function_tool, run_demo_loop, set_tracing_disabled, set_trace_processors
from agents.models.openai_responses import OpenAIResponsesModel
from agents.tracing.processors import default_processor
from openai import AsyncOpenAI

from ai_tutor.system import TutorSystem

async def main():
    system = TutorSystem.from_config(None)     # loads config/default.yaml, uses OPENAI_API_KEY
    learner_id = "demo_learner"
    model_name = system.settings.model.name
    openai_client = AsyncOpenAI()

    set_tracing_disabled(False)
    set_trace_processors([default_processor()])

    @function_tool
    def ingest_corpus(directory: str) -> str:
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return json.dumps({"error": f"{directory} does not exist"})
        result = system.ingest_directory(path)
        payload = {
            "documents_ingested": len(result.documents),
            "chunks_created": len(result.chunks),
            "skipped_files": [str(item) for item in result.skipped],
        }
        return json.dumps(payload)

    @function_tool
    def answer_question(question: str, mode: str = "learning") -> str:
        response = system.answer_question(learner_id=learner_id, question=question, mode=mode)
        payload = {
            "answer": response.answer,
            "citations": response.citations,
            "style": response.style,
            "difficulty": response.difficulty,
            "next_topic": response.next_topic,
        }
        return json.dumps(payload)

    tutor_agent = Agent(
        name="TutorAnswerAgent",
        instructions=(
            "You answer learner questions using the available tools. "
            "Use answer_question to consult the local corpus; if that tool returns no evidence, "
            "call web_search and cite the returned URLs."
        ),
        model=OpenAIResponsesModel(model=model_name, openai_client=openai_client),
        tools=[answer_question, WebSearchTool()],
    )

    print("Interactive tutor session. Type 'quit' to exit.")
    await run_demo_loop(tutor_agent)

if __name__ == "__main__":
    asyncio.run(main())
