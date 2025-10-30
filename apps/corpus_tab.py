from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from ai_tutor.system import TutorSystem


def render_corpus_management_tab(system: TutorSystem) -> None:
	"""Render the corpus management and ingestion tab."""
	st.header("📚 Corpus Management")
	
	# Initialize session state for corpus management
	if "uploaded_files_for_ingestion" not in st.session_state:
		st.session_state.uploaded_files_for_ingestion = []
	if "ingestion_result" not in st.session_state:
		st.session_state.ingestion_result = None
	
	col1, col2 = st.columns([1, 1])
	
	with col1:
		st.subheader("📤 Upload & Ingest Documents")
		st.markdown("""
		Upload PDF, Markdown, or TXT files to add them to the permanent knowledge base.
		These documents will be chunked, embedded, and stored in the vector database for future retrieval.
		""")
		
		uploaded_files = st.file_uploader(
			"Select files to ingest into vector store",
			type=["pdf", "txt", "md"],
			accept_multiple_files=True,
			key="corpus_uploader"
		)
		
		if uploaded_files:
			st.session_state.uploaded_files_for_ingestion = uploaded_files
			st.success(f"Queued {len(uploaded_files)} file(s) for ingestion.")

		if st.button("🚀 Ingest queued files", use_container_width=True):
			with st.spinner("Ingesting files..."):
				result = system.ingestion_pipeline.ingest_files(uploaded_files)
				st.session_state.ingestion_result = result
			st.success("Ingestion completed.")

	with col2:
		st.subheader("📈 Corpus Overview")
		stats = analyze_corpus(system)
		st.metric("Total Chunks", stats.get("total_chunks", 0))
		st.metric("Documents", stats.get("total_documents", 0))
		
		with st.expander("Sample Topics", expanded=False):
			for item in stats.get("sample_topics", []):
				st.write(f"- {item['text']} ({item['doc']})")


def analyze_corpus(system: TutorSystem) -> Dict[str, Any]:
	"""Lightweight stats for the corpus; mirrors UI helper logic."""
	chunks = system.chunk_store.load()
	if not chunks:
		return {
			"total_chunks": 0,
			"total_documents": 0,
			"domains": {},
			"documents": [],
			"sample_topics": [],
		}
	
	from collections import Counter
	domains = Counter(chunk.metadata.domain for chunk in chunks)
	doc_ids = set(chunk.metadata.doc_id for chunk in chunks)
	doc_titles: Dict[str, str] = {}
	for chunk in chunks:
		if chunk.metadata.doc_id not in doc_titles:
			doc_titles[chunk.metadata.doc_id] = chunk.metadata.title
	
	import random
	sample_size = min(10, len(chunks))
	sample_chunks = random.sample(chunks, sample_size) if len(chunks) > sample_size else chunks
	sample_topics = []
	for chunk in sample_chunks:
		text = chunk.text.strip()
		first_sentence = text.split('.')[0][:100]
		if first_sentence:
			sample_topics.append({
				"text": first_sentence + "...",
				"doc": chunk.metadata.title,
				"domain": chunk.metadata.domain,
			})
	
	return {
		"total_chunks": len(chunks),
		"total_documents": len(doc_ids),
		"domains": dict(domains),
		"documents": [{"id": doc_id, "title": doc_titles[doc_id]} for doc_id in doc_ids],
		"sample_topics": sample_topics,
	}


