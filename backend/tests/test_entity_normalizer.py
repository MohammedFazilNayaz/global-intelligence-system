import pytest
from backend.app.extractors.normalizer import (
    EntityNormalizer,
    normalize_text_key,
)


def test_normalize_text_key():
    """Verify punctuation stripping, lowercasing, and whitespace collapsing."""
    assert normalize_text_key("  United   States  ") == "united states"
    assert normalize_text_key("U.S.A.") == "usa"
    assert normalize_text_key("People's Republic of China") == "peoples republic of china"
    assert normalize_text_key("OPEC+") == "opec"
    assert normalize_text_key("") == ""


def test_country_normalization_aliases():
    """Verify multiple country aliases resolve to the same canonical country entity."""
    aliases = ["United States", "USA", "U.S.", "United States of America", "US"]
    for alias in aliases:
        result = EntityNormalizer.lookup(alias)
        assert result is not None, f"Failed lookup for alias '{alias}'"
        assert result.canonical_name == "United States"
        assert result.normalized_name == "united states"
        assert result.entity_type == "COUNTRY"
        assert result.country_code == "US"


def test_uk_and_china_normalization():
    """Verify UK and China canonicalization."""
    uk_res = EntityNormalizer.lookup("Britain")
    assert uk_res is not None
    assert uk_res.canonical_name == "United Kingdom"
    assert uk_res.country_code == "GB"

    cn_res = EntityNormalizer.lookup("PRC")
    assert cn_res is not None
    assert cn_res.canonical_name == "China"
    assert cn_res.country_code == "CN"


def test_central_bank_normalization():
    """Verify central bank alias resolution."""
    fed_res = EntityNormalizer.lookup("the Fed")
    assert fed_res is not None
    assert fed_res.canonical_name == "Federal Reserve"
    assert fed_res.entity_type == "CENTRAL_BANK"
    assert fed_res.country_code == "US"

    ecb_res = EntityNormalizer.lookup("ECB")
    assert ecb_res is not None
    assert ecb_res.canonical_name == "European Central Bank"
    assert ecb_res.entity_type == "CENTRAL_BANK"


def test_currency_and_commodity_normalization():
    """Verify currency and commodity canonicalization."""
    usd = EntityNormalizer.lookup("USD")
    assert usd is not None
    assert usd.canonical_name == "US Dollar"
    assert usd.entity_type == "CURRENCY"

    btc = EntityNormalizer.lookup("BTC")
    assert btc is not None
    assert btc.canonical_name == "Bitcoin"
    assert btc.entity_type == "CRYPTOCURRENCY"

    oil = EntityNormalizer.lookup("Brent Crude")
    assert oil is not None
    assert oil.canonical_name == "Crude Oil"
    assert oil.entity_type == "COMMODITY"


def test_resolve_or_fallback_unknown_entity():
    """Verify fallback for uncataloged entity strings."""
    res = EntityNormalizer.resolve_or_fallback("Neo Dynamics Corp", entity_type="COMPANY")
    assert res.canonical_name == "Neo Dynamics Corp"
    assert res.normalized_name == "neo dynamics corp"
    assert res.entity_type == "COMPANY"
