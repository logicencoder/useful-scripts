"""Load MEXC WebSocket decoders from generated_proto/ (built from mexc_api_schema_from_github/)."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional


def setup_proto_env() -> None:
    """Required when pip protobuf >= 4.x and protoc is 3.12."""
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")


def _ensure_generated_proto_on_path() -> None:
    if not os.path.isdir("generated_proto"):
        raise FileNotFoundError(
            "generated_proto/ not found — run: python3 mexc_proto_auto_setup.py"
        )
    if "generated_proto" not in sys.path:
        sys.path.insert(0, "generated_proto")


def load_orderbook_modules() -> Dict[str, Any]:
    """Wrapper + public depth modules (orderbook monitors)."""
    setup_proto_env()
    _ensure_generated_proto_on_path()
    import PushDataV3ApiWrapper_pb2
    import PublicLimitDepthsV3Api_pb2
    import PublicAggreDepthsV3Api_pb2

    return {
        "wrapper": PushDataV3ApiWrapper_pb2,
        "limit_depths": PublicLimitDepthsV3Api_pb2,
        "aggre_depths": PublicAggreDepthsV3Api_pb2,
    }


def load_balance_modules() -> Dict[str, Any]:
    """Wrapper + private account (balance monitor)."""
    setup_proto_env()
    _ensure_generated_proto_on_path()
    import PrivateAccountV3Api_pb2
    import PushDataV3ApiWrapper_pb2

    return {
        "wrapper": PushDataV3ApiWrapper_pb2,
        "account": PrivateAccountV3Api_pb2,
    }


def load_orderbook_modules_safe() -> tuple[Optional[Dict[str, Any]], bool]:
    try:
        return load_orderbook_modules(), True
    except Exception:
        return None, False


def load_balance_modules_safe() -> tuple[Optional[Dict[str, Any]], bool]:
    try:
        return load_balance_modules(), True
    except Exception:
        return None, False
