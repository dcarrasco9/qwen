"""Watchlist module for tracking stocks across sectors."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd


class Sector(Enum):
    """Investment sectors."""
    AI_SEMICONDUCTORS = "AI/Semiconductors"
    DEFENSE = "Defense & Aerospace"
    DATA_CENTER = "Data Center Infrastructure"
    NUCLEAR = "Nuclear/Power"
    EVTOL = "eVTOL"
    NETWORKING = "Networking"
    COOLING = "Cooling Infrastructure"
    HYPERSCALER = "Hyperscaler"
    SPACE_SATELLITE = "Space/Satellite"


class RiskLevel(Enum):
    """Risk classification for stocks."""
    HIGH_CONVICTION = "High Conviction"
    MODERATE = "Moderate"
    SPECULATIVE = "Speculative"


@dataclass
class WatchlistStock:
    """A stock in the watchlist with metadata."""
    ticker: str
    name: str
    sector: Sector
    risk_level: RiskLevel
    thesis: str
    themes: list[str] = field(default_factory=list)
    notes: str = ""
    added_date: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return f"WatchlistStock({self.ticker}, {self.sector.value}, {self.risk_level.value})"


# Research-based watchlist for 2026
WATCHLIST_2026: list[WatchlistStock] = [
    # ============================================
    # AI / SEMICONDUCTORS
    # ============================================
    WatchlistStock(
        ticker="NVDA",
        name="Nvidia",
        sector=Sector.AI_SEMICONDUCTORS,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="GPU dominance, Blackwell shipping, Rubin platform H2 2026. ~21% undervalued vs Morningstar FV",
        themes=["AI", "Data Center", "Gaming"],
    ),
    WatchlistStock(
        ticker="AVGO",
        name="Broadcom",
        sector=Sector.AI_SEMICONDUCTORS,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="70-80% custom ASIC market share. Customers: Google, Meta, OpenAI, Anthropic, ByteDance",
        themes=["AI", "Custom Silicon", "Networking"],
    ),
    WatchlistStock(
        ticker="TSM",
        name="Taiwan Semiconductor",
        sector=Sector.AI_SEMICONDUCTORS,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="World's largest foundry, 23% rev growth expected. $140B+ US expansion underway. Geopolitical risk discount",
        themes=["AI", "Foundry", "Geopolitical"],
        notes="Monitor China-Taiwan tensions closely",
    ),
    WatchlistStock(
        ticker="MU",
        name="Micron Technology",
        sector=Sector.AI_SEMICONDUCTORS,
        risk_level=RiskLevel.MODERATE,
        thesis="Morgan Stanley top pick. Most severe DRAM/NAND shortage in 30 years. 48% annual EPS growth expected",
        themes=["AI", "Memory", "HBM"],
    ),
    WatchlistStock(
        ticker="LRCX",
        name="Lam Research",
        sector=Sector.AI_SEMICONDUCTORS,
        risk_level=RiskLevel.MODERATE,
        thesis="BofA top pick. Semiconductor equipment leader for chip manufacturing",
        themes=["Equipment", "Foundry"],
    ),
    WatchlistStock(
        ticker="KLAC",
        name="KLA Corporation",
        sector=Sector.AI_SEMICONDUCTORS,
        risk_level=RiskLevel.MODERATE,
        thesis="BofA top pick. Semiconductor inspection and metrology equipment",
        themes=["Equipment", "Quality Control"],
    ),
    WatchlistStock(
        ticker="ADI",
        name="Analog Devices",
        sector=Sector.AI_SEMICONDUCTORS,
        risk_level=RiskLevel.MODERATE,
        thesis="BofA top pick. Analog/mixed-signal chips for industrial and automotive",
        themes=["Analog", "Industrial", "Automotive"],
    ),
    WatchlistStock(
        ticker="CDNS",
        name="Cadence Design Systems",
        sector=Sector.AI_SEMICONDUCTORS,
        risk_level=RiskLevel.MODERATE,
        thesis="BofA top pick. EDA software essential for chip design",
        themes=["EDA", "Software", "AI Design"],
    ),
    WatchlistStock(
        ticker="AMD",
        name="Advanced Micro Devices",
        sector=Sector.AI_SEMICONDUCTORS,
        risk_level=RiskLevel.MODERATE,
        thesis="MI300X gaining traction. Data center GPU competitor to Nvidia",
        themes=["AI", "Data Center", "Gaming"],
    ),

    # ============================================
    # DEFENSE & AEROSPACE
    # ============================================
    WatchlistStock(
        ticker="AVAV",
        name="AeroVironment",
        sector=Sector.DEFENSE,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="KeyBanc highest conviction pick. Industry-leading margins, deep DoD relationships. Drones, Golden Dome leverage",
        themes=["Drones", "Defense Tech", "Autonomous"],
    ),
    WatchlistStock(
        ticker="KTOS",
        name="Kratos Defense",
        sector=Sector.DEFENSE,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="First-to-market in hypersonics, Collaborative Combat Aircraft program",
        themes=["Hypersonics", "Drones", "Defense Tech"],
    ),
    WatchlistStock(
        ticker="GE",
        name="GE Aerospace",
        sector=Sector.DEFENSE,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="UBS top pick. Commercial + defense engines. Meaningful upside to consensus estimates",
        themes=["Engines", "Commercial Aviation", "Defense"],
    ),
    WatchlistStock(
        ticker="NOC",
        name="Northrop Grumman",
        sector=Sector.DEFENSE,
        risk_level=RiskLevel.MODERATE,
        thesis="B-21 bomber program, space systems, nuclear modernization",
        themes=["Bombers", "Space", "Nuclear"],
    ),
    WatchlistStock(
        ticker="LMT",
        name="Lockheed Martin",
        sector=Sector.DEFENSE,
        risk_level=RiskLevel.MODERATE,
        thesis="F-35 program, missiles, space. Largest US defense contractor",
        themes=["Fighter Jets", "Missiles", "Space"],
    ),
    WatchlistStock(
        ticker="RTX",
        name="RTX Corporation",
        sector=Sector.DEFENSE,
        risk_level=RiskLevel.MODERATE,
        thesis="Diversified defense: Pratt & Whitney engines, Raytheon missiles, Collins avionics",
        themes=["Engines", "Missiles", "Avionics"],
    ),
    WatchlistStock(
        ticker="HWM",
        name="Howmet Aerospace",
        sector=Sector.DEFENSE,
        risk_level=RiskLevel.MODERATE,
        thesis="Aerospace components supplier. Benefits from commercial aviation recovery and defense spending",
        themes=["Components", "Materials", "Defense"],
    ),

    # ============================================
    # DATA CENTER INFRASTRUCTURE - COOLING
    # ============================================
    WatchlistStock(
        ticker="VRT",
        name="Vertiv Holdings",
        sector=Sector.COOLING,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="Default cooling solution for hyperscalers. 70% 3-year rev growth. Deep Nvidia integration for liquid cooling",
        themes=["Cooling", "Power", "Data Center"],
    ),
    WatchlistStock(
        ticker="TT",
        name="Trane Technologies",
        sector=Sector.COOLING,
        risk_level=RiskLevel.MODERATE,
        thesis="Data center HVAC specialist. Critical as AI drives power density higher",
        themes=["HVAC", "Cooling", "Industrial"],
    ),

    # ============================================
    # DATA CENTER INFRASTRUCTURE - NETWORKING
    # ============================================
    WatchlistStock(
        ticker="ANET",
        name="Arista Networks",
        sector=Sector.NETWORKING,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="93% 3-year rev growth. High-speed Ethernet for AI clusters. Primary beneficiary of Ethernet pivot",
        themes=["Networking", "Ethernet", "AI"],
    ),
    WatchlistStock(
        ticker="CLS",
        name="Celestica",
        sector=Sector.NETWORKING,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="Up 230% in 2025. Hyperscaler hardware integration. Manages final stage of hardware assembly",
        themes=["Hardware", "Integration", "Switches"],
    ),
    WatchlistStock(
        ticker="LITE",
        name="Lumentum Holdings",
        sector=Sector.NETWORKING,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="Up 372% in 2025. Optical components for GPU interconnects. Critical for rack-scale AI",
        themes=["Optical", "Lasers", "Interconnects"],
    ),

    # ============================================
    # DATA CENTER INFRASTRUCTURE - POWER
    # ============================================
    WatchlistStock(
        ticker="GEV",
        name="GE Vernova",
        sector=Sector.DATA_CENTER,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="$41-42B 2026 rev guidance, $200B backlog by 2028. Backbone of AI power surge",
        themes=["Power", "Grid", "Renewables"],
    ),
    WatchlistStock(
        ticker="ETN",
        name="Eaton Corporation",
        sector=Sector.DATA_CENTER,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="$9.5B Boyd Thermal acquisition. Positioned for liquid cooling standard",
        themes=["Power", "Electrical", "Cooling"],
    ),
    WatchlistStock(
        ticker="SBGSY",
        name="Schneider Electric",
        sector=Sector.DATA_CENTER,
        risk_level=RiskLevel.MODERATE,
        thesis="Microgrid-in-a-box solutions for on-site data center power generation",
        themes=["Power", "Microgrids", "Infrastructure"],
        notes="ADR - Paris-listed primary",
    ),

    # ============================================
    # HYPERSCALERS
    # ============================================
    WatchlistStock(
        ticker="AMZN",
        name="Amazon",
        sector=Sector.HYPERSCALER,
        risk_level=RiskLevel.MODERATE,
        thesis="AWS acceleration. 2025 capex topped $100B, remains elevated 2026. Custom Trainium chips",
        themes=["Cloud", "AI", "E-commerce"],
    ),
    WatchlistStock(
        ticker="MSFT",
        name="Microsoft",
        sector=Sector.HYPERSCALER,
        risk_level=RiskLevel.MODERATE,
        thesis="Azure cloud leader. OpenAI partnership. Unprecedented data center buildout",
        themes=["Cloud", "AI", "Enterprise"],
    ),
    WatchlistStock(
        ticker="GOOGL",
        name="Alphabet",
        sector=Sector.HYPERSCALER,
        risk_level=RiskLevel.MODERATE,
        thesis="GCP growth accelerating. Custom TPU chips. Gemini AI models",
        themes=["Cloud", "AI", "Search"],
    ),
    WatchlistStock(
        ticker="META",
        name="Meta Platforms",
        sector=Sector.HYPERSCALER,
        risk_level=RiskLevel.MODERATE,
        thesis="Massive AI infrastructure investment. Llama models. Partnering with Oklo for nuclear power",
        themes=["AI", "Social", "Metaverse"],
    ),

    # ============================================
    # NUCLEAR / POWER FOR AI
    # ============================================
    WatchlistStock(
        ticker="CEG",
        name="Constellation Energy",
        sector=Sector.NUCLEAR,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="Largest US nuclear fleet. Microsoft deal for Three Mile Island restart",
        themes=["Nuclear", "Utilities", "Clean Energy"],
    ),
    WatchlistStock(
        ticker="LEU",
        name="Centrus Energy",
        sector=Sector.NUCLEAR,
        risk_level=RiskLevel.HIGH_CONVICTION,
        thesis="ONLY Western HALEU producer. $2.7B DOE contract. Strategic choke point in nuclear fuel cycle",
        themes=["Nuclear Fuel", "HALEU", "Strategic"],
    ),
    WatchlistStock(
        ticker="VST",
        name="Vistra Corp",
        sector=Sector.NUCLEAR,
        risk_level=RiskLevel.MODERATE,
        thesis="20-year, 2,600 MW Meta nuclear PPA. Nuclear + natural gas portfolio",
        themes=["Nuclear", "Utilities", "Data Center Power"],
    ),
    WatchlistStock(
        ticker="CCJ",
        name="Cameco Corporation",
        sector=Sector.NUCLEAR,
        risk_level=RiskLevel.MODERATE,
        thesis="Leading uranium miner. 68.5% 1-year return. Benefits from nuclear renaissance",
        themes=["Uranium", "Mining", "Nuclear"],
    ),
    WatchlistStock(
        ticker="UEC",
        name="Uranium Energy Corp",
        sector=Sector.NUCLEAR,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="US uranium producer. Inventory value rising with spot uranium above $81/lb",
        themes=["Uranium", "Mining", "US Producer"],
    ),
    WatchlistStock(
        ticker="OKLO",
        name="Oklo Inc",
        sector=Sector.NUCLEAR,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="SMR developer. Meta partnership for data center power. Sam Altman backed",
        themes=["SMR", "Nuclear", "Data Center Power"],
    ),
    WatchlistStock(
        ticker="SMR",
        name="NuScale Power",
        sector=Sector.NUCLEAR,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="First NRC-approved SMR design. Pioneering small modular reactor technology",
        themes=["SMR", "Nuclear", "Technology"],
    ),
    WatchlistStock(
        ticker="NNE",
        name="Nano Nuclear Energy",
        sector=Sector.NUCLEAR,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="Micro-reactor developer. High beta to AI sentiment. Up 35%+ YTD through Jan 8",
        themes=["Micro-reactor", "Nuclear", "Portable Power"],
    ),

    # ============================================
    # eVTOL
    # ============================================
    WatchlistStock(
        ticker="JOBY",
        name="Joby Aviation",
        sector=Sector.EVTOL,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="Strongest balance sheet (~$1B liquidity). Toyota backing. 70% FAA Stage 4 complete. Dubai 2026 launch",
        themes=["Air Taxi", "Electric", "Urban Mobility"],
        notes="$13.2B market cap. Best positioned in sector",
    ),
    WatchlistStock(
        ticker="ACHR",
        name="Archer Aviation",
        sector=Sector.EVTOL,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="Stellantis manufacturing partnership. Capital efficient approach. Higher risk/reward vs JOBY",
        themes=["Air Taxi", "Electric", "Urban Mobility"],
        notes="$5.9B market cap. Some short interest concerns",
    ),
    WatchlistStock(
        ticker="EH",
        name="EHang Holdings",
        sector=Sector.EVTOL,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="Already generating revenue in China. Proof of concept for Western peers",
        themes=["Air Taxi", "Electric", "China"],
        notes="ADR - China operations",
    ),

    # ============================================
    # SPACE / SATELLITE
    # ============================================
    WatchlistStock(
        ticker="ASTS",
        name="AST SpaceMobile",
        sector=Sector.SPACE_SATELLITE,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="Direct-to-cell satellite connectivity. BlueBird 6 launched Dec 2025 (largest commercial LEO array). "
               "AT&T + Verizon partnerships, 50/50 revenue split. $1B+ contracted revenue. "
               "45-60 satellites planned by end 2026 for nationwide US coverage. Beta service H1 2026.",
        themes=["Satellite", "5G", "Telecom", "Space", "Direct-to-Cell"],
        notes="Binary outcome: ~$270M 2026E rev at 100x sales. Competes with Starlink/T-Mobile. "
              "BofA PT $100, Scotiabank PT $45. High dilution risk but $3.2B liquidity. "
              "Key catalyst: launch cadence execution and commercial service activation.",
    ),
    WatchlistStock(
        ticker="RKLB",
        name="Rocket Lab USA",
        sector=Sector.SPACE_SATELLITE,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="Leading small satellite launch provider. Electron rocket with proven track record. "
               "Neutron medium-lift rocket in development. Vertically integrated with spacecraft components.",
        themes=["Space", "Launch", "Satellite", "Defense"],
        notes="Competes with SpaceX for small/medium payloads. Growing backlog.",
    ),
    WatchlistStock(
        ticker="ONDS",
        name="Ondas Holdings",
        sector=Sector.NETWORKING,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="Industrial wireless networking and autonomous drone solutions. "
               "FullMAX platform for mission-critical IoT. American Robotics subsidiary for drone automation.",
        themes=["Drones", "Industrial IoT", "Wireless", "Automation"],
        notes="Small cap, early stage revenue growth.",
    ),
    WatchlistStock(
        ticker="SSYS",
        name="Stratasys",
        sector=Sector.DATA_CENTER,
        risk_level=RiskLevel.SPECULATIVE,
        thesis="3D printing and additive manufacturing leader. Industrial and healthcare applications. "
               "Potential beneficiary of reshoring and advanced manufacturing trends.",
        themes=["3D Printing", "Manufacturing", "Industrial", "Healthcare"],
        notes="Consolidation in 3D printing space.",
    ),
]


class Watchlist:
    """Manages a collection of watchlist stocks with filtering and analysis."""

    def __init__(self, stocks: list[WatchlistStock] | None = None):
        """Initialize watchlist with stocks. Defaults to 2026 research watchlist."""
        self.stocks = stocks if stocks is not None else WATCHLIST_2026.copy()

    @property
    def tickers(self) -> list[str]:
        """Get list of all tickers."""
        return [s.ticker for s in self.stocks]

    def filter_by_sector(self, sector: Sector) -> "Watchlist":
        """Return new Watchlist filtered by sector."""
        filtered = [s for s in self.stocks if s.sector == sector]
        return Watchlist(filtered)

    def filter_by_risk(self, risk_level: RiskLevel) -> "Watchlist":
        """Return new Watchlist filtered by risk level."""
        filtered = [s for s in self.stocks if s.risk_level == risk_level]
        return Watchlist(filtered)

    def filter_by_theme(self, theme: str) -> "Watchlist":
        """Return new Watchlist filtered by theme (case-insensitive)."""
        theme_lower = theme.lower()
        filtered = [s for s in self.stocks if any(theme_lower in t.lower() for t in s.themes)]
        return Watchlist(filtered)

    def get_stock(self, ticker: str) -> Optional[WatchlistStock]:
        """Get a specific stock by ticker."""
        ticker_upper = ticker.upper()
        for stock in self.stocks:
            if stock.ticker == ticker_upper:
                return stock
        return None

    def to_dataframe(self) -> pd.DataFrame:
        """Convert watchlist to pandas DataFrame."""
        data = []
        for s in self.stocks:
            data.append({
                "Ticker": s.ticker,
                "Name": s.name,
                "Sector": s.sector.value,
                "Risk": s.risk_level.value,
                "Thesis": s.thesis,
                "Themes": ", ".join(s.themes),
            })
        return pd.DataFrame(data)

    def fetch_prices(self, period: str = "1mo") -> pd.DataFrame:
        """
        Fetch current prices and returns for watchlist stocks.

        Args:
            period: yfinance period string ('1d', '5d', '1mo', '3mo', '6mo', '1y')

        Returns:
            DataFrame with price data and returns
        """
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("yfinance required for price fetching. Install with: pip install yfinance")

        tickers_str = " ".join(self.tickers)
        data = yf.download(tickers_str, period=period, progress=False, group_by='ticker')

        results = []
        for stock in self.stocks:
            try:
                if len(self.stocks) == 1:
                    ticker_data = data
                else:
                    ticker_data = data[stock.ticker]

                if ticker_data.empty:
                    continue

                current_price = ticker_data['Close'].iloc[-1]
                start_price = ticker_data['Close'].iloc[0]
                period_return = (current_price - start_price) / start_price * 100
                high = ticker_data['High'].max()
                low = ticker_data['Low'].min()
                avg_volume = ticker_data['Volume'].mean()

                results.append({
                    "Ticker": stock.ticker,
                    "Name": stock.name,
                    "Sector": stock.sector.value,
                    "Risk": stock.risk_level.value,
                    "Price": round(current_price, 2),
                    f"Return ({period})": round(period_return, 2),
                    "High": round(high, 2),
                    "Low": round(low, 2),
                    "Avg Volume": int(avg_volume),
                })
            except Exception:
                continue

        return pd.DataFrame(results)

    def summary_by_sector(self) -> pd.DataFrame:
        """Get count of stocks by sector."""
        sector_counts = {}
        for stock in self.stocks:
            sector = stock.sector.value
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        return pd.DataFrame([
            {"Sector": k, "Count": v}
            for k, v in sorted(sector_counts.items(), key=lambda x: -x[1])
        ])

    def summary_by_risk(self) -> pd.DataFrame:
        """Get count of stocks by risk level."""
        risk_counts = {}
        for stock in self.stocks:
            risk = stock.risk_level.value
            risk_counts[risk] = risk_counts.get(risk, 0) + 1

        return pd.DataFrame([
            {"Risk Level": k, "Count": v}
            for k, v in risk_counts.items()
        ])

    def high_conviction_picks(self) -> "Watchlist":
        """Get high conviction stocks only."""
        return self.filter_by_risk(RiskLevel.HIGH_CONVICTION)

    def speculative_picks(self) -> "Watchlist":
        """Get speculative stocks only."""
        return self.filter_by_risk(RiskLevel.SPECULATIVE)

    def __len__(self) -> int:
        return len(self.stocks)

    def __iter__(self):
        return iter(self.stocks)

    def __repr__(self) -> str:
        return f"Watchlist({len(self.stocks)} stocks)"

    def display(self) -> None:
        """Pretty print the watchlist."""
        df = self.to_dataframe()
        print(df.to_string(index=False))


def get_watchlist() -> Watchlist:
    """Get the default 2026 research watchlist."""
    return Watchlist()


def get_ai_plays() -> Watchlist:
    """Get AI/semiconductor focused watchlist."""
    wl = Watchlist()
    return wl.filter_by_theme("AI")


def get_defense_plays() -> Watchlist:
    """Get defense sector watchlist."""
    return Watchlist().filter_by_sector(Sector.DEFENSE)


def get_infrastructure_plays() -> Watchlist:
    """Get data center infrastructure watchlist."""
    wl = Watchlist()
    infra_sectors = {Sector.DATA_CENTER, Sector.COOLING, Sector.NETWORKING}
    filtered = [s for s in wl.stocks if s.sector in infra_sectors]
    return Watchlist(filtered)


def get_nuclear_plays() -> Watchlist:
    """Get nuclear/power sector watchlist."""
    return Watchlist().filter_by_sector(Sector.NUCLEAR)


def get_evtol_plays() -> Watchlist:
    """Get eVTOL sector watchlist."""
    return Watchlist().filter_by_sector(Sector.EVTOL)


def get_space_plays() -> Watchlist:
    """Get space/satellite sector watchlist."""
    return Watchlist().filter_by_sector(Sector.SPACE_SATELLITE)
