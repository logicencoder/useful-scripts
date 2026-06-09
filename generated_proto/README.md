# generated_proto

Compiled Python modules (`*_pb2.py`) used by all MEXC monitor scripts.

**Do not rename this folder** — every `mexc_*` script imports from here via `mexc_proto_loader.py`.

Regenerate after updating GitHub schemas:

```bash
python3 mexc_proto_auto_setup.py
```

Sources live in `mexc_api_schema_from_github/` (downloaded from https://github.com/mexcdevelop/websocket-proto).
