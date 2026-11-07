from __future__ import annotations

import os
from typing import Any

from .storage import Store

MISSION = "Act as the decision memory for this business. Never invent numbers. Cite the memories used and say when evidence is thin."


class HindsightMemory:
    """The one boundary around Hindsight Cloud; all failures fall back to local audit memory."""
    def __init__(self, store: Store):
        self.store = store
        self.api_key = os.getenv("HINDSIGHT_API_KEY", "").strip()
        self.base_url = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io").rstrip("/")
        self.bank_id = os.getenv("HINDSIGHT_BANK_ID", "whatif-lumen-wick")
        self.client: Any | None = None
        self.bank_attempted = False
        self.last_error: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> Any | None:
        if not self.configured: return None
        if self.client is None:
            try:
                from hindsight_client import Hindsight
                self.client = Hindsight(base_url=self.base_url, api_key=self.api_key, timeout=20)
            except Exception as exc: self.last_error = str(exc); return None
        return self.client

    def _ensure_bank(self) -> bool:
        client = self._get_client()
        if not client: return False
        if self.bank_attempted: return True
        self.bank_attempted = True
        try:
            client.create_bank(bank_id=self.bank_id, name="WHATIF · Lumen & Wick", mission=MISSION,
                               disposition={"skepticism": .9, "literalism": .9, "empathy": .2},
                               enable_observations=True, enable_temporal_retrieval=True, enable_graph_retrieval=True,
                               reflect_mission="Explain only from retrieved business experience. Do not change numeric beliefs.")
        except Exception as exc:
            # Existing banks commonly produce a conflict. It is safe to continue and prove it on retain.
            self.last_error = str(exc)
        return True

    def retain(self, kind: str, document_id: str, content: str, tags: list[str], timestamp: str | None = None) -> dict[str, Any]:
        state = "local"
        client = self._get_client()
        if client and self._ensure_bank():
            try:
                client.retain(bank_id=self.bank_id, content=content, document_id=document_id, tags=tags,
                              timestamp=timestamp, context=f"WHATIF {kind}", update_mode="replace")
                state = "hindsight"
            except Exception as exc:
                self.last_error = str(exc)
                # Update modes differ across older servers; retaining a new version is still valuable.
                try:
                    client.retain(bank_id=self.bank_id, content=content, document_id=document_id, tags=tags, timestamp=timestamp, context=f"WHATIF {kind}")
                    state = "hindsight"
                except Exception as retry_exc: self.last_error = str(retry_exc)
        self.store.add_memory_event(kind, document_id, content, tags, state)
        return {"state": state, "bank_id": self.bank_id if state == "hindsight" else None}

    def recall(self, query: str, tags: list[str] | None = None, memory_on: bool = True) -> dict[str, Any]:
        if not memory_on: return {"enabled": False, "source": "off", "items": []}
        client = self._get_client()
        if client and self._ensure_bank():
            try:
                response = client.recall(bank_id=self.bank_id, query=query, tags=tags or None, tags_match="any", max_tokens=900, budget="low")
                items = []
                for result in getattr(response, "results", [])[:5]:
                    items.append({"id": str(getattr(result, "id", "")), "text": getattr(result, "text", str(result)), "tags": list(getattr(result, "tags", []) or []), "type": getattr(result, "type", "memory"), "source": "hindsight"})
                return {"enabled": True, "source": "hindsight", "items": items}
            except Exception as exc: self.last_error = str(exc)
        return {"enabled": True, "source": "local", "items": self.store.local_recall(query)}

    def reflect(self, query: str, tags: list[str] | None = None) -> dict[str, Any]:
        client = self._get_client()
        if client and self._ensure_bank():
            try:
                response = client.reflect(bank_id=self.bank_id, query=query, tags=tags or None, budget="low", max_tokens=500, include_facts=True)
                return {"source": "hindsight", "text": getattr(response, "text", str(response)), "facts": getattr(response, "facts", [])}
            except Exception as exc: self.last_error = str(exc)
        recalled = self.store.local_recall(query, 3)
        if not recalled: return {"source": "local", "text": "There is not enough reviewed evidence yet. WHATIF is using starting assumptions and will learn only after a clean review.", "facts": []}
        return {"source": "local", "text": "Based on recorded experience: " + " ".join(item["text"] for item in recalled), "facts": recalled}

    def status(self) -> dict[str, Any]:
        return {"configured": self.configured, "bank_id": self.bank_id if self.configured else None, "last_error": self.last_error, "mode": "Hindsight Cloud" if self.configured else "Local demo memory"}
