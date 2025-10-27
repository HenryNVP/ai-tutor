"""
Example: Using LLM Function Calling for Intent Detection

Instead of keyword matching, let the LLM understand user intent
and decide when to call quiz generation tools.
"""

from openai import OpenAI
from typing import Optional, List
import json

# Define tools/functions the LLM can call
QUIZ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_quiz",
            "description": "Generate a quiz for the student based on topics or uploaded documents. Use this when the student asks for a quiz, test, practice questions, or assessment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic for the quiz. Use 'uploaded_documents' if the student wants a quiz from their uploaded files."
                    },
                    "num_questions": {
                        "type": "integer",
                        "description": "Number of questions to generate",
                        "minimum": 3,
                        "maximum": 40
                    },
                    "use_uploaded_docs": {
                        "type": "boolean",
                        "description": "Whether to generate quiz from uploaded documents"
                    }
                },
                "required": ["topic", "num_questions"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "answer_question",
            "description": "Answer a regular question about a topic. Use this for normal Q&A, explanations, or help with concepts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The student's question"
                    },
                    "use_uploaded_docs": {
                        "type": "boolean",
                        "description": "Whether to search in uploaded documents for the answer"
                    }
                },
                "required": ["question"]
            }
        }
    }
]


def demo_llm_intent_detection(user_message: str, has_uploaded_docs: bool = False):
    """
    Demonstrate how LLM understands intent and calls appropriate tools.
    """
    client = OpenAI()  # Uses OPENAI_API_KEY from environment
    
    system_prompt = "You are a helpful AI tutor assistant. Understand the student's intent and use the appropriate tool."
    if has_uploaded_docs:
        system_prompt += " The student has uploaded documents about computer vision."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    # Let the LLM decide which tool to call
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # or gpt-4
        messages=messages,
        tools=QUIZ_TOOLS,
        tool_choice="auto"  # LLM decides when to call tools
    )
    
    message = response.choices[0].message
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        for tool_call in message.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            print(f"\n🤖 LLM understood intent and wants to call:")
            print(f"   Function: {function_name}")
            print(f"   Arguments: {json.dumps(arguments, indent=2)}")
            
            if function_name == "generate_quiz":
                print(f"\n   ✅ Will generate quiz:")
                print(f"      Topic: {arguments.get('topic')}")
                print(f"      Questions: {arguments.get('num_questions')}")
                print(f"      From docs: {arguments.get('use_uploaded_docs', False)}")
            
            elif function_name == "answer_question":
                print(f"\n   ✅ Will answer question:")
                print(f"      Question: {arguments.get('question')}")
                print(f"      Search docs: {arguments.get('use_uploaded_docs', False)}")
    else:
        print(f"\n💬 LLM response: {message.content}")


if __name__ == "__main__":
    print("=" * 70)
    print("LLM FUNCTION CALLING - INTENT DETECTION EXAMPLES")
    print("=" * 70)
    
    # Test cases
    test_cases = [
        ("Create 10 quizzes from the documents", True),
        ("I'd like to practice what I learned, can you test me?", False),
        ("Make me some questions on neural networks", False),
        ("What is YOLO?", True),
        ("Quiz me on the stuff I uploaded", True),
        ("Explain convolutional layers", False),
    ]
    
    for user_msg, has_docs in test_cases:
        print(f"\n{'─' * 70}")
        print(f"📝 User: \"{user_msg}\"")
        print(f"📁 Has uploaded docs: {has_docs}")
        
        try:
            demo_llm_intent_detection(user_msg, has_docs)
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()

