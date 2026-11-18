"""Smoke tests for agent-skill-store component, parser, and action dispatcher."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import TypeAdapter, ValidationError

from mindor.dsl.schema.component import (
    ComponentConfig,
    AgentSkillStoreComponentConfig,
    AgentSkillRepositoryActions,
)
from mindor.dsl.schema.action import (
    AgentSkillStoreActionMethod,
    AgentSkillStoreListActionConfig,
    AgentSkillStoreGetActionConfig,
    AgentSkillStoreFindActionConfig,
)
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.agent_skill_store.agent_skill_store import (
    AgentSkillStoreAction,
    AgentSkillStoreComponent,
)
from mindor.core.component.services.agent_skill_store.loader import (
    AgentSkill,
    AgentSkillParser,
)


_SAMPLE_SKILLS: Dict[str, str] = {
    "pdf": """---
name: pdf
description: Read PDF documents.
metadata:
  tags: [documents, pdf]
---
pdf body
""",
    "docx": """---
name: docx
description: Edit Word files.
metadata:
  tags: [documents, office]
---
docx body
""",
    "weather": """---
name: weather
description: Fetch weather for a city.
metadata:
  tags: [api]
---
weather body
""",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_context():
    """ComponentActionContext with passthrough render_variable + real render_text_array."""
    from mindor.core.foundation.variable.text import TextValueRenderer

    context = MagicMock(spec=ComponentActionContext)
    context.cancellation_token = None

    async def render_variable(value, ignore_files=False):
        return value

    async def render_text_array(value, item_is_list=False, single_as_array=False):
        return await TextValueRenderer().render_array(value, item_is_list, single_as_array)

    context.render_variable = AsyncMock(side_effect=render_variable)
    context.render_text_array = AsyncMock(side_effect=render_text_array)
    context.register_source = MagicMock()
    return context


def make_repository(skills: Optional[Dict[str, str]] = None):
    """Create a mock repository component whose `list` and `get` actions mirror file-store responses.

    `skills` maps skill name to raw SKILL.md text; defaults to the full sample set.
    """
    corpus = _SAMPLE_SKILLS if skills is None else skills
    repo = MagicMock()

    async def run(action_id: str, run_id: str, input: Dict[str, Any]) -> Dict[str, Any]:
        if action_id == "list":
            return {
                "items": [ {"path": f"{name}/SKILL.md"} for name in sorted(corpus.keys()) ],
                "count": len(corpus),
                "next_token": None,
            }
        if action_id == "get":
            path = input["path"]
            name = path.split("/", 1)[0]
            if name not in corpus:
                raise FileNotFoundError(f"File not found: {path!r}")
            return {"path": path, "content": corpus[name]}
        raise ValueError(f"Unexpected action id: {action_id}")

    repo.run = AsyncMock(side_effect=run)
    return repo


def make_action(action_config, repository=None, repository_actions=None) -> AgentSkillStoreAction:
    return AgentSkillStoreAction(
        action_config,
        repository or make_repository(),
        repository_actions or AgentSkillRepositoryActions(),
    )


# ──────────────────────────────────────────────
# Schema validation
# ──────────────────────────────────────────────


class TestAgentSkillStoreSchema:
    component_adapter = TypeAdapter(ComponentConfig)

    def test_minimal_config_with_shorthand_repository(self):
        cfg = self.component_adapter.validate_python({
            "id": "skills",
            "type": "agent-skill-store",
            "repository": "local-fs",
            "actions": [],
        })
        assert cfg.type.value == "agent-skill-store"
        assert cfg.repository.component == "local-fs"
        assert cfg.repository.actions.list == "list"
        assert cfg.repository.actions.get == "get"
        assert cfg.actions == []

    def test_full_repository_form(self):
        cfg = self.component_adapter.validate_python({
            "id": "skills",
            "type": "agent-skill-store",
            "repository": {
                "component": "local-fs",
                "actions": {"list": "scan", "get": "fetch"},
            },
        })
        assert cfg.repository.component == "local-fs"
        assert cfg.repository.actions.list == "scan"
        assert cfg.repository.actions.get == "fetch"

    def test_all_three_actions(self):
        cfg = self.component_adapter.validate_python({
            "id": "skills",
            "type": "agent-skill-store",
            "repository": "local-fs",
            "actions": [
                {"id": "list_all", "method": "list"},
                {"id": "get_pdf", "method": "get", "name": "pdf"},
                {"id": "find_doc", "method": "find", "query": "docs"},
            ],
        })
        methods = [a.method.value for a in cfg.actions]
        assert methods == ["list", "get", "find"]

    def test_repository_required(self):
        with pytest.raises(ValidationError, match="repository"):
            self.component_adapter.validate_python({
                "id": "skills",
                "type": "agent-skill-store",
                "actions": [],
            })

    def test_get_requires_name(self):
        with pytest.raises(ValidationError, match="name"):
            self.component_adapter.validate_python({
                "id": "skills",
                "type": "agent-skill-store",
                "repository": "fs",
                "actions": [{"method": "get"}],
            })

    def test_find_requires_query(self):
        with pytest.raises(ValidationError, match="query"):
            self.component_adapter.validate_python({
                "id": "skills",
                "type": "agent-skill-store",
                "repository": "fs",
                "actions": [{"method": "find"}],
            })

    def test_find_limit_positive(self):
        with pytest.raises(ValidationError):
            self.component_adapter.validate_python({
                "id": "skills",
                "type": "agent-skill-store",
                "repository": "fs",
                "actions": [{"method": "find", "query": "x", "limit": 0}],
            })


# ──────────────────────────────────────────────
# AgentSkillParser (text-based)
# ──────────────────────────────────────────────


class TestAgentSkillParser:
    def test_parse_minimal_frontmatter(self):
        skill = AgentSkillParser().parse("sk", "---\nname: sk\ndescription: Does a thing.\n---\nHello body.\n")
        assert skill.name == "sk"
        assert skill.description == "Does a thing."
        assert skill.body.strip() == "Hello body."
        assert skill.tags == []
        assert skill.metadata == {}

    def test_tags_from_list(self):
        skill = AgentSkillParser().parse("sk", "---\nname: sk\ndescription: x\nmetadata:\n  tags: [a, b]\n---\n")
        assert skill.tags == ["a", "b"]

    def test_tags_from_csv_string(self):
        skill = AgentSkillParser().parse("sk", "---\nname: sk\nmetadata:\n  tags: 'a, b , c'\n---\n")
        assert skill.tags == ["a", "b", "c"]

    def test_tags_invalid_type_becomes_empty(self):
        skill = AgentSkillParser().parse("sk", "---\nname: sk\nmetadata:\n  tags: 42\n---\n")
        assert skill.tags == []

    def test_no_frontmatter_preserved_as_body(self):
        skill = AgentSkillParser().parse("fallback", "# Just body\nno frontmatter\n")
        assert skill.name == "fallback"
        assert "Just body" in skill.body

    def test_malformed_yaml_preserved_as_body(self):
        skill = AgentSkillParser().parse("sk", "---\nname: [unclosed\n---\n# Body\n")
        assert skill.name == "sk"
        assert "# Body" in skill.body

    def test_name_falls_back_to_passed_name(self):
        skill = AgentSkillParser().parse("my-skill", "---\ndescription: no name field\n---\nbody\n")
        assert skill.name == "my-skill"

    def test_metadata_passthrough(self):
        skill = AgentSkillParser().parse(
            "sk",
            "---\nname: sk\nmetadata:\n  author: example\n  version: '1.2'\n---\n",
        )
        assert skill.metadata.get("author") == "example"
        assert skill.metadata.get("version") == "1.2"

    def test_parser_is_reusable(self):
        parser = AgentSkillParser()
        s1 = parser.parse("one", "---\nname: one\ndescription: first\n---\n")
        s2 = parser.parse("two", "---\nname: two\ndescription: second\n---\n")
        assert (s1.name, s2.name) == ("one", "two")


# ──────────────────────────────────────────────
# AgentSkillStoreAction dispatch (non-streaming)
# ──────────────────────────────────────────────


class TestListAction:
    @pytest.mark.anyio
    async def test_returns_all_skills_as_dicts(self, mock_context):
        action = make_action(AgentSkillStoreListActionConfig(method="list"))
        result = await action.run(mock_context)
        assert [s["name"] for s in result] == ["docx", "pdf", "weather"]
        assert set(result[0].keys()) == {"name", "description", "tags", "metadata", "body"}

    @pytest.mark.anyio
    async def test_filter_by_single_tag(self, mock_context):
        action = make_action(AgentSkillStoreListActionConfig(method="list", tags=["api"]))
        result = await action.run(mock_context)
        assert [s["name"] for s in result] == ["weather"]

    @pytest.mark.anyio
    async def test_filter_by_multiple_tags_is_and(self, mock_context):
        action = make_action(AgentSkillStoreListActionConfig(method="list", tags=["documents", "pdf"]))
        result = await action.run(mock_context)
        assert [s["name"] for s in result] == ["pdf"]

    @pytest.mark.anyio
    async def test_filter_no_match_returns_empty(self, mock_context):
        action = make_action(AgentSkillStoreListActionConfig(method="list", tags=["nonexistent"]))
        result = await action.run(mock_context)
        assert result == []

    @pytest.mark.anyio
    async def test_registers_result_source(self, mock_context):
        action = make_action(AgentSkillStoreListActionConfig(method="list"))
        await action.run(mock_context)
        mock_context.register_source.assert_called()
        call = mock_context.register_source.call_args
        assert call.args[0] == "result"

    @pytest.mark.anyio
    async def test_invokes_repository_list_then_get_per_skill(self, mock_context):
        repo = make_repository()
        action = make_action(AgentSkillStoreListActionConfig(method="list"), repository=repo)
        await action.run(mock_context)

        action_ids = [call.args[0] for call in repo.run.call_args_list]
        assert action_ids[0] == "list"
        assert action_ids.count("get") == 3

    @pytest.mark.anyio
    async def test_honors_custom_repository_action_ids(self, mock_context):
        repo = make_repository()

        async def run(action_id: str, run_id: str, input: Dict[str, Any]) -> Dict[str, Any]:
            assert action_id in ("scan", "fetch")
            if action_id == "scan":
                return {"items": [{"path": "pdf/SKILL.md"}], "count": 1, "next_token": None}
            return {"path": input["path"], "content": _SAMPLE_SKILLS["pdf"]}

        repo.run = AsyncMock(side_effect=run)
        action = make_action(
            AgentSkillStoreListActionConfig(method="list"),
            repository=repo,
            repository_actions=AgentSkillRepositoryActions(list="scan", get="fetch"),
        )
        result = await action.run(mock_context)
        assert [s["name"] for s in result] == ["pdf"]


class TestGetAction:
    @pytest.mark.anyio
    async def test_get_by_name(self, mock_context):
        action = make_action(AgentSkillStoreGetActionConfig(method="get", name="pdf"))
        result = await action.run(mock_context)
        assert result["name"] == "pdf"
        assert "pdf body" in result["body"]

    @pytest.mark.anyio
    async def test_get_missing_raises(self, mock_context):
        action = make_action(AgentSkillStoreGetActionConfig(method="get", name="no-such-skill"))
        with pytest.raises(LookupError, match="no-such-skill"):
            await action.run(mock_context)

    @pytest.mark.anyio
    async def test_get_empty_name_raises(self, mock_context):
        action = make_action(AgentSkillStoreGetActionConfig(method="get", name=""))
        with pytest.raises(ValueError, match="'name' is required"):
            await action.run(mock_context)

    @pytest.mark.anyio
    async def test_get_fetches_only_one_skill_file(self, mock_context):
        repo = make_repository()
        action = make_action(AgentSkillStoreGetActionConfig(method="get", name="pdf"), repository=repo)
        await action.run(mock_context)
        assert repo.run.call_count == 1
        assert repo.run.call_args.args[0] == "get"


class TestFindAction:
    @pytest.mark.anyio
    async def test_find_in_name(self, mock_context):
        action = make_action(AgentSkillStoreFindActionConfig(method="find", query="pdf"))
        result = await action.run(mock_context)
        assert {s["name"] for s in result} == {"pdf"}

    @pytest.mark.anyio
    async def test_find_in_description(self, mock_context):
        action = make_action(AgentSkillStoreFindActionConfig(method="find", query="weather"))
        result = await action.run(mock_context)
        assert [s["name"] for s in result] == ["weather"]

    @pytest.mark.anyio
    async def test_find_in_tag(self, mock_context):
        action = make_action(AgentSkillStoreFindActionConfig(method="find", query="office"))
        result = await action.run(mock_context)
        assert [s["name"] for s in result] == ["docx"]

    @pytest.mark.anyio
    async def test_find_case_insensitive(self, mock_context):
        action = make_action(AgentSkillStoreFindActionConfig(method="find", query="PDF"))
        result = await action.run(mock_context)
        assert [s["name"] for s in result] == ["pdf"]

    @pytest.mark.anyio
    async def test_find_limit(self, mock_context):
        action = make_action(AgentSkillStoreFindActionConfig(method="find", query="documents", limit=1))
        result = await action.run(mock_context)
        assert len(result) == 1

    @pytest.mark.anyio
    async def test_find_with_tag_filter(self, mock_context):
        action = make_action(AgentSkillStoreFindActionConfig(method="find", query="documents", tags=["pdf"]))
        result = await action.run(mock_context)
        assert [s["name"] for s in result] == ["pdf"]

    @pytest.mark.anyio
    async def test_find_no_match(self, mock_context):
        action = make_action(AgentSkillStoreFindActionConfig(method="find", query="quantum"))
        result = await action.run(mock_context)
        assert result == []

    @pytest.mark.anyio
    async def test_find_empty_query_raises(self, mock_context):
        action = make_action(AgentSkillStoreFindActionConfig(method="find", query=""))
        with pytest.raises(ValueError, match="'query' is required"):
            await action.run(mock_context)


# ──────────────────────────────────────────────
# Batched (list input)
# ──────────────────────────────────────────────


class TestBatchedGet:
    @pytest.mark.anyio
    async def test_get_multiple_names_returns_list(self, mock_context):
        action = make_action(AgentSkillStoreGetActionConfig(method="get", name=["pdf", "docx"]))
        result = await action.run(mock_context)
        assert isinstance(result, list)
        assert [s["name"] for s in result] == ["pdf", "docx"]

    @pytest.mark.anyio
    async def test_get_missing_in_batch_raises(self, mock_context):
        action = make_action(AgentSkillStoreGetActionConfig(method="get", name=["pdf", "nope"]))
        with pytest.raises(LookupError, match="nope"):
            await action.run(mock_context)


class TestBatchedFind:
    @pytest.mark.anyio
    async def test_find_multiple_queries_returns_list_of_lists(self, mock_context):
        action = make_action(AgentSkillStoreFindActionConfig(method="find", query=["pdf", "weather"]))
        result = await action.run(mock_context)
        assert isinstance(result, list)
        assert len(result) == 2
        assert {s["name"] for s in result[0]} == {"pdf"}
        assert {s["name"] for s in result[1]} == {"weather"}


# ──────────────────────────────────────────────
# Component lifecycle
# ──────────────────────────────────────────────


def make_lifecycle_global_configs():
    return ComponentGlobalConfigs(components=[], listeners=[], gateways=[], workflows=[])


class TestAgentSkillStoreComponentLifecycle:
    @pytest.mark.anyio
    async def test_resolves_repository_on_start(self, monkeypatch):
        """_start() calls _create_component(repository.component) to obtain the backing service."""
        from mindor.core.component.services.agent_skill_store import agent_skill_store as module

        cfg = TypeAdapter(ComponentConfig).validate_python({
            "id": "skills",
            "type": "agent-skill-store",
            "repository": "my-fs",
            "actions": [],
        })
        comp = AgentSkillStoreComponent("skills", cfg, make_lifecycle_global_configs(), daemon=False)

        stub_repo = MagicMock()
        monkeypatch.setattr(comp, "_create_component", MagicMock(return_value=stub_repo))

        try:
            await comp._start()
            comp._create_component.assert_called_once_with("my-fs")
            assert comp._repository_component is stub_repo
        finally:
            await comp._stop()

    @pytest.mark.anyio
    async def test_run_dispatches_to_action(self, monkeypatch, mock_context):
        """_run forwards to AgentSkillStoreAction with the resolved repository."""
        cfg = TypeAdapter(ComponentConfig).validate_python({
            "id": "skills",
            "type": "agent-skill-store",
            "repository": "my-fs",
            "actions": [{"id": "list_all", "method": "list"}],
        })
        comp = AgentSkillStoreComponent("skills", cfg, make_lifecycle_global_configs(), daemon=False)

        stub_repo = make_repository()
        monkeypatch.setattr(comp, "_create_component", MagicMock(return_value=stub_repo))
        await comp._start()

        try:
            action_cfg = cfg.actions[0]
            result = await comp._run(action_cfg, mock_context)
            assert [s["name"] for s in result] == ["docx", "pdf", "weather"]
        finally:
            await comp._stop()
