import types
import pytest

# We unit-test the pure helper using a lightweight dummy task and dict-like form
from blueprints.student.routes import _extract_user_answer


class DummyTask:
    def __init__(self, answer_type, correct_answer):
        self.answer_type = answer_type
        self.correct_answer = correct_answer


def test_extract_number_simple():
    task = DummyTask('number', {"type": "number", "value": 42.0})
    form = {"answer": "42"}
    out = _extract_user_answer(task, form)
    assert out == {"type": "number", "value": 42.0}


def test_extract_variables_legacy_per_key():
    # Legacy student template renders fields per variable key
    correct = {"type": "variables", "variables": [{"name": "x", "value": 1.0}, {"name": "y", "value": 2.5}]}
    # For legacy mapping branch we provide a mapping to hint available keys
    # keys are expected to be names in task.correct_answer when legacy template used
    task = DummyTask('variables', {"x": 0, "y": 0})
    form = {"x": "1", "y": "2,5"}  # comma as decimal
    out = _extract_user_answer(task, form)
    assert out == correct


def test_extract_variables_indexed_rows():
    task = DummyTask('variables', {"type": "variables", "variables": []})
    form = {
        "name_0": "a",
        "value_0": "-3",
        "name_1": "b",
        "value_1": "4.75",
    }
    out = _extract_user_answer(task, form)
    assert out == {
        "type": "variables",
        "variables": [
            {"name": "a", "value": -3.0},
            {"name": "b", "value": 4.75},
        ],
    }


def test_extract_interval_with_infinities_and_bounds():
    task = DummyTask('interval', {"type": "interval"})
    form = {
        "start_infinity": "on",  # -inf
        "end": "10,5",
        "end_infinity": "",  # not set
        "start_inclusive": "on",
        "end_inclusive": "",  # unchecked
    }
    out = _extract_user_answer(task, form)
    assert out == {
        "type": "interval",
        "start": None,
        "end": 10.5,
        "start_inclusive": True,
        "end_inclusive": False,
    }


def test_extract_sequence_from_textarea():
    task = DummyTask('sequence', {"type": "sequence"})
    form = {"sequence_input": "1, 2; 3, 4.5"}
    out = _extract_user_answer(task, form)
    assert out == {"type": "sequence", "sequence_values": [1.0, 2.0, 3.0, 4.5]}


def test_extract_sequence_from_items():
    # Legacy rendering with item_i inputs
    task = DummyTask('sequence', [0, 0, 0])
    form = {"item_0": "-1", "item_1": "0", "item_2": "2.5"}
    out = _extract_user_answer(task, form)
    assert out == {"type": "sequence", "sequence_values": [-1.0, 0.0, 2.5]}
