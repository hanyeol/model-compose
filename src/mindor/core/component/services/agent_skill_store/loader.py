from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
import yaml

@dataclass
class AgentSkill:
    """A parsed Agent Skills entry (native format)."""
    name: str
    description: str
    body: str
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "metadata": self.metadata,
            "body": self.body,
        }

class AgentSkillParser:
    """Parse SKILL.md documents per the Anthropic Agent Skills spec.

    Stateless: a single instance can parse any number of documents,
    sequentially or concurrently.
    """

    def parse(self, name: str, text: str) -> AgentSkill:
        """Return the parsed skill. Falls back gracefully on malformed frontmatter."""
        frontmatter, body = self._split_frontmatter(text)
        metadata = frontmatter.get("metadata") or {}

        return AgentSkill(
            name=frontmatter.get("name") or name,
            description=frontmatter.get("description", ""),
            body=body,
            tags=self._normalize_tags(metadata.get("tags")),
            metadata=metadata,
        )

    def _split_frontmatter(self, text: str) -> tuple[Dict[str, Any], str]:
        """Return (frontmatter dict, body) for a SKILL.md document.

        The spec requires ``---\\n...\\n---\\n`` at the very top. Missing or
        malformed frontmatter yields ({}, text) so partial skills still surface.
        """
        if not text.startswith("---"):
            return {}, text

        end = text.find("\n---", 3)

        if end == -1:
            return {}, text

        yaml_text = text[3:end].lstrip("\n")
        body_start = end + len("\n---")

        if body_start < len(text) and text[body_start] == "\n":
            body_start += 1

        try:
            frontmatter = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError:
            return {}, text

        if not isinstance(frontmatter, dict):
            return {}, text

        return frontmatter, text[body_start:]

    def _normalize_tags(self, tags: Any) -> List[str]:
        if isinstance(tags, str):
            return [ tag.strip() for tag in tags.split(",") if tag.strip() ]

        if isinstance(tags, list):
            return [ str(tag) for tag in tags ]

        return []
