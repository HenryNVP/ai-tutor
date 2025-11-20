from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api import app, get_service
from ai_tutor.learning.quiz import Quiz, QuizEvaluation, QuizQuestion


class StubTutorService:
    def __init__(self) -> None:
        self.evaluations = []

    def evaluate_quiz(self, learner_id: str, quiz_payload: Quiz, answers):
        evaluation = QuizEvaluation(
            topic=quiz_payload.topic,
            total_questions=len(quiz_payload.questions),
            correct_count=2,
            score=0.5,
            answers=[],
        )
        self.evaluations.append((learner_id, answers))
        return evaluation


@pytest.fixture()
def quiz_client():
    stub_service = StubTutorService()
    app.dependency_overrides[get_service] = lambda: stub_service
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    with TestClient(app) as client:
        yield client, stub_service
    app.dependency_overrides.clear()


def _sample_quiz_payload() -> dict:
    quiz = Quiz(
        topic="physics",
        questions=[
            QuizQuestion(
                question="What is torque?",
                choices=["Force", "Moment", "Velocity", "Energy"],
                correct_index=1,
            ),
            QuizQuestion(
                question="SI unit of torque?",
                choices=["Joule", "Newton-meter", "Watt", "Tesla"],
                correct_index=1,
            ),
        ],
    )
    return quiz.model_dump(mode="json")


def test_quiz_evaluation_endpoint(quiz_client):
    client, stub = quiz_client
    payload = {
        "learner_id": "student-7",
        "quiz": _sample_quiz_payload(),
        "answers": [1, 0],
    }
    response = client.post("/quiz/evaluate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["evaluation"]["topic"] == "physics"
    assert stub.evaluations == [("student-7", [1, 0])]

