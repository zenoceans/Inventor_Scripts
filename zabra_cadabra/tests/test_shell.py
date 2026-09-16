"""Tests for zabra_cadabra.shell pure helpers."""

from __future__ import annotations

from zabra_cadabra.shell import filter_visible_tabs
from zabra_cadabra.tab_registry import TabSpec


def _spec(title: str, prototype: bool = False) -> TabSpec:
    return TabSpec(
        title=title,
        factory=lambda parent, config: None,  # type: ignore[return-value]
        prototype=prototype,
    )


def test_no_hidden_excludes_prototypes_by_default() -> None:
    specs = [_spec("Export"), _spec("Vendor API", prototype=True)]

    result = filter_visible_tabs(specs, hidden_tabs=[], show_prototypes=False)

    assert [s.title for s in result] == ["Export"]


def test_show_prototypes_includes_prototype_tabs() -> None:
    specs = [_spec("Export"), _spec("Vendor API", prototype=True)]

    result = filter_visible_tabs(specs, hidden_tabs=[], show_prototypes=True)

    assert [s.title for s in result] == ["Export", "Vendor API"]


def test_hidden_tab_excluded_regardless_of_prototype() -> None:
    specs = [_spec("Export"), _spec("Vendor API", prototype=True)]

    result = filter_visible_tabs(specs, hidden_tabs=["Export"], show_prototypes=True)

    assert [s.title for s in result] == ["Vendor API"]


def test_hidden_and_prototype_filters_apply_independently() -> None:
    specs = [_spec("Export"), _spec("Vendor API", prototype=True), _spec("Drawing")]

    result = filter_visible_tabs(specs, hidden_tabs=["Drawing"], show_prototypes=False)

    assert [s.title for s in result] == ["Export"]
