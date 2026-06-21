from hand_evaluator import evaluate_hand


def test_straight_flush():
    hand = [(10, 'hearts'), (11, 'hearts')]
    community = [(12, 'hearts'), (9, 'hearts'), (13, 'hearts'), (2, 'clubs'), (3, 'diamonds')]
    hand_rank, _ = evaluate_hand(hand, community)
    assert hand_rank == 9


def test_four_of_a_kind():
    hand = [(13, 'hearts'), (13, 'spades')]
    community = [(13, 'clubs'), (13, 'diamonds'), (9, 'hearts'), (4, 'hearts'), (2, 'clubs')]
    hand_rank, _ = evaluate_hand(hand, community)
    assert hand_rank == 8


def test_full_house():
    hand = [(13, 'hearts'), (13, 'spades')]
    community = [(13, 'clubs'), (9, 'diamonds'), (9, 'spades'), (4, 'hearts'), (2, 'clubs')]
    hand_rank, _ = evaluate_hand(hand, community)
    assert hand_rank == 7


def test_flush():
    hand = [(2, 'hearts'), (9, 'hearts')]
    community = [(5, 'hearts'), (6, 'hearts'), (7, 'hearts'), (13, 'spades'), (2, 'clubs')]
    hand_rank, _ = evaluate_hand(hand, community)
    assert hand_rank == 6


def test_straight():
    hand = [(10, 'hearts'), (8, 'clubs')]
    community = [(9, 'diamonds'), (7, 'spades'), (6, 'hearts'), (2, 'clubs'), (3, 'spades')]
    hand_rank, _ = evaluate_hand(hand, community)
    assert hand_rank == 5


def test_three_of_a_kind():
    hand = [(13, 'hearts'), (13, 'clubs')]
    community = [(13, 'spades'), (9, 'hearts'), (4, 'spades'), (2, 'clubs'), (8, 'diamonds')]
    hand_rank, _ = evaluate_hand(hand, community)
    assert hand_rank == 4


def test_two_pair():
    hand = [(13, 'hearts'), (13, 'clubs')]
    community = [(9, 'hearts'), (9, 'clubs'), (4, 'spades'), (2, 'clubs'), (8, 'diamonds')]
    hand_rank, _ = evaluate_hand(hand, community)
    assert hand_rank == 3


def test_one_pair():
    hand = [(13, 'hearts'), (13, 'clubs')]
    community = [(9, 'hearts'), (7, 'clubs'), (4, 'spades'), (2, 'clubs'), (8, 'diamonds')]
    hand_rank, _ = evaluate_hand(hand, community)
    assert hand_rank == 2


def test_high_card():
    hand = [(13, 'hearts'), (10, 'clubs')]
    community = [(9, 'hearts'), (7, 'clubs'), (4, 'spades'), (2, 'clubs'), (8, 'diamonds')]
    hand_rank, _ = evaluate_hand(hand, community)
    assert hand_rank == 1
