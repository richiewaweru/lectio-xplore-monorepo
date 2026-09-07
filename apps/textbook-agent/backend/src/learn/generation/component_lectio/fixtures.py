"""Minimal valid Lectio field fixtures for Component Lectio contract tests."""

from __future__ import annotations

from typing import Any


def valid_content_for(component_id: str, *, purpose: str = "ok") -> dict[str, Any]:
    """Return a minimal schema-valid Lectio content object for the component."""
    table: dict[str, dict[str, Any]] = {
        "section-header": {
            "title": purpose,
            "subtitle": "Lesson",
            "subject": "General",
            "grade_band": "secondary",
        },
        "hook-hero": {
            "headline": purpose,
            "body": "Students need this idea.",
            "anchor": "Anchor example",
        },
        "prerequisite-strip": {
            "items": [{"concept": "prior knowledge", "refresher": "brief"}],
        },
        "explanation-block": {
            "body": purpose,
            "emphasis": ["key idea"],
        },
        "callout-block": {"variant": "remember", "body": purpose},
        "what-next-bridge": {"body": purpose, "next": "Apply it"},
        "section-divider": {"label": "Next"},
        "definition-card": {
            "term": "Term",
            "formal": "Formal definition",
            "plain": "Plain language",
        },
        "definition-family": {
            "family_title": "Family",
            "definitions": [
                {
                    "term": "Term",
                    "formal": "Formal definition",
                    "plain": "Plain language",
                }
            ],
        },
        "glossary-rail": {
            "terms": [{"term": "Term", "definition": "Meaning"}],
        },
        "insight-strip": {
            "cells": [{"label": "Insight", "value": purpose}],
        },
        "key-fact": {"fact": purpose},
        "comparison-grid": {
            "title": "Compare",
            "columns": [
                {"id": "a", "title": "A", "summary": "First"},
                {"id": "b", "title": "B", "summary": "Second"},
            ],
            "rows": [{"criterion": "row", "values": ["1", "2"]}],
        },
        "worked-example-card": {
            "title": "Example",
            "setup": "Setup",
            "steps": [{"label": "1", "content": "Do this"}],
            "conclusion": "Done",
        },
        "process-steps": {
            "title": "Process",
            "steps": [
                {"number": 1.0, "action": "Start", "detail": "Begin"},
                {"number": 2.0, "action": "Finish", "detail": "End"},
            ],
        },
        "pitfall-alert": {
            "misconception": purpose,
            "correction": "Avoid it",
        },
        "summary-block": {
            "heading": "Summary",
            "items": [{"text": purpose}],
        },
        "practice-stack": {
            "problems": [
                {
                    "difficulty": "warm",
                    "question": "What is 2+2?",
                    "hints": [{"level": 1, "text": "Add the numbers"}],
                    "solution": {
                        "approach": "Add",
                        "answer": "4",
                        "worked": "2+2=4",
                    },
                }
            ],
            "solutions_available": True,
        },
        "quiz-check": {
            "question": "What is 2+2?",
            "options": [
                {"text": "3", "correct": False, "explanation": "Too small"},
                {"text": "4", "correct": True, "explanation": "Correct"},
            ],
            "feedback_correct": "Well done",
            "feedback_incorrect": "Try again",
        },
        "short-answer": {
            "question": "Explain the method",
            "marks": 2.0,
            "lines": 3.0,
            "mark_scheme": "Mentions the key step",
        },
        "fill-in-blank": {
            "instruction": "Complete the sentence",
            "segments": [
                {"text": "The answer is ", "is_blank": False},
                {"text": "", "is_blank": True, "answer": "four"},
            ],
        },
        "reflection-prompt": {
            "prompt": "What surprised you?",
            "type": "open",
        },
        "student-textbox": {
            "prompt": "Write your reasoning",
            "lines": 4.0,
        },
        "diagram-block": {
            "caption": purpose,
            "alt_text": purpose,
            "image_url": "https://example.test/diagram.png",
        },
        "diagram-compare": {
            "before_label": "Before",
            "after_label": "After",
            "caption": purpose,
            "alt_text": purpose,
            "before_image_url": "https://example.test/before.png",
            "after_image_url": "https://example.test/after.png",
        },
        "diagram-series": {
            "title": purpose,
            "diagrams": [
                {
                    "step_label": "Step 1",
                    "caption": "First",
                    "image_url": "https://example.test/s1.png",
                },
                {
                    "step_label": "Step 2",
                    "caption": "Second",
                    "image_url": "https://example.test/s2.png",
                },
            ],
        },
        "answer-key": {
            "entries": [
                {
                    "question_number": 1.0,
                    "question": "What is 2+2?",
                    "correct_answer": "4",
                }
            ]
        },
    }
    if component_id not in table:
        raise KeyError(f"No valid fixture for component {component_id}")
    return dict(table[component_id])


__all__ = ["valid_content_for"]
