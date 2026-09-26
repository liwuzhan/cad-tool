"""Tests for assertion-set recording (P1).

The policy is record-only: these assertions belong to whoever wrote the model, so
nothing here blocks a revision. What the tests pin down is that the record is
*legible* — that a quietly loosened tolerance is distinguishable from an
unchanged build, because an opaque "assertions changed" flag would not be.
"""

import pytest

from cad_cli.feedback.assertions import (
    AssertionSyntaxError,
    assertion_keys,
    diff_assertions,
    extract_assertions,
    summarize,
)

BASELINE = '''
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

Checkpoint(part, "base").expect_volume(100, tolerance=1.0).expect_solids(1).verify()
Checkpoint(part, "hole").expect_solids(1).verify(render=False)
'''


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def test_extracts_each_chained_assertion_once():
    items = extract_assertions(BASELINE)
    assert [item["checkpoint"] for item in items] == ["base", "hole"]
    assert items[0]["checks"] == ["expect_volume(100, tolerance=1.0)", "expect_solids(1)"]
    assert items[1]["checks"] == ["expect_solids(1)"]


def test_line_continuations_and_comments_are_handled():
    source = '''
Checkpoint(part, "base") \\
    .expect_solids(1) \\
    .verify()
# Checkpoint(part, "ghost").expect_volume(9).verify()
text = "Checkpoint(part, 'also_ghost').expect_volume(9).verify()"
'''
    items = extract_assertions(source)
    assert len(items) == 1
    assert items[0]["checkpoint"] == "base"
    assert items[0]["checks"] == ["expect_solids(1)"]


def test_checkpoint_without_checks_is_not_an_assertion():
    assert extract_assertions("Checkpoint.reset()\nCheckpoint(part, 'x').verify()\n") == []


def test_unparsable_source_raises_rather_than_silently_returning_nothing():
    with pytest.raises(AssertionSyntaxError):
        extract_assertions("def broken(:\n")


def test_assertion_keys_are_prefixed_by_checkpoint():
    keys = assertion_keys(extract_assertions(BASELINE))
    assert "base:expect_solids(1)" in keys
    assert "hole:expect_solids(1)" in keys


# --------------------------------------------------------------------------
# The failure this exists to catch: quiet loosening
# --------------------------------------------------------------------------

def test_loosened_tolerance_is_recorded_as_a_removed_added_pair():
    """Not "changed" — both the old and the new value must stay legible."""

    relaxed = BASELINE.replace("tolerance=1.0", "tolerance=1000.0")
    delta = diff_assertions(BASELINE, relaxed)

    assert delta["removed"] == ["base:expect_volume(100, tolerance=1.0)"]
    assert delta["added"] == ["base:expect_volume(100, tolerance=1000.0)"]
    # And it must not look like the untouched check was rewritten too.
    assert not any("expect_solids" in item for item in delta["removed"] + delta["added"])


def test_removing_an_assertion_is_recorded():
    without_hole = BASELINE.replace(
        'Checkpoint(part, "hole").expect_solids(1).verify(render=False)\n', ""
    )
    delta = diff_assertions(BASELINE, without_hole)
    assert delta["removed"] == ["hole:expect_solids(1)"]
    assert delta["added"] == []
    assert delta["previous_total"] == 3 and delta["current_total"] == 2


def test_adding_an_assertion_is_recorded():
    stricter = BASELINE + 'Checkpoint(part, "top").expect_faces(9).verify()\n'
    delta = diff_assertions(BASELINE, stricter)
    assert delta["added"] == ["top:expect_faces(9)"]
    assert delta["removed"] == []


def test_unchanged_assertions_produce_an_empty_summary():
    delta = diff_assertions(BASELINE, BASELINE)
    assert delta["added"] == [] and delta["removed"] == []
    assert summarize(delta) == ""


def test_first_commit_records_the_whole_set():
    delta = diff_assertions(None, BASELINE)
    assert delta["first_commit"] is True
    assert delta["previous_total"] == 0
    assert delta["current_total"] == 3
    assert "首次记录" in summarize(delta)


def test_unreadable_previous_revision_degrades_to_a_note():
    delta = diff_assertions("def broken(:\n", BASELINE)
    assert delta["available"] is False
    assert "上一版" in delta["reason"]


def test_summary_states_both_directions():
    delta = diff_assertions(BASELINE, BASELINE + 'Checkpoint(part, "top").expect_faces(9).verify()\n')
    text = summarize(delta)
    assert "新增 1 条" in text and "3 → 4" in text


# --------------------------------------------------------------------------
# Tunables live at the top of the file, so the extraction must see through them
# --------------------------------------------------------------------------

WITH_TUNABLES = '''
ASSEMBLY_VOLUME = 24289.22
VOLUME_TOLERANCE = 1.0
OFFSET = -2.5

Checkpoint(assembly, "assembly") \\
    .expect_solids(2) \\
    .expect_volume(ASSEMBLY_VOLUME, tolerance=VOLUME_TOLERANCE) \\
    .verify(render=False)
'''


def test_module_level_constants_are_folded_into_the_rendering():
    items = extract_assertions(WITH_TUNABLES)
    assert items[0]["checks"] == [
        "expect_solids(2)",
        "expect_volume(24289.22, tolerance=1.0)",
    ]


def test_changing_a_top_level_tunable_is_detected():
    """The convention is "no magic numbers, tunables at the top".

    Unfolded, the assertion text would still read ``tolerance=VOLUME_TOLERANCE``
    and loosening it from 1.0 to 1000.0 would be invisible — the single most
    likely form of quiet loosening in this codebase.
    """

    loosened = WITH_TUNABLES.replace("VOLUME_TOLERANCE = 1.0", "VOLUME_TOLERANCE = 1000.0")
    delta = diff_assertions(WITH_TUNABLES, loosened)
    assert delta["removed"] == ["assembly:expect_volume(24289.22, tolerance=1.0)"]
    assert delta["added"] == ["assembly:expect_volume(24289.22, tolerance=1000.0)"]


def test_changing_the_asserted_value_itself_is_detected():
    moved = WITH_TUNABLES.replace("ASSEMBLY_VOLUME = 24289.22", "ASSEMBLY_VOLUME = 999.0")
    delta = diff_assertions(WITH_TUNABLES, moved)
    assert delta["added"] == ["assembly:expect_volume(999.0, tolerance=1.0)"]


def test_non_literal_assignments_are_left_alone():
    """Only literals are folded; a computed value keeps its expression form."""

    source = '''
TOL = compute_tolerance()
Checkpoint(p, "c").expect_volume(1.0, tolerance=TOL).verify()
'''
    assert extract_assertions(source)[0]["checks"] == ["expect_volume(1.0, tolerance=TOL)"]
