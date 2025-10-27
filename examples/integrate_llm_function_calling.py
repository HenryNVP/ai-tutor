"""
How to integrate LLM Function Calling into the AI Tutor

This shows how to replace keyword matching with intelligent intent detection.
"""

from openai import OpenAI
from typing import Optional, Dict, Any
import json


class IntentDetector:
    """
    Uses LLM to understand user intent and determine what action to take.
    Replaces brittle keyword matching with intelligent understanding.
    """
    
    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)
        
        # Define available tools
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "generate_quiz",
                    "description": (
                        "Generate an interactive quiz or practice questions for the student. "
                        "Use this when student requests: quiz, test, assessment, practice questions, "
                        "mcq, multiple choice, 'test me', 'quiz me', or wants to practice/review."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": (
                                    "The topic for the quiz. If student says 'from documents', "
                                    "'from my files', 'from what I uploaded', use 'uploaded_documents'. "
                                    "Otherwise use the specific topic mentioned."
                                )
                            },
                            "num_questions": {
                                "type": "integer",
                                "description": "Number of questions (default: 4, max: 40)",
                                "default": 4
                            },
                            "from_uploaded_docs": {
                                "type": "boolean",
                                "description": (
                                    "True if student wants quiz from their uploaded documents/files. "
                                    "Look for phrases like: 'from the documents', 'from my files', "
                                    "'based on what I uploaded', 'quiz the PDFs I gave you'"
                                ),
                                "default": False
                            }
                        },
                        "required": ["topic"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "answer_question",
                    "description": (
                        "Answer a regular question, provide explanation, or help understand a concept. "
                        "Use this for normal Q&A, not for quiz/test requests."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The student's question or topic to explain"
                            },
                            "search_uploaded_docs": {
                                "type": "boolean",
                                "description": (
                                    "True if student asks about their uploaded documents specifically. "
                                    "Look for: 'in my documents', 'according to the PDF', 'in the file I uploaded'"
                                ),
                                "default": False
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
    
    def detect_intent(
        self, 
        user_message: str,
        has_uploaded_docs: bool = False,
        uploaded_doc_names: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to understand user intent and determine action.
        
        Returns dict with:
        - action: "generate_quiz" | "answer_question" | "unknown"
        - params: dict of parameters for the action
        """
        # Build context
        system_msg = "You are an AI tutor assistant. Understand student intent and use appropriate tools."
        if has_uploaded_docs:
            doc_list = ", ".join(uploaded_doc_names) if uploaded_doc_names else "some documents"
            system_msg += f" Student has uploaded: {doc_list}"
        
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_message}
        ]
        
        # Get LLM to decide
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=self.tools,
                tool_choice="auto"
            )
            
            msg = response.choices[0].message
            
            # Check if tool was called
            if msg.tool_calls:
                tool_call = msg.tool_calls[0]  # Take first tool call
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                return {
                    "action": function_name,
                    "params": arguments,
                    "confidence": "high"  # LLM made explicit tool call
                }
            else:
                # No tool called - just conversation
                return {
                    "action": "answer_question",
                    "params": {"query": user_message, "search_uploaded_docs": False},
                    "confidence": "low"
                }
                
        except Exception as e:
            print(f"Intent detection error: {e}")
            # Fallback to treating as question
            return {
                "action": "answer_question",
                "params": {"query": user_message, "search_uploaded_docs": False},
                "confidence": "error"
            }


# Example integration into your UI code
def enhanced_chat_handler_example():
    """
    Example of how to use IntentDetector in the chat handler.
    
    Replace the current keyword-based detection with this approach.
    """
    
    # In your render() function, replace this:
    # if detect_quiz_request(prompt):  # OLD WAY
    
    # With this:
    detector = IntentDetector(openai_api_key="your-key")
    
    intent = detector.detect_intent(
        user_message="Create 10 quizzes from the documents",
        has_uploaded_docs=True,
        uploaded_doc_names=["Lecture9.pdf", "Lecture10.pdf"]
    )
    
    print(f"Action: {intent['action']}")
    print(f"Params: {intent['params']}")
    
    if intent['action'] == 'generate_quiz':
        params = intent['params']
        topic = params['topic']
        num_questions = params.get('num_questions', 4)
        from_docs = params.get('from_uploaded_docs', False)
        
        print(f"\n🎯 Generating quiz:")
        print(f"   Topic: {topic}")
        print(f"   Questions: {num_questions}")
        print(f"   From uploaded docs: {from_docs}")
        
        # Call your quiz generation logic
        # quiz = system.generate_quiz(...)
        
    elif intent['action'] == 'answer_question':
        params = intent['params']
        query = params['query']
        search_docs = params.get('search_uploaded_docs', False)
        
        print(f"\n💬 Answering question:")
        print(f"   Query: {query}")
        print(f"   Search docs: {search_docs}")
        
        # Call your Q&A logic
        # response = system.answer_question(...)


if __name__ == "__main__":
    print("=" * 70)
    print("INTEGRATION EXAMPLE: LLM-Based Intent Detection")
    print("=" * 70)
    print()
    print("This approach replaces keyword matching with intelligent understanding.")
    print()
    
    # Show how it works
    enhanced_chat_handler_example()

