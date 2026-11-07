# Portfolio Optimization by Khim (v2.4 Institutional Edition)

> **Modern Portfolio Theory (Markowitz 1952 & Merton 1972) & Institutional Asset Allocation Workbench for the Vietnam Stock Market**

[![Live Demo](https://img.shields.io/badge/Live_Demo-Render_Cloud-2563eb?style=for-the-badge)](https://portfolio-optimization-by-khim.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

---

## 1. Overview

**Portfolio Optimization by Khim** is a quantitative asset allocation and portfolio management platform built on the rigorous mathematical foundations of **Harry Markowitz (1952)**, **Robert Merton (1972)**, and **Bodie, Kane, & Marcus (2024)**, tailored specifically for institutional fund management in the **Vietnam Equity Market (HOSE / HNX / UPCoM)**.

### Key Institutional Capabilities
- **Analytical & Quadratic Programming Solvers:**
  - Closed-form **Merton (1972)** matrix algebra ($\mathbf{A}, \mathbf{B}, \mathbf{C}, \mathbf{D}$ scalars and $\boldsymbol{\Sigma}^{-1}$) for unconstrained portfolios.
  - Constrained **Quadratic Programming (SLSQP)** for long-only and box-constrained institutional mandates.
- **Circular 98/2020/TT-BTC Compliance & Weight Bounds:**
  - 1-click preset enforcing the **20% maximum single-stock NAV concentration limit** for Vietnamese open-ended public funds, plus customizable floor/ceiling bounds ($w_{\min} \le w_i \le w_{\max}$) with an automatic mathematical feasibility guard.
- **Tactical Cash & Risk-Free Asset Management ($R_f$):**
  - Switch between **Academic Utility Mode** ($y^* = \frac{E(R_p) - R_f}{A \cdot \sigma_p^2}$) and **Mandated Cash Buffer Mode** (fixed liquidity reserve from 0% to 50% NAV).
- **Institutional Benchmark Scorecard (`VN-Index` & `VN30`):**
  - Real-time relative performance evaluation: **Portfolio Beta ($\beta$)**, **Jensen's Alpha ($\alpha$)**, **Tracking Error ($TE$)**, **Information Ratio ($IR$)**, **Active Return**, and normalized **Cumulative Wealth Index (Base = 100)**.
- **Tail-Risk & Historical Crisis Stress Testing (`VaR` & `CVaR`):**
  - 1-Day and 1-Month (21d) **Value at Risk (VaR 95%/99%)**, **Conditional VaR (Expected Shortfall)**, and **Maximum Historical Drawdown (MDD)**.
  - Simulates NAV impact across **4 historical Vietnamese market shocks**: Covid-19 Crash (03/2020: `-33.5%`), Bond & Rate Hike Cycle (2022: `-34.1%`), FX & SBV T-Bill Issuance (04/2024: `-8.5%`), and Risk Committee Standard Shock (`-15.0%`).
- **Round-Lot 100 Execution & 6-Sheet Institutional Excel Reporting:**
  - Automatically sizes orders in multiples of **100 shares** (HOSE/HNX board lot rule), accounts for brokerage fee (`0.15%`) and sell tax (`0.10%`), and exports a comprehensive 6-sheet Excel report.

---

## 2. Project Structure

```text
textbook_mvo/
├── app.py                        # FastAPI server & REST API endpoints
├── requirements.txt              # Cloud deployment dependencies
├── render.yaml                   # Render Infrastructure-as-Code specification
├── engine/
│   ├── textbook_math.py          # Merton (1972) matrix algebra & Bounded QP solvers
│   ├── benchmark_engine.py       # VN-Index / VN30 Benchmark & VaR Stress Testing engine
│   ├── hayinsights_client.py     # Live Vietnam equity market data connector (150+ tickers)
│   ├── risk_profiler.py          # Investor risk aversion (A) calibration engine
│   ├── data_loader.py            # Excel / CSV parser & fallback market calibration
│   ├── template_generator.py     # Downloadable Excel input templates
│   └── excel_exporter.py         # 6-Sheet institutional Excel workbook generator
├── static/
│   ├── index.html                # Linear / Swiss Minimalist Single-Canvas UI
│   ├── styles.css                # Light & Dark mode design tokens
│   └── textbook_mvo.js           # Interactive Plotly analytics & state engine
└── tests/
    └── test_textbook_engine.py   # 9 automated quantitative & contract test suites
```

---

## 3. Local Development & Testing

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment variable (optional for live HayInsights API)
# Create a .env file in the root directory:
# HAYINSIGHTS_API_KEY=your_api_key_here

# 3. Run the automated verification suite (9 test suites)
python tests/test_textbook_engine.py

# 4. Launch the development server
python -m uvicorn app:app --host 127.0.0.1 --port 8005 --reload
```

---

## 4. Cloud Deployment (Render.com)

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
- **Health Check Path:** `/healthz`
- **Environment Variables:**
  - `PYTHON_VERSION` = `3.11.9`
  - `HAYINSIGHTS_API_KEY` = `<your_secret_key>`
