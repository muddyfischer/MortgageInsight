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
    lump_sum_month = st.number_input(
    "Month to apply one‑time extra payment",
    min_value=1,
    max_value=term_years * 12,
    value=1
)
with col2:
    inv_return = st.number_input("Investment Return (%)", 0.0, 20.0, 6.0) / 100
    tax_drag = st.number_input("Investment Tax Drag (%)", 0.0, 20.0, 1.0) / 100
     # New: helper controls
    use_auto_shield = st.checkbox("Estimate mortgage tax shield automatically", value=True)
    tax_bracket = st.number_input("Marginal Tax Rate (%)", 0.0, 60.0, 24.0) / 100
    standard_deduction = st.number_input("Standard Deduction ($)", 0, 500000, 0)
    other_itemized = st.number_input("Other Itemized Deductions (excluding mortgage interest) ($)", 0, 1000000, 0)
     # Keep your manual override if helper is off
    mortgage_tax_shield = st.number_input("Mortgage Interest Tax Shield (%)", 0.0, 50.0, 0.0) / 100
    
    sell_year = st.number_input("Sell after X years", 1, term_years, 10)
    sell_cost_pct = st.number_input("Selling Costs (%)", 0.0, 20.0, 6.0) / 100

# ----------------------------
# Custom PMT (no numpy_financial needed)
# ----------------------------
def pmt(rate, nper, pv):
    """Monthly payment for a loan."""
    if rate == 0:
        return -(pv / nper)
    return -(pv * rate * (1 + rate)**nper) / ((1 + rate)**nper - 1)

# ----------------------------
# Core amortization with tax logic
# ----------------------------
def amortization_with_tax(
    principal, annual_rate, years, 
    extra_monthly=0, lump_sum=0, lump_month=1,
    tax_rate=0.0, standard_deduction=0, other_itemized=0
):
    monthly_rate = annual_rate / 12
    months = years * 12
    monthly_payment = pmt(monthly_rate, months, principal)
    balance = principal
    records = []

    for m in range(1, months + 1):
        interest = balance * monthly_rate
        principal_payment = monthly_payment - interest
        extra = 0
        if m == lump_month and lump_sum > 0:
            extra += lump_sum
        if extra_monthly > 0:
            extra += extra_monthly
        if principal_payment + extra > balance:
            extra = balance - principal_payment
        balance -= principal_payment + extra

        records.append({
            "Month": m,
            "Interest": interest,
            "Principal": principal_payment,
            "Extra": extra,
            "Balance": max(balance, 0)
        })

        if balance <= 0:
            break

    df = pd.DataFrame(records)
    df["Year"] = ((df["Month"] - 1) // 12) + 1

    # Annual roll-up with tax savings
    annual = df.groupby("Year").agg({
        "Interest": "sum",
        "Principal": "sum",
        "Extra": "sum"
    }).reset_index()

    deduction_type = []
    tax_savings = []
    after_tax_cost = []

    for _, row in annual.iterrows():
        MI = row["Interest"]
        total_itemized = other_itemized + MI
        if total_itemized > standard_deduction:
            deduction_type.append("Itemized")
            deductible = max(0, min(MI, total_itemized - standard_deduction))
            savings = deductible * tax_rate
        else:
            deduction_type.append("Standard")
            savings = 0
        tax_savings.append(savings)
        after_tax_cost.append(
            (row["Interest"] + row["Principal"] + row["Extra"]) - savings
        )

    annual["Deduction_Type"] = deduction_type
    annual["Tax_Savings"] = tax_savings
    annual["After_Tax_Cost"] = after_tax_cost
    annual["Cumulative_After_Tax_Cost"] = annual["After_Tax_Cost"].cumsum()

    return df, annual

# ----------------------------
# Comparison orchestrator
# ----------------------------
def run_baseline_vs_prepay(
    principal, annual_rate, years,
    extra_monthly=0, lump_sum=0, lump_month=1,
    tax_rate=0.0, standard_deduction=0, other_itemized=0
):
    base_df, base_annual = amortization_with_tax(
        principal, annual_rate, years,
        tax_rate=tax_rate,
        standard_deduction=standard_deduction,
        other_itemized=other_itemized
    )
    prepay_df, prepay_annual = amortization_with_tax(
        principal, annual_rate, years,
        extra_monthly=extra_monthly,
        lump_sum=lump_sum,
        lump_month=lump_month,
        tax_rate=tax_rate,
        standard_deduction=standard_deduction,
        other_itemized=other_itemized
    )

    return base_df, base_annual, prepay_df, prepay_annual

# ----------------------------
# Investment growth
# ----------------------------
def future_value(pmt, rate, nper):
    return pmt * (((1 + rate)**nper - 1) / rate) if rate > 0 else pmt * nper

# ----------------------------
# Sale equity + net worth calc
# ----------------------------
def net_worth_at_sale(base_df, prepay_df, principal, sell_year, sell_cost_pct, inv_return, tax_drag, extra_monthly, lump_sum=0):
    months_invest = sell_year * 12
    invest_value = future_value(extra_monthly, (inv_return - tax_drag)/12, months_invest)
    if lump_sum > 0:
        invest_value += lump_sum * (1 + (inv_return - tax_drag))**sell_year

    appreciation_rates = [-0.02, 0.00, 0.02, 0.05]
    results = []
    for appr in appreciation_rates:
        home_value = principal * (1 + appr) ** sell_year
        base_balance = base_df.loc[min(months_invest, len(base_df))-1, "Balance"]
        prepay_balance = prepay_df.loc[min(months_invest, len(prepay_df))-1, "Balance"]
        base_equity = home_value - base_balance - home_value * sell_cost_pct
        prepay_equity = home_value - prepay_balance - home_value * sell_cost_pct
        base_net = base_equity + invest_value
        prepay_net = prepay_equity
        results.append([appr, base_net, prepay_net])
    sale_df = pd.DataFrame(results, columns=["Appreciation", "Net Worth (Invest)", "Net Worth (Prepay)"])
    return sale_df

# ----------------------------
# Example: Swap for Streamlit inputs
# ----------------------------
principal = 300000
annual_rate = 0.04
years = 30
extra_monthly = 200
lump_sum = 0
lump_month = 1
tax_rate = 0.24
standard_deduction = 14600
other_itemized = 0
sell_year = 10
sell_cost_pct = 0.06
inv_return = 0.06
tax_drag = 0.01

base_df, base_annual, prepay_df, prepay_annual = run_baseline_vs_prepay(
    principal, annual_rate, years,
    extra_monthly=extra_monthly,
    lump_sum=lump_sum,
    lump_month=lump_month,
    tax_rate=tax_rate,
    standard_deduction=standard_deduction,
    other_itemized=other_itemized
)

# Annual table
print("\n--- Annual Summary (Baseline) ---\n", base_annual)
print("\n--- Annual Summary (Prepay) ---\n", prepay_annual)

# Sale / Net Worth table
sale_df = net_worth_at_sale(
    base_df, prepay_df, principal,
    sell_year, sell_cost_pct,
    inv_return, tax_drag,
    extra_monthly, lump_sum
)
print("\n--- Net Worth at Sale ---\n", sale_df)

# Months saved + interest savings
months_saved = len(base_df) - len(prepay_df)
interest_saved = base_df["Interest"].sum() - prepay_df["Interest"].sum()
after_tax_interest_saved = (
    base_annual["Interest"].sum() - prepay_annual["Interest"].sum()
) - (base_annual["Tax_Savings"].sum() - prepay_annual["Tax_Savings"].sum())

print(f"\nMonths Saved: {months_saved}")
print(f"Interest Saved: ${interest_saved:,.0f}")
print(f"After-tax Interest Saved: ${after_tax_interest_saved:,.0f}")


st.subheader("Net Worth at Sale (by Appreciation Rate)")
st.dataframe(sale_df.style.format({"Appreciation":"{:.0%}", "Net Worth (Invest)":"${:,.0f}", "Net Worth (Prepay)":"${:,.0f}"}))

st.subheader("Amortization Schedules")
tabs = st.tabs(["Baseline", "Prepay"])
with tabs[0]:
    st.dataframe(base_df)
with tabs[1]:
    st.dataframe(prepay_df)

# Plot loan balances
chart_df = pd.DataFrame({
    "Month": base_df["Month"],
    "Baseline Balance": base_df["Balance"]
})
chart_df = chart_df.merge(prepay_df[["Month", "Balance"]].rename(columns={"Balance": "Prepay Balance"}), on="Month", how="outer")
chart_df = chart_df.fillna(method="ffill")
st.line_chart(chart_df.set_index("Month"))
