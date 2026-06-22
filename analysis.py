"""Bounded spectator-only equity calculations."""

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
import random
from threading import RLock

from deck import RANKS, SUITS
from hand_evaluator import evaluate_hand


class EquityCalculator:
    """Cache equity work and never block a state/overlay request."""

    def __init__(self, samples=1600, cache_size=128):
        self.samples = max(100, int(samples))
        self.cache_size = max(8, int(cache_size))
        self._cache = OrderedDict()
        self._pending = set()
        self._lock = RLock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="poker-equity")

    def get_or_schedule(self, players, board, hand_number=0):
        contenders = [(player.id, tuple(player.hand)) for player in players if player.is_active and not player.folded]
        if not contenders or any(len(cards) != 2 for _player_id, cards in contenders):
            return {}, False
        key = (tuple(contenders), tuple(board))
        if len(contenders) < 2:
            return {player_id: 100.0 for player_id, _cards in contenders}, False
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return dict(self._cache[key]), False
            if key not in self._pending and len(self._pending) < 4:
                self._pending.add(key)
                future = self._pool.submit(self._calculate, contenders, tuple(board), hand_number)
                future.add_done_callback(lambda result, cache_key=key: self._store(cache_key, result))
        return {player_id: None for player_id, _cards in contenders}, True

    def _store(self, key, future):
        try:
            result = future.result()
        except Exception:
            result = {}
        with self._lock:
            self._pending.discard(key)
            if result:
                self._cache[key] = result
                self._cache.move_to_end(key)
                while len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)

    def _calculate(self, contenders, board, seed):
        known = set(board)
        for _player_id, cards in contenders:
            known.update(cards)
        remaining = [(rank, suit) for rank in RANKS for suit in SUITS if (rank, suit) not in known]
        cards_needed = 5 - len(board)
        if cards_needed <= 0:
            runouts = [()]
        else:
            total = _combination_count(len(remaining), cards_needed)
            if len(board) >= 3 and total <= 5000:
                runouts = combinations(remaining, cards_needed)
            else:
                rng = random.Random(repr((contenders, board, seed)))
                runouts = (tuple(rng.sample(remaining, cards_needed)) for _ in range(self.samples))

        shares = {player_id: 0.0 for player_id, _cards in contenders}
        count = 0
        for runout in runouts:
            complete_board = list(board) + list(runout)
            values = {
                player_id: evaluate_hand(list(cards), complete_board)
                for player_id, cards in contenders
            }
            best = max(values.values())
            winners = [player_id for player_id, value in values.items() if value == best]
            share = 1.0 / len(winners)
            for player_id in winners:
                shares[player_id] += share
            count += 1
        return {player_id: round(100 * value / max(1, count), 1) for player_id, value in shares.items()}

    def close(self):
        self._pool.shutdown(wait=False, cancel_futures=True)


def _combination_count(n, k):
    if k < 0 or k > n:
        return 0
    result = 1
    for index in range(1, k + 1):
        result = result * (n - index + 1) // index
    return result
