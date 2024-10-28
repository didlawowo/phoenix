from collections.abc import Mapping
from typing import Any

import pytest

from phoenix.trace.attributes import get_attribute_value, unflatten


@pytest.mark.parametrize(
    "mapping,key,expected",
    [
        ({}, "a.b.c", None),
        ({"a": "b"}, "a", "b"),
        ({"a": "b"}, "a.b", None),
        ({"a": "b"}, "a.b.c", None),
        ({"a": {"b": "c", "d": "e"}}, "a", {"b": "c", "d": "e"}),
        ({"a": {"b": "c", "d": "e"}}, "a.b", "c"),
        ({"a": {"b": "c", "d": "e"}}, "a.b.c", None),
        ({"a": {"b": {"c": "d"}}}, "a", {"b": {"c": "d"}}),
        ({"a": {"b": {"c": "d"}}}, "a.b", {"c": "d"}),
        ({"a": {"b": {"c": "d"}}}, "a.b.c", "d"),
        ({"a": {"bb": {"c": "d"}}}, "a.b.c", None),
        ("{}", "a.b.c", None),
        ({"a": {"b": "c"}}, "", None),
        ({"a": {"b": "c"}}, ".", None),
        ({"a": {"b": "c"}}, "a.", None),
        ({"a": {"b": "c"}}, "..", None),
        ({"a": {"b": "c"}}, "a..", None),
    ],
)
def test_get_attribute_value(
    mapping: Mapping[str, Any],
    key: str,
    expected: Any,
) -> None:
    assert get_attribute_value(mapping, key) == expected


@pytest.mark.parametrize(
    "key_value_pairs,desired",
    [
        (
            (
                ("retrieval.documents.1.document.content", "bcd"),
                ("llm.token_count.prompt", 10),
                ("retrieval.documents.3.document.score", 345),
                ("input.value", "xyz"),
                ("retrieval.documents.0.document.content", "abc"),
                ("llm.token_count.completion", 20),
                ("retrieval.documents.1.document.score", 432),
                ("output.value", "zyx"),
                ("retrieval.documents.2.document.content", "cde"),
                ("metadata", {"a.b.c": 123, "1.2.3": "abc"}),
                ("retrieval.documents.0.document.score", 321),
            ),
            {
                "input": {"value": "xyz"},
                "output": {"value": "zyx"},
                "metadata": {"a.b.c": 123, "1.2.3": "abc"},
                "llm": {"token_count": {"prompt": 10, "completion": 20}},
                "retrieval": {
                    "documents": [
                        {"document": {"content": "abc", "score": 321}},
                        {"document": {"content": "bcd", "score": 432}},
                        {"document": {"content": "cde"}},
                        {"document": {"score": 345}},
                    ]
                },
            },
        ),
        ((), {}),
        ((("1", 0),), {"1": 0}),
        ((("1.2", 0),), {"1": {"2": 0}}),
        ((("1.0.2", 0),), {"1": [{"2": 0}]}),
        ((("1.0.2.3", 0),), {"1": [{"2": {"3": 0}}]}),
        ((("1.0.2.0.3", 0),), {"1": [{"2": [{"3": 0}]}]}),
        ((("1.0.2.0.3.4", 0),), {"1": [{"2": [{"3": {"4": 0}}]}]}),
        ((("1.0.2.0.3.0.4", 0),), {"1": [{"2": [{"3": [{"4": 0}]}]}]}),
        ((("1.2", 1), ("1", 0)), {"1": 0, "1.2": 1}),
        ((("1.2.3", 1), ("1", 0)), {"1": 0, "1.2": {"3": 1}}),
        ((("1.2.3", 1), ("1.2", 0)), {"1": {"2": 0, "2.3": 1}}),
        ((("1.2.0.3", 1), ("1", 0)), {"1": 0, "1.2": [{"3": 1}]}),
        ((("1.2.3.4", 1), ("1.2", 0)), {"1": {"2": 0, "2.3": {"4": 1}}}),
        ((("1.0.2.3", 1), ("1.0.2", 0)), {"1": [{"2": 0, "2.3": 1}]}),
        ((("1.2.0.3.4", 1), ("1", 0)), {"1": 0, "1.2": [{"3": {"4": 1}}]}),
        ((("1.2.3.0.4", 1), ("1.2", 0)), {"1": {"2": 0, "2.3": [{"4": 1}]}}),
        ((("1.0.2.3.4", 1), ("1.0.2", 0)), {"1": [{"2": 0, "2.3": {"4": 1}}]}),
        ((("1.0.2.3.4", 1), ("1.0.2.3", 0)), {"1": [{"2": {"3": 0, "3.4": 1}}]}),
        ((("1.2.0.3.0.4", 1), ("1", 0)), {"1": 0, "1.2": [{"3": [{"4": 1}]}]}),
        ((("1.2.3.0.4.5", 1), ("1.2", 0)), {"1": {"2": 0, "2.3": [{"4": {"5": 1}}]}}),
        ((("1.0.2.3.0.4", 1), ("1.0.2", 0)), {"1": [{"2": 0, "2.3": [{"4": 1}]}]}),
        ((("1.0.2.3.4.5", 1), ("1.0.2.3", 0)), {"1": [{"2": {"3": 0, "3.4": {"5": 1}}}]}),
        ((("1.0.2.0.3.4", 1), ("1.0.2.0.3", 0)), {"1": [{"2": [{"3": 0, "3.4": 1}]}]}),
        ((("1.2.0.3.0.4.5", 1), ("1", 0)), {"1": 0, "1.2": [{"3": [{"4": {"5": 1}}]}]}),
        ((("1.2.3.0.4.0.5", 1), ("1.2", 0)), {"1": {"2": 0, "2.3": [{"4": [{"5": 1}]}]}}),
        ((("1.0.2.3.0.4.5", 1), ("1.0.2", 0)), {"1": [{"2": 0, "2.3": [{"4": {"5": 1}}]}]}),
        ((("1.0.2.3.4.0.5", 1), ("1.0.2.3", 0)), {"1": [{"2": {"3": 0, "3.4": [{"5": 1}]}}]}),
        ((("1.0.2.0.3.4.5", 1), ("1.0.2.0.3", 0)), {"1": [{"2": [{"3": 0, "3.4": {"5": 1}}]}]}),
        ((("1.0.2.0.3.4.5", 1), ("1.0.2.0.3.4", 0)), {"1": [{"2": [{"3": {"4": 0, "4.5": 1}}]}]}),
        (
            (("1.0.2.3.4.5.6", 2), ("1.0.2.3.4", 1), ("1.0.2", 0)),
            {"1": [{"2": 0, "2.3": {"4": 1, "4.5": {"6": 2}}}]},
        ),
        (
            (("0.0.0.0.0", 4), ("0.0.0.0", 3), ("0.0.0", 2), ("0.0", 1), ("0", 0)),
            {"0": 0, "0.0": 1, "0.0.0": 2, "0.0.0.0": 3, "0.0.0.0.0": 4},
        ),
        (
            (("a.9999999.c", 2), ("a.9999999.b", 1), ("a.99999.b", 0)),
            {"a": [{"b": 0}, {"b": 1, "c": 2}]},
        ),
        ((("a", 0), ("c", 2), ("b", 1), ("d", 3)), {"a": 0, "b": 1, "c": 2, "d": 3}),
        (
            (("a.b.c", 0), ("a.e", 2), ("a.b.d", 1), ("f", 3)),
            {"a": {"b": {"c": 0, "d": 1}, "e": 2}, "f": 3},
        ),
        (
            (("a.1.d", 3), ("a.0.d", 2), ("a.0.c", 1), ("a.b", 0)),
            {"a.b": 0, "a": [{"c": 1, "d": 2}, {"d": 3}]},
        ),
        (
            (("a.0.d", 3), ("a.0.c", 2), ("a.b", 1), ("a", 0)),
            {"a": 0, "a.b": 1, "a.0": {"c": 2, "d": 3}},
        ),
        (
            (("a.0.1.d", 3), ("a.0.0.c", 2), ("a", 1), ("a.b", 0)),
            {"a.b": 0, "a": 1, "a.0": [{"c": 2}, {"d": 3}]},
        ),
        (
            (("a.1.0.e", 3), ("a.0.0.d", 2), ("a.0.0.c", 1), ("a.b", 0)),
            {"a.b": 0, "a": [{"0": {"c": 1, "d": 2}}, {"0": {"e": 3}}]},
        ),
        (
            (("a.b.1.e.0.f", 2), ("a.b.0.c", 0), ("a.b.0.d.e.0.f", 1)),
            {"a": {"b": [{"c": 0, "d": {"e": [{"f": 1}]}}, {"e": [{"f": 2}]}]}},
        ),
    ],
)
def test_unflatten(key_value_pairs: tuple[tuple[str, Any], ...], desired: dict[str, Any]) -> None:
    actual = dict(unflatten(key_value_pairs))
    assert actual == desired
    actual = dict(unflatten(reversed(key_value_pairs)))
    assert actual == desired


@pytest.mark.parametrize(
    "separator,key_value_pairs,desired",
    [
        ("#", (("1#2#3", 1), ("1", 0)), {"1": 0, "1#2": {"3": 1}}),
        (
            "$$",
            (("1$$0$$2$$3$$0$$4$$5", 1), ("1$$0$$2", 0)),
            {"1": [{"2": 0, "2$$3": [{"4": {"5": 1}}]}]},
        ),
        (
            "!!!",
            (("1!!!0!!!2!!!0!!!3!!!4!!!5", 1), ("1!!!0!!!2!!!0!!!3!!!4", 0)),
            {"1": [{"2": [{"3": {"4": 0, "4!!!5": 1}}]}]},
        ),
    ],
)
def test_unflatten_separator(
    separator: str, key_value_pairs: tuple[tuple[str, Any], ...], desired: dict[str, Any]
) -> None:
    actual = dict(unflatten(key_value_pairs, separator=separator))
    assert actual == desired
    actual = dict(unflatten(reversed(key_value_pairs), separator=separator))
    assert actual == desired
