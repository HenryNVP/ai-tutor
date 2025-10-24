from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional

from ai_tutor.agents.llm_client import LLMClient
from ai_tutor.agents.tutor import TutorAgent, TutorResponse
from ai_tutor.config import Settings, load_settings
from ai_tutor.ingestion import IngestionPipeline
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.learning import PersonalizationManager, ProgressTracker, QuizService
from ai_tutor.learning.quiz import Quiz, QuizEvaluation
from ai_tutor.retrieval import create_vector_store
from ai_tutor.retrieval.retriever import Retriever
from ai_tutor.search.tool import SearchTool
from ai_tutor.storage import ChunkJsonlStore
from ai_tutor.utils.files import collect_documents
from ai_tutor.utils.logging import configure_logging

logger = logging.getLogger(__name__)


class TutorSystem:
    """
    Main facade coordinating all tutoring system components.
    
    This class provides a high-level API for the entire AI tutoring system,
    wiring together ingestion, retrieval, generation, personalization, and
    assessment components. It serves as the primary entry point for both
    CLI and web interfaces.
    
    The system follows a configuration-driven design where all parameters
    (model names, chunking settings, retrieval thresholds) are defined in
    config/default.yaml and loaded via the Settings object.
    
    Architecture
    ------------
    - Document Ingestion: PDF/Markdown → Chunks → Embeddings → Vector Store
    - Question Answering: Query → Retrieval → LLM → Cited Answer
    - Assessment: Topic → Context Retrieval → Quiz Generation → Evaluation
    - Personalization: Interaction History → Profile Updates → Adaptive Difficulty
    
    Attributes
    ----------
    settings : Settings
        Configuration object loaded from YAML, containing all system parameters.
    embedder : EmbeddingClient
        Sentence transformer for encoding queries and documents (BAAI/bge-base-en).
    vector_store : VectorStore
        Indexed vector database for similarity search (FAISS or ChromaDB).
    chunk_store : ChunkJsonlStore
        JSONL storage for document chunks with metadata.
    progress_tracker : ProgressTracker
        Manager for learner profile persistence and updates.
    personalizer : PersonalizationManager
        Adaptive learning coordinator that adjusts difficulty and selects styles.
    llm_client : LLMClient
        OpenAI API client for text generation (GPT-4o-mini by default).
    search_tool : SearchTool
        Web search interface for non-local queries (DuckDuckGo).
    quiz_service : QuizService
        Assessment generator and evaluator with RAG-based question creation.
    ingestion_pipeline : IngestionPipeline
        Document processing workflow (parse → chunk → embed → store).
    tutor_agent : TutorAgent
        Multi-agent orchestrator that handles query routing and response generation.
    
    Examples
    --------
    >>> # Initialize from default config
    >>> system = TutorSystem.from_config(api_key="sk-...")
    >>> 
    >>> # Ingest course materials
    >>> from pathlib import Path
    >>> system.ingest_directory(Path("data/raw"))
    >>> 
    >>> # Ask a question
    >>> response = system.answer_question(
    ...     learner_id="student123",
    ...     question="What is the derivative of x^2?",
    ...     mode="learning"
    ... )
    >>> print(response.answer)
    >>> print(response.citations)
    >>> 
    >>> # Generate a quiz
    >>> quiz = system.generate_quiz(
    ...     learner_id="student123",
    ...     topic="derivatives",
    ...     num_questions=4
    ... )
    >>> 
    >>> # Evaluate quiz submission
    >>> evaluation = system.evaluate_quiz(
    ...     learner_id="student123",
    ...     quiz_payload=quiz,
    ...     answers=[2, 0, 1, 3]  # Selected choice indices
    ... )
    >>> print(f"Score: {evaluation.score:.0%}")
    """

    def __init__(self, settings: Settings, api_key: Optional[str] = None):
        """
        Initialize the tutoring system with all required components.
        
        This constructor creates and wires together all system dependencies,
        including embedders, vector stores, LLM clients, and agent orchestrators.
        All configuration is loaded from the provided Settings object.
        
        Parameters
        ----------
        settings : Settings
            Configuration object containing model parameters, paths, and thresholds.
            Typically loaded from config/default.yaml via load_settings().
        api_key : Optional[str], default=None
            OpenAI API key for LLM access. If None, attempts to read from
            OPENAI_API_KEY environment variable.
        
        Raises
        ------
        ValueError
            If API key is not provided and OPENAI_API_KEY env var is not set.
        FileNotFoundError
            If vector store directory or chunk index doesn't exist during load.
        """
        self.settings = settings
        configure_logging(settings.logging.level, settings.logging.use_json)

        # Initialize core embedding and storage infrastructure
        self.embedder = EmbeddingClient(settings.embeddings, api_key=api_key)
        self.vector_store = create_vector_store(settings.paths.vector_store_dir)
        self.chunk_store = ChunkJsonlStore(settings.paths.chunks_index)
        
        # Initialize learner tracking and personalization
        self.progress_tracker = ProgressTracker(settings.paths.profiles_dir)
        self.personalizer = PersonalizationManager(self.progress_tracker)
        
        # Initialize LLM and web search clients
        self.llm_client = LLMClient(settings.model, api_key=api_key)
        self.search_tool = SearchTool(model=settings.model.name, api_key=api_key)
        
        # Build quiz service with dedicated retriever instance
        quiz_retriever = Retriever(settings.retrieval, embedder=self.embedder, vector_store=self.vector_store)
        self.quiz_service = QuizService(
            retriever=quiz_retriever,
            llm_client=self.llm_client,
            progress_tracker=self.progress_tracker,
        )

        # Build document ingestion pipeline
        self.ingestion_pipeline = IngestionPipeline(
            settings=settings,
            embedder=self.embedder,
            vector_store=self.vector_store,
            chunk_store=self.chunk_store,
        )
        
        # Build multi-agent tutor orchestrator
        self.tutor_agent = TutorAgent(
            retrieval_config=settings.retrieval,
            embedder=self.embedder,
            vector_store=self.vector_store,
            search_tool=self.search_tool,
            ingest_directory=self.ingest_directory,
            session_db_path=settings.paths.processed_data_dir / "sessions.sqlite",
            quiz_service=self.quiz_service,
        )

    @classmethod
    def from_config(cls, config_path: str | Path | None = None, api_key: Optional[str] = None) -> "TutorSystem":
        """
        Factory method to construct a TutorSystem from configuration file.
        
        This is the recommended way to initialize the system. It loads settings
        from YAML, creates all necessary directories, and returns a fully
        configured TutorSystem instance ready for use.
        
        Parameters
        ----------
        config_path : str | Path | None, default=None
            Path to YAML configuration file. If None, searches for config/default.yaml
            in the project root. Can be absolute or relative to current directory.
        api_key : Optional[str], default=None
            OpenAI API key. If None, reads from OPENAI_API_KEY environment variable.
        
        Returns
        -------
        TutorSystem
            Fully initialized system with all components wired and ready.
        
        Raises
        ------
        FileNotFoundError
            If config_path is specified but doesn't exist.
        ValueError
            If required configuration fields are missing or invalid.
        
        Examples
        --------
        >>> # Use default config
        >>> system = TutorSystem.from_config(api_key="sk-...")
        >>> 
        >>> # Use custom config
        >>> system = TutorSystem.from_config(
        ...     config_path="configs/production.yaml",
        ...     api_key="sk-..."
        ... )
        """
        # Load settings from YAML configuration
        settings = load_settings(config_path)
        
        # Ensure all required directories exist
        settings.paths.processed_data_dir.mkdir(parents=True, exist_ok=True)
        settings.paths.raw_data_dir.mkdir(parents=True, exist_ok=True)
        settings.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        settings.paths.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        return cls(settings, api_key=api_key)

    def ingest_directory(self, directory: Path):
        """
        Ingest every supported document under a directory and persist the resulting chunks.

        Uses `collect_documents` to gather PDFs/Markdown/TXT files, then hands the paths to
        `IngestionPipeline.ingest_paths`, which parses, chunks, embeds, and stores them via
        `ChunkJsonlStore` and `SimpleVectorStore`. Logs a summary before returning the pipeline result.
        """
        documents = collect_documents(directory)
        logger.info("Found %s documents to ingest.", len(documents))
        result = self.ingestion_pipeline.ingest_paths(documents)
        return result

    def answer_question(
        self,
        learner_id: str,
        question: str,
        mode: str = "learning",
        extra_context: Optional[str] = None,
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> TutorResponse:
        """
        Generate a personalized, cited answer to a student's question.
        
        This is the primary interface for question-answering. It orchestrates the
        entire Q&A flow: loading learner profiles, selecting explanation styles,
        routing to appropriate agents, generating answers, and updating progress.
        
        The method supports streaming responses via the on_delta callback, enabling
        real-time display of generated text. After answering, it updates the learner's
        profile with domain-specific progress and recommends next topics.
        
        Parameters
        ----------
        learner_id : str
            Unique identifier for the learner. Used to load/save profile and manage
            conversation sessions. New learners get default profiles automatically.
        question : str
            The student's question. Can be STEM content (routed to QA agent), current
            events (routed to web agent), or system queries (handled by orchestrator).
        mode : str, default="learning"
            Interaction mode. "learning" provides detailed explanations, "review"
            is more concise. Currently not fully utilized but reserved for future use.
        extra_context : Optional[str], default=None
            Additional context from uploaded documents. Injected into retrieval
            prompt to enable temporary knowledge expansion without full ingestion.
        on_delta : Optional[Callable[[str], None]], default=None
            Streaming callback invoked with each generated token. Enables real-time
            response display in web UI. If None, returns complete answer only.
        
        Returns
        -------
        TutorResponse
            Structured response containing:
            - answer: Generated text with citation markers [1], [2], etc.
            - hits: Raw retrieval results (chunks + scores)
            - citations: Formatted references with titles, docs, and pages
            - style: Explanation style used ("scaffolded", "stepwise", "concise")
            - next_topic: Suggested next topic based on knowledge gaps
            - difficulty: Current difficulty level for this domain
            - source: Answer origin ("local", "web", "quiz", or None)
        
        Notes
        -----
        - Profile updates only occur for local (RAG-based) answers, not web results
        - Domain is inferred from retrieval hits metadata (falls back to None)
        - Conversation history is automatically managed via daily-rotating sessions
        - Citations are only included for local answers; web answers use URLs
        
        Examples
        --------
        >>> system = TutorSystem.from_config(api_key="sk-...")
        >>> 
        >>> # Basic question
        >>> response = system.answer_question(
        ...     learner_id="student123",
        ...     question="What is Newton's second law?"
        ... )
        >>> print(response.answer)
        "Newton's second law [1] states that F = ma..."
        >>> print(response.citations)
        ["[1] College Physics Vol 1 (Doc: phys_v1, Page: 87)"]
        >>> 
        >>> # With streaming
        >>> def print_token(token: str):
        ...     print(token, end="", flush=True)
        >>> 
        >>> response = system.answer_question(
        ...     learner_id="student123",
        ...     question="Explain derivatives",
        ...     on_delta=print_token
        ... )
        >>> 
        >>> # With extra context from uploaded file
        >>> with open("lecture_notes.txt") as f:
        ...     notes = f.read()
        >>> 
        >>> response = system.answer_question(
        ...     learner_id="student123",
        ...     question="Summarize the key points from the lecture",
        ...     extra_context=notes
        ... )
        """
        # Load learner profile (creates new one if doesn't exist)
        profile = self.personalizer.load_profile(learner_id)
        
        # Select explanation style based on learner's domain mastery
        # Will be "scaffolded", "stepwise", or "concise"
        style_hint = self.personalizer.select_style(profile, None)

        # Delegate to multi-agent orchestrator for answer generation
        response = self.tutor_agent.answer(
            learner_id=learner_id,
            question=question,
            mode=mode,
            style_hint=style_hint,
            profile=profile,
            extra_context=extra_context,
            on_delta=on_delta,
        )
        
        # Only update profile for local (RAG) answers, not web or quiz results
        if response.source != "local":
            return response
        
        # Infer subject domain from retrieval hits metadata
        domain = self.personalizer.infer_domain(response.hits)
        
        # Record this interaction and get personalization recommendations
        personalization = self.personalizer.record_interaction(
            profile=profile,
            question=question,
            answer=response.answer,
            domain=domain,
            citations=response.citations,
        )
        
        # Save updated profile to disk for persistence
        self.personalizer.save_profile(profile)
        
        # Attach personalization hints to response
        response.next_topic = personalization.get("next_topic")
        response.difficulty = personalization.get("difficulty")
        
        return response

    def generate_quiz(
        self,
        learner_id: str,
        topic: str,
        num_questions: int = 4,
        extra_context: Optional[str] = None,
    ) -> Quiz:
        """Produce a multiple-choice quiz tailored to the learner and topic."""
        profile = self.personalizer.load_profile(learner_id)
        style = self.personalizer.select_style(profile, None)
        difficulty = self._style_to_difficulty(style)
        quiz = self.tutor_agent.create_quiz(
            topic=topic,
            profile=profile,
            num_questions=num_questions,
            difficulty=difficulty,
            extra_context=extra_context,
        )
        self.personalizer.save_profile(profile)
        return quiz

    def evaluate_quiz(
        self,
        learner_id: str,
        quiz_payload: Quiz | dict,
        answers: List[int],
    ) -> QuizEvaluation:
        """Evaluate a learner's quiz submission, returning detailed feedback."""
        profile = self.personalizer.load_profile(learner_id)
        quiz = quiz_payload if isinstance(quiz_payload, Quiz) else Quiz.model_validate(quiz_payload)
        evaluation = self.tutor_agent.evaluate_quiz(
            quiz=quiz,
            answers=answers,
            profile=profile,
        )
        self.personalizer.save_profile(profile)
        return evaluation

    def clear_conversation_history(self, learner_id: str) -> None:
        """Clear the conversation session history for a learner to prevent token overflow."""
        self.tutor_agent.clear_session(learner_id)
        logger.info(f"Cleared conversation history for learner: {learner_id}")

    @staticmethod
    def _style_to_difficulty(style: str) -> str:
        mapping = {
            "scaffolded": "foundational",
            "stepwise": "guided",
            "concise": "advanced",
        }
        return mapping.get(style, "balanced")
