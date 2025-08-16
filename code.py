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

# Custom PMT function
def pmt(rate, nper, pv):
    if rate == 0:
        return pv / nper
    return (pv * rate * (1 + rate)**nper) / ((1 + rate)**nper - 1) # positive

# Amortization function
def amortization_with_tax(
    loan, rate, term, extra_monthly=0, lump_sum=0, lump_month=1,
    tax_rate=0.24, standard_deduction=14600, other_itemized=0
):
    import pandas as pd

    monthly_rate = rate / 12
    months = term * 12
    payment = pmt(monthly_rate, months, loan)  # negative by convention
    balance = loan
    schedule = []

    for m in range(1, months + 1):
        interest = balance * monthly_rate
        principal = -payment - interest  # scheduled principal only
        extra = 0

        # Lump sum in chosen month
        if m == lump_month and lump_sum > 0:
            extra += lump_sum

        # Monthly extra
        if extra_monthly > 0:
            extra += extra_monthly

        # Cap on final payment
        if principal + extra > balance:
            extra = balance - principal
            if extra < 0:
                principal += extra
                extra = 0

        balance -= principal + extra

        schedule.append([
            m,
            round(interest, 2),
            round(principal, 2),
            round(extra, 2),
            round(balance, 2)
        ])

        if balance <= 0:
            break

    df = pd.DataFrame(schedule, columns=["Month", "Interest", "Principal", "Extra", "Balance"])

    # Add year column
    df["Year"] = ((df["Month"] - 1) // 12) + 1

    # Annual roll‑up
    annual = df.groupby("Year").agg({
        "Interest": "sum",
        "Principal": "sum",
        "Extra": "sum"
    }).reset_index()

    # Tax benefit calculation
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
        after_tax_cost.append((row["Interest"] + row["Principal"] + row["Extra"]) - savings)

    annual["Deduction_Type"] = deduction_type
    annual["Tax_Savings"] = tax_savings
    annual["After_Tax_Cost"] = after_tax_cost
    annual["Cumulative_After_Tax_Cost"] = annual["After_Tax_Cost"].cumsum()

    return df, annual
def add_year_column(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["Year"] = ((d["Month"] - 1) // 12) + 1
    return d

def after_tax_interest_helper(df: pd.DataFrame, tax_rate: float, std_ded: float, other_itemized: float) -> float:
    """
    Sum after-tax mortgage interest across years using itemize-vs-standard rule.
    """
    if df.empty:
        return 0.0
    d = add_year_column(df)
    annual = d.groupby("Year")["Interest"].sum().reset_index()
    after_tax_total = 0.0
    for _, row in annual.iterrows():
        MI = float(row["Interest"])
        if MI <= 0:
            continue
        deductible = max(0.0, min(MI, other_itemized + MI - std_ded))
        shield_dollars = tax_rate * deductible
        after_tax_total += MI - shield_dollars
    return after_tax_total

def effective_avg_shield_rate(df: pd.DataFrame, tax_rate: float, std_ded: float, other_itemized: float) -> float:
    """
    Weighted-average effective tax shield rate across the whole schedule.
    """
    total_MI = float(df["Interest"].sum())
    if total_MI <= 0:
        return 0.0
    after_tax = after_tax_interest_helper(df, tax_rate, std_ded, other_itemized)
    eff_rate = 1.0 - (after_tax / total_MI)
    return max(0.0, min(1.0, eff_rate))

# Run scenarios
base_df = amortization(loan_amount, annual_rate, term_years)
prepay_df = amortization(
    loan_amount, annual_rate, term_years,
    extra_payment, lump_sum, lump_sum_month
)

# Interest savings (after tax)
base_interest = base_df["Interest"].sum()
prepay_interest = prepay_df["Interest"].sum()

if use_auto_shield:
    base_interest_after_tax = after_tax_interest_helper(base_df, tax_bracket, standard_deduction, other_itemized)
    prepay_interest_after_tax = after_tax_interest_helper(prepay_df, tax_bracket, standard_deduction, other_itemized)

    # Show the effective average rates that were applied
    eff_base = effective_avg_shield_rate(base_df, tax_bracket, standard_deduction, other_itemized)
    eff_prepay = effective_avg_shield_rate(prepay_df, tax_bracket, standard_deduction, other_itemized)
    st.caption(f"Effective average tax shield applied — Baseline: {eff_base:.1%} | Prepay: {eff_prepay:.1%}")
else:
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

# Plot loan balances
chart_df = pd.DataFrame({
    "Month": base_df["Month"],
    "Baseline Balance": base_df["Balance"]
})
chart_df = chart_df.merge(prepay_df[["Month", "Balance"]].rename(columns={"Balance": "Prepay Balance"}), on="Month", how="outer")
chart_df = chart_df.fillna(method="ffill")
st.line_chart(chart_df.set_index("Month"))
