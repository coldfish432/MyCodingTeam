from my_coding_team.agents.intake_router import route_request_deterministically


def test_review_file_routes_to_review_only_with_file_hint():
    route = route_request_deterministically("review src/auth.py")

    assert route.workflow == "review_only"
    assert route.suggested_review_input == {
        "input_kind": "file_list",
        "files_to_review": ["src/auth.py"],
    }


def test_review_my_changes_routes_to_workspace_diff():
    route = route_request_deterministically("look at my changes")

    assert route.workflow == "review_only"
    assert route.suggested_review_input["input_kind"] == "workspace_diff"


def test_pasted_code_review_routes_to_pasted_text():
    route = route_request_deterministically("check this code:\n```python\ndef f():\n    pass\n```")

    assert route.workflow == "review_only"
    assert route.suggested_review_input["input_kind"] == "pasted_text"


def test_review_and_fix_routes_to_implementation():
    route = route_request_deterministically("review my code and fix the bugs")

    assert route.workflow == "lightweight"
    assert route.suggested_review_input is None


def test_conceptual_code_question_routes_to_direct_answer():
    route = route_request_deterministically("what does this code do?")

    assert route.workflow == "direct_answer"
