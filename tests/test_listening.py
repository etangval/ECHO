import pytest
from digitalcreativity.listening import orient_rating,holm,summarize


def test_blinding_orientation_and_neutral():
    assert orient_rating(1,'optimized') == 3
    assert orient_rating(1,'random') == -3
    assert orient_rating(4,'random') == 0
    with pytest.raises(ValueError): orient_rating(3,'unknown')


def test_holm_is_monotone_in_order():
    assert holm([.03,.001,.02]) == pytest.approx([.04,.003,.04])


def test_domain_balance_and_ties_do_not_become_random_votes():
    rows=[dict(domain=d,comparisons={k:v for k in ('beauty','pleasantness','preference')},firstCondition='optimized') for d,v in [('x',1),('x',1),('y',4)]]
    s=summarize(rows,replicates=100)
    o=s['outcomes']['beauty']
    assert o['equal_domain_weighted']['mean'] == 1.5
    assert o['overall']['equal'] == 1
    assert o['overall']['optimized_share_decisive'] == 1.
