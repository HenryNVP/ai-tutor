Retrieval Evaluation Checklist
==============================

Use this playbook after adding new STEM sources to ensure the tutor’s answers stay grounded and citeable.

1. **Confirm clean ingestion**
   - Run `python scripts/openstax_ingest.py --book-id openstax_physics --ingest`.
   - Verify the JSON summary reports `documents > 0` and that `skipped` is empty. Investigate any skipped files before proceeding.

2. **Smoke-test retrieval coverage**
   - Issue representative CLI queries covering definition, derivation, worked example, and conceptual `why` questions. Example:
     - `ai-tutor ask student123 "State Newton's three laws of motion."`
     - `ai-tutor ask student123 "Solve for projectile range with launch angle θ and speed v₀."`
   - Confirm each response cites OpenStax titles with page numbers that match the expected section.

3. **Spot-check chunk fidelity**
   - Locate cited chunk IDs in `data/processed/chunks.jsonl` and confirm the chunk text aligns with the quoted passage.
   - Rerun `ai-tutor ask` if the chunk feels incomplete; adjust `chunk_size`/`chunk_overlap` in `config/default.yaml` if needed.

4. **Evaluate fallback behaviour**
   - Pose a topic outside the corpus (e.g., `ai-tutor ask student123 "Explain quantum field theory path integrals."`).
   - Confirm the tutor clearly reports that no local evidence was found instead of fabricating an answer.

5. **Regression log**
   - Capture CLI output and chunk excerpts for any failures.
   - File follow-up fixes (e.g., expand sources, tweak retrieval `top_k`, re-run ingestion) before accepting additional materials.

Repeat the checklist whenever new sources are ingested or the chunking configuration changes.
