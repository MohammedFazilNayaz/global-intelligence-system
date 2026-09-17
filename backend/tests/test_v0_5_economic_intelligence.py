"""
Deterministic V0.5 Economic Intelligence Benchmark Corpus.
Exhaustively tests all 18 required scenarios:
1. CPI release
2. GDP release
3. Unemployment release
4. Payroll release
5. Central-bank rate hike
6. Central-bank rate cut
7. Unchanged central-bank decision
8. Trade-balance release
9. Oil/commodity economic event
10. Fiscal-policy decision
11. Economic event with previous value
12. Economic event with expected/consensus value
13. Economic event with revised value
14. Passing indicator mention (filtered out)
15. Historical economic article (filtered out)
16. Negated economic claim (filtered out)
17. Multiple economic indicators in one document
18. Multi-country economic event
"""

import pytest
from datetime import datetime, timezone
from backend.app.extractors.economic import DeterministicEconomicExtractor
from backend.app.schemas.economic import (
    IndicatorType,
    EconomicDomain,
    CentralBankDecisionType,
    ObservationDirection,
)


@pytest.fixture
def extractor():
    return DeterministicEconomicExtractor()


# --- Case 1: CPI release ---
def test_case_01_cpi_release(extractor):
    text = "US CPI rose 3.2% year-over-year in August, compared with 3.0% previously."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    cpi_obs = next(o for o in obs if o.indicator_type in ("cpi", "inflation"))
    assert cpi_obs.country_name == "United States"
    assert cpi_obs.country_code == "US"
    assert cpi_obs.economic_domain == EconomicDomain.INFLATION.value
    assert cpi_obs.reported_value == 3.2
    assert cpi_obs.reported_unit == "%"
    assert cpi_obs.previous_value == 3.0
    assert cpi_obs.change_value == 0.2
    assert cpi_obs.direction in ("increase", "up")
    assert cpi_obs.expected_value is None  # Zero fabrication!
    assert cpi_obs.revised_value is None
    assert cpi_obs.economic_relevance >= 0.85


# --- Case 2: GDP release ---
def test_case_02_gdp_release(extractor):
    text = "Eurozone GDP grew 0.3% in the second quarter, slowing from 0.4% in Q1."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    gdp_obs = next(o for o in obs if o.indicator_type == "gdp")
    assert gdp_obs.country_name == "Eurozone"
    assert gdp_obs.country_code == "EU"
    assert gdp_obs.economic_domain == EconomicDomain.GROWTH.value
    assert gdp_obs.reported_value == 0.3
    assert gdp_obs.previous_value == 0.4
    assert gdp_obs.change_value == -0.1
    assert gdp_obs.direction in ("decrease", "slowed", "down")


# --- Case 3: Unemployment release ---
def test_case_03_unemployment_release(extractor):
    text = "US unemployment rate ticked up to 4.3% in July from 4.1% in June."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    unemp_obs = next(o for o in obs if o.indicator_type == "unemployment")
    assert unemp_obs.country_name == "United States"
    assert unemp_obs.reported_value == 4.3
    assert unemp_obs.previous_value == 4.1
    assert unemp_obs.change_value == 0.2
    assert unemp_obs.direction == "increase"
    assert unemp_obs.expected_value is None


# --- Case 4: Payroll release with consensus expectation ---
def test_case_04_payroll_release(extractor):
    text = "US non-farm payrolls increased by 142,000 in August, below expectations of 165,000."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    pay_obs = next(o for o in obs if o.indicator_type == "payrolls")
    assert pay_obs.country_name == "United States"
    assert pay_obs.reported_value == 142000.0
    assert pay_obs.expected_value == 165000.0
    assert pay_obs.previous_value is None  # Not reported in text
    assert pay_obs.direction == "increase"
    assert "consensus_variance_surprise" in pay_obs.metadata["relevance_explanation"]


# --- Case 5: Central-bank rate hike ---
def test_case_05_cb_rate_hike(extractor):
    text = "European Central Bank raised its benchmark deposit facility rate by 25 basis points to 4.00%."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    cb_obs = next(o for o in obs if o.central_bank_decision is not None)
    assert cb_obs.country_name == "Eurozone"
    assert cb_obs.central_bank_decision["decision_type"] == CentralBankDecisionType.RATE_HIKE.value
    assert cb_obs.central_bank_decision["rate_change_bps"] == 25.0
    assert cb_obs.reported_value == 4.00
    assert cb_obs.direction == ObservationDirection.HIKE.value


# --- Case 6: Central-bank rate cut ---
def test_case_06_cb_rate_cut(extractor):
    text = "Bank of England cut its policy rate by 25 bps to 5.00%, down from 5.25%."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    cb_obs = next(o for o in obs if o.central_bank_decision is not None)
    assert cb_obs.country_name == "United Kingdom"
    assert cb_obs.central_bank_decision["decision_type"] == CentralBankDecisionType.RATE_CUT.value
    assert cb_obs.reported_value == 5.00
    assert cb_obs.previous_value == 5.25
    assert cb_obs.change_value == -0.25
    assert cb_obs.direction == ObservationDirection.CUT.value


# --- Case 7: Unchanged central-bank decision ---
def test_case_07_cb_unchanged_decision(extractor):
    text = "Federal Reserve holds benchmark rate steady at 5.25%-5.50% range."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    cb_obs = next(o for o in obs if o.central_bank_decision is not None)
    assert cb_obs.country_name == "United States"
    assert cb_obs.central_bank_decision["decision_type"] == CentralBankDecisionType.RATE_HOLD.value
    assert cb_obs.reported_value == 5.50
    assert cb_obs.direction == ObservationDirection.HOLD.value


# --- Case 8: Trade-balance release ---
def test_case_08_trade_balance_release(extractor):
    text = "Japan trade deficit narrowed to 621 billion yen in July, compared to 1.02 trillion yen a year earlier."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    tb_obs = next(o for o in obs if o.indicator_type == "trade_balance")
    assert tb_obs.country_name == "Japan"
    assert tb_obs.reported_value == 621.0
    assert tb_obs.previous_value == 1020.0  # normalized in billions
    assert tb_obs.direction == "decrease"


# --- Case 9: Oil/commodity economic event ---
def test_case_09_oil_commodity_event(extractor):
    text = "OPEC+ agreed to voluntary crude oil output cuts of 2.2 million barrels per day."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    oil_obs = next(o for o in obs if o.indicator_type == "oil")
    assert oil_obs.reported_value == 2.2
    assert "barrels" in oil_obs.reported_unit or "bbl" in oil_obs.reported_unit
    assert oil_obs.direction == "decrease"


# --- Case 10: Fiscal-policy decision ---
def test_case_10_fiscal_policy_decision(extractor):
    text = "US federal budget deficit widened to $1.9 trillion for fiscal year 2024."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    def_obs = next(o for o in obs if o.indicator_type == "public_deficit")
    assert def_obs.country_name == "United States"
    assert def_obs.reported_value == 1900.0  # billions
    assert def_obs.direction == "increase"
    assert def_obs.previous_value is None  # Zero fabrication


# --- Case 11: Economic event with previous value ---
def test_case_11_event_with_previous_value(extractor):
    text = "UK retail sales volumes rose 0.5% in July, rebounding from a 1.2% decline in June."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    ret_obs = next(o for o in obs if o.indicator_type == "retail_sales")
    assert ret_obs.country_name == "United Kingdom"
    assert ret_obs.reported_value == 0.5
    assert ret_obs.previous_value == 1.2
    assert ret_obs.direction == "increase"


# --- Case 12: Economic event with expected/consensus value ---
def test_case_12_event_with_consensus_value(extractor):
    text = "German Ifo business climate index dropped to 86.6 in August, missing consensus expectations of 87.0."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    biz_obs = next(o for o in obs if o.indicator_type == "business_confidence")
    assert biz_obs.country_name == "Germany"
    assert biz_obs.reported_value == 86.6
    assert biz_obs.expected_value == 87.0
    assert biz_obs.previous_value is None  # Unstated in text
    assert biz_obs.direction == "decrease"


# --- Case 13: Economic event with revised value ---
def test_case_13_event_with_revised_value(extractor):
    text = "US non-farm payrolls for July were revised down to 89,000 from the initially reported 114,000."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 1
    rev_obs = next(o for o in obs if o.indicator_type == "payrolls")
    assert rev_obs.reported_value == 89000.0
    assert rev_obs.previous_value == 114000.0
    assert rev_obs.revised_value == 89000.0
    assert rev_obs.calculation_method == "explicitly_reported"
    assert rev_obs.direction == "decrease"


# --- Case 14: Article mentioning an indicator without reporting an event ---
def test_case_14_passing_mention_filtered(extractor):
    text = "The central bank will watch incoming CPI and employment data before its next policy meeting."
    obs = extractor.extract_economic_intelligence(text)
    # No release verb or numerical values -> MUST NOT emit false positive observation!
    assert len(obs) == 0


# --- Case 15: Historical economic article ---
def test_case_15_historical_retrospective_filtered(extractor):
    text = "Remembering the Volcker shock in 1981 when the Fed raised rates to 20% to combat double-digit inflation."
    obs = extractor.extract_economic_intelligence(text)
    # Retrospective marker with 1981 -> MUST NOT emit as active contemporary economic release!
    assert len(obs) == 0


# --- Case 16: Negated economic claim ---
def test_case_16_negated_claim_filtered(extractor):
    text = "Federal Reserve confirmed it will not cut rates at the upcoming September meeting."
    obs = extractor.extract_economic_intelligence(text)
    # Negated action -> MUST NOT emit as positive rate cut!
    assert len(obs) == 0


# --- Case 17: Multiple economic indicators in one document ---
def test_case_17_multiple_indicators_in_one_document(extractor):
    text = "US consumer prices rose 0.2% in July, while retail sales surged 1.0%."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 2
    types = {o.indicator_type for o in obs}
    assert "cpi" in types or "inflation" in types
    assert "retail_sales" in types


# --- Case 18: Economic event involving multiple countries/regions ---
def test_case_18_multi_country_economic_event(extractor):
    text = "EU exports slipped 2.4% in July, while German industrial output dropped 1.8%."
    obs = extractor.extract_economic_intelligence(text)
    assert len(obs) >= 2
    countries = {o.country_name for o in obs}
    assert "Eurozone" in countries
    assert "Germany" in countries
