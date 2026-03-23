import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- PAGE CONFIG ---
st.set_page_config(page_title="Transaction Analysis Dashboard", layout="wide")
st.title("Transaction Analysis Dashboard")

# --- 1. FILE UPLOADER ---
uploaded_file = st.file_uploader("Upload your aggregated CSV file", type=['csv'])

if uploaded_file is not None:
    # Load the data
    df = pd.read_csv(uploaded_file)
    
    # Ensure Month is treated as a string or period for sorting
    df['Month'] = df['Month'].astype(str)
    
    # --- 2. DATA MANIPULATION ---
    # Create "Processor grouped" column based on your logic
    def group_processor(proc):
        if pd.isna(proc):
            return "null"
        proc_str = str(proc).lower()
        if proc_str.startswith("cko"):
            return "Checkout"
        elif proc_str.endswith("mpgs"):
            return "mpgs"
        elif proc_str.endswith("cybersource"):
            return "cybersource"
        else:
            return "null"

    df['Processor grouped'] = df['Processor'].apply(group_processor)

    # --- 3. HIGH LEVEL KPI BOXES ---
    st.header("Latest Month Performance")
    
    # Sort months to find the latest and previous
    months = sorted(df['Month'].unique())
    
    if len(months) >= 2:
        latest_month = months[-1]
        prev_month = months[-2]
    elif len(months) == 1:
        latest_month = months[0]
        prev_month = None
    else:
        st.stop()

    def get_shares(month):
        month_data = df[df['Month'] == month]
        total_success = month_data['Successful Trx'].sum()
        
        if total_success == 0:
            return 0, 0
            
        mpgs_success = month_data[month_data['Processor grouped'] == 'mpgs']['Successful Trx'].sum()
        non_mpgs_success = total_success - mpgs_success
        
        return (mpgs_success / total_success), (non_mpgs_success / total_success)

    # Calculate metrics
    latest_mpgs_share, latest_non_mpgs_share = get_shares(latest_month)
    
    if prev_month:
        prev_mpgs_share, prev_non_mpgs_share = get_shares(prev_month)
        mpgs_delta = (latest_mpgs_share - prev_mpgs_share) * 100
        non_mpgs_delta = (latest_non_mpgs_share - prev_non_mpgs_share) * 100
    else:
        mpgs_delta, non_mpgs_delta = 0, 0

    # Display KPI Boxes
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            label=f"MPGS Share ({latest_month})", 
            value=f"{latest_mpgs_share:.1%}", 
            delta=f"{mpgs_delta:.1f} bps MoM" if prev_month else None
        )
    with col2:
        st.metric(
            label=f"Non-MPGS Share ({latest_month})", 
            value=f"{latest_non_mpgs_share:.1%}", 
            delta=f"{non_mpgs_delta:.1f} bps MoM" if prev_month else None,
            delta_color="inverse" # Usually if Non-MPGS goes up, MPGS goes down, adjust as needed
        )

    st.divider()

    # --- 4. TABLE: SHARES OVER MONTHS (PROCESSOR GROUPED) ---
    st.header("Processor Grouped Shares Over Time")
    
    # Group by Month and Processor grouped
    proc_monthly = df.groupby(['Month', 'Processor grouped'])['Successful Trx'].sum().reset_index()
    # Pivot to get processors as columns
    proc_pivot = proc_monthly.pivot(index='Month', columns='Processor grouped', values='Successful Trx').fillna(0)
    # Convert to percentages (shares)
    proc_shares = proc_pivot.div(proc_pivot.sum(axis=1), axis=0) * 100
    
    st.dataframe(proc_shares.style.format("{:.1f}%"))

    st.divider()

    # --- 5. DEVELOPMENT BY BUSINESS NAME & PROCESSOR GROUPED ---
    st.header("Volume Shift Analysis")
    st.write("100% Stacked Bar Charts to visualize share shifts over time.")
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("Business Name Share")
        biz_monthly = df.groupby(['Month', 'Business Name'])['Successful Trx'].sum().reset_index()
        fig_biz = px.bar(biz_monthly, x="Month", y="Successful Trx", color="Business Name", 
                         title="Share of Total by Business Name", barnorm='percent')
        st.plotly_chart(fig_biz, use_container_width=True)

    with col4:
        st.subheader("Processor Share")
        fig_proc = px.bar(proc_monthly, x="Month", y="Successful Trx", color="Processor grouped", 
                          title="Share of Total by Processor Grouped", barnorm='percent')
        st.plotly_chart(fig_proc, use_container_width=True)

    st.divider()

    # --- 6. SHARES BASED ON CC TYPE & CC CATEGORY ---
    st.header("Credit Card Dimensions (Overall)")
    
    col5, col6 = st.columns(2)
    
    with col5:
        cc_type = df.groupby('Cc Type')['Successful Trx'].sum().reset_index()
        fig_type = px.pie(cc_type, values='Successful Trx', names='Cc Type', title="Share by CC Type", hole=0.4)
        st.plotly_chart(fig_type, use_container_width=True)

    with col6:
        cc_cat = df.groupby('Cc Category')['Successful Trx'].sum().reset_index()
        fig_cat = px.pie(cc_cat, values='Successful Trx', names='Cc Category', title="Share by CC Category", hole=0.4)
        st.plotly_chart(fig_cat, use_container_width=True)

    st.divider()

    # --- 7. SANKEY DIAGRAM ---
    st.header("Transaction Flow (Sankey Diagram)")
    st.write("Visualizing the flow of Successful Transactions: Business Name ➔ Processor ➔ CC Category ➔ CC Type")

    # Aggregate data for Sankey
    sankey_df = df.groupby(['Business Name', 'Processor grouped', 'Cc Category', 'Cc Type'])['Successful Trx'].sum().reset_index()
    sankey_df = sankey_df[sankey_df['Successful Trx'] > 0] # Remove 0 values to clean up diagram

    # Define nodes and links
    nodes = list(pd.unique(sankey_df[['Business Name', 'Processor grouped', 'Cc Category', 'Cc Type']].values.ravel('K')))
    node_mapping = {node: i for i, node in enumerate(nodes)}

    # Link: Business Name -> Processor
    source1 = sankey_df['Business Name'].map(node_mapping).tolist()
    target1 = sankey_df['Processor grouped'].map(node_mapping).tolist()
    value1 = sankey_df['Successful Trx'].tolist()

    # Link: Processor -> CC Category
    source2 = sankey_df['Processor grouped'].map(node_mapping).tolist()
    target2 = sankey_df['Cc Category'].map(node_mapping).tolist()
    value2 = sankey_df['Successful Trx'].tolist()

    # Link: CC Category -> CC Type
    source3 = sankey_df['Cc Category'].map(node_mapping).tolist()
    target3 = sankey_df['Cc Type'].map(node_mapping).tolist()
    value3 = sankey_df['Successful Trx'].tolist()

    # Combine links
    sources = source1 + source2 + source3
    targets = target1 + target2 + target3
    values = value1 + value2 + value3

    fig_sankey = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=nodes
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values
        )
    )])
    
    fig_sankey.update_layout(height=600, font_size=12)
    st.plotly_chart(fig_sankey, use_container_width=True)

else:
    st.info("Please upload the aggregated CSV file to view the dashboard.")
