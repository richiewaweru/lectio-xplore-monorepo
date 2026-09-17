from pathlib import Path

p = Path("packages/lectio-learn/src/lib/learn/capabilities/interactions.ts")
text = p.read_text(encoding="utf-8")
marker = "id: 'image-hotspot'"
parts = text.split(marker, 1)
if len(parts) != 2:
    raise SystemExit(f"marker not found uniquely: {len(parts)}")
head, tail = parts
head = head.replace("authoring_support: false", "authoring_support: true")
head = head.replace("consumer_selection_support: false", "consumer_selection_support: true")
out = head + marker + tail
p.write_text(out, encoding="utf-8")
print(
    "remaining false:",
    out.count("authoring_support: false"),
    out.count("consumer_selection_support: false"),
)
