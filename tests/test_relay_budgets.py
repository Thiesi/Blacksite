"""Game 7.5/7.7/8.2: one shared budget through period and cap changes."""

from dataclasses import asdict

from blacksite.server.vendors import VendorBudget


def test_game_7_7_half_hour_refill_and_ownership_loss_never_reset_same_boundary():
    budget=VendorBudget(0)
    budget.refill(0)
    budget.spend(1800)
    budget.refill(1799,period=1800)
    assert budget.remaining==200
    budget.refill(1800,period=1800)
    assert budget.remaining==2000 and budget.refilled_at==1800
    budget.spend(1500)
    budget.refill(1850,period=3600)
    assert budget.remaining==500 and budget.spent==1500
    budget=VendorBudget(**asdict(budget))
    budget.refill(1900,period=1800)
    assert budget.remaining==500
    budget.refill(3600,period=3600)
    assert budget.remaining==2000 and budget.refilled_at==3600


def test_game_7_5_7_7_depot_period_and_service_cap_have_independent_spending():
    budget=VendorBudget(0)
    budget.refill(0,4000,1800)
    budget.spend(3500)
    budget.refill(100,2000,1800)
    assert budget.remaining==0 and budget.spent==3500
    budget.refill(101,4000,1800)
    assert budget.remaining==500 and budget.spent==3500
    budget.refill(1800,2000,1800)
    assert budget.remaining==2000 and budget.spent==0
    budget.spend(2000)
    budget.refill(1801,2000,3600)
    assert budget.remaining==0
