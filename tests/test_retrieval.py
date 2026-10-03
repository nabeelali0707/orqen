import pytest

from orqen import CatalogPolicy

CATALOG = (
    {"name": "lookup", "description": "customer identity", "capability": "customer.lookup"},
    {"name": "refund", "description": "refund payment", "capability": "payment.refund"},
    {"name": "balance", "description": "account balance", "capability": "account.balance"},
)


def test_full_catalog_is_default():
    assert CatalogPolicy().select("refund", CATALOG) == CATALOG


def test_fixed_top_k_ranks_across_capabilities():
    assert CatalogPolicy("fixed", 1).select("refund payment", CATALOG) == (CATALOG[1],)


def test_adaptive_unknown_query_abstains_from_filtering():
    assert CatalogPolicy("adaptive", 1).select("unfamiliar words", CATALOG) == CATALOG


def test_adaptive_retains_tied_candidates():
    selected = CatalogPolicy("adaptive", 1).select("customer account", CATALOG)
    assert selected == (CATALOG[0], CATALOG[2])


def test_adaptive_uses_less_than_limit_when_few_positive_matches():
    assert CatalogPolicy("adaptive", 5).select("refund", CATALOG) == (CATALOG[1],)


@pytest.mark.parametrize("kwargs", [{"mode": "unknown"}, {"top_k": 0}, {"top_k": True}])
def test_invalid_retrieval_policy_rejected(kwargs):
    with pytest.raises(ValueError):
        CatalogPolicy(**kwargs)
