"""Hand and bank balances remain separate (game design 8.1 / death 5.4)."""

from blacksite.server.players import Player


def transfer(player: Player, amount: int, deposit: bool) -> None:
    if type(amount) is not int or amount <= 0:
        raise ValueError("Enter a positive whole number of chits.")
    source, target = ("chits_hand", "chits_bank") if deposit else ("chits_bank", "chits_hand")
    if getattr(player, source) < amount:
        raise ValueError("You do not have that many chits.")
    setattr(player, source, getattr(player, source) - amount)
    setattr(player, target, getattr(player, target) + amount)
