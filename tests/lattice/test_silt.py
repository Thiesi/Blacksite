"""Game 6.5-6.7: generation cannot turn escape into an equipment check."""

from dataclasses import asdict, replace
import os
from pathlib import Path
import subprocess
import sys

import pytest

from blacksite.content.loader import load_content
from blacksite.server.lattice.silt import adjacent_hidden, descent_seed, generate, survey_directions


@pytest.fixture(scope="module")
def rules():
    return load_content(Path(__file__).parents[2] / "src/blacksite/content").silt


def test_design_6_5_seed_replays_and_changes_with_descent(rules):
    first = generate("node", 1, "lat-core", 7, rules)
    assert asdict(first) == asdict(generate("node", 1, "lat-core", 7, rules))
    assert first.seed != generate("node", 1, "lat-core", 8, rules).seed
    assert first.seed != generate("node", 2, "lat-core", 7, rules).seed
    assert first.id.startswith("node:")


def test_design_6_5_seed_ignores_process_hash_randomization():
    command = [sys.executable, "-c", "from blacksite.server.lattice.silt import descent_seed; print(descent_seed(1,'lat-core',7))"]
    outputs = [subprocess.check_output(command, env={**os.environ, "PYTHONHASHSEED": value}, text=True).strip()
               for value in ("1", "932")]
    assert outputs == [str(descent_seed(1, "lat-core", 7))] * 2


def test_design_6_5_every_seed_has_visible_continuation_and_risers(rules):
    sizes = set()
    for nonce in range(80):
        graph = generate("node", 1, "lat-vatside", nonce, rules)
        assert len(graph.bands) == 5
        for depth, band in enumerate(graph.bands):
            index = {c.id: c for c in band.cells}
            sizes.add(len(index))
            assert 8 <= len(index) <= 20
            assert len({c.pos for c in band.cells}) == len(index)
            assert all(0 <= c.pos[0] < 5 and 0 <= c.pos[1] < 4 for c in band.cells)
            assert sum(c.hidden for c in band.cells) <= len(index) / 5
            assert sum(c.role == "riser" for c in band.cells) == 1
            assert not index[band.riser].hidden
            visible = {c.id for c in band.cells if not c.hidden}
            # Independent flood, excluding every hidden node. A zero-
            # Listening starter needs no key or Lantern to return.
            seen, pending = set(), [band.riser]
            while pending:
                cell = pending.pop()
                if cell in seen:
                    continue
                seen.add(cell)
                pending.extend(n for n in index[cell].neighbours if n in visible and n not in seen)
            assert seen == visible
            if depth < 4:
                assert 1 <= len(band.sinks) <= 3
                assert set(band.sinks) & seen
            else:
                assert not band.sinks
            for cell in band.cells:
                assert all(cell.id in index[n].neighbours for n in cell.neighbours)
                assert band.route(cell.id, band.riser, set(index))
            # Every seed includes an orthogonal patrol loop with a bypass.
            square = ("b%d-00" % depth, "b%d-01" % depth,
                      "b%d-05" % depth, "b%d-04" % depth)
            assert all(b in index[a].neighbours for a, b in zip(square, (*square[1:], square[0])))
    assert sizes == set(range(8, 21))


def test_design_6_5_low_listening_shows_directions_without_hidden_ids(rules):
    band = generate("node", 1, "lat-core", 1, rules).bands[0]
    index = {c.id: c for c in band.cells}
    hidden = next(c for c in band.cells if c.hidden and any(not index[n].hidden for n in c.neighbours))
    source = next(n for n in hidden.neighbours if not index[n].hidden)
    assert hidden in adjacent_hidden(band, source, set())
    assert all(word in ("north", "south", "east", "west") for word in survey_directions(band, source, set()))
    assert hidden.id not in survey_directions(band, source, set())
    assert hidden not in adjacent_hidden(band, source, {hidden.id})


@pytest.mark.parametrize("fraction", [0, .05, .1, .2])
def test_valid_silt_override_without_hidden_cells_stays_inside_the_terminal(rules, fraction):
    override = replace(rules, minimum_cells=20, maximum_cells=20, hidden_fraction=fraction)
    for nonce in range(10):
        for band in generate("node", 1, "lat-core", nonce, override).bands:
            assert all(0 <= c.pos[0] < 5 and 0 <= c.pos[1] < 4 for c in band.cells)
            assert all(band.route(c.id, band.riser) for c in band.cells if not c.hidden)


def test_silt_band_cannot_alias_two_rewards_to_one_source(repo_root):
    from blacksite.content.validate import validate
    tree = load_content(repo_root / "src/blacksite/content")
    band = tree.silt.bands[0]
    tree.silt = replace(tree.silt, bands=(replace(band, data=(*band.data, band.data[0])), *tree.silt.bands[1:]))
    assert any("duplicate data ids" in p.message for p in validate(tree))
