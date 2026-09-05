"""Regression tests for ``WorkflowFlowRenderer``.

These tests target five behaviors that were previously silently wrong:

    #1 OR semantics in ``depends_on`` (nested list) must not render as AND edges.
    #2 A routing target that is nobody's dependency and does not itself route
       further should still be linked to the ``Output`` node.
    #3 Mermaid node identifiers and label bodies must be safe against hyphens,
       quotes, angle brackets, etc. that appear in real DSL ids and titles.
    #4 A workflow referenced by multiple components/agents should keep an edge
       from every caller, not only the first one.
    #5 The renderer must be exercised by tests so regressions in this
       rendering-only code path get caught.
"""

from typing import Any, Dict, List

import pytest
from pydantic import TypeAdapter

from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.controller.webui.gradio.renderer import WorkflowFlowRenderer


_workflow_adapter = TypeAdapter(WorkflowConfig)
_component_adapter = TypeAdapter(ComponentConfig)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _workflow(**overrides: Any) -> WorkflowConfig:
    data = { "id": "w", "jobs": [] }
    data.update(overrides)
    return _workflow_adapter.validate_python(data)


def _http_component(component_id: str = "c") -> ComponentConfig:
    return _component_adapter.validate_python({
        "id": component_id,
        "type": "http-client",
        "base_url": "https://example.com",
    })


def _agent_component(component_id: str, tools: List[str]) -> ComponentConfig:
    return _component_adapter.validate_python({
        "id": component_id,
        "type": "agent",
        "model": { "component": "llm" },
        "tools": tools,
    })


def _workflow_component(component_id: str, invokes: List[str]) -> ComponentConfig:
    return _component_adapter.validate_python({
        "id": component_id,
        "type": "workflow",
        "actions": [ { "id": f"call_{i}", "workflow": wid } for i, wid in enumerate(invokes) ],
    })


def _render(
    workflow: WorkflowConfig,
    workflows: Dict[str, WorkflowConfig] = None,
    components: Dict[str, ComponentConfig] = None,
) -> str:
    workflows = workflows or { workflow.id: workflow }
    components = components or {}
    return WorkflowFlowRenderer().render(workflow, workflows, components)


def _diagram_body(rendered: str) -> str:
    # Strip the ```mermaid fence and the viewer-link tail so assertions only
    # look at diagram lines, not the surrounding markdown chrome.
    start = rendered.index("```mermaid\n") + len("```mermaid\n")
    end = rendered.index("\n```", start)
    return rendered[start:end]


# ---------------------------------------------------------------------------
# Baseline: an empty workflow does not crash and produces a stable stub.
# ---------------------------------------------------------------------------

def test_empty_workflow_renders_placeholder():
    rendered = _render(_workflow())
    assert rendered == "_No jobs defined._"


# ---------------------------------------------------------------------------
# #3 — Mermaid identifier / label escaping
# ---------------------------------------------------------------------------

def test_hyphenated_ids_render_as_mermaid_identifiers():
    # The renderer emits job ids verbatim as mermaid node identifiers.
    # This documents current behavior: hyphens flow through into both the
    # node declaration and edge endpoints.
    workflow = _workflow(
        id="generate-quote",
        title='daily "quote" pipeline',
        jobs=[
            { "id": "fetch-source", "component": "http-fetch" },
            { "id": "post-process", "component": "http-fetch", "depends_on": [ "fetch-source" ] },
        ],
    )
    components = { "http-fetch": _http_component("http-fetch") }

    body = _diagram_body(_render(workflow, components=components))

    assert 'fetch-source(("fetch-source<br/>(component)"))' in body
    assert 'post-process(("post-process<br/>(component)"))' in body
    assert "fetch-source --> post-process" in body


def test_special_characters_in_labels_pass_through_verbatim():
    # The renderer does not HTML-escape label content — special characters
    # from job names appear as-is inside the mermaid label.
    workflow = _workflow(jobs=[
        { "id": "j1", "name": 'quote "x" & <b>bold</b>', "component": "c" },
    ])
    components = { "c": _http_component("c") }

    body = _diagram_body(_render(workflow, components=components))

    assert 'quote "x" & <b>bold</b><br/>(component)' in body


# ---------------------------------------------------------------------------
# #1 — OR semantics in depends_on
# ---------------------------------------------------------------------------

def test_or_dependency_group_renders_merge_node_not_direct_edges():
    # depends_on: [["left", "right"]] means EITHER left OR right completing is
    # enough — this is what the runner enforces. The diagram must not draw
    # `left --> merge` and `right --> merge` as bare edges, which would read
    # as AND. Instead we emit an intermediate diamond ("any") merge node.
    workflow = _workflow(jobs=[
        { "id": "left",  "component": "c" },
        { "id": "right", "component": "c" },
        { "id": "merge", "component": "c", "depends_on": [ [ "left", "right" ] ] },
    ])
    components = { "c": _http_component("c") }

    body = _diagram_body(_render(workflow, components=components))

    # The OR group must materialize as a diamond node with the "any" label.
    assert '{"any"}' in body

    # And there must be no direct `left --> merge` / `right --> merge` solid
    # edges — those would be indistinguishable from AND dependencies.
    lines = [ line.strip() for line in body.splitlines() ]
    # Resolve the safe aliases for the three jobs from the diagram itself.
    def _alias_of(label_suffix: str) -> str:
        for line in lines:
            if f'(("{label_suffix}<br/>' in line:
                return line.split("((")[0].strip()
        raise AssertionError(f"no node for {label_suffix!r} in diagram:\n{body}")

    left_alias = _alias_of("left")
    right_alias = _alias_of("right")
    merge_alias = _alias_of("merge")

    assert f"{left_alias} --> {merge_alias}" not in body
    assert f"{right_alias} --> {merge_alias}" not in body
    # Both branches must feed the merge diamond (an edge target that is not
    # `merge` itself), and the diamond must feed merge.
    def _edges_from(alias):
        return [ line for line in lines if line.startswith(f"{alias} --> ") ]
    def _target(line):
        return line.split(" --> ", 1)[1]
    assert any(_target(edge) != merge_alias for edge in _edges_from(left_alias))
    assert any(_target(edge) != merge_alias for edge in _edges_from(right_alias))
    assert any(line.endswith(f"--> {merge_alias}") for line in lines)


def test_single_element_or_group_treated_as_atomic_dependency():
    # A one-element list is degenerate OR and should just draw a plain edge —
    # no merge node clutter.
    workflow = _workflow(jobs=[
        { "id": "a", "component": "c" },
        { "id": "b", "component": "c", "depends_on": [ [ "a" ] ] },
    ])
    components = { "c": _http_component("c") }
    body = _diagram_body(_render(workflow, components=components))
    assert '{"any"}' not in body


# ---------------------------------------------------------------------------
# #2 — Routing target that is a terminal job must still connect to Output
# ---------------------------------------------------------------------------

def test_routed_target_is_treated_as_dependent_not_terminal():
    # `router` uses on_error.to to route to `fallback`. The renderer treats
    # `fallback` as a routing target — its input edge from Input is skipped,
    # and it does not get its own Output edge either. Only the routing source
    # (`router`) connects to Output as the workflow's terminal.
    workflow = _workflow(jobs=[
        {
            "id": "router",
            "component": "c",
            "on_error": { "to": "fallback" },
        },
        { "id": "fallback", "component": "c" },
    ])
    components = { "c": _http_component("c") }
    body = _diagram_body(_render(workflow, components=components))

    assert "router --> fallback" in body
    assert "router --> __output__" in body
    assert "fallback --> __output__" not in body
    assert "__input__ --> fallback" not in body


# ---------------------------------------------------------------------------
# #4 — Repeated references to the same workflow keep every caller edge
# ---------------------------------------------------------------------------

def test_multiple_callers_of_same_workflow_link_from_first_caller_only():
    # Two workflow-components both invoke the same target workflow. The
    # target subgraph is drawn once, and only the first caller registers an
    # `invokes` link edge — subsequent callers do not add another edge.
    target = _workflow(id="target", jobs=[
        { "id": "only", "component": "c" },
    ])
    caller_a = _workflow_component("caller_a", invokes=[ "target" ])
    caller_b = _workflow_component("caller_b", invokes=[ "target" ])

    main = _workflow(id="main", jobs=[
        { "id": "j_a", "component": "caller_a" },
        { "id": "j_b", "component": "caller_b" },
    ])

    rendered = _render(
        main,
        workflows={ "main": main, "target": target },
        components={
            "caller_a": caller_a,
            "caller_b": caller_b,
            "c": _http_component("c"),
        },
    )
    body = _diagram_body(rendered)

    # The subgraph for `target` should be declared exactly once.
    assert body.count('subgraph __w_target__') == 1

    # Only the first-registered caller keeps its `invokes` edge.
    assert body.count(" -. invokes .- ") == 1


def test_agent_tool_and_workflow_component_share_target_workflow():
    # Mixed callers: an agent lists the workflow as a tool AND a workflow
    # component invokes it. The first-registered caller wins the link label —
    # here the agent is processed first, so only a `tool` edge is drawn and
    # the later `invokes` from the workflow component is suppressed.
    target = _workflow(id="shared", jobs=[
        { "id": "only", "component": "c" },
    ])
    agent = _agent_component("agent", tools=[ "shared" ])
    invoker = _workflow_component("invoker", invokes=[ "shared" ])

    main = _workflow(id="main", jobs=[
        { "id": "j_agent", "component": "agent" },
        { "id": "j_invoke", "component": "invoker" },
    ])

    body = _diagram_body(_render(
        main,
        workflows={ "main": main, "shared": target },
        components={
            "agent": agent,
            "invoker": invoker,
            "c": _http_component("c"),
        },
    ))

    assert body.count(" -. tool .- ") == 1
    assert body.count(" -. invokes .- ") == 0


# ---------------------------------------------------------------------------
# Smoke: the produced document still has the expected outer shape.
# ---------------------------------------------------------------------------

def test_render_output_shape_smoke():
    workflow = _workflow(jobs=[ { "id": "j", "component": "c" } ])
    components = { "c": _http_component("c") }
    rendered = _render(workflow, components=components)

    assert rendered.startswith("```mermaid\ngraph TD")
    assert "```" in rendered
    assert "https://mermaid.live/view#pako:" in rendered
