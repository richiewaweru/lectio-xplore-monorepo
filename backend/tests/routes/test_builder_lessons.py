from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.dependencies import get_gcs_image_store
from core.database.models import GenerationModel, UserModel
from core.database.session import get_async_session
from core.entities.user import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


USER_A = User(
    id="builder-user-a",
    email="builder-a@example.com",
    name="Builder A",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)

USER_B = User(
    id="builder-user-b",
    email="builder-b@example.com",
    name="Builder B",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)


def _minimal_lesson(document_id: str = "client-doc-id") -> dict:
    block_id = "block-1"
    return {
        "version": 1,
        "id": document_id,
        "title": "Fractions basics",
        "subject": "mathematics",
        "preset_id": "blue-classroom",
        "source": "manual",
        "sections": [
            {
                "id": "section-1",
                "template_id": "open-canvas",
                "title": "Fractions basics",
                "position": 0,
                "block_ids": [block_id],
            }
        ],
        "blocks": {
            block_id: {
                "id": block_id,
                "component_id": "explanation-block",
                "position": 0,
                "content": {"body": "A fraction represents part of a whole."},
            }
        },
        "media": {},
        "created_at": "2026-05-13T00:00:00Z",
        "updated_at": "2026-05-13T00:00:00Z",
    }


def _lesson_with_answers(document_id: str = "client-doc-id") -> dict:
    return {
        "version": 1,
        "id": document_id,
        "title": "Assessment practice",
        "subject": "mathematics",
        "preset_id": "blue-classroom",
        "source": "manual",
        "sections": [
            {
                "id": "section-1",
                "template_id": "open-canvas",
                "title": "Quiz section",
                "position": 0,
                "block_ids": ["quiz-1", "short-1", "practice-1", "fib-1"],
            }
        ],
        "blocks": {
            "quiz-1": {
                "id": "quiz-1",
                "component_id": "quiz-check",
                "position": 0,
                "content": {
                    "question": "2 + 2 = ?",
                    "options": [
                        {"text": "3", "correct": False, "explanation": "Too small"},
                        {"text": "4", "correct": True, "explanation": "Correct sum"},
                    ],
                    "feedback_correct": "Great work.",
                    "feedback_incorrect": "Try again.",
                },
            },
            "short-1": {
                "id": "short-1",
                "component_id": "short-answer",
                "position": 1,
                "content": {
                    "question": "Explain equivalent fractions.",
                    "marks": 2,
                    "mark_scheme": "1 mark for definition, 1 mark for example",
                },
            },
            "practice-1": {
                "id": "practice-1",
                "component_id": "practice-stack",
                "position": 2,
                "content": {
                    "problems": [
                        {
                            "difficulty": "warm",
                            "question": "Simplify 6/8",
                            "hints": [{"level": 1, "text": "Divide numerator and denominator by 2"}],
                            "solution": {"approach": "Divide by 2", "answer": "3/4"},
                        }
                    ]
                },
            },
            "fib-1": {
                "id": "fib-1",
                "component_id": "fill-in-blank",
                "position": 3,
                "content": {
                    "segments": [
                        {"text": "The value is ", "is_blank": False},
                        {"text": "", "is_blank": True, "answer": "4"},
                    ]
                },
            },
        },
        "media": {},
        "created_at": "2026-05-13T00:00:00Z",
        "updated_at": "2026-05-13T00:00:00Z",
    }


class _FakeGcsStore:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.calls: list[dict[str, str | int]] = []

    async def upload_with_key(
        self, *, key: str, image_bytes: bytes, content_type: str = "image/png"
    ) -> str | None:
        self.calls.append(
            {
                "key": key,
                "content_type": content_type,
                "size": len(image_bytes),
            }
        )
        return f"https://cdn.example.test/{key}"


@pytest.fixture(autouse=True)
def _install_dependency_overrides(db_session_factory):
    state = {"user": USER_A, "gcs_store": _FakeGcsStore()}

    async def override_current_user():
        return state["user"]

    async def override_session():
        async with db_session_factory() as session:
            yield session

    def override_gcs_store():
        return state["gcs_store"]

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_gcs_image_store] = override_gcs_store
    yield state
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def _seed_users_and_generations(db_session_factory):
    async with db_session_factory() as session:
        session.add(
            UserModel(
                id=USER_A.id,
                email=USER_A.email,
                name=USER_A.name,
            )
        )
        session.add(
            UserModel(
                id=USER_B.id,
                email=USER_B.email,
                name=USER_B.name,
            )
        )
        session.add(
            GenerationModel(
                id="gen-owned-by-a",
                user_id=USER_A.id,
                subject="mathematics",
                context="",
                requested_template_id="guided-concept-path",
                requested_preset_id="blue-classroom",
                status="completed",
            )
        )
        session.add(
            GenerationModel(
                id="gen-owned-by-b",
                user_id=USER_B.id,
                subject="physics",
                context="",
                requested_template_id="guided-concept-path",
                requested_preset_id="blue-classroom",
                status="completed",
            )
        )
        await session.commit()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestBuilderLessonRoutes:
    async def test_create_load_update_list_and_delete(self):
        create_body = {
            "source_type": "manual",
            "title": "Fractions draft",
            "document": _minimal_lesson(),
        }

        async with await _client() as client:
            create_response = await client.post("/api/v1/builder/lessons", json=create_body)
            assert create_response.status_code == 201
            created = create_response.json()
            lesson_id = created["id"]
            assert created["source_type"] == "manual"
            assert created["title"] == "Fractions draft"
            assert created["document"]["id"] == lesson_id
            assert created["document"]["title"] == "Fractions draft"

            list_response = await client.get("/api/v1/builder/lessons")
            assert list_response.status_code == 200
            listed = list_response.json()
            assert len(listed) == 1
            assert listed[0]["id"] == lesson_id

            load_response = await client.get(f"/api/v1/builder/lessons/{lesson_id}")
            assert load_response.status_code == 200
            loaded = load_response.json()
            block_id = loaded["document"]["sections"][0]["block_ids"][0]
            loaded["document"]["blocks"][block_id]["content"] = {"body": "Updated explanation"}

            update_response = await client.put(
                f"/api/v1/builder/lessons/{lesson_id}",
                json={"title": "Fractions final", "document": loaded["document"]},
            )
            assert update_response.status_code == 200
            updated = update_response.json()
            assert updated["title"] == "Fractions final"
            assert updated["document"]["id"] == lesson_id
            assert updated["document"]["blocks"][block_id]["content"]["body"] == "Updated explanation"

            delete_response = await client.delete(f"/api/v1/builder/lessons/{lesson_id}")
            assert delete_response.status_code == 204
            after_delete = await client.get(f"/api/v1/builder/lessons/{lesson_id}")
            assert after_delete.status_code == 404

    async def test_owner_checks_block_cross_user_access(self, _install_dependency_overrides):
        async with await _client() as client:
            created = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": _minimal_lesson()},
            )
            assert created.status_code == 201
            lesson_id = created.json()["id"]

            _install_dependency_overrides["user"] = USER_B
            forbidden_get = await client.get(f"/api/v1/builder/lessons/{lesson_id}")
            forbidden_put = await client.put(
                f"/api/v1/builder/lessons/{lesson_id}",
                json={"document": _minimal_lesson(document_id=lesson_id)},
            )
            forbidden_delete = await client.delete(f"/api/v1/builder/lessons/{lesson_id}")

        assert forbidden_get.status_code == 404
        assert forbidden_put.status_code == 404
        assert forbidden_delete.status_code == 404

    async def test_create_from_generation_requires_owned_generation(self):
        async with await _client() as client:
            ok_response = await client.post(
                "/api/v1/builder/lessons",
                json={
                    "source_type": "v3_generation",
                    "source_generation_id": "gen-owned-by-a",
                    "document": _minimal_lesson(),
                },
            )
            assert ok_response.status_code == 201

            denied_response = await client.post(
                "/api/v1/builder/lessons",
                json={
                    "source_type": "v3_generation",
                    "source_generation_id": "gen-owned-by-b",
                    "document": _minimal_lesson(),
                },
            )
            assert denied_response.status_code == 404

    async def test_rejects_unknown_component_and_bad_section_references(self):
        invalid_component = _minimal_lesson()
        block_id = invalid_component["sections"][0]["block_ids"][0]
        invalid_component["blocks"][block_id]["component_id"] = "not-a-real-component"

        bad_reference = _minimal_lesson()
        bad_reference["sections"][0]["block_ids"] = ["missing-block"]

        async with await _client() as client:
            unknown_component_response = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": invalid_component},
            )
            missing_block_response = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": bad_reference},
            )

        assert unknown_component_response.status_code == 400
        assert missing_block_response.status_code == 422

    async def test_media_upload_uses_gcs_with_lesson_owned_path(self, _install_dependency_overrides):
        async with await _client() as client:
            created = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": _minimal_lesson()},
            )
            assert created.status_code == 201
            lesson_id = created.json()["id"]

            upload = await client.post(
                f"/api/v1/builder/lessons/{lesson_id}/media/upload",
                files={"file": ("diagram.png", b"\x89PNG\r\n\x1a\nfake-image", "image/png")},
            )

        assert upload.status_code == 200
        body = upload.json()
        assert body["type"] == "image"
        assert body["mime_type"] == "image/png"
        assert body["url"].startswith("https://cdn.example.test/editable-lessons/")
        calls = _install_dependency_overrides["gcs_store"].calls
        assert len(calls) == 1
        assert calls[0]["key"].startswith(f"editable-lessons/{lesson_id}/media/")
        assert calls[0]["content_type"] == "image/png"

    async def test_media_upload_requires_lesson_ownership(self, _install_dependency_overrides):
        async with await _client() as client:
            created = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": _minimal_lesson()},
            )
            assert created.status_code == 201
            lesson_id = created.json()["id"]

            _install_dependency_overrides["user"] = USER_B
            denied = await client.post(
                f"/api/v1/builder/lessons/{lesson_id}/media/upload",
                files={"file": ("diagram.png", b"\x89PNG\r\n\x1a\nfake-image", "image/png")},
            )

        assert denied.status_code == 404

    async def test_media_upload_rejects_unsupported_content_type(self):
        async with await _client() as client:
            created = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": _minimal_lesson()},
            )
            assert created.status_code == 201
            lesson_id = created.json()["id"]

            upload = await client.post(
                f"/api/v1/builder/lessons/{lesson_id}/media/upload",
                files={"file": ("note.txt", b"not-an-image", "text/plain")},
            )

        assert upload.status_code == 415

    async def test_media_upload_rejects_oversized_file(self):
        async with await _client() as client:
            created = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": _minimal_lesson()},
            )
            assert created.status_code == 201
            lesson_id = created.json()["id"]

            oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024 + 1)
            upload = await client.post(
                f"/api/v1/builder/lessons/{lesson_id}/media/upload",
                files={"file": ("huge.png", oversized, "image/png")},
            )

        assert upload.status_code == 413

    async def test_print_document_student_mode_strips_answers_without_mutating_saved_document(self):
        async with await _client() as client:
            created = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": _lesson_with_answers()},
            )
            assert created.status_code == 201
            lesson_id = created.json()["id"]

            teacher_view = await client.get(
                f"/api/v1/builder/lessons/{lesson_id}/print-document",
                params={"audience": "teacher"},
            )
            student_view = await client.get(
                f"/api/v1/builder/lessons/{lesson_id}/print-document",
                params={"audience": "student"},
            )
            saved = await client.get(f"/api/v1/builder/lessons/{lesson_id}")

        assert teacher_view.status_code == 200
        assert student_view.status_code == 200
        assert saved.status_code == 200

        teacher_doc = teacher_view.json()
        student_doc = student_view.json()
        saved_doc = saved.json()["document"]

        assert teacher_doc["blocks"]["quiz-1"]["content"]["options"][1]["correct"] is True
        assert teacher_doc["blocks"]["short-1"]["content"]["mark_scheme"]
        assert teacher_doc["blocks"]["practice-1"]["content"]["problems"][0]["solution"]["answer"] == "3/4"
        assert teacher_doc["blocks"]["fib-1"]["content"]["segments"][1]["answer"] == "4"

        student_options = student_doc["blocks"]["quiz-1"]["content"]["options"]
        assert all(option["correct"] is False for option in student_options)
        assert all(option["explanation"] == "" for option in student_options)
        assert student_doc["blocks"]["quiz-1"]["content"]["feedback_correct"] == ""
        assert student_doc["blocks"]["quiz-1"]["content"]["feedback_incorrect"] == ""
        assert "mark_scheme" not in student_doc["blocks"]["short-1"]["content"]
        assert "solution" not in student_doc["blocks"]["practice-1"]["content"]["problems"][0]
        assert "answer" not in student_doc["blocks"]["fib-1"]["content"]["segments"][1]

        # Export views must not mutate the persisted teacher-owned lesson.
        assert saved_doc["blocks"]["quiz-1"]["content"]["options"][1]["correct"] is True
        assert saved_doc["blocks"]["short-1"]["content"]["mark_scheme"]
        assert saved_doc["blocks"]["practice-1"]["content"]["problems"][0]["solution"]["answer"] == "3/4"
        assert saved_doc["blocks"]["fib-1"]["content"]["segments"][1]["answer"] == "4"

    async def test_print_document_and_export_pdf_enforce_ownership(self, _install_dependency_overrides):
        async with await _client() as client:
            created = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": _minimal_lesson()},
            )
            assert created.status_code == 201
            lesson_id = created.json()["id"]

            _install_dependency_overrides["user"] = USER_B

            denied_print = await client.get(
                f"/api/v1/builder/lessons/{lesson_id}/print-document",
                params={"audience": "student"},
            )

            denied_export = await client.post(
                f"/api/v1/builder/lessons/{lesson_id}/export/pdf",
                json={"audience": "student"},
            )

        assert denied_print.status_code == 404
        assert denied_export.status_code == 404

    async def test_print_preflight_enforces_ownership(self, _install_dependency_overrides):
        async with await _client() as client:
            created = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": _minimal_lesson()},
            )
            assert created.status_code == 201
            lesson_id = created.json()["id"]

            _install_dependency_overrides["user"] = USER_B
            denied = await client.post(
                f"/api/v1/builder/lessons/{lesson_id}/print-preflight",
                json={"audience": "student"},
            )

        assert denied.status_code == 404

    async def test_print_preflight_returns_playwright_report(self):
        async with await _client() as client:
            created = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": _minimal_lesson()},
            )
            assert created.status_code == 201
            lesson_id = created.json()["id"]

            captured: dict[str, object] = {}

            async def fake_preflight(**kwargs):
                captured.update(kwargs)
                return {
                    "print_layout_report": {
                        "page_count_estimate": 4,
                        "images_loaded": "3",
                        "images_failed": "2",
                        "images_timed_out": "1",
                        "print_contract_coverage": {"declared": 5, "total": 6},
                        "oversized_blocks": [
                            {"type": "atomic", "block": "practice-stack", "height": 1200}
                        ],
                    }
                }

            with patch("builder.routes.render_generation_print_preflight", side_effect=fake_preflight):
                response = await client.post(
                    f"/api/v1/builder/lessons/{lesson_id}/print-preflight",
                    json={"audience": "student"},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["page_count_estimate"] == 4
        assert body["images"] == {"loaded": 3, "failed": 2, "timed_out": 1}
        assert body["print_contract_coverage"] == {"declared": 5, "total": 6}
        assert body["oversized_blocks"] == [
            {"type": "atomic", "block": "practice-stack", "height": 1200}
        ]
        assert "Block practice-stack is taller than one A4 page." in body["warnings"]
        assert "2 images failed to load." in body["warnings"]
        assert "1 images timed out while loading." in body["warnings"]
        assert captured["render_path"] == f"/builder/print/{lesson_id}?audience=student"

    async def test_export_pdf_uses_builder_print_route_and_audience(self, tmp_path: Path):
        async with await _client() as client:
            created = await client.post(
                "/api/v1/builder/lessons",
                json={"source_type": "manual", "document": _minimal_lesson()},
            )
            assert created.status_code == 201
            lesson_id = created.json()["id"]

            exported_pdf = tmp_path / "builder.pdf"
            exported_pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

            captured: dict[str, object] = {}

            async def fake_export_generation_pdf(**kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    pdf_path=exported_pdf,
                    filename="builder-student.pdf",
                    file_size_bytes=exported_pdf.stat().st_size,
                    page_count=3,
                    generation_time_ms=420,
                    cleanup_paths=[],
                    print_page_debug=None,
                )

            with patch("builder.routes.export_generation_pdf", side_effect=fake_export_generation_pdf):
                response = await client.post(
                    f"/api/v1/builder/lessons/{lesson_id}/export/pdf",
                    json={"audience": "student"},
                )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["x-page-count"] == "3"
        assert response.headers["x-file-size"] == str(exported_pdf.stat().st_size)
        assert response.headers["x-generation-time-ms"] == "420"

        assert captured["render_path"] == f"/builder/print/{lesson_id}?audience=student"
        request_body = captured["request"]
        assert getattr(request_body, "include_answers", None) is False
