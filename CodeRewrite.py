import streamlit as st
import pandas as pd
import numpy as np

# --- Loan Payment Helper ---
def pmt(rate, nper, pv):
    return (pv * rate) / (1 - (1 + rate)**(-nper))

# --- Amortization with extras ---
def amortization_with_tax(loan, rate, years, tax_rate, extra_monthly=0, lump_sum=0, lump_month=0):
    monthly_rate = rate / 12
    months = years * 12
    payment = pmt(monthly_rate, months, loan)
    balance = loan
    data = []

    for m in range(1, months+1):
        if balance <= 0:
            break

        interest = balance * monthly_rate
        principal_payment = payment - interest

        # --- Extras ---
        extra = 0
        if m == lump_month and lump_sum > 0:
            extra += lump_sum
        if extra_monthly > 0:
            extra += extra_monthly

        # --- Cap at remaining balance ---
        total_payment = principal_payment + extra
        if total_payment > balance:
            total_payment = balance
            extra = total_payment - principal_payment

        balance -= total_payment

        after_tax_interest = interest * (1 - tax_rate)

        data.append({
            "Month": m,
            "Interest": interest,
            "Principal": principal_payment,
            "Extra": extra,
            "Balance": balance,
            "After-Tax Interest": after_tax_interest
        })

    return pd.DataFrame(data)

# --- Net worth at sale ---
def net_worth_at_sale(df, sale_month, home_value, invest_rate, invest_extra):
    """ Equity + invested cash """
    if sale_month > len(df):
        sale_month = len(df)

    balance = df.iloc[sale_month-1]["Balance"]

    # Home equity
    equity = home_value - balance

    # Investment growth (for baseline/invest strategy)
    invested = 0
    for i in range(sale_month):
        invested = invested * (1 + invest_rate/12) + invest_extra

    return equity + invested

# --- Streamlit UI ---
st.title("🏡 Mortgage Prepayment vs. Investment Calculator")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Loan Parameters")
    loan = st.number_input("Loan Amount", 100000, 2000000, 400000, step=5000)
    rate = st.number_input("Interest Rate (%)", 1.0, 15.0, 6.0, step=0.1)/100
    years = st.number_input("Term (years)", 10, 40, 30)
    tax_rate = st.number_input("Tax Shield (%)", 0, 50, 24, step=1)/100

    st.subheader("Prepayment Options")
    extra_monthly = st.number_input("Extra Monthly Payment", 0, 5000, 200)
    lump_sum = st.number_input("Lump Sum Payment", 0, 500000, 10000)
    lump_month = st.number_input("Lump Sum Month", 0, years*12, 12)

with col2:
    st.subheader("Investment Assumptions")
    invest_rate = st.number_input("Annual Investment Return (%)", 0.0, 15.0, 6.0, step=0.1)/100
    sale_year = st.number_input("Sale Year", 1, years, 10)
    appreciation = st.number_input("Annual Home Appreciation (%)", -10.0, 15.0, 3.0, step=0.1)/100

# --- Run Scenarios ---
base = amortization_with_tax(loan, rate, years, tax_rate, 0, 0, 0)
prepay = amortization_with_tax(loan, rate, years, tax_rate, extra_monthly, lump_sum, lump_month)

# Sale price projection
sale_month = sale_year * 12
home_value = loan * (1 + appreciation)**sale_year

# Net worth
nw_base = net_worth_at_sale(base, sale_month, home_value, invest_rate, extra_monthly + (lump_sum if lump_month > 0 else 0))
nw_prepay = net_worth_at_sale(prepay, sale_month, home_value, invest_rate, 0)

# --- Results ---
st.header("📊 Results")
colA, colB, colC = st.columns(3)
colA.metric("Baseline Net Worth", f"${nw_base:,.0f}")
colB.metric("Prepay Net Worth", f"${nw_prepay:,.0f}")
colC.metric("Difference", f"${(nw_prepay - nw_base):,.0f}")

# ROI of prepay
interest_saved = base["After-Tax Interest"].sum() - prepay["After-Tax Interest"].sum()
total_extra = prepay["Extra"].sum()
if total_extra > 0:
    years_to_payoff = len(prepay)/12
    effective_roi = (1 + interest_saved/total_extra)**(1/years_to_payoff) - 1
    st.metric("Effective ROI of Prepay", f"{effective_roi*100:.2f}%")

# Chart
chart_df = pd.DataFrame({
    "Baseline Balance": base["Balance"],
    "Prepay Balance": prepay["Balance"]
})
st.line_chart(chart_df)

# Expanders for detail
with st.expander("Amortization Table (Prepay)"):
    st.dataframe(prepay)
with st.expander("Amortization Table (Baseline)"):
    st.dataframe(base)