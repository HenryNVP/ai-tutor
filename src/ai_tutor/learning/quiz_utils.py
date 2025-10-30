from __future__ import annotations

from ai_tutor.learning.quiz import Quiz, QuizEvaluation


def quiz_to_markdown(quiz: Quiz) -> str:
    """Convert a Quiz object to markdown for download/export."""
    lines: list[str] = [f"# {quiz.topic}", ""]

    for idx, question in enumerate(quiz.questions):
        lines.append(f"{idx + 1}. {question.question}")
        lines.append("")
        for choice_idx, choice in enumerate(question.choices):
            prefix = chr(65 + choice_idx)
            lines.append(f"   - {prefix}. {choice}")
        if question.explanation:
            lines.append("")
            lines.append(f"   > Explanation: {question.explanation}")
        if question.references:
            lines.append("")
            lines.append("   References:")
            for ref in question.references:
                lines.append(f"   - {ref}")
        lines.append("")

    return "\n".join(lines)


def format_quiz_context(result: QuizEvaluation) -> str:
    """Summarize a recent quiz result to provide context to the tutor."""
    lines: list[str] = [
        f"Recent quiz: {result.topic}",
        f"Score: {result.correct_count}/{result.total_questions} ({result.score * 100:.0f}%)",
    ]
    for answer in result.answers:
        status = "correct" if answer.is_correct else "incorrect"
        lines.append(f"- Q{answer.index + 1}: {status}")
    if result.review_topics:
        lines.append("Focus areas: " + "; ".join(result.review_topics))
    return "\n".join(lines)


