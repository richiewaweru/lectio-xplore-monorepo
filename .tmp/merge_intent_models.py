from pathlib import Path
import re

src = Path(r"C:\Projects\Textbook agent\backend\src\v3_blueprint\planning\models.py").read_text(
    encoding="utf-8"
)
dst = Path(r"C:\Projects\lectio\apps\textbook-agent\backend\src\v3_blueprint\planning\models.py")
mono = dst.read_text(encoding="utf-8")

# Extract from IntentSectionPlan through end of intent_plan_to_structural_plan
start = src.index("class IntentSectionPlan(BaseModel):")
# find function end: next top-level def/class after the function, or EOF
fn_start = src.index("def intent_plan_to_structural_plan(")
rest = src[fn_start:]
# naive: take until double newline followed by class/def at column 0, or EOF
m = re.search(r"\n(?=class |\ndef |\Z)", rest[1:])
end = fn_start + 1 + (m.start() if m else len(rest) - 1)
snippet = src[start:end].rstrip() + "\n"

if "class IntentPlan(BaseModel)" in mono:
    print("already present")
else:
    # append before final line if any
    dst.write_text(mono.rstrip() + "\n\n\n" + snippet, encoding="utf-8")
    print("appended IntentPlan helpers", len(snippet))
