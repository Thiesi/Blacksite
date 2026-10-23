"""Game 9/PR38: economic source receipts and honest affordability roles."""
import pytest

from scripts.report_s19_economy import report


@pytest.fixture(scope='module')
def economy():
    return report()


def test_game_9_1_real_paid_roster_and_operator_income_exclude_duplicate_and_late_credit(economy):
    receipts=economy['receipts']
    assert receipts['solo']['required_defeats'] == 4
    assert receipts['solo']['paid'] == [{'archetype':'ghost','chits':200,'xp':200}]
    assert receipts['crew']['required_defeats'] == 6
    assert receipts['crew']['paid'] == [
        {'archetype':'ghost','chits':250,'xp':250}, {'archetype':'operator','chits':275,'xp':250}]
    assert receipts['solo']['duplicate_credit'] == receipts['crew']['duplicate_credit'] == 0


def test_game_8_2_actual_loot_resale_consumes_budget_without_selling_starting_principal(economy):
    street=economy['receipts']['street']
    assert street['defeats'] == 20 and street['loot']
    assert street['sold_chits'] == street['vendor_budget_spent'] > 0
    assert street['starting_principal_sold'] == 0
    assert economy['receipts']['core']['chits'] == 80
    rates=economy['gross_chits_per_hour']
    assert rates['mixed_crew_support'] == rates['crew_jobs_operator']
    assert rates['mixed_crew_lifter'] > rates['crew_jobs_ghost']


def test_game_8_5_8_6_9_forecast_respects_discrete_jobs_and_real_surgery_and_detox_quotes(economy):
    costs=economy['prices']['catalog']
    arm=costs['imp_halvard_reflex_arm']['sablier']
    assert (arm['item_price'],arm['service_price'],arm['total']) == (2200,440,2640)
    assert costs['detox']['total'] == 400
    forecasts=economy['gross_minutes_to_afford_from_starting_cash']
    assert forecasts['wpn_halvard_hv7']['solo_jobs'] == 15
    assert forecasts['prg_lance']['solo_jobs'] == 105
    assert forecasts['prg_lance']['crew_jobs_ghost'] == 90
    assert forecasts['owned_reflex_arm_installation_only']['solo_jobs'] == 30
    assert 'assumed cadence' in economy['kind']
    assert 'human enjoyment and full-city pacing' in economy['unmeasured']
