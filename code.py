import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Mortgage Prepay vs Invest Calculator", layout="wide")

st.title("🏠 Mortgage Prepayment vs Investment Impact")

# Inputs
col1, col2 = st.columns(2)
with col1:
    loan_amount = st.number_input("Loan Amount ($)", 10000, 2000000, 300000)
    annual_rate = st.number_input("Mortgage Interest Rate (%)", 0.1, 15.0, 4.0) / 100
    term_years = st.number_input("Term (years)", 1, 40, 30)
    extra_payment = st.number_input("Extra Monthly Payment ($)", 0, 5000, 200)
    lump_sum = st.number_input("One-time Extra Payment ($)", 0, 500000, 0)
with col2:
    inv_return = st.number_input("Investment Return (%)", 0.0, 20.0, 6.0) / 100
    tax_drag = st.number_input("Investment Tax Drag (%)", 0.0, 20.0, 1.0) / 100
    mortgage_tax_shield = st.number_input("Mortgage Interest Tax Shield (%)", 0.0, 50.0, 0.0) / 100
    sell_year = st.number_input("Sell after X years", 1, term_years, 10)
    sell_cost_pct = st.number_input("Selling Costs (%)", 0.0, 20.0, 6.0) / 100

# Custom PMT function
def pmt(rate, nper, pv):
    if rate == 0:
        return -(pv / nper)
    return -(pv * rate * (1 + rate)**nper) / ((1 + rate)**nper - 1)

# Amortization function
def amortization(loan, rate, term, extra_monthly=0, lump_sum=0):
    monthly_rate = rate / 12
    months = term * 12
    payment = pmt(monthly_rate, months, loan)
    balance = loan
    schedule = []
    for m in range(1, months+1):
        interest = balance * monthly_rate
        principal = payment - interest
        if m == 1 and lump_sum > 0:
            balance -= lump_sum
            principal += lump_sum
        balance -= (principal + extra_monthly)
        if balance < 0:
            principal += balance
            balance = 0
        schedule.append([m, interest, principal, balance])
        if balance <= 0:
            break
    return pd.DataFrame(schedule, columns=["Month", "Interest", "Principal", "Balance"])

# Run scenarios
base_df = amortization(loan_amount, annual_rate, term_years)
prepay_df = amortization(loan_amount, annual_rate, term_years, extra_payment, lump_sum)

# Interest savings (after tax)
base_interest = base_df["Interest"].sum()
prepay_interest = prepay_df["Interest"].sum()
base_interest_after_tax = base_interest * (1 - mortgage_tax_shield)
prepay_interest_after_tax = prepay_interest * (1 - mortgage_tax_shield)

# Investment growth of saved money
def future_value(pmt, rate, nper):
    return pmt * (((1 + rate)**nper - 1) / rate) if rate > 0 else pmt * nper

monthly_invest = extra_payment
months_invest = sell_year * 12
investment_value = future_value(monthly_invest, (inv_return - tax_drag)/12, months_invest)

# Add lump sum to investments if choosing "invest" strategy
if lump_sum > 0:
    investment_value += lump_sum * (1 + (inv_return - tax_drag))**sell_year

# Equity at sale
appreciation_rates = [-0.02, 0.00, 0.02, 0.05]
sale_results = []
for appr in appreciation_rates:
    home_value = loan_amount * (1 + appr) ** sell_year
    base_balance = base_df.loc[min(sell_year*12, len(base_df))-1, "Balance"]
    prepay_balance = prepay_df.loc[min(sell_year*12, len(prepay_df))-1, "Balance"]
    base_equity = home_value - base_balance - home_value*sell_cost_pct
    prepay_equity = home_value - prepay_balance - home_value*sell_cost_pct
    base_net = base_equity + investment_value
    prepay_net = prepay_equity
    sale_results.append([appr, base_net, prepay_net])

sale_df = pd.DataFrame(sale_results, columns=["Appreciation", "Net Worth (Invest)", "Net Worth (Prepay)"])

# Output
st.subheader("Summary")
st.write(f"**Months Saved:** {len(base_df) - len(prepay_df)}")
st.write(f"**Interest Saved:** ${base_interest - prepay_interest:,.0f}")
st.write(f"**After-tax Interest Saved:** ${base_interest_after_tax - prepay_interest_after_tax:,.0f}")

st.subheader("Net Worth at Sale (by Appreciation Rate)")
st.dataframe(sale_df.style.format({"Appreciation":"{:.0%}", "Net Worth (Invest)":"${:,.0f}", "Net Worth (Prepay)":"${:,.0f}"}))

st.subheader("Amortization Schedules")
tabs = st.tabs(["Baseline", "Prepay"])
with tabs[0]:
    st.dataframe(base_df)
with tabs[1]:
    st.dataframe(prepay_df)

import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot(base_df["Month"], base_df["Balance"], label="Baseline")
ax.plot(prepay_df["Month"], prepay_df["Balance"], label="Prepay")
ax.set_xlabel("Month")
ax.set_ylabel("Balance")
ax.legend()
st.pyplot(fig)
