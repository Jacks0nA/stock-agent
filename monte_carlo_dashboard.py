"""
Monte Carlo Analysis Dashboard

Comprehensive display of all Monte Carlo simulation metrics.
Designed to be expanded with new analysis features over time.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from monte_carlo import get_monte_carlo_analysis
from monte_carlo_learning import learning_system


def display_monte_carlo_dashboard():
    """
    Main Monte Carlo dashboard component.
    Displays all simulation metrics and learning stats.
    """

    st.title("🎲 Monte Carlo Analysis Dashboard")

    # Input section
    st.subheader("Configure Analysis")
    col1, col2 = st.columns(2)

    with col1:
        ticker_input = st.text_input(
            "Enter ticker(s)",
            value="AAPL,TSLA,SNAP",
            help="Comma-separated list of tickers to analyze"
        )
        num_simulations = st.slider(
            "Number of simulations",
            min_value=1000,
            max_value=50000,
            value=10000,
            step=1000,
            help="More simulations = more accuracy but slower"
        )

    with col2:
        run_analysis = st.button("🚀 Run Monte Carlo Analysis", use_container_width=True)
        show_learning = st.checkbox("Show Learning System Stats", value=True)

    # Parse tickers
    if ticker_input:
        tickers = [t.strip().upper() for t in ticker_input.split(",")]
    else:
        tickers = []

    # Run analysis if button clicked
    if run_analysis and tickers:
        st.divider()

        with st.spinner("Running 10K simulations... this may take 30-60 seconds"):
            results = get_monte_carlo_analysis(tickers, num_simulations=num_simulations)

        if results:
            # Create tabs for different views
            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 Summary",
                "📈 Detailed Analysis",
                "🎯 Probability Distributions",
                "🧠 Learning System"
            ])

            with tab1:
                display_summary_view(results)

            with tab2:
                display_detailed_view(results)

            with tab3:
                display_distribution_view(results)

            with tab4:
                if show_learning:
                    display_learning_view(results)
                else:
                    st.info("Enable 'Show Learning System Stats' above to view")

        else:
            st.error("No analysis results. Check ticker symbols.")


def display_summary_view(results):
    """Summary view: Key metrics for each stock."""

    st.subheader("Recovery Probability Summary")

    # Create summary table
    summary_data = []
    for ticker, data in results.items():
        summary_data.append({
            "Ticker": ticker,
            "Recovery Prob": f"{data.get('recovery_probability_pct', 0):.1f}%",
            "Median Return (1yr)": f"{data.get('percentile_50', 0):.1f}%",
            "Best Case (95th)": f"${data.get('upside_potential', 0):.2f}",
            "Worst Case (5th)": f"${data.get('downside_risk', 0):.2f}",
            "Volatility": f"{data.get('volatility', 0)*100:.1f}%"
        })

    df_summary = pd.DataFrame(summary_data)
    st.dataframe(df_summary, use_container_width=True)

    # Gauge charts for recovery probability
    st.subheader("Recovery Probability Gauge")
    col1, col2, col3 = st.columns(3)

    for i, (ticker, data) in enumerate(list(results.items())[:3]):
        recovery_pct = data.get('recovery_probability_pct', 0)

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=recovery_pct,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': f"{ticker} Recovery Prob"},
            delta={'reference': 50},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 25], 'color': "lightgray"},
                    {'range': [25, 50], 'color': "#ffa500"},
                    {'range': [50, 75], 'color': "#90ee90"},
                    {'range': [75, 100], 'color': "darkgreen"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 70
                }
            }
        ))
        fig.update_layout(height=300)

        if i == 0:
            col1.plotly_chart(fig, use_container_width=True)
        elif i == 1:
            col2.plotly_chart(fig, use_container_width=True)
        else:
            col3.plotly_chart(fig, use_container_width=True)


def display_detailed_view(results):
    """Detailed view: Full metrics for each stock."""

    st.subheader("Detailed Monte Carlo Analysis")

    for ticker, data in results.items():
        with st.expander(f"📍 {ticker} — Recovery: {data.get('recovery_probability_pct', 0):.1f}%", expanded=True):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Recovery Probability",
                    f"{data.get('recovery_probability_pct', 0):.1f}%",
                    help="Chance stock recovers to current price or higher in 1 year"
                )
                st.metric(
                    "Current Price",
                    f"${data.get('current_price', 0):.2f}",
                    help="Most recent closing price"
                )
                st.metric(
                    "Volatility (Annual)",
                    f"{data.get('volatility', 0)*100:.1f}%",
                    help="Expected annual price volatility"
                )

            with col2:
                st.metric(
                    "Median Return (1yr)",
                    f"{data.get('percentile_50', 0):.1f}%",
                    help="50th percentile outcome"
                )
                st.metric(
                    "75th Percentile",
                    f"{data.get('percentile_75', 0):.1f}%",
                    help="Optimistic scenario (top 25%)"
                )
                st.metric(
                    "25th Percentile",
                    f"{data.get('percentile_25', 0):.1f}%",
                    help="Pessimistic scenario (bottom 25%)"
                )

            with col3:
                st.metric(
                    "Best Case (95th)",
                    f"${data.get('upside_potential', 0):.2f}",
                    help="Top 5% outcome"
                )
                st.metric(
                    "Worst Case (5th)",
                    f"${data.get('downside_risk', 0):.2f}",
                    help="Bottom 5% outcome"
                )
                st.metric(
                    "Expected Return",
                    f"{data.get('expected_return', 0):.1f}%",
                    help="Average return across all simulations"
                )

            # Return distribution visualization
            st.subheader("Return Distribution Analysis")
            col1, col2 = st.columns(2)

            with col1:
                # Create probability ranges
                ranges = [
                    ("Worst Case (5%)", data.get('downside_risk', 0), data.get('percentile_25', 0)),
                    ("Pessimistic (25-50%)", data.get('percentile_25', 0), data.get('percentile_50', 0)),
                    ("Median (50%)", data.get('percentile_50', 0), data.get('percentile_50', 0)),
                    ("Optimistic (50-75%)", data.get('percentile_50', 0), data.get('percentile_75', 0)),
                    ("Best Case (95%)", data.get('percentile_75', 0), data.get('upside_potential', 0))
                ]

                range_data = []
                for label, low, high in ranges:
                    range_data.append({"Scenario": label, "Value": (low + high) / 2})

                df_ranges = pd.DataFrame(range_data)

                fig = px.bar(
                    df_ranges,
                    x="Scenario",
                    y="Value",
                    title="Return Scenarios",
                    labels={"Value": "Return (%)"},
                    color="Value",
                    color_continuous_scale="RdYlGn"
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Risk-Reward profile
                st.write("**Risk-Reward Profile**")
                risk_data = {
                    "Metric": [
                        "Probability of Recovery",
                        "Expected Return",
                        "Downside Risk",
                        "Upside Potential",
                        "Volatility"
                    ],
                    "Value": [
                        data.get('recovery_probability_pct', 0),
                        data.get('expected_return', 0),
                        abs(data.get('downside_risk', 0) - data.get('current_price', 0)) / data.get('current_price', 1) * 100 if data.get('current_price') else 0,
                        (data.get('upside_potential', 0) - data.get('current_price', 0)) / data.get('current_price', 1) * 100 if data.get('current_price') else 0,
                        data.get('volatility', 0) * 100
                    ]
                }
                df_risk = pd.DataFrame(risk_data)
                st.dataframe(df_risk, use_container_width=True)

            st.divider()


def display_distribution_view(results):
    """Probability distribution visualizations."""

    st.subheader("Probability Distributions")

    for ticker, data in results.items():
        st.write(f"**{ticker}** — Recovery: {data.get('recovery_probability_pct', 0):.1f}%")

        # Create a distribution chart
        percentiles = [5, 25, 50, 75, 95]
        values = [
            data.get('downside_risk', 0),
            data.get('percentile_25', 0),
            data.get('percentile_50', 0),
            data.get('percentile_75', 0),
            data.get('upside_potential', 0)
        ]

        dist_data = pd.DataFrame({
            "Percentile": [f"{p}th" for p in percentiles],
            "Price": values
        })

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dist_data["Percentile"],
            y=dist_data["Price"],
            fill='tozeroy',
            mode='lines+markers',
            name='Simulated Price Distribution',
            line=dict(color='darkblue'),
            marker=dict(size=8)
        ))

        fig.add_hline(
            y=data.get('current_price', 0),
            line_dash="dash",
            line_color="red",
            annotation_text="Current Price",
            annotation_position="right"
        )

        fig.update_layout(
            title=f"{ticker} — 1-Year Price Distribution",
            xaxis_title="Probability Percentile",
            yaxis_title="Stock Price ($)",
            height=400,
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True)
        st.divider()


def display_learning_view(results):
    """Learning system statistics and accuracy tracking."""

    st.subheader("🧠 Learning System Performance")

    # Get learning stats
    accuracy = learning_system.calculate_accuracy()
    monthly_summary = learning_system.get_monthly_summary()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Predictions",
            accuracy.get('total_predictions', 0),
            help="Total predictions made since system started"
        )

    with col2:
        st.metric(
            "Completed Results",
            accuracy.get('completed_predictions', 0),
            help="Predictions with actual results"
        )

    with col3:
        overall_acc = accuracy.get('overall_accuracy', 0)
        st.metric(
            "Overall Accuracy",
            f"{overall_acc*100:.1f}%" if overall_acc else "N/A",
            help="Percentage of predictions that were correct"
        )

    with col4:
        multiplier = learning_system.volatility_multiplier
        change = "🔽 Conservative" if multiplier < 1.0 else "🔼 Aggressive" if multiplier > 1.0 else "⚖️ Balanced"
        st.metric(
            "Volatility Multiplier",
            f"{multiplier:.2f}x",
            help=change
        )

    st.divider()

    # Accuracy by confidence level
    st.subheader("Accuracy by Prediction Confidence")

    conf_data = {
        "Confidence Level": [
            "High (>70%)",
            "Medium (50-70%)",
            "Low (<50%)"
        ],
        "Accuracy": [
            accuracy.get('high_confidence_accuracy', 0),
            accuracy.get('medium_confidence_accuracy', 0),
            accuracy.get('low_confidence_accuracy', 0)
        ],
        "Count": [
            accuracy.get('high_confidence_count', 0),
            accuracy.get('medium_confidence_count', 0),
            accuracy.get('low_confidence_count', 0)
        ]
    }

    df_conf = pd.DataFrame(conf_data)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_conf["Confidence Level"],
        y=df_conf["Accuracy"].apply(lambda x: x*100 if x else 0),
        name="Accuracy (%)",
        yaxis="y1"
    ))

    fig.add_trace(go.Scatter(
        x=df_conf["Confidence Level"],
        y=df_conf["Count"],
        name="Count",
        yaxis="y2",
        mode='lines+markers'
    ))

    fig.update_layout(
        title="Prediction Accuracy by Confidence Level",
        xaxis_title="Confidence Level",
        yaxis=dict(title="Accuracy (%)", side="left"),
        yaxis2=dict(title="Number of Predictions", overlaying="y", side="right"),
        height=400,
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Monthly summary
    if monthly_summary.get('completed', 0) > 0:
        st.subheader("Last 30 Days Summary")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Month Predictions",
                monthly_summary.get('month_predictions', 0)
            )

        with col2:
            st.metric(
                "Completed",
                monthly_summary.get('completed', 0)
            )

        with col3:
            month_acc = monthly_summary.get('accuracy', 0)
            st.metric(
                "Month Accuracy",
                f"{month_acc*100:.1f}%"
            )

    else:
        st.info("Not enough data yet. System gathers accuracy metrics as trades complete.")

    st.divider()

    # Volatility adjustment history
    st.subheader("System Calibration")

    st.write(f"**Current Volatility Multiplier: {learning_system.volatility_multiplier:.2f}x**")

    if learning_system.volatility_multiplier < 1.0:
        st.warning(
            f"🔽 System is being CONSERVATIVE\n\n"
            f"Predictions have been too optimistic. "
            f"Volatility reduced by {(1-learning_system.volatility_multiplier)*100:.0f}% "
            f"to be more realistic."
        )
    elif learning_system.volatility_multiplier > 1.0:
        st.success(
            f"🔼 System is being AGGRESSIVE\n\n"
            f"Predictions have been too pessimistic. "
            f"Volatility increased by {(learning_system.volatility_multiplier-1)*100:.0f}% "
            f"to be more optimistic."
        )
    else:
        st.success(
            f"⚖️ System is WELL-CALIBRATED\n\n"
            f"Predictions are accurately calibrated. "
            f"No volatility adjustment needed."
        )


if __name__ == "__main__":
    display_monte_carlo_dashboard()
