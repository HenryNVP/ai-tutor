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
        - Domain filtering to search only relevant collections
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
            # For document-specific searches, use a much larger top_k to ensure
            # we get all chunks from sparse documents (e.g., documents with only 1-3 chunks)
            # This is especially important for summaries where we need comprehensive coverage
            retriever.config.top_k = max(top_k, 100)  # Ensure we get all chunks even for sparse docs
            
            # Try to determine domain from chunk store to optimize search
            # This avoids searching all domains when we know which domain the file belongs to
            domain = None
            if hasattr(retriever.vector_store, "use_domain_collections") and retriever.vector_store.use_domain_collections:
                try:
                    # Look up domain from chunk store (more efficient than querying vector store)
                    from pathlib import Path
                    chunk_store = self.system.chunk_store
                    all_chunks = chunk_store.load()
                    
                    # Find chunks matching the filenames
                    for chunk in all_chunks:
                        chunk_filename = Path(chunk.metadata.source_path).name.lower()
                        # Check if this chunk matches any of the requested filenames
                        if any(Path(f).name.lower() == chunk_filename for f in filenames):
                            domain = chunk.metadata.primary_domain or chunk.metadata.domain
                            if domain and domain != "general":
                                logger.debug(
                                    "[TutorService] Determined domain '%s' from chunk store for files %s. "
                                    "Will search only this domain collection for efficiency.",
                                    domain,
                                    filenames
                                )
                                break
                    
                    if not domain:
                        logger.debug(
                            "[TutorService] Could not determine domain from chunk store for files %s. "
                            "Will search all domains.",
                            filenames
                        )
                except Exception as lookup_exc:
                    logger.debug(
                        "[TutorService] Could not determine domain from chunk store: %s. Will search all domains.",
                        lookup_exc
                    )
            
            # Search with source filter and domain filter (if available)
            query = Query(text=query_text, source_filter=filenames, domain=domain)
            hits = retriever.retrieve(query)
            
            # Remove duplicates
            seen_chunk_ids = set()
            unique_hits = []
            for hit in hits:
                if hit.chunk.metadata.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(hit.chunk.metadata.chunk_id)
                    unique_hits.append(hit)
            
            # Log warning if very few chunks found (may indicate sparse document)
            if len(unique_hits) <= 3 and filenames:
                logger.warning(
                    "[TutorService] Only found %d chunks for file(s) %s. "
                    "This may indicate sparse content or parsing issues. "
                    "Document may need OCR or have image-based content.",
                    len(unique_hits),
                    filenames
                )
            
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
            quiz_payload=quiz_payload,
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
                quiz_payload=quiz_model,
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

        question, extra_context, source_hints = self._build_prompt_from_event(event, session_id=session_id)
        logger.info(
            "[TutorService] Processing event: type=%s, question=%s, source_hints=%s",
            event.type,
            question[:100] if question else None,
            source_hints,
        )
        try:
            tutor_response = self.answer_question(
                learner_id=session_id,
                question=question,
                extra_context=extra_context,
                source_hints=source_hints,
            )
            logger.info(
                "[TutorService] Answer generated: route=%s, answer_length=%d",
                tutor_response.route,
                len(tutor_response.answer) if tutor_response.answer else 0,
            )
        except Exception as exc:
            logger.exception("[TutorService] Error generating answer: %s", exc)
            raise
        quiz_payload = (
            tutor_response.quiz.model_dump(mode="json") if tutor_response.quiz else None
        )
        quiz_markdown = quiz_to_markdown(tutor_response.quiz) if tutor_response.quiz else None
        
        # Include saved file path and visualization in metadata if present
        metadata = {"event_type": event.type}
        if tutor_response.saved_file_path:
            metadata["saved_file_path"] = tutor_response.saved_file_path
        if tutor_response.visualization:
            # Store visualization result in metadata
            viz_result = tutor_response.visualization
            dataset_info = viz_result.get("dataset_info") if isinstance(viz_result, dict) else getattr(viz_result, "dataset_info", None)
            
            dataset_info_dict = None
            if dataset_info:
                # Handle both dict and DatasetInfo object
                if isinstance(dataset_info, dict):
                    dataset_info_dict = {
                        "filename": dataset_info.get("filename"),
                        "shape": dataset_info.get("shape"),
                        "columns": dataset_info.get("columns"),
                    }
                else:
                    # It's a DatasetInfo object
                    dataset_info_dict = {
                        "filename": getattr(dataset_info, "filename", None),
                        "shape": getattr(dataset_info, "shape", None),
                        "columns": getattr(dataset_info, "columns", None),
                    }
            
            metadata["visualization"] = {
                "success": viz_result.get("success", False) if isinstance(viz_result, dict) else getattr(viz_result, "success", False),
                "image_base64": viz_result.get("image_base64") if isinstance(viz_result, dict) else getattr(viz_result, "image_base64", None),
                "code": viz_result.get("code") if isinstance(viz_result, dict) else getattr(viz_result, "code", None),
                "error": viz_result.get("error") if isinstance(viz_result, dict) else getattr(viz_result, "error", None),
                "dataset_info": dataset_info_dict,
            }
        
        response = SessionResponse(
            session_id=session_id,
            turn_id=turn_id,
            route=tutor_response.route,
            answer=tutor_response.answer,
            citations=tutor_response.citations,
            source=tutor_response.source,
            quiz=quiz_payload,
            quiz_markdown=quiz_markdown,
            metadata=metadata,
        )
        self._session_responses[session_id].append(response)
        return response

    def get_session_history(self, session_id: str) -> SessionHistoryResponse:
        return SessionHistoryResponse(
            session_id=session_id,
            events=self._session_events.get(session_id, []),
            responses=self._session_responses.get(session_id, []),
        )

    def _build_prompt_from_event(self, event: SessionEvent, session_id: Optional[str] = None) -> tuple[str, Optional[str], Optional[List[str]]]:
        source_hints = event.source_hints or event.file_ids or []
        documents_phrase = " Please use the uploaded documents only." if event.documents_only else ""
        
        # Add CSV filename to context for visualization requests
        extra_context_parts = []
        if event.csv_filename:
            extra_context_parts.append(f"CSV_FILENAME: {event.csv_filename}")
        
        # CRITICAL FIX: Detect "save notes" or "create summary file" requests and include previous notes in prompt
        content_lower = (event.content or "").lower()
        is_save_request = any(keyword in content_lower for keyword in [
            "save notes", "save to file", "write notes to file", "save the notes",
            "save this", "save that", "save it", "write to file",
            "create a summary file", "create summary file", "create a file",
            "save summary", "export notes", "download notes"
        ])
        
        previous_notes = None
        if is_save_request and session_id:
            # Get previous response from session history
            previous_responses = self._session_responses.get(session_id, [])
            # Look for the most recent note response
            for response in reversed(previous_responses):
                if response.route == "note" and response.answer:
                    previous_notes = response.answer
                    logger.info(
                        "[TutorService] Detected save notes request, found previous notes (%d chars)",
                        len(previous_notes)
                    )
                    break

        # CRITICAL FIX: If source_hints is empty but user is asking about uploaded documents,
        # try to extract from the message or use session context
        if not source_hints and event.documents_only:
            # Try to extract filename from the message content
            from ai_tutor.agents.routing import extract_source_mentions
            extracted = extract_source_mentions(event.content or "")
            if extracted:
                source_hints = extracted
                logger.info(
                    "[TutorService] Extracted source hints from message: %s",
                    source_hints
                )
            # If still empty, check if we can infer from context
            # For now, we'll let the agent handle it, but log a warning
            if not source_hints:
                logger.warning(
                    "[TutorService] No source_hints provided but documents_only=True. "
                    "Agent will need to infer from context or use fetch_full_document."
                )

        # Retrieve document content if source_hints are provided
        # SKIP retrieval for save requests - we already have the notes
        extra_context = None
        if source_hints and not is_save_request:
            try:
                # Use a broad query to retrieve all relevant content from the specified documents
                # For notes/summaries, retrieve comprehensive content
                # For other queries, use the question text
                query_text = event.content or "What does this document cover?"
                if event.type in ["note", "quiz"] or event.documents_only:
                    # For notes and quizzes, retrieve comprehensive content
                    query_text = "What does this document cover?"
                
                logger.info(
                    "[TutorService] Retrieving content from uploaded documents: %s",
                    source_hints
                )
                
                # Try multiple filename variations to handle path differences
                # Use shared utility function to avoid code duplication
                from ai_tutor.utils.path_utils import generate_filename_variations
                
                filename_variations = []
                for hint in source_hints:
                    filename_variations.extend(generate_filename_variations(hint))
                
                # Remove duplicates while preserving order
                seen = set()
                unique_variations = []
                for var in filename_variations:
                    if var not in seen:
                        seen.add(var)
                        unique_variations.append(var)
                
                logger.debug(
                    "[TutorService] Trying filename variations: %s",
                    unique_variations
                )
                
                hits = []
                for variation_set in [source_hints, unique_variations]:
                    if hits:
                        break
                    hits = self.retrieve_from_uploaded_documents(
                        query_text=query_text,
                        filenames=variation_set,
                        top_k=50,  # Retrieve more content for comprehensive summaries
                    )
                    if hits:
                        logger.info(
                            "[TutorService] Found %d hits using filename variations: %s",
                            len(hits),
                            variation_set
                        )
                        break
                
                if hits:
                    # Format the retrieved content as context
                    context_str, _ = self.format_context_from_hits(
                        hits,
                        max_passages=50,  # Include many passages for comprehensive context
                        passages_per_doc=None,  # Auto-calculate
                    )
                    
                    if context_str:
                        # Add SOURCE_FILTER_HINTS metadata for routing
                        filename_hints = ", ".join(source_hints)
                        context_parts = []
                        if extra_context_parts:
                            context_parts.extend(extra_context_parts)
                        context_parts.append(f"SOURCE_FILTER_HINTS: {filename_hints}")
                        context_parts.append(context_str)
                        extra_context = "\n\n".join(context_parts)
                        logger.info(
                            "[TutorService] Successfully retrieved %d passages from uploaded documents (%d chars of context)",
                            len(hits),
                            len(context_str)
                        )
                    elif extra_context_parts:
                        # If no document context but we have CSV filename, include it
                        extra_context = "\n\n".join(extra_context_parts)
                    else:
                        logger.warning(
                            "[TutorService] Retrieved %d hits but formatted context is empty",
                            len(hits)
                        )
                else:
                    logger.warning(
                        "[TutorService] No hits found for source_hints %s after trying all variations. "
                        "Possible causes: document not indexed, filename mismatch, empty chunks, or file was skipped.",
                        source_hints
                    )
                    
                    # Try a very generic query to see if ANY chunks exist for this file
                    # This helps diagnose if the issue is semantic matching vs. filename matching
                    # Use a generic query that should match any document content
                    try:
                        generic_queries = [
                            "document content",  # Generic query
                            "text",  # Very generic
                            query_text,  # Original query
                        ]
                        for generic_query in generic_queries:
                            diagnostic_hits = self.retrieve_from_uploaded_documents(
                                query_text=generic_query,
                                filenames=unique_variations if 'unique_variations' in locals() else source_hints,
                                top_k=100,  # Get many results to check if file exists
                            )
                            if diagnostic_hits:
                                logger.warning(
                                    "[TutorService] Found %d chunks for file using generic query '%s' "
                                    "(original query '%s' returned 0 hits). "
                                    "This suggests the document content may be sparse or doesn't match the original query semantically.",
                                    len(diagnostic_hits),
                                    generic_query,
                                    query_text
                                )
                                # Use diagnostic hits if available (even if not semantically relevant)
                                hits = diagnostic_hits[:50]  # Limit to 50 for context
                                break
                    except Exception as diag_exc:
                        logger.debug(
                            "[TutorService] Diagnostic query failed: %s",
                            diag_exc
                        )
                    
                    if not hits:
                        # Provide helpful error context for the agent to inform the user
                        missing_files = ", ".join(f'"{f}"' for f in source_hints)
                        extra_context = (
                            f"IMPORTANT: The requested document(s) {missing_files} could not be found in the vector store. "
                            f"Possible reasons:\n"
                            f"1. File was not successfully ingested (check ingestion logs for skipped files)\n"
                            f"2. File was ingested but chunks are empty or contain no searchable text\n"
                            f"3. Filename mismatch between stored metadata and search filter\n"
                            f"4. Document not yet indexed (wait a moment and try again)\n\n"
                            f"Please inform the user and suggest:\n"
                            f"- Verify the file was uploaded and ingested successfully\n"
                            f"- Check if the file appears in the ingestion results\n"
                            f"- If the file was ingested but has very few chunks (e.g., 3 chunks), the PDF may have failed to extract text\n"
                            f"- Try re-uploading the file if it was skipped"
                        )
            except Exception as exc:
                # Log but don't fail - fall back to source filtering without pre-retrieved content
                logger.warning(
                    "[TutorService] Failed to retrieve document content for source_hints %s: %s. "
                    "Will rely on source filtering during agent execution.",
                    source_hints,
                    exc,
                    exc_info=True
                )

        if event.type == "note":
            topic = event.content or "the uploaded documents"
            question = f"Create detailed study notes about {topic}.{documents_phrase}"
            # Combine extra_context_parts with existing extra_context
            if extra_context_parts and extra_context:
                extra_context = "\n\n".join(extra_context_parts) + "\n\n" + extra_context
            elif extra_context_parts:
                extra_context = "\n\n".join(extra_context_parts)
            return question, extra_context, source_hints

        if event.type == "quiz":
            topic = event.quiz_topic or event.content or "uploaded documents"
            count = event.quiz_count or 4
            question = f"Create {count} quiz questions about {topic}.{documents_phrase}"
            # Combine extra_context_parts with existing extra_context
            if extra_context_parts and extra_context:
                extra_context = "\n\n".join(extra_context_parts) + "\n\n" + extra_context
            elif extra_context_parts:
                extra_context = "\n\n".join(extra_context_parts)
            return question, extra_context, source_hints

        # Default: standard message
        content = event.content or ""
        
        # If this is a save request and we have previous notes, include them explicitly
        if is_save_request and previous_notes:
            question = (
                f"SAVE NOTES TO FILE - IMMEDIATE ACTION REQUIRED\n\n"
                f"User request: {content}\n\n"
                f"NOTES TO SAVE (from your previous response):\n"
                f"{'='*60}\n"
                f"{previous_notes}\n"
                f"{'='*60}\n\n"
                f"CRITICAL INSTRUCTIONS:\n"
                f"1. Generate a descriptive filename based on the topic (e.g., 'regnet_notes.txt', 'tesla_regnet_notes.txt')\n"
                f"2. Call write_text_file IMMEDIATELY with path: 'data/generated/[filename]'\n"
                f"   - Use the exact notes text above (no modifications)\n"
                f"3. DO NOT call fetch_full_document or retrieve_local_context\n"
                f"4. DO NOT regenerate, summarize, or modify the notes\n"
                f"5. After write_text_file succeeds, respond with ONLY: 'Notes saved to data/generated/[actual_file_path]'\n"
                f"6. Keep your response under 20 words - just confirm the save\n"
                f"7. DO NOT write a long explanation or repeat the notes\n\n"
                f"Your response should be: 'Notes saved to data/generated/[filename]'"
            )
            # Don't include extra_context for save requests - we already have the notes
            extra_context = None
        else:
            question = f"{content}{documents_phrase}" if content else documents_phrase.strip()
        
        # Combine extra_context_parts with existing extra_context for visualization requests
        if extra_context_parts:
            if extra_context:
                extra_context = "\n\n".join(extra_context_parts) + "\n\n" + extra_context
            else:
                extra_context = "\n\n".join(extra_context_parts)
        
        return question, extra_context, source_hints
    
    def detect_quiz_request(self, message: str) -> bool:
        """Detect if a message is a quiz request."""
        return self.system.detect_quiz_request(message)
    
    def extract_quiz_topic(self, message: str) -> str:
        """Extract quiz topic from a message."""
        return self.system.extract_quiz_topic(message)
    
    def extract_quiz_num_questions(self, message: str) -> int:
        """Extract number of quiz questions from a message."""
        return self.system.extract_quiz_num_questions(message)

