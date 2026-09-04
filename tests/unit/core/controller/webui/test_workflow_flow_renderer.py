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

from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.controller.webui.gradio.renderer import WorkflowFlowRenderer


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _workflow(**overrides: Any) -> WorkflowConfig:
    data = { "id": "w", "jobs": [] }
    data.update(overrides)
    return WorkflowConfig.model_validate(data)


def _http_component(component_id: str = "c") -> ComponentConfig:
    return ComponentConfig.model_validate({
        "id": component_id,
        "type": "http-client",
        "base_url": "https://example.com",
    })


def _agent_component(component_id: str, tools: List[str]) -> ComponentConfig:
    return ComponentConfig.model_validate({
        "id": component_id,
        "type": "agent",
        "model": { "component": "llm" },
        "tools": tools,
    })


def _workflow_component(component_id: str, invokes: List[str]) -> ComponentConfig:
    return ComponentConfig.model_validate({
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

def test_hyphen_in_ids_does_not_leak_into_mermaid_identifiers():
    # Hyphens in mermaid node ids break the parser; the renderer must remap
    # user-provided ids to safe aliases and only expose the original in the
    # (escaped) label body.
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

    # The raw hyphenated ids must never appear as node identifiers on the
    # left-hand side of a node declaration or as an edge endpoint.
    for hyphenated in ("fetch-source", "post-process", "generate-quote"):
        assert f" {hyphenated}(" not in body, f"leaked id {hyphenated!r} into node decl"
        assert f" {hyphenated} " not in body, f"leaked id {hyphenated!r} into edge"

    # But they must still show up inside label bodies for readability.
    assert "fetch-source" in body
    assert "post-process" in body


def test_special_characters_in_labels_are_escaped():
    workflow = _workflow(jobs=[
        { "id": "j1", "name": 'quote "x" & <b>bold</b>', "component": "c" },
    ])
    components = { "c": _http_component("c") }

    body = _diagram_body(_render(workflow, components=components))

    # Angle brackets and quotes get HTML-entity encoded so mermaid does not
    # confuse them with tag syntax or terminate the quoted label early.
    assert "&quot;x&quot;" in body
    assert "&amp;" in body
    assert "&lt;b&gt;bold&lt;/b&gt;" in body
    # The literal `"x"` (a bare quote) must not survive into the label.
    assert '"x"' not in body


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
    # Both branches must feed the merge diamond, and the diamond must feed merge.
    assert any(line.startswith(f"{left_alias} -->") and merge_alias not in line for line in lines)
    assert any(line.startswith(f"{right_alias} -->") and merge_alias not in line for line in lines)
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

def test_routed_terminal_branch_connects_to_output():
    # `router` uses on_error.to to route to `fallback`. `fallback` has no
    # depends_on and nobody depends on it, so it is a genuine terminal —
    # the runner would treat its output as the workflow output. The diagram
    # must not orphan it from the Output node.
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

    lines = [ line.strip() for line in body.splitlines() ]
    fallback_alias = next(
        line.split("((")[0].strip() for line in lines
        if '(("fallback<br/>' in line
    )
    output_alias = next(
        line.split("((")[0].strip() for line in lines
        if line.endswith("((Output))")
    )
    assert f"{fallback_alias} --> {output_alias}" in body


def test_routing_source_does_not_connect_to_output():
    # A job that hands off via routing is not itself a terminal — its result
    # is discarded in favor of the routed-to job's output. So it must NOT
    # gain an Output edge just because nobody `depends_on` it.
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

    lines = [ line.strip() for line in body.splitlines() ]
    router_alias = next(
        line.split("((")[0].strip() for line in lines
        if '(("router<br/>' in line
    )
    output_alias = next(
        line.split("((")[0].strip() for line in lines
        if line.endswith("((Output))")
    )
    assert f"{router_alias} --> {output_alias}" not in body


# ---------------------------------------------------------------------------
# #4 — Repeated references to the same workflow keep every caller edge
# ---------------------------------------------------------------------------

def test_multiple_callers_of_same_workflow_all_link_to_it():
    # Two workflow-components both invoke the same target workflow. The
    # target subgraph should be drawn once, but BOTH callers must show a
    # link edge to it — previously only the first caller's edge survived.
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
    assert body.count('<br/>(workflow)"]') == 1

    # But there must be two "invokes" link edges pointing at it, one per
    # caller component.
    assert body.count(" -. invokes .- ") == 2


def test_agent_tool_and_workflow_component_share_target_workflow():
    # Mixed callers: an agent lists the workflow as a tool AND a workflow
    # component invokes it. Both edges must survive.
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
    assert body.count(" -. invokes .- ") == 1


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
