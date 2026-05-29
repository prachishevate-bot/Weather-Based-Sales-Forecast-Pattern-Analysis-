import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# ==========================================
# 1. Configuration & Setup
# ==========================================
st.set_page_config(page_title="Multi-Season Comparison Dashboard", layout="wide")

LOCATIONS = {
    "India": ["Mumbai", "Delhi", "Bengaluru", "Chennai"],
    "USA": ["New York", "San Francisco", "Miami", "Chicago"],
    "UK": ["London", "Manchester", "Edinburgh"]
}

# Define mapping for seasons based on Indian climate patterns
SEASON_MONTHS = {
    "Summer": {"start_month": "03-01", "end_month": "05-31"},
    "Monsoon": {"start_month": "06-01", "end_month": "09-30"},
    "Winter": {"start_month": "10-01", "end_month": "02-28"}
}

# ==========================================
# 2. Helper Functions
# ==========================================
@st.cache_data
def get_coordinates(city):
    """Fetches latitude and longitude for a given city."""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&format=json"
    response = requests.get(url)
    if response.status_code == 200 and 'results' in response.json():
        data = response.json()['results'][0]
        return data['latitude'], data['longitude']
    return None, None

@st.cache_data
def fetch_season_weather(lat, lon, season_name, year):
    """Calculates strict dates and fetches historical data, preventing future date API crashes."""
    year_int = int(year)
    
    if season_name == "Winter":
        start_date_str = f"{year_int}-10-01"
        end_date_str = f"{year_int + 1}-02-28"
    else:
        start_date_str = f"{year_int}-{SEASON_MONTHS[season_name]['start_month']}"
        end_date_str = f"{year_int}-{SEASON_MONTHS[season_name]['end_month']}"
        
    # --- FIX: Prevent future date API crashes ---
    start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    
    # Open-Meteo Archive API only reliably processes data up to 3 days ago.
    max_allowed_date = datetime.today().date() - timedelta(days=3)
    
    if start_date_obj > max_allowed_date:
        # The entire season is in the future. Cannot fetch historical data.
        return pd.DataFrame()
        
    if end_date_obj > max_allowed_date:
        # Season is currently ongoing. Cap the end date to the max allowed so API doesn't crash.
        end_date_str = max_allowed_date.strftime("%Y-%m-%d")
    # --------------------------------------------
        
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date_str}&end_date={end_date_str}&daily=temperature_2m_max,precipitation_sum&timezone=auto"
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if "daily" in data:  # Extra safety check
            df = pd.DataFrame({
                "Date": pd.to_datetime(data["daily"]["time"]),
                "Max Temperature (°C)": data["daily"]["temperature_2m_max"],
                "Precipitation (mm)": data["daily"]["precipitation_sum"]
            })
            df["Season_Label"] = f"{season_name} ({year})"
            return df
    return pd.DataFrame()

def simulate_sales_data(weather_df, product_type):
    """Simulates realistic product sales based on weather metrics."""
    if weather_df.empty:
        return weather_df
    
    np.random.seed(42) 
    sales = []
    
    for _, row in weather_df.iterrows():
        temp = row["Max Temperature (°C)"]
        rain = row["Precipitation (mm)"]
        base_sales = 100 
        noise = np.random.randint(-20, 20)
        
        if product_type == "Cold Drinks":
            daily_sales = base_sales + (temp * 15) + noise
        elif product_type == "Umbrellas":
            daily_sales = base_sales + (rain * 40) + noise
        elif product_type == "Winter Heaters":
            daily_sales = base_sales + ((30 - temp) * 20) + noise if temp < 20 else base_sales / 2 + noise
        elif product_type == "Seasonal Fruits":
            daily_sales = base_sales + (temp * 12) - (rain * 5) + noise
        else:
            daily_sales = base_sales + noise
            
        sales.append(max(0, int(daily_sales))) 
        
    weather_df["Units Sold"] = sales
    return weather_df

# ==========================================
# 3. Streamlit UI Layout
# ==========================================
st.title("⚖️ Cross-Season Comparative Analytics Dashboard")
st.markdown("Select two distinct historical seasonal windows side-by-side to directly compare weather impacts and product velocities.")

# --- Sidebar Filters ---
st.sidebar.header("Global Filters")
selected_country = st.sidebar.selectbox("Select Country", list(LOCATIONS.keys()), index=0)
selected_city = st.sidebar.selectbox("Select City", LOCATIONS[selected_country], index=0)
selected_product = st.sidebar.selectbox(
    "Select Product Category", 
    ["Cold Drinks", "Umbrellas", "Winter Heaters", "Seasonal Fruits"]
)

st.sidebar.markdown("---")

# Left Column / Baseline Season Configuration
st.sidebar.subheader("Period A (Baseline)")
season_a = st.sidebar.selectbox("Season A", ["Summer", "Monsoon", "Winter"], index=0)
year_a = st.sidebar.selectbox("Year A", ["2020", "2021", "2022", "2023", "2024", "2025", "2026"], index=5)

# Right Column / Target Comparison Season Configuration
st.sidebar.subheader("Period B (Comparison)")
season_b = st.sidebar.selectbox("Season B", ["Summer", "Monsoon", "Winter"], index=1)
year_b = st.sidebar.selectbox("Year B", ["2020", "2021", "2022", "2023", "2024", "2025", "2026"], index=6)

# Execution Pipeline
with st.spinner("Processing regional coordinates and querying multi-year weather matrix..."):
    lat, lon = get_coordinates(selected_city)
    
    if lat and lon:
        # Fetch data for both configured timelines
        df_a = fetch_season_weather(lat, lon, season_a, year_a)
        df_b = fetch_season_weather(lat, lon, season_b, year_b)
        
        # Apply simulated production data models
        df_a = simulate_sales_data(df_a, selected_product)
        df_b = simulate_sales_data(df_b, selected_product)
        
        if not df_a.empty and not df_b.empty:
            
            # ==========================================
            # 4. View: Dynamic Side-by-Side Summary Metrics
            # ==========================================
            st.subheader(f"Strategic Comparison: Period A vs. Period B ({selected_city})")
            
            label_a = f"{season_a} {year_a}"
            label_b = f"{season_b} {year_b}"
            
            col1, col2, col3 = st.columns(3)
            
            # Metric Block 1: Total Volumes
            sales_diff = int(df_b['Units Sold'].sum() - df_a['Units Sold'].sum())
            col1.metric(
                label=f"Total Sales Shift (A → B)", 
                value=f"{df_b['Units Sold'].sum():,} Units",
                delta=f"{sales_diff:+,} vs {label_a}"
            )
            
            # Metric Block 2: Daily Velocity
            velocity_diff = int(df_b['Units Sold'].mean() - df_a['Units Sold'].mean())
            col2.metric(
                label=f"Avg Daily Velocity (Period B)", 
                value=f"{int(df_b['Units Sold'].mean()):,} Units/Day",
                delta=f"{velocity_diff:+,} vs {label_a}"
            )
            
            # Metric Block 3: Primary Weather Multiplier Difference
            weather_col = "Precipitation (mm)" if selected_product == "Umbrellas" else "Max Temperature (°C)"
            weather_diff = df_b[weather_col].mean() - df_a[weather_col].mean()
            col3.metric(
                label=f"Avg {weather_col} (Period B)",
                value=f"{df_b[weather_col].mean():.1f}",
                delta=f"{weather_diff:+.1f} unit shift"
            )

            # ==========================================
            # 5. Visual Comparison: Parallel Trend Timelines
            # ==========================================
            st.markdown("---")
            st.subheader("📈 Time-Series Performance Convergence")
            st.markdown("This timeline maps both seasons starting from Day 1 to track how early-season weather cycles accelerate or stunt demand trajectory.")
            
            # Reset index to create a uniform 'Day of Season' x-axis for a clean overlapping line chart
            df_a_reset = df_a.reset_index(drop=True).reset_index().rename(columns={"index": "Day of Season"})
            df_b_reset = df_b.reset_index(drop=True).reset_index().rename(columns={"index": "Day of Season"})
            
            combined_trend_df = pd.concat([df_a_reset, df_b_reset], ignore_index=True)
            
            fig_compare = px.line(
                combined_trend_df, 
                x="Day of Season", 
                y="Units Sold", 
                color="Season_Label",
                title=f"Daily Run-Rate Tracking: {selected_product}",
                labels={"Units Sold": "Volume Transacted", "Day of Season": "Timeline (Days elapsed from start)"},
                color_discrete_map={f"{season_a} ({year_a})": "#1f77b4", f"{season_b} ({year_b})": "#ff7f0e"}
            )
            fig_compare.update_layout(hovermode="x unified")
            st.plotly_chart(fig_compare, use_container_width=True)

            # ==========================================
            # 6. Strategic Executive Action Matrix
            # ==========================================
            st.markdown("---")
            st.subheader("🔮 Predictive Variance Analysis & Business Directives")
            
            # Compile key summary stats for structured decision-making tables
            comparison_summary = pd.DataFrame([
                {
                    "Period": label_a,
                    "Total Volume": df_a['Units Sold'].sum(),
                    "Daily Run-Rate": int(df_a['Units Sold'].mean()),
                    f"Max {weather_col} Recorded": df_a[weather_col].max(),
                    "Peak Sales Single Day": df_a['Units Sold'].max()
                },
                {
                    "Period": label_b,
                    "Total Volume": df_b['Units Sold'].sum(),
                    "Daily Run-Rate": int(df_b['Units Sold'].mean()),
                    f"Max {weather_col} Recorded": df_b[weather_col].max(),
                    "Peak Sales Single Day": df_b['Units Sold'].max()
                }
            ])
            
            st.dataframe(comparison_summary.set_index("Period"), use_container_width=True)
            
            # Dynamic Strategy Builder Injection
            st.markdown("### 🎯 Core Operational Decision Directives")
            
            pct_change = ((df_b['Units Sold'].sum() - df_a['Units Sold'].sum()) / df_a['Units Sold'].sum()) * 100
            
            if pct_change > 5:
                st.success(
                    f"**Demand Expansion Strategy:** Moving from {label_a} to {label_b} yields a **{pct_change:+.1f}% upward surge** in transaction volume. "
                    f"This growth correlates tightly to variations in regional *{weather_col}*. "
                    f"**Action Item:** For upcoming cycles showing patterns close to {label_b}, increase supply-chain pipelines by 15% to mitigate stockouts."
                )
            elif pct_change < -5:
                st.warning(
                    f"**Risk Mitigation & Contraction Strategy:** A structural **{pct_change:+.1f}% drop** in sales velocity is observed when moving to {label_b}. "
                    f"**Action Item:** Implement tighter procurement thresholds if climatic forecasters model weather patterns trending toward {label_b} parameters. Divert working capital into less weather-volatile SKU segments."
                )
            else:
                st.info(
                    f"**Equilibrium Maintenance Strategy:** Total performance variance remains flat (**{pct_change:+.1f}%** baseline change). "
                    f"**Action Item:** Maintain structural standard reorder patterns. Current marketing expenditures and stock layers require no immediate shifts."
                )
                
        else:
            st.error("Data extraction boundaries failed to locate matrix points for one or both requested timelines.")
            st.info("💡 **Tip:** If you selected a season in 2026 that hasn't happened yet (e.g., Monsoon or Winter 2026), the historical archive cannot fetch data for it. Please select a past or currently ongoing season.")
    else:
        st.error(f"Geocoding server rejected search index values for target destination: {selected_city}.")