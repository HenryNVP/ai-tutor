AI Tutor - Demo Script

⚡ Quick Start


```bash
# Start MCP Servers
python filesystem_mcp_server/server.py
python chroma_mcp_server/server.py

# Start REST API
uvicorn apps.api:app --reload --port 8080


# Start UI
streamlit run apps/ui.py

```

🎯 Core Use Cases

1. Basics & Conversation

    Action: Type Hello or Hi there.

    Expectation: Friendly greeting and capability overview.

    Action: Ask What is YOLO in computer vision?

    Expectation: Concise answer with context-aware explanation.

2. Document QA (RAG)

    Action: Upload CMPE249_Lecture7.pdf (Sidebar).

    Wait: Green checkmark ✅.

    Action: Ask What is RegNet?

    Expectation: Answer cited directly from the uploaded PDF (e.g., "RegNet is a family of CNNs... ").

3. Generate Study Notes

    Action: Ask Create lesson notes about RegNet from the file.

    Expectation: Structured Markdown output (Headers, Bullet points).

    Action: Ask Save these notes to a file.

    Expectation: Confirmation message. Check 🗂️ Generated Files in sidebar to download regnet_notes.txt.

4. Generate Quiz

    Action: Ask Create 5 review quizzes from the uploaded file.

    Expectation: Interactive quiz UI appears.

    Interact: Select answers, click Submit.

    Result: Instant scoring and explanations. Markdown file auto-saved to sidebar.

5. Data Visualization

    Action: Upload sales_data.csv (Sidebar).

    Action: Ask Plot sales per month.

    Expectation: Python code is generated and executed. A PNG chart appears in the chat window.