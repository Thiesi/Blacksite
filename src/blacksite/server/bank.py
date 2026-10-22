"""Hand and bank balances remain separate (game design 8.1 / death 5.4)."""

from blacksite.server.players import Player


def exchange(hand: int, account: int, amount: int, deposit: bool) -> tuple[int, int]:
    if type(amount) is not int or amount <= 0:
        raise ValueError("Enter a positive whole number of chits.")
    if (hand if deposit else account) < amount:
        raise ValueError("You do not have that many chits.")
    return (hand-amount, account+amount) if deposit else (hand+amount, account-amount)


def transfer(player: Player, amount: int, deposit: bool) -> None:
    player.chits_hand, player.chits_bank = exchange(player.chits_hand, player.chits_bank, amount, deposit)
