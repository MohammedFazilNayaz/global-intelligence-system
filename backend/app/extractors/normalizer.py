import re
import unicodedata
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel
from backend.app.schemas.extraction import EntityType


class NormalizedEntityResult(BaseModel):
    canonical_name: str
    normalized_name: str
    entity_type: str
    country_code: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = {}


# Pre-compiled regex for punctuation stripping and whitespace cleanup
_PUNCT_REGEX = re.compile(r"[^\w\s-]")
_MULTI_SPACE_REGEX = re.compile(r"\s+")


def normalize_text_key(text: str) -> str:
    """Deterministic lowercased, punctuation-stripped, and whitespace-collapsed text key."""
    if not text:
        return ""
    # Normalize unicode (NFKD)
    normalized = unicodedata.normalize("NFKD", text)
    # Remove apostrophes and dots without adding spaces (e.g. People's -> Peoples, U.S.A. -> USA)
    normalized = normalized.replace("'", "").replace("’", "").replace(".", "")
    # Replace other punctuation with space
    cleaned = _PUNCT_REGEX.sub(" ", normalized)
    # Lowercase and collapse multi-space
    collapsed = _MULTI_SPACE_REGEX.sub(" ", cleaned).strip().lower()
    return collapsed


# Curated Knowledge Base mapping alias normalized keys to canonical entities
_ENTITY_KNOWLEDGE_BASE: Dict[str, NormalizedEntityResult] = {}
# Structured surface catalog preserving original surface forms for high-precision regex extraction
_REGISTERED_CATALOG: list[Tuple[NormalizedEntityResult, list[str]]] = []


def _register_entity(
    canonical_name: str,
    entity_type: EntityType,
    aliases: list[str],
    country_code: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    norm_key = normalize_text_key(canonical_name)
    result = NormalizedEntityResult(
        canonical_name=canonical_name,
        normalized_name=norm_key,
        entity_type=entity_type.value,
        country_code=country_code,
        description=description,
        metadata=metadata or {},
    )
    # Register canonical key
    _ENTITY_KNOWLEDGE_BASE[norm_key] = result

    # Register all aliases
    for alias in aliases:
        a_key = normalize_text_key(alias)
        if a_key:
            _ENTITY_KNOWLEDGE_BASE[a_key] = result

    # Preserve exact surface forms for regex pattern compilation
    surface_forms = [canonical_name] + [a for a in aliases if a]
    _REGISTERED_CATALOG.append((result, surface_forms))


# Populate Countries
_register_entity(
    "United States", EntityType.COUNTRY,
    ["USA", "U.S.", "U.S.A.", "United States of America", "the United States", "US"],
    country_code="US", description="Federal republic in North America",
)
_register_entity(
    "United Kingdom", EntityType.COUNTRY,
    ["UK", "U.K.", "Britain", "Great Britain", "the United Kingdom"],
    country_code="GB", description="Island nation in northwestern Europe",
)
_register_entity(
    "China", EntityType.COUNTRY,
    ["PRC", "People's Republic of China", "P.R.C.", "Mainland China"],
    country_code="CN", description="Sovereign state in East Asia",
)
_register_entity(
    "Russia", EntityType.COUNTRY,
    ["Russian Federation", "the Russian Federation"],
    country_code="RU", description="Transcontinental country spanning Eastern Europe and Northern Asia",
)
_register_entity(
    "Germany", EntityType.COUNTRY,
    ["Federal Republic of Germany", "Deutschland"],
    country_code="DE", description="Federal parliamentary republic in Central Europe",
)
_register_entity(
    "France", EntityType.COUNTRY,
    ["French Republic"],
    country_code="FR", description="Unitary state in Western Europe",
)
_register_entity(
    "Japan", EntityType.COUNTRY,
    ["Nippon"],
    country_code="JP", description="Island country in East Asia",
)
_register_entity(
    "India", EntityType.COUNTRY,
    ["Republic of India", "Bharat"],
    country_code="IN", description="Country in South Asia",
)
_register_entity(
    "Ukraine", EntityType.COUNTRY,
    [],
    country_code="UA", description="Country in Eastern Europe",
)
_register_entity(
    "Israel", EntityType.COUNTRY,
    ["State of Israel"],
    country_code="IL", description="Country in the Middle East",
)
_register_entity(
    "Iran", EntityType.COUNTRY,
    ["Islamic Republic of Iran"],
    country_code="IR", description="Country in Western Asia",
)
_register_entity(
    "Saudi Arabia", EntityType.COUNTRY,
    ["KSA", "Kingdom of Saudi Arabia"],
    country_code="SA", description="Country in Western Asia on the Arabian Peninsula",
)
_register_entity(
    "Canada", EntityType.COUNTRY,
    [],
    country_code="CA", description="Country in North America",
)
_register_entity(
    "Brazil", EntityType.COUNTRY,
    ["Federative Republic of Brazil"],
    country_code="BR", description="Largest country in South and Latin America",
)
_register_entity(
    "Australia", EntityType.COUNTRY,
    ["Commonwealth of Australia"],
    country_code="AU", description="Sovereign country comprising mainland Australian continent",
)
_register_entity(
    "South Korea", EntityType.COUNTRY,
    ["ROK", "Republic of Korea", "Korea"],
    country_code="KR", description="Country in East Asia",
)
_register_entity(
    "North Korea", EntityType.COUNTRY,
    ["DPRK", "Democratic People's Republic of Korea"],
    country_code="KP", description="Country in East Asia",
)
_register_entity(
    "Taiwan", EntityType.COUNTRY,
    ["ROC", "Republic of China"],
    country_code="TW", description="Country in East Asia",
)
_register_entity(
    "Turkey", EntityType.COUNTRY,
    ["Turkiye", "Republic of Turkey"],
    country_code="TR", description="Transcontinental country located mainly on Anatolian Peninsula",
)
_register_entity(
    "Italy", EntityType.COUNTRY,
    ["Italian Republic"],
    country_code="IT", description="Country in Southern Europe",
)
_register_entity(
    "Mexico", EntityType.COUNTRY,
    ["United Mexican States"],
    country_code="MX", description="Country in North America",
)
_register_entity(
    "South Africa", EntityType.COUNTRY,
    ["RSA", "Republic of South Africa"],
    country_code="ZA", description="Country on southernmost tip of African continent",
)
_register_entity(
    "Singapore", EntityType.COUNTRY,
    ["Republic of Singapore"],
    country_code="SG", description="Island city-state in Southeast Asia",
)
_register_entity(
    "Switzerland", EntityType.COUNTRY,
    ["Swiss Confederation"],
    country_code="CH", description="Landlocked country in Central Europe",
)
_register_entity(
    "Sweden", EntityType.COUNTRY,
    ["Kingdom of Sweden"],
    country_code="SE", description="Nordic country in Northern Europe",
)
_register_entity(
    "Norway", EntityType.COUNTRY,
    ["Kingdom of Norway"],
    country_code="NO", description="Nordic country in Northern Europe",
)
_register_entity(
    "Poland", EntityType.COUNTRY,
    ["Republic of Poland"],
    country_code="PL", description="Country in Central Europe",
)
_register_entity(
    "Indonesia", EntityType.COUNTRY,
    ["Republic of Indonesia"],
    country_code="ID", description="Archipelagic country in Southeast Asia",
)
_register_entity(
    "Argentina", EntityType.COUNTRY,
    ["Argentine Republic"],
    country_code="AR", description="Country in the southern half of South America",
)
_register_entity(
    "Egypt", EntityType.COUNTRY,
    ["Arab Republic of Egypt"],
    country_code="EG", description="Transcontinental country spanning northeast Africa and Sinai",
)
_register_entity(
    "United Arab Emirates", EntityType.COUNTRY,
    ["UAE", "the UAE", "Emirates"],
    country_code="AE", description="Country in Western Asia",
)
_register_entity(
    "Qatar", EntityType.COUNTRY,
    ["State of Qatar"],
    country_code="QA", description="Country in Western Asia",
)
_register_entity(
    "Pakistan", EntityType.COUNTRY,
    ["Islamic Republic of Pakistan"],
    country_code="PK", description="Country in South Asia",
)
_register_entity(
    "Iraq", EntityType.COUNTRY,
    ["Republic of Iraq"],
    country_code="IQ", description="Country in Western Asia",
)
_register_entity(
    "Syria", EntityType.COUNTRY,
    ["Syrian Arab Republic"],
    country_code="SY", description="Country in Western Asia",
)
_register_entity(
    "Lebanon", EntityType.COUNTRY,
    ["Lebanese Republic"],
    country_code="LB", description="Country in Western Asia",
)
_register_entity(
    "Vanuatu", EntityType.COUNTRY,
    ["Republic of Vanuatu"],
    country_code="VU", description="Island nation located in the South Pacific Ocean",
)
_register_entity(
    "Solomon Islands", EntityType.COUNTRY,
    ["Solomons"],
    country_code="SB", description="Nation consisting of hundreds of islands in the South Pacific",
)
_register_entity(
    "Georgia", EntityType.COUNTRY,
    ["Sakartvelo"],
    country_code="GE", description="Transcontinental country at the intersection of Eastern Europe and Western Asia",
)
_register_entity("Spain", EntityType.COUNTRY, ["Spanish Kingdom", "Espana"], country_code="ES", description="Country in Southwestern Europe")
_register_entity("Netherlands", EntityType.COUNTRY, ["Holland", "the Netherlands", "Dutch Republic"], country_code="NL", description="Country in Northwestern Europe")
_register_entity("Belgium", EntityType.COUNTRY, ["Kingdom of Belgium"], country_code="BE", description="Country in Western Europe")
_register_entity("Philippines", EntityType.COUNTRY, ["the Philippines", "Republic of the Philippines"], country_code="PH", description="Archipelagic country in Southeast Asia")
_register_entity("Vietnam", EntityType.COUNTRY, ["Viet Nam", "Socialist Republic of Vietnam"], country_code="VN", description="Country in Southeast Asia")
_register_entity("Thailand", EntityType.COUNTRY, ["Kingdom of Thailand", "Siam"], country_code="TH", description="Country in Southeast Asia")
_register_entity("Malaysia", EntityType.COUNTRY, [], country_code="MY", description="Country in Southeast Asia")
_register_entity("Nigeria", EntityType.COUNTRY, ["Federal Republic of Nigeria"], country_code="NG", description="Country in West Africa")
_register_entity("Kenya", EntityType.COUNTRY, ["Republic of Kenya"], country_code="KE", description="Country in East Africa")
_register_entity("Ethiopia", EntityType.COUNTRY, ["Federal Democratic Republic of Ethiopia"], country_code="ET", description="Landlocked country in the Horn of Africa")
_register_entity("Colombia", EntityType.COUNTRY, ["Republic of Colombia"], country_code="CO", description="Country in South America")
_register_entity("Chile", EntityType.COUNTRY, ["Republic of Chile"], country_code="CL", description="Country in western South America")
_register_entity("Venezuela", EntityType.COUNTRY, ["Bolivarian Republic of Venezuela"], country_code="VE", description="Country on the northern coast of South America")
_register_entity("New Zealand", EntityType.COUNTRY, ["Aotearoa"], country_code="NZ", description="Island country in the southwestern Pacific Ocean")
_register_entity("Yemen", EntityType.COUNTRY, ["Republic of Yemen"], country_code="YE", description="Country in Western Asia on the Arabian Peninsula")
_register_entity("Jordan", EntityType.COUNTRY, ["Hashemite Kingdom of Jordan"], country_code="JO", description="Country in Western Asia")
_register_entity("Sudan", EntityType.COUNTRY, ["Republic of the Sudan"], country_code="SD", description="Country in Northeast Africa")
_register_entity("Ireland", EntityType.COUNTRY, ["Republic of Ireland", "Eire"], country_code="IE", description="Island nation in northwestern Europe")
_register_entity("Austria", EntityType.COUNTRY, ["Republic of Austria"], country_code="AT", description="Landlocked country in Central Europe")
_register_entity("Portugal", EntityType.COUNTRY, ["Portuguese Republic"], country_code="PT", description="Country on the Iberian Peninsula")
_register_entity("Greece", EntityType.COUNTRY, ["Hellenic Republic"], country_code="GR", description="Country in Southeastern Europe")
_register_entity("Finland", EntityType.COUNTRY, ["Republic of Finland"], country_code="FI", description="Nordic country in Northern Europe")
_register_entity("Denmark", EntityType.COUNTRY, ["Kingdom of Denmark"], country_code="DK", description="Nordic country in Northern Europe")
_register_entity("Somalia", EntityType.COUNTRY, ["Federal Republic of Somalia"], country_code="SO", description="Country in the Horn of Africa")
_register_entity("Libya", EntityType.COUNTRY, ["State of Libya"], country_code="LY", description="Country in the Maghreb region of North Africa")
_register_entity("Kazakhstan", EntityType.COUNTRY, ["Republic of Kazakhstan"], country_code="KZ", description="Transcontinental country in Central Asia and Eastern Europe")
_register_entity("Uzbekistan", EntityType.COUNTRY, ["Republic of Uzbekistan"], country_code="UZ", description="Landlocked country in Central Asia")
_register_entity("Bangladesh", EntityType.COUNTRY, ["People's Republic of Bangladesh"], country_code="BD", description="Country in South Asia")


# Populate Cities & Locations
_register_entity("Washington, D.C.", EntityType.CITY, ["Washington", "Washington D.C.", "Washington DC"], country_code="US")
_register_entity("London", EntityType.CITY, [], country_code="GB")
_register_entity("Beijing", EntityType.CITY, ["Peking"], country_code="CN")
_register_entity("Tokyo", EntityType.CITY, [], country_code="JP")
_register_entity("Moscow", EntityType.CITY, [], country_code="RU")
_register_entity("Kyiv", EntityType.CITY, ["Kiev"], country_code="UA")
_register_entity("Brussels", EntityType.CITY, [], country_code="BE")
_register_entity("Paris", EntityType.CITY, [], country_code="FR")
_register_entity("Berlin", EntityType.CITY, [], country_code="DE")
_register_entity("Riyadh", EntityType.CITY, [], country_code="SA")
_register_entity("Tehran", EntityType.CITY, [], country_code="IR")
_register_entity("Jerusalem", EntityType.CITY, [], country_code="IL")
_register_entity("New York City", EntityType.CITY, ["New York", "NYC"], country_code="US")
_register_entity("Geneva", EntityType.CITY, [], country_code="CH")
_register_entity("Tbilisi", EntityType.CITY, ["Tiflis"], country_code="GE")
_register_entity("Honiara", EntityType.CITY, [], country_code="SB")
_register_entity("Gaza Strip", EntityType.LOCATION, ["Gaza"])
_register_entity("West Bank", EntityType.LOCATION, [])
_register_entity("Red Sea", EntityType.LOCATION, [])
_register_entity("Strait of Hormuz", EntityType.LOCATION, [])
_register_entity("Taiwan Strait", EntityType.LOCATION, [])

# Central Banks
_register_entity("Federal Reserve", EntityType.CENTRAL_BANK, ["the Fed", "Fed", "US Fed", "Federal Reserve System"], country_code="US")
_register_entity("European Central Bank", EntityType.CENTRAL_BANK, ["ECB"], country_code="EU")
_register_entity("Bank of England", EntityType.CENTRAL_BANK, ["BoE", "BOE"], country_code="GB")
_register_entity("Bank of Japan", EntityType.CENTRAL_BANK, ["BoJ", "BOJ"], country_code="JP")
_register_entity("People's Bank of China", EntityType.CENTRAL_BANK, ["PBOC", "PBoC"], country_code="CN")
_register_entity("Reserve Bank of India", EntityType.CENTRAL_BANK, ["RBI"], country_code="IN")
_register_entity("Swiss National Bank", EntityType.CENTRAL_BANK, ["SNB"], country_code="CH")

# Financial Institutions
_register_entity("International Monetary Fund", EntityType.FINANCIAL_INSTITUTION, ["IMF"])
_register_entity("World Bank", EntityType.FINANCIAL_INSTITUTION, ["World Bank Group"])
_register_entity("Bank for International Settlements", EntityType.FINANCIAL_INSTITUTION, ["BIS"])
_register_entity("Goldman Sachs", EntityType.FINANCIAL_INSTITUTION, [])
_register_entity("JPMorgan Chase", EntityType.FINANCIAL_INSTITUTION, ["JPMorgan", "JP Morgan"])

# International Organizations & Governments
_register_entity("United Nations", EntityType.INTERNATIONAL_ORGANIZATION, ["UN", "the UN", "U.N."])
_register_entity("NATO", EntityType.INTERNATIONAL_ORGANIZATION, ["North Atlantic Treaty Organization"])
_register_entity("European Union", EntityType.INTERNATIONAL_ORGANIZATION, ["EU", "the EU", "E.U.", "European Commission", "EU Commission", "European Council"], country_code="EU")
_register_entity("OPEC", EntityType.INTERNATIONAL_ORGANIZATION, ["OPEC+", "Organization of the Petroleum Exporting Countries"])
_register_entity("World Health Organization", EntityType.INTERNATIONAL_ORGANIZATION, ["WHO"])
_register_entity("World Trade Organization", EntityType.INTERNATIONAL_ORGANIZATION, ["WTO"])
_register_entity("G7", EntityType.INTERNATIONAL_ORGANIZATION, ["Group of Seven"])
_register_entity("G20", EntityType.INTERNATIONAL_ORGANIZATION, ["Group of Twenty"])
_register_entity("United States Government", EntityType.GOVERNMENT, ["White House", "US Administration", "Biden Administration"], country_code="US")
_register_entity("Russian Government", EntityType.GOVERNMENT, ["Kremlin"], country_code="RU")
_register_entity("United States Department of Defense", EntityType.GOVERNMENT, ["Pentagon"], country_code="US")
_register_entity("Government of the United Kingdom", EntityType.GOVERNMENT, ["Downing Street", "10 Downing Street"], country_code="GB")
_register_entity("African Union", EntityType.INTERNATIONAL_ORGANIZATION, ["AU"])
_register_entity("ASEAN", EntityType.INTERNATIONAL_ORGANIZATION, ["Association of Southeast Asian Nations"])
_register_entity("Houthis", EntityType.ORGANIZATION, ["Houthi movement", "Ansar Allah", "Houthi forces", "Houthi militants"], country_code="YE")
_register_entity("Hezbollah", EntityType.ORGANIZATION, ["Hizballah", "Hezbollah forces"], country_code="LB")
_register_entity("Hamas", EntityType.ORGANIZATION, [], country_code="PS")

# World Leaders & Key Officials
_register_entity("Donald Trump", EntityType.PERSON, ["Trump", "President Trump"], country_code="US")
_register_entity("Joe Biden", EntityType.PERSON, ["Biden", "President Biden"], country_code="US")
_register_entity("Vladimir Putin", EntityType.PERSON, ["Putin", "President Putin"], country_code="RU")
_register_entity("Volodymyr Zelensky", EntityType.PERSON, ["Zelensky", "President Zelensky", "Zelenskyy"], country_code="UA")
_register_entity("Xi Jinping", EntityType.PERSON, ["President Xi", "Xi"], country_code="CN")
_register_entity("Benjamin Netanyahu", EntityType.PERSON, ["Netanyahu", "Prime Minister Netanyahu"], country_code="IL")
_register_entity("Narendra Modi", EntityType.PERSON, ["Modi", "Prime Minister Modi"], country_code="IN")
_register_entity("Keir Starmer", EntityType.PERSON, ["Starmer", "Prime Minister Starmer"], country_code="GB")
_register_entity("Emmanuel Macron", EntityType.PERSON, ["Macron", "President Macron"], country_code="FR")
_register_entity("Olaf Scholz", EntityType.PERSON, ["Scholz", "Chancellor Scholz"], country_code="DE")
_register_entity("Jerome Powell", EntityType.PERSON, ["Chair Powell", "Chairman Powell", "Powell"], country_code="US")
_register_entity("Christine Lagarde", EntityType.PERSON, ["President Lagarde", "Lagarde"], country_code="EU")
_register_entity("Antony Blinken", EntityType.PERSON, ["Secretary Blinken", "Blinken"], country_code="US")
_register_entity("Antonio Guterres", EntityType.PERSON, ["Secretary-General Guterres", "Guterres"])
_register_entity("Masoud Pezeshkian", EntityType.PERSON, ["Pezeshkian", "President Pezeshkian"], country_code="IR")
_register_entity("Ali Khamenei", EntityType.PERSON, ["Ayatollah Khamenei", "Khamenei", "Supreme Leader Khamenei"], country_code="IR")


# Currencies & Cryptocurrencies
_register_entity("US Dollar", EntityType.CURRENCY, ["USD", "Dollar", "Greenback"])
_register_entity("Euro", EntityType.CURRENCY, ["EUR"])
_register_entity("British Pound", EntityType.CURRENCY, ["GBP", "Pound Sterling", "Sterling"])
_register_entity("Japanese Yen", EntityType.CURRENCY, ["JPY", "Yen"])
_register_entity("Chinese Yuan", EntityType.CURRENCY, ["CNY", "Renminbi", "RMB"])
_register_entity("Swiss Franc", EntityType.CURRENCY, ["CHF"])
_register_entity("Bitcoin", EntityType.CRYPTOCURRENCY, ["BTC"])
_register_entity("Ethereum", EntityType.CRYPTOCURRENCY, ["ETH", "Ether"])

# Commodities
_register_entity("Crude Oil", EntityType.COMMODITY, ["Brent Crude", "WTI", "Petroleum", "Oil", "Crude"])
_register_entity("Gold", EntityType.COMMODITY, ["XAU", "Gold Bullion"])
_register_entity("Silver", EntityType.COMMODITY, ["XAG"])
_register_entity("Natural Gas", EntityType.COMMODITY, ["LNG", "Methane"])
_register_entity("Copper", EntityType.COMMODITY, [])
_register_entity("Uranium", EntityType.COMMODITY, [])
_register_entity("Wheat", EntityType.COMMODITY, ["Grain"])

# Companies
_register_entity("Microsoft", EntityType.COMPANY, ["MSFT"])
_register_entity("Apple Inc.", EntityType.COMPANY, ["Apple", "AAPL"])
_register_entity("Alphabet Inc.", EntityType.COMPANY, ["Google", "Alphabet", "GOOGL"])
_register_entity("Amazon", EntityType.COMPANY, ["AMZN"])
_register_entity("NVIDIA", EntityType.COMPANY, ["Nvidia", "NVDA"])
_register_entity("Meta Platforms", EntityType.COMPANY, ["Meta", "Facebook"])
_register_entity("Tesla", EntityType.COMPANY, ["TSLA"])
_register_entity("Saudi Aramco", EntityType.COMPANY, ["Aramco"], country_code="SA")
_register_entity("TSMC", EntityType.COMPANY, ["Taiwan Semiconductor", "Taiwan Semiconductor Manufacturing Co."], country_code="TW")
_register_entity("OpenAI", EntityType.COMPANY, [])

# Economic Indicators
_register_entity("Consumer Price Index", EntityType.ECONOMIC_INDICATOR, ["CPI", "Core CPI", "Headline Inflation", "Inflation Pressures", "Consumer Price Index"])
_register_entity("Gross Domestic Product", EntityType.ECONOMIC_INDICATOR, ["GDP", "Real GDP"])
_register_entity("Employment and Labor Data", EntityType.ECONOMIC_INDICATOR, ["Unemployment Rate", "Jobless Claims", "Non-Farm Payrolls", "NFP"])
_register_entity("Interest Rates", EntityType.ECONOMIC_INDICATOR, ["Policy Rate", "Benchmark Rate", "Fed Funds Rate", "Interest Rate", "Interest Rates", "Benchmark Interest Rates", "Benchmark Interest Rate"])
_register_entity("Purchasing Managers Index", EntityType.ECONOMIC_INDICATOR, ["PMI", "Manufacturing PMI", "Services PMI"])


def disambiguate_georgia_context(full_text: str) -> Tuple[str, str, str]:
    """Disambiguate Georgia the sovereign nation from Georgia the US state.
    
    Returns (entity_type, country_code, description).
    """
    if re.search(r"\b(?:Atlanta|governor|state legislature|US Senate|county|GA)\b", full_text):
        return (EntityType.LOCATION.value, "US", "US State of Georgia")
    return (EntityType.COUNTRY.value, "GE", "Transcontinental country at the intersection of Eastern Europe and Western Asia")


class EntityNormalizer:
    """Canonicalization engine mapping mentions to authoritative entities."""

    @staticmethod
    def normalize_key(text: str) -> str:
        return normalize_text_key(text)

    @staticmethod
    def lookup(mention: str) -> Optional[NormalizedEntityResult]:
        """Attempt to find an entity in the curated knowledge base."""
        key = normalize_text_key(mention)
        return _ENTITY_KNOWLEDGE_BASE.get(key)

    @staticmethod
    def resolve_or_fallback(
        mention_text: str,
        entity_type: Optional[str] = None,
        country_code: Optional[str] = None,
        description: Optional[str] = None,
    ) -> NormalizedEntityResult:
        """Resolve mention via knowledge base or cleanly construct a normalized entity."""
        match = EntityNormalizer.lookup(mention_text)
        if match:
            return match

        # Fallback to standardized normalized entity
        clean_name = mention_text.strip()
        norm_key = normalize_text_key(clean_name)
        etype = entity_type or EntityType.OTHER.value

        return NormalizedEntityResult(
            canonical_name=clean_name,
            normalized_name=norm_key,
            entity_type=etype,
            country_code=country_code,
            description=description,
            metadata={"source": "extracted_mention"},
        )
