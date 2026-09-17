from pathlib import Path
import re

path = Path("apps/textbook-agent/backend/src/builder/routes.py")
text = path.read_text(encoding="utf-8")

# Remove PDF request/response models
text = re.sub(
    r"\nclass BuilderLessonPDFExportRequest\(BaseModel\):.*?class BuilderLessonPrintPreflightRequest\(BaseModel\):.*?\n\n",
    "\n",
    text,
    count=1,
    flags=re.S,
)
text = re.sub(
    r"\nclass BuilderPrintPreflightImages\(BaseModel\):.*?class BuilderPrintPreflightResponse\(BaseModel\):.*?\n\n",
    "\n",
    text,
    count=1,
    flags=re.S,
)

# Remove helpers from _first_section_template_id through _builder_print_preflight_response (keep _log_builder_event)
text = re.sub(
    r"\ndef _first_section_template_id\(document: dict\[str, Any\]\) -> str:.*?def _log_builder_event\(",
    "\ndef _log_builder_event(",
    text,
    count=1,
    flags=re.S,
)

# Remove export/pdf and print-preflight routes; keep print-document
text = re.sub(
    r"\n@router\.post\(\"/lessons/\{lesson_id\}/export/pdf\"\).*?\n@router\.post\(\"/lessons/\{lesson_id\}/print-preflight\".*$",
    "\n",
    text,
    count=1,
    flags=re.S,
)

path.write_text(text, encoding="utf-8", newline="\n")
print("builder routes length", len(text.splitlines()))
# sanity
assert "export_generation_pdf" not in text
assert "print-preflight" not in text
assert "print-document" in text
assert "_owned_lesson_or_404" in text
print("ok")
