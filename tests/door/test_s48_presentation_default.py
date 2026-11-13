"""S48 part 3 (step one of two): the new presentation is the door's default."""

import pytest

from karst41.door.client import presentation_on


@pytest.mark.parametrize('environment', [
    {}, {'DOOR_KARST41_PRESENTATION': '1'}, {'DOOR_KARST41_PRESENTATION': ''},
    {'DOOR_KARST41_PRESENTATION': 'yes'}, {'DOOR_KARST41_PRESENTATION': 'on'},
    {'DOOR_KARST41_PRESENTATION': 'present'}, {'DOOR_KARST41_PRESENTATION': '00'}])
def test_s48_unset_or_any_other_value_gives_the_new_presentation(environment):
    assert presentation_on(environment) is True


@pytest.mark.parametrize('value', ['0', 'false', 'off', 'no', 'FALSE', 'Off', 'No', ' no ', 'nO'])
def test_s48_falsy_values_keep_the_old_renderer(value):
    assert presentation_on({'DOOR_KARST41_PRESENTATION': value}) is False


def test_s48_the_pre_r1_alias_still_selects_the_old_renderer():
    # Remove in S31 with the BLACKSITE aliases.
    assert presentation_on({'DOOR_BLACKSITE_PRESENTATION': '0'}) is False
    assert presentation_on({'DOOR_KARST41_PRESENTATION': '1', 'DOOR_BLACKSITE_PRESENTATION': '0'}) is True


def test_s48_choosing_the_renderer_writes_nothing(capsys):
    """Nothing about the setting reaches the caller's terminal (AGENTS 4)."""
    presentation_on({})
    presentation_on({'DOOR_KARST41_PRESENTATION': '0'})
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == ''
