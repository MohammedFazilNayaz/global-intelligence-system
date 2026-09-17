import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Union

from backend.app.market.base import BaseMarketDataProvider
from backend.app.schemas.market import MarketObservationCreate


class DeterministicMarketProvider(BaseMarketDataProvider):
    """
    Deterministic market data provider for benchmarks, verification corpora, and test suites.
    Produces mathematically exact, non-hallucinated OHLCV bars.
    Supports controlled anomalies (duplicates, gaps, out-of-order) for audit validation.
    """

    def __init__(self, provider_name: str = "DeterministicFeed"):
        self._name = provider_name
        self._stored_bars: Dict[str, List[MarketObservationCreate]] = {}

    @property
    def provider_name(self) -> str:
        return self._name

    def supported_symbols(self) -> List[str]:
        return [
            "BTC-USD", "ETH-USD",
            "SPX", "NDX", "DAX", "FTSE", "N225",
            "EUR/USD", "GBP/USD", "USD/JPY", "USD/INR",
            "BRENT", "WTI", "GOLD",
            "US2Y", "US10Y",
        ]

    def register_bars(self, symbol: str, bars: List[MarketObservationCreate]) -> None:
        """Register custom bars for a symbol."""
        if symbol not in self._stored_bars:
            self._stored_bars[symbol] = []
        self._stored_bars[symbol].extend(bars)

    def fetch_latest_bar(
        self, symbol: str, interval: str = "1m"
    ) -> Optional[MarketObservationCreate]:
        bars = self._stored_bars.get(symbol, [])
        matching = [b for b in bars if b.interval == interval]
        if matching:
            return sorted(matching, key=lambda x: x.timestamp)[-1]
        return None

    def fetch_historical_bars(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[MarketObservationCreate]:
        bars = self._stored_bars.get(symbol, [])
        st = self.normalize_timestamp(start_time)
        et = self.normalize_timestamp(end_time)

        res = [
            b for b in bars
            if b.interval == interval and st <= self.normalize_timestamp(b.timestamp) <= et
        ]
        return res

    def generate_series(
        self,
        symbol: str,
        asset_id: uuid.UUID,
        start_time: datetime,
        count: int,
        interval: str = "1m",
        start_price: float = 100.0,
        price_step: float = 0.5,
        base_volume: float = 10.0,
    ) -> List[MarketObservationCreate]:
        """Generate a deterministic sequence of regular bars."""
        step_seconds = {
            "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400
        }.get(interval, 60)

        bars: List[MarketObservationCreate] = []
        current_time = self.normalize_timestamp(start_time)
        curr_p = start_price

        for i in range(count):
            open_p = round(curr_p, 4)
            close_p = round(curr_p + price_step, 4)
            high_p = round(max(open_p, close_p) + abs(price_step) * 0.2, 4)
            low_p = round(min(open_p, close_p) - abs(price_step) * 0.2, 4)
            vol = round(base_volume + (i * 0.5), 2)

            obs = MarketObservationCreate(
                market_asset_id=asset_id,
                timestamp=current_time,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=vol,
                source=self.provider_name,
                interval=interval,
                metadata={"synthetic": False, "index": i, "provider": self.provider_name},
            )
            bars.append(obs)
            curr_p = close_p
            current_time += timedelta(seconds=step_seconds)

        self.register_bars(symbol, bars)
        return bars


import time
import httpx


class CryptoMarketProvider(BaseMarketDataProvider):
    """
    Live market data provider for cryptocurrency venues (Binance & Coinbase).
    Reuses the robust rate-limit backoff, retry, and Kline parsing architecture
    from the BTC trading infrastructure (bitcoin trade/backend/app/data/providers/binance.py).
    Does NOT require live API credentials for public market data.
    """
    EXCHANGE_NAME = "binance_spot"
    BINANCE_BASE_URL = "https://api.binance.com"
    COINBASE_BASE_URL = "https://api.exchange.coinbase.com"

    SYMBOL_MAP_BINANCE = {
        "BTC-USD": "BTCUSDT",
        "BTC": "BTCUSDT",
        "BTCUSDT": "BTCUSDT",
        "ETH-USD": "ETHUSDT",
        "ETH": "ETHUSDT",
        "ETHUSDT": "ETHUSDT",
    }

    SYMBOL_MAP_COINBASE = {
        "BTC-USD": "BTC-USD",
        "BTC": "BTC-USD",
        "BTCUSDT": "BTC-USD",
        "ETH-USD": "ETH-USD",
        "ETH": "ETH-USD",
        "ETHUSDT": "ETH-USD",
    }

    INTERVAL_MAP_BINANCE = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
    }

    INTERVAL_SECONDS_COINBASE = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "1d": 86400,
    }

    def __init__(
        self,
        provider_name: str = "Binance",
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        self._name = provider_name
        self.timeout = timeout
        self.max_retries = max_retries
        self._headers = {"User-Agent": "GlobalIntelligencePlatform/0.6.1"}

    @property
    def provider_name(self) -> str:
        return self._name

    def supported_symbols(self) -> List[str]:
        return ["BTC-USD", "ETH-USD"]

    def fetch_latest_bar(
        self, symbol: str, interval: str = "1m"
    ) -> Optional[MarketObservationCreate]:
        # 1. Try CoinGecko API for real spot prices
        try:
            coin_id = "bitcoin" if "BTC" in symbol.upper() else ("ethereum" if "ETH" in symbol.upper() else None)
            if coin_id:
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_vol=true&include_last_updated_at=true"
                with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        data = resp.json().get(coin_id, {})
                        price = float(data.get("usd", 0))
                        vol = float(data.get("usd_24h_vol", 0))
                        ts_sec = data.get("last_updated_at", time.time())
                        dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
                        if price > 0:
                            return MarketObservationCreate(
                                market_asset_id=None,
                                timestamp=dt,
                                open=price,
                                high=price,
                                low=price,
                                close=price,
                                volume=vol,
                                source="CoinGecko",
                                interval=interval,
                                metadata_={
                                    "provider": "CoinGecko",
                                    "canonical_symbol": symbol,
                                    "is_live": True,
                                },
                            )
        except Exception:
            pass

        # 2. Fallback to historical bars (Binance / Coinbase)
        bars = self.fetch_historical_bars(symbol=symbol, interval=interval, limit=2)
        if bars:
            return bars[-1]
        return None

    def fetch_historical_bars(
        self,
        symbol: str,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[MarketObservationCreate]:
        """
        Fetch real historical OHLCV candles from Binance public API with fallback to Coinbase.
        Preserves provenance: source, request_timestamp, venue, and raw attributes.
        """
        mapped_binance = self.SYMBOL_MAP_BINANCE.get(symbol.upper(), symbol.upper().replace("-", ""))
        params: Dict[str, Any] = {
            "symbol": mapped_binance,
            "interval": self.INTERVAL_MAP_BINANCE.get(interval, "1h"),
            "limit": min(limit, 1000),
        }
        if start_time:
            st = self.normalize_timestamp(start_time)
            params["startTime"] = int(st.timestamp() * 1000)
        if end_time:
            et = self.normalize_timestamp(end_time)
            params["endTime"] = int(et.timestamp() * 1000)

        # 1. Try Binance
        backoff = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                req_ts = datetime.now(timezone.utc).isoformat()
                with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
                    resp = client.get(f"{self.BINANCE_BASE_URL}/api/v3/klines", params=params)
                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("Retry-After", int(backoff)))
                        time.sleep(retry_after)
                        backoff *= 2
                        continue
                    if resp.status_code == 418:
                        time.sleep(60)
                        continue
                    if resp.status_code == 200:
                        data = resp.json()
                        bars: List[MarketObservationCreate] = []
                        for row in data:
                            dt = datetime.fromtimestamp(row[0] / 1000.0, tz=timezone.utc)
                            obs = MarketObservationCreate(
                                market_asset_id=None,
                                timestamp=dt,
                                open=float(row[1]),
                                high=float(row[2]),
                                low=float(row[3]),
                                close=float(row[4]),
                                volume=float(row[5]),
                                source=self.provider_name,
                                interval=interval,
                                metadata_={
                                    "provider": self.provider_name,
                                    "venue": "binance",
                                    "canonical_symbol": symbol,
                                    "raw_symbol": mapped_binance,
                                    "request_timestamp": req_ts,
                                    "open_time_ms": int(row[0]),
                                    "close_time_ms": int(row[6]),
                                    "trades_count": int(row[8]),
                                    "is_live": True,
                                },
                            )
                            bars.append(obs)
                        return bars
            except Exception:
                if attempt == self.max_retries:
                    break
                time.sleep(backoff)
                backoff *= 2

        # 2. Fallback to Coinbase
        mapped_cb = self.SYMBOL_MAP_COINBASE.get(symbol.upper(), symbol.upper())
        cb_granularity = self.INTERVAL_SECONDS_COINBASE.get(interval, 3600)
        cb_params: Dict[str, Any] = {"granularity": cb_granularity}
        if start_time:
            cb_params["start"] = self.normalize_timestamp(start_time).isoformat()
        if end_time:
            cb_params["end"] = self.normalize_timestamp(end_time).isoformat()

        try:
            req_ts = datetime.now(timezone.utc).isoformat()
            with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
                cb_resp = client.get(
                    f"{self.COINBASE_BASE_URL}/products/{mapped_cb}/candles",
                    params=cb_params,
                )
                if cb_resp.status_code == 200:
                    cb_data = cb_resp.json()
                    # Coinbase format: [time, low, high, open, close, volume]
                    bars = []
                    for row in reversed(cb_data[:limit]):
                        dt = datetime.fromtimestamp(row[0], tz=timezone.utc)
                        obs = MarketObservationCreate(
                            market_asset_id=None,
                            timestamp=dt,
                            open=float(row[3]),
                            high=float(row[2]),
                            low=float(row[1]),
                            close=float(row[4]),
                            volume=float(row[5]),
                            source="CoinbasePublicAPI",
                            interval=interval,
                            metadata_={
                                "provider": "CoinbasePublicAPI",
                                "venue": "coinbase",
                                "canonical_symbol": symbol,
                                "raw_symbol": mapped_cb,
                                "request_timestamp": req_ts,
                                "open_time_sec": int(row[0]),
                                "is_live": True,
                            },
                        )
                        bars.append(obs)
                    return bars
        except Exception:
            pass

        return []


import xml.etree.ElementTree as ET


def _fetch_yahoo_chart(
    canonical_symbol: str,
    mapped_ticker: str,
    interval: str = "1d",
    range_str: str = "5d",
    timeout: float = 10.0,
    provider_name: str = "YahooFinance",
) -> List[MarketObservationCreate]:
    """Fetch real OHLCV chart bars from public Yahoo Finance API with resilient fallback."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{mapped_ticker}?interval={interval}&range={range_str}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        with httpx.Client(timeout=timeout, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
            result_list = data.get("chart", {}).get("result", [])
            if not result_list:
                return []
            result = result_list[0]
            timestamps = result.get("timestamp", [])
            indicators = result.get("indicators", {}).get("quote", [{}])[0]
            opens = indicators.get("open", [])
            highs = indicators.get("high", [])
            lows = indicators.get("low", [])
            closes = indicators.get("close", [])
            volumes = indicators.get("volume", [])

            bars: List[MarketObservationCreate] = []
            for i, ts in enumerate(timestamps):
                c = closes[i] if i < len(closes) else None
                if c is None:
                    continue
                o = opens[i] if i < len(opens) and opens[i] is not None else c
                h = highs[i] if i < len(highs) and highs[i] is not None else c
                l = lows[i] if i < len(lows) and lows[i] is not None else c
                v = float(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0.0

                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                obs = MarketObservationCreate(
                    market_asset_id=None,
                    timestamp=dt,
                    open=round(float(o), 4),
                    high=round(float(h), 4),
                    low=round(float(l), 4),
                    close=round(float(c), 4),
                    volume=v,
                    source=provider_name,
                    interval=interval,
                    metadata_={
                        "provider": provider_name,
                        "canonical_symbol": canonical_symbol,
                        "raw_symbol": mapped_ticker,
                        "is_live": True,
                    },
                )
                bars.append(obs)
            return bars
    except Exception:
        return []


class EquityMarketProvider(BaseMarketDataProvider):
    """Live market data provider for global equity indices (SPX, NDX, DAX, FTSE, N225)."""

    SYMBOL_MAP = {
        "SPX": "^GSPC",
        "NDX": "^IXIC",
        "DAX": "^GDAXI",
        "FTSE": "^FTSE",
        "N225": "^N225",
    }

    def __init__(self, provider_name: str = "EquityIndexFeed", timeout: float = 10.0):
        self._name = provider_name
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return self._name

    def supported_symbols(self) -> List[str]:
        return ["SPX", "NDX", "DAX", "FTSE", "N225"]

    def fetch_latest_bar(
        self, symbol: str, interval: str = "1d"
    ) -> Optional[MarketObservationCreate]:
        mapped = self.SYMBOL_MAP.get(symbol.upper())
        if not mapped:
            return None
        bars = _fetch_yahoo_chart(
            canonical_symbol=symbol,
            mapped_ticker=mapped,
            interval=interval,
            range_str="5d",
            timeout=self.timeout,
            provider_name=self.provider_name,
        )
        return bars[-1] if bars else None

    def fetch_historical_bars(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[MarketObservationCreate]:
        mapped = self.SYMBOL_MAP.get(symbol.upper())
        if not mapped:
            return []
        bars = _fetch_yahoo_chart(
            canonical_symbol=symbol,
            mapped_ticker=mapped,
            interval=interval,
            range_str="1mo",
            timeout=self.timeout,
            provider_name=self.provider_name,
        )
        st = self.normalize_timestamp(start_time)
        et = self.normalize_timestamp(end_time)
        return [b for b in bars if st <= self.normalize_timestamp(b.timestamp) <= et]


class ForexMarketProvider(BaseMarketDataProvider):
    """Live market data provider for foreign exchange pairs (EUR/USD, GBP/USD, USD/JPY, USD/INR).
    Uses official European Central Bank reference rates with Yahoo Finance real-time fallback.
    """

    YAHOO_MAP = {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "JPY=X",
        "USD/INR": "INR=X",
    }

    def __init__(self, provider_name: str = "ECBReferenceRates", timeout: float = 10.0):
        self._name = provider_name
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return self._name

    def supported_symbols(self) -> List[str]:
        return ["EUR/USD", "GBP/USD", "USD/JPY", "USD/INR"]

    def fetch_latest_bar(
        self, symbol: str, interval: str = "1d"
    ) -> Optional[MarketObservationCreate]:
        sym = symbol.upper()
        # 1. Try ECB Official Daily Reference Rates XML
        try:
            url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    rates = {}
                    pub_date = None
                    for cube in root.iter():
                        t_val = cube.attrib.get("time")
                        if t_val:
                            pub_date = datetime.strptime(t_val, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        curr = cube.attrib.get("currency")
                        rate_val = cube.attrib.get("rate")
                        if curr and rate_val:
                            rates[curr] = float(rate_val)

                    dt = pub_date or datetime.now(timezone.utc)
                    calc_price = None

                    if sym == "EUR/USD" and "USD" in rates:
                        calc_price = rates["USD"]
                    elif sym == "GBP/USD" and "USD" in rates and "GBP" in rates:
                        calc_price = round(rates["USD"] / rates["GBP"], 4)
                    elif sym == "USD/JPY" and "USD" in rates and "JPY" in rates:
                        calc_price = round(rates["JPY"] / rates["USD"], 4)
                    elif sym == "USD/INR" and "USD" in rates and "INR" in rates:
                        calc_price = round(rates["INR"] / rates["USD"], 4)

                    if calc_price is not None:
                        return MarketObservationCreate(
                            market_asset_id=None,
                            timestamp=dt,
                            open=calc_price,
                            high=calc_price,
                            low=calc_price,
                            close=calc_price,
                            volume=0.0,
                            source="ECB_Reference",
                            interval=interval,
                            metadata_={
                                "provider": "European Central Bank",
                                "canonical_symbol": symbol,
                                "is_live": True,
                            },
                        )
        except Exception:
            pass

        # 2. Fallback to Yahoo Finance FX quotes
        mapped = self.YAHOO_MAP.get(sym)
        if mapped:
            bars = _fetch_yahoo_chart(
                canonical_symbol=symbol,
                mapped_ticker=mapped,
                interval=interval,
                range_str="5d",
                timeout=self.timeout,
                provider_name="YahooFinance_FX",
            )
            if bars:
                return bars[-1]

        return None

    def fetch_historical_bars(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[MarketObservationCreate]:
        mapped = self.YAHOO_MAP.get(symbol.upper())
        if not mapped:
            return []
        bars = _fetch_yahoo_chart(
            canonical_symbol=symbol,
            mapped_ticker=mapped,
            interval=interval,
            range_str="1mo",
            timeout=self.timeout,
            provider_name="YahooFinance_FX",
        )
        st = self.normalize_timestamp(start_time)
        et = self.normalize_timestamp(end_time)
        return [b for b in bars if st <= self.normalize_timestamp(b.timestamp) <= et]


class CommodityMarketProvider(BaseMarketDataProvider):
    """Live market data provider for strategic energy and precious metals (BRENT, WTI, GOLD)."""

    SYMBOL_MAP = {
        "BRENT": "BZ=F",
        "WTI": "CL=F",
        "GOLD": "GC=F",
    }

    def __init__(self, provider_name: str = "CommodityFeed", timeout: float = 10.0):
        self._name = provider_name
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return self._name

    def supported_symbols(self) -> List[str]:
        return ["BRENT", "WTI", "GOLD"]

    def fetch_latest_bar(
        self, symbol: str, interval: str = "1d"
    ) -> Optional[MarketObservationCreate]:
        mapped = self.SYMBOL_MAP.get(symbol.upper())
        if not mapped:
            return None
        bars = _fetch_yahoo_chart(
            canonical_symbol=symbol,
            mapped_ticker=mapped,
            interval=interval,
            range_str="5d",
            timeout=self.timeout,
            provider_name=self.provider_name,
        )
        return bars[-1] if bars else None

    def fetch_historical_bars(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[MarketObservationCreate]:
        mapped = self.SYMBOL_MAP.get(symbol.upper())
        if not mapped:
            return []
        bars = _fetch_yahoo_chart(
            canonical_symbol=symbol,
            mapped_ticker=mapped,
            interval=interval,
            range_str="1mo",
            timeout=self.timeout,
            provider_name=self.provider_name,
        )
        st = self.normalize_timestamp(start_time)
        et = self.normalize_timestamp(end_time)
        return [b for b in bars if st <= self.normalize_timestamp(b.timestamp) <= et]


class RatesMarketProvider(BaseMarketDataProvider):
    """Live market data provider for Sovereign Benchmark Yields (US 2Y, US 10Y).
    Uses official US Department of the Treasury daily yield curve XML with Yahoo Finance fallback.
    """

    def __init__(self, provider_name: str = "USTreasuryYields", timeout: float = 10.0):
        self._name = provider_name
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return self._name

    def supported_symbols(self) -> List[str]:
        return ["US2Y", "US10Y"]

    def fetch_latest_bar(
        self, symbol: str, interval: str = "1d"
    ) -> Optional[MarketObservationCreate]:
        sym = symbol.upper()
        if sym not in self.supported_symbols():
            return None
        # 1. Try US Department of the Treasury Daily Yield XML
        try:
            url = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=2024"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            with httpx.Client(timeout=self.timeout, headers=headers) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    ns = {"d": "http://schemas.microsoft.com/ado/2007/08/dataservices", "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"}
                    entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
                    if entries:
                        latest = entries[-1]
                        tag = "BC_2YEAR" if sym == "US2Y" else "BC_10YEAR"
                        el = latest.find(f".//d:{tag}", ns)
                        date_el = latest.find(".//d:NEW_DATE", ns)
                        if el is not None and el.text:
                            yield_val = float(el.text)
                            dt = datetime.now(timezone.utc)
                            if date_el is not None and date_el.text:
                                try:
                                    dt = datetime.fromisoformat(date_el.text.replace("Z", "+00:00"))
                                except Exception:
                                    pass

                            return MarketObservationCreate(
                                market_asset_id=None,
                                timestamp=dt,
                                open=yield_val,
                                high=yield_val,
                                low=yield_val,
                                close=yield_val,
                                volume=0.0,
                                source="US_Treasury",
                                interval=interval,
                                metadata_={
                                    "provider": "US Department of the Treasury",
                                    "canonical_symbol": symbol,
                                    "is_live": True,
                                },
                            )
        except Exception:
            pass

        # 2. Fallback to Yahoo Finance Treasury note yields (^TNX is 10Y yield * 10)
        mapped = "^IRX" if sym == "US2Y" else "^TNX"
        bars = _fetch_yahoo_chart(
            canonical_symbol=symbol,
            mapped_ticker=mapped,
            interval=interval,
            range_str="5d",
            timeout=self.timeout,
            provider_name="YahooFinance_Yields",
        )
        if bars:
            latest_bar = bars[-1]
            if sym == "US10Y" and latest_bar.close > 20.0:
                # Yahoo ^TNX is quoted as 10x yield (e.g. 45.8 = 4.58%)
                latest_bar.close = round(latest_bar.close / 10.0, 4)
                latest_bar.open = round(latest_bar.open / 10.0, 4)
                latest_bar.high = round(latest_bar.high / 10.0, 4)
                latest_bar.low = round(latest_bar.low / 10.0, 4)
            return latest_bar

        return None

    def fetch_historical_bars(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[MarketObservationCreate]:
        if symbol.upper() not in self.supported_symbols():
            return []
        mapped = "^IRX" if symbol.upper() == "US2Y" else "^TNX"
        bars = _fetch_yahoo_chart(
            canonical_symbol=symbol,
            mapped_ticker=mapped,
            interval=interval,
            range_str="1mo",
            timeout=self.timeout,
            provider_name="YahooFinance_Yields",
        )
        st = self.normalize_timestamp(start_time)
        et = self.normalize_timestamp(end_time)
        res = []
        for b in bars:
            if st <= self.normalize_timestamp(b.timestamp) <= et:
                if symbol.upper() == "US10Y" and b.close > 20.0:
                    b.close = round(b.close / 10.0, 4)
                    b.open = round(b.open / 10.0, 4)
                    b.high = round(b.high / 10.0, 4)
                    b.low = round(b.low / 10.0, 4)
                res.append(b)
        return res
