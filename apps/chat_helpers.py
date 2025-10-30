from __future__ import annotations

import re
from pathlib import Path
from typing import List

import streamlit as st


def format_answer(text: str) -> str:
	normalized = re.sub(r"(?<=\S)\s+(?=(?:[-•*]|\d+\.)\s)", "\n", text)
	normalized = re.sub(r"\n{3,}", "\n\n", normalized)
	lines = normalized.splitlines()
	formatted: List[str] = []
	for line in lines:
		stripped = line.rstrip()
		is_bullet = stripped.startswith(("-", "*", "•"))
		is_enumeration = bool(re.match(r"^\d+\.\s", stripped))
		if (is_bullet or is_enumeration) and formatted and formatted[-1] != "":
			formatted.append("")
		formatted.append(stripped)
	return "\n".join(formatted)


def is_question_about_uploaded_docs(message: str) -> bool:
	upload_keywords = [
		"uploaded",
		"upload",
		"the documents i uploaded",
		"the files i uploaded",
		"these documents",
		"these files",
		"the 2 documents",
		"the 2 files",
		"the two documents",
		"the two files",
		"this document",
		"this file",
	]
	message_lower = message.lower()
	return any(keyword in message_lower for keyword in upload_keywords)


def filter_hits_by_filenames(hits: List, filenames: List[str]) -> List:
	if not filenames:
		return hits
	normalized_filenames = {Path(fn).name.lower() for fn in filenames}
	import logging
	logger = logging.getLogger(__name__)
	logger.info(f"Filtering by filenames: {normalized_filenames}")
	with st.expander("🔍 Debug: Filename Matching", expanded=False):
		st.write("**Looking for these files:**")
		for fn in normalized_filenames:
			st.write(f"- `{fn}`")
		st.write("")
		st.write(f"**Found in top {len(hits)} retrieval results (unique sources):**")
		seen_sources = set()
		matches_found = 0
		match_list = []
		no_match_list = []
		for hit in hits:
			source_name = Path(hit.chunk.metadata.source_path).name.lower()
			if source_name not in seen_sources:
				seen_sources.add(source_name)
				if source_name in normalized_filenames:
					match_list.append(source_name)
					matches_found += 1
				else:
					no_match_list.append(source_name)
		# Show matches first
		if match_list:
			st.write("**✅ MATCHES (your uploaded files):**")
			for source in match_list:
				st.write(f"  - `{source}` ✅")
		else:
			st.write("**❌ NO MATCHES FOUND**")
		st.write("")
		if no_match_list:
			st.write(f"**Other files in results (showing first 10 of {len(no_match_list)}):**")
			for source in no_match_list[:10]:
				st.write(f"  - `{source}` ❌")
		st.write("")
		st.write(f"**Summary:** {matches_found}/{len(normalized_filenames)} uploaded files found in {len(hits)} total results")
	filtered_hits = []
	for hit in hits:
		source_name = Path(hit.chunk.metadata.source_path).name.lower()
		if source_name in normalized_filenames:
			filtered_hits.append(hit)
	return filtered_hits


__all__ = [
	"format_answer",
	"is_question_about_uploaded_docs",
	"filter_hits_by_filenames",
]


