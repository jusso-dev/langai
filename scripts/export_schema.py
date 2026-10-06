import json
from pathlib import Path
from apps.api.main import app
from apps.api.schemas import DictionaryEntrySchema, Governance

Path("packages/schemas/openapi.json").write_text(
    json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"
)
print("Exported OpenAPI contract")

for schema in [DictionaryEntrySchema, Governance]:
    Path(f"packages/schemas/{schema.__name__}.json").write_text(
        json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2) + "\n"
    )
