# BTC QUANT PRO Project Ares

An advanced, real-time Bitcoin quantitative research terminal and dashboard. This project bridges raw exchange data with rigorous quantitative mathematics, completely built from scratch without relying on high-level machine learning libraries for the core logic.

🔬 Core Mathematical Models
This terminal implements institutional-grade quantitative models directly using `numpy` and `scipy`:

* Volatility Forecasting: GARCH(1,1) model using Maximum Likelihood Estimation (MLE) to forecast conditional volatility.
* Regime Detection: 2-State Hidden Markov Model (HMM) fitted via the Baum-Welch EM algorithm to classify high-volatility (trending) vs. low-volatility (ranging) environments.
* Signal Filtering: State-Space Kalman Filter for noise reduction and price velocity tracking.
* Options Pricing: Custom Black-Scholes engine calculating Greeks (Delta, Gamma, Vega, Theta) and an implied volatility solver using the bisection method.
* Market Microstructure: Volume-Synchronized Probability of Informed Trading (VPIN) and Cumulative Volume Delta (CVD) tracking for order flow toxicity.
* Time Series Analysis: Hurst Exponent (R/S Analysis) and Bipower Variation (BNS Jump Test) for structural market analysis.

📡 Live Data Infrastructure
Pulls and processes real-time data using asynchronous REST and WebSockets:
* Binance Futures: Order book depth, taker flow, open interest, and funding rates.
* Deribit Options: Full options chain data for Max Pain and Gamma Exposure (GEX) surface calculations.
* Macro/Sentiment: CoinGecko (BTC Dominance) and Alternative.me (Fear & Greed Index).

🚀 Installation and Usage

1. Clone the repository:
   bash
   git clone [https://github.com/tarun142006/bitcoinalgo.git](https://github.com/tarun142006/bitcoinalgo.git)
   cd bitcoinalgo
