"""
Voice notes storage - saves transcribed notes as local files.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


class NotesStore:
    """Stores and retrieves voice notes from local JSON files."""

    def __init__(self, notes_dir: Path):
        self.notes_dir = Path(notes_dir)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.notes_dir / "index.json"
        self._index: List[Dict] = []
        self._load_index()
        logger.info(f"NotesStore initialized: {self.notes_dir}")

    def _load_index(self):
        """Load the notes index from disk."""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    self._index = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load notes index: {e}")
                self._index = []
        else:
            self._index = []

    def _save_index(self):
        """Save the notes index to disk."""
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self._index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save notes index: {e}")

    def save_note(self, raw_text: str, enhanced_text: str, tags: Optional[List[str]] = None) -> Dict:
        """Save a new voice note.

        Args:
            raw_text: The original transcription
            enhanced_text: The cleaned-up/enhanced version
            tags: Optional tags for categorization

        Returns:
            The saved note entry
        """
        now = datetime.now()
        note_id = now.strftime("%Y%m%d_%H%M%S")
        filename = f"{note_id}.json"

        note = {
            "id": note_id,
            "timestamp": now.isoformat(),
            "raw_text": raw_text,
            "text": enhanced_text,
            "tags": tags or [],
            "filename": filename,
        }

        # Save note file
        note_path = self.notes_dir / filename
        try:
            with open(note_path, 'w', encoding='utf-8') as f:
                json.dump(note, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save note: {e}")
            return note

        # Update index
        index_entry = {
            "id": note_id,
            "timestamp": now.isoformat(),
            "preview": enhanced_text[:100],
            "tags": tags or [],
            "filename": filename,
        }
        self._index.insert(0, index_entry)
        self._save_index()

        logger.info(f"Note saved: {note_id}")
        return note

    def get_note(self, note_id: str) -> Optional[Dict]:
        """Retrieve a note by ID."""
        for entry in self._index:
            if entry["id"] == note_id:
                note_path = self.notes_dir / entry["filename"]
                if note_path.exists():
                    with open(note_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
        return None

    def list_notes(self, limit: int = 50) -> List[Dict]:
        """List recent notes (index entries)."""
        return self._index[:limit]

    def search_notes(self, query: str) -> List[Dict]:
        """Search notes by text content."""
        query_lower = query.lower()
        results = []
        for entry in self._index:
            if query_lower in entry.get("preview", "").lower():
                results.append(entry)
                continue
            # Check full note file for deeper search
            note = self.get_note(entry["id"])
            if note and query_lower in note.get("text", "").lower():
                results.append(entry)
        return results

    def delete_note(self, note_id: str) -> bool:
        """Delete a note by ID."""
        for i, entry in enumerate(self._index):
            if entry["id"] == note_id:
                note_path = self.notes_dir / entry["filename"]
                if note_path.exists():
                    note_path.unlink()
                self._index.pop(i)
                self._save_index()
                logger.info(f"Note deleted: {note_id}")
                return True
        return False

    def get_note_count(self) -> int:
        return len(self._index)
