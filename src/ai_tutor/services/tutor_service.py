"""Service layer for tutor operations - separates UI from agent internals.

This module provides a clean API for the UI to interact with the tutoring system
without directly accessing agents, retrievers, or other internal components.
"""

from __future__ import annotations

import logging
from pathlib import Path
from collections import defaultdict
from typing import DefaultDict, List, Optional

from ai_tutor.data_models import Query, RetrievalHit
from ai_tutor.system import TutorSystem
from ai_tutor.learning.quiz import Quiz
from ai_tutor.learning.quiz_utils import quiz_to_markdown
from ai_tutor.data_models import SessionEvent, SessionResponse, SessionHistoryResponse

logger = logging.getLogger(__name__)


class TutorService:
    """Service layer that provides a clean API for UI interactions.
    
    This class encapsulates all business logic and prevents the UI from
    directly accessing agent internals like retrievers, configs, etc.
    """
    
    def __init__(self, system: TutorSystem):
        """Initialize service with a TutorSystem instance."""
        self.system = system
        self._session_events: DefaultDict[str, List[SessionEvent]] = defaultdict(list)
        self._session_responses: DefaultDict[str, List[SessionResponse]] = defaultdict(list)
    
    def answer_question(
        self,
        learner_id: str,
        question: str,
        mode: str = "learning",
        extra_context: Optional[str] = None,
        source_hints: Optional[List[str]] = None,
        on_delta: Optional[callable] = None,
    ):
        """Answer a question using the full agent system.
        
        This is the main method for Q&A - use this instead of accessing
        agents directly.
        """
        return self.system.answer_question(
            learner_id=learner_id,
            question=question,
            mode=mode,
            extra_context=extra_context,
            source_hints=source_hints,
            on_delta=on_delta,
        )
    
    def retrieve_from_uploaded_documents(
        self,
        query_text: str,
        filenames: List[str],
        top_k: int = 50,
    ) -> List[RetrievalHit]:
        """Retrieve passages from specific uploaded documents.
        
        This method handles all the complexity of:
        - Adjusting top_k for document-specific searches
        - Using source filters
        - Removing duplicates
        - Formatting results
        
        Args:
            query_text: The search query
            filenames: List of filenames to search within
            top_k: Maximum number of results to return
            
        Returns:
            List of retrieval hits from the specified documents
        """
        # Access retriever through the service layer (not directly from UI)
        retriever = self.system.tutor_agent.retriever
        
        # Save original config
        original_top_k = retriever.config.top_k
        
        try:
            # Temporarily increase top_k for document-specific search
            retriever.config.top_k = top_k
            
            # Search with source filter
            query = Query(text=query_text, source_filter=filenames)
            hits = retriever.retrieve(query)
            
            # Remove duplicates
            seen_chunk_ids = set()
            unique_hits = []
            for hit in hits:
                if hit.chunk.metadata.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(hit.chunk.metadata.chunk_id)
                    unique_hits.append(hit)
            
            return unique_hits
        finally:
            # Always restore original config
            retriever.config.top_k = original_top_k
    
    def retrieve_multiple_queries(
        self,
        queries: List[str],
        filenames: Optional[List[str]] = None,
        top_k: int = 50,
    ) -> List[RetrievalHit]:
        """Retrieve passages using multiple query strings.
        
        Useful for searching uploaded documents with filename-based queries
        plus the user's actual question.
        
        Args:
            queries: List of query strings to search
            filenames: Optional list of filenames to filter by
            top_k: Maximum results per query
            
        Returns:
            Combined list of unique retrieval hits
        """
        retriever = self.system.tutor_agent.retriever
        original_top_k = retriever.config.top_k
        
        try:
            retriever.config.top_k = top_k
            
            all_hits = []
            for query_text in queries:
                query = Query(
                    text=query_text,
                    source_filter=filenames if filenames else None
                )
                hits = retriever.retrieve(query)
                all_hits.extend(hits)
            
            # Remove duplicates
            seen_chunk_ids = set()
            unique_hits = []
            for hit in all_hits:
                if hit.chunk.metadata.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(hit.chunk.metadata.chunk_id)
                    unique_hits.append(hit)
            
            return unique_hits
        finally:
            retriever.config.top_k = original_top_k
    
    def format_context_from_hits(
        self,
        hits: List[RetrievalHit],
        max_passages: int = 15,
        passages_per_doc: Optional[int] = None,
    ) -> tuple[str, List[str]]:
        """Format retrieval hits into context string and citations.
        
        Args:
            hits: List of retrieval hits to format
            max_passages: Maximum total passages to include
            passages_per_doc: Passages per document (auto-calculated if None)
            
        Returns:
            Tuple of (context_string, citations_list)
        """
        if not hits:
            return "", []
        
        # Group hits by document for balanced representation
        from collections import defaultdict
        hits_by_doc = defaultdict(list)
        for hit in hits:
            doc_title = hit.chunk.metadata.title or "Unknown"
            hits_by_doc[doc_title].append(hit)
        
        # Calculate passages per document
        if passages_per_doc is None:
            passages_per_doc = max(3, max_passages // len(hits_by_doc))
        
        # Format context and citations
        context_parts = []
        citations = []
        idx = 1
        
        for doc_title, doc_hits in hits_by_doc.items():
            for hit in doc_hits[:passages_per_doc]:
                if len(context_parts) >= max_passages:
                    break
                
                context_parts.append(
                    f"[{idx}] {hit.chunk.metadata.title}\n"
                    f"{hit.chunk.text}"
                )
                citations.append(f"{hit.chunk.metadata.title}")
                idx += 1
            
            if len(context_parts) >= max_passages:
                break
        
        context_string = "\n\n".join(context_parts)
        return context_string, citations
    
    def answer_with_context(
        self,
        learner_id: str,
        question: str,
        context: str,
    ):
        """Answer a question using provided context (bypasses agent retrieval).
        
        This is useful when the UI has already retrieved specific context
        (e.g., from uploaded documents) and wants to use it directly.
        
        Args:
            learner_id: Learner identifier
            question: The question to answer
            context: Pre-retrieved context to use
            
        Returns:
            TutorResponse with answer based on provided context
        """
        from ai_tutor.agents.tutor import TutorResponse
        
        # Use LLM directly with provided context
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI tutor. Answer the student's question using "
                    "ONLY the provided context from their uploaded documents. "
                    "Be clear and educational. If the context doesn't contain enough "
                    "information, say so."
                )
            },
            {
                "role": "user",
                "content": f"""Context from uploaded documents:
{context}

Student's question: {question}

Please answer based only on the provided context."""
            }
        ]
        
        llm_response = self.system.llm_client.generate(messages)
        
        return TutorResponse(
            answer=llm_response,
            hits=[],  # No hits since we used provided context
            citations=[],  # Citations should be extracted from context
            style="concise",
            next_topic=None,
            difficulty=None,
            source="local",
            quiz=None,
            route="qa",
        )
    
    def create_quiz(
        self,
        learner_id: str,
        topic: str,
        num_questions: int = 4,
        difficulty: Optional[str] = None,
        extra_context: Optional[str] = None,
    ):
        """Create a quiz on a given topic."""
        return self.system.create_quiz(
            learner_id=learner_id,
            topic=topic,
            num_questions=num_questions,
            difficulty=difficulty,
            extra_context=extra_context,
        )
    
    def ingest_directory(self, directory: Path):
        """Ingest documents from a directory."""
        return self.system.ingest_directory(directory)
    
    def create_error_response(self, error_message: str):
        """Create an error response for UI display.
        
        Args:
            error_message: Error message to display to user
            
        Returns:
            TutorResponse with error message
        """
        from ai_tutor.agents.tutor import TutorResponse
        return TutorResponse(
            answer=f"I encountered an error while generating an answer: {error_message}. Please try again or check the logs.",
            hits=[],
            citations=[],
            style="concise",
            source=None,
            quiz=None,
            route="error",
        )
    
    def format_quiz_context(self, result):
        """Format quiz evaluation result as context string."""
        return self.system.format_quiz_context(result)

    def evaluate_quiz(
        self,
        learner_id: str,
        quiz_payload,
        answers: List[int],
    ):
        return self.system.evaluate_quiz(
            learner_id=learner_id,
            quiz=quiz_payload,
            answers=answers,
        )

    def quiz_to_markdown(self, quiz) -> str:
        return self.system.quiz_to_markdown(quiz)
    
    def process_event(self, session_id: str, event: SessionEvent) -> SessionResponse:
        """Process a session event and return structured response."""
        history = self._session_events[session_id]
        history.append(event)
        turn_id = len(history)

        if event.type == "upload":
            metadata = {"file_ids": event.file_ids or []}
            response = SessionResponse(
                session_id=session_id,
                turn_id=turn_id,
                route="upload",
                answer=None,
                citations=[],
                source="upload",
                quiz=None,
                metadata=metadata,
            )
            self._session_responses[session_id].append(response)
            return response

        if event.type == "quiz_submission":
            if not event.quiz:
                raise ValueError("quiz_submission events require quiz payload")
            answers = event.answers or []
            quiz_model = Quiz.model_validate(event.quiz)
            evaluation = self.system.evaluate_quiz(
                learner_id=session_id,
                quiz=quiz_model,
                answers=answers,
            )
            markdown = quiz_to_markdown(quiz_model)
            response = SessionResponse(
                session_id=session_id,
                turn_id=turn_id,
                route="quiz_submission",
                answer=None,
                citations=[],
                source="quiz",
                quiz=event.quiz,
                quiz_markdown=markdown,
                metadata={
                    "event_type": "quiz_submission",
                    "evaluation": evaluation.model_dump(mode="json"),
                },
            )
            self._session_responses[session_id].append(response)
            return response

        question, extra_context, source_hints = self._build_prompt_from_event(event)
        tutor_response = self.answer_question(
            learner_id=session_id,
            question=question,
            extra_context=extra_context,
            source_hints=source_hints,
        )
        quiz_payload = (
            tutor_response.quiz.model_dump(mode="json") if tutor_response.quiz else None
        )
        quiz_markdown = quiz_to_markdown(tutor_response.quiz) if tutor_response.quiz else None
        response = SessionResponse(
            session_id=session_id,
            turn_id=turn_id,
            route=tutor_response.route,
            answer=tutor_response.answer,
            citations=tutor_response.citations,
            source=tutor_response.source,
            quiz=quiz_payload,
            quiz_markdown=quiz_markdown,
            metadata={"event_type": event.type},
        )
        self._session_responses[session_id].append(response)
        return response

    def get_session_history(self, session_id: str) -> SessionHistoryResponse:
        return SessionHistoryResponse(
            session_id=session_id,
            events=self._session_events.get(session_id, []),
            responses=self._session_responses.get(session_id, []),
        )

    @staticmethod
    def _build_prompt_from_event(event: SessionEvent) -> tuple[str, Optional[str], Optional[List[str]]]:
        source_hints = event.source_hints or event.file_ids or []
        documents_phrase = " Please use the uploaded documents only." if event.documents_only else ""

        if event.type == "note":
            topic = event.content or "the uploaded documents"
            question = f"Create detailed study notes about {topic}.{documents_phrase}"
            return question, None, source_hints

        if event.type == "quiz":
            topic = event.quiz_topic or event.content or "uploaded documents"
            count = event.quiz_count or 4
            question = f"Create {count} quiz questions about {topic}.{documents_phrase}"
            return question, None, source_hints

        # Default: standard message
        content = event.content or ""
        question = f"{content}{documents_phrase}" if content else documents_phrase.strip()
        return question, None, source_hints
    
    def detect_quiz_request(self, message: str) -> bool:
        """Detect if a message is a quiz request."""
        return self.system.detect_quiz_request(message)
    
    def extract_quiz_topic(self, message: str) -> str:
        """Extract quiz topic from a message."""
        return self.system.extract_quiz_topic(message)
    
    def extract_quiz_num_questions(self, message: str) -> int:
        """Extract number of quiz questions from a message."""
        return self.system.extract_quiz_num_questions(message)

