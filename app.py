import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
st.set_page_config(page_title="IM 70.3 Training Dashboard", layout="wide", page_icon="logo.png")

col_logo, col_title = st.columns([0.05, 0.95])
with col_logo:
    st.image("logo.png", width=55)
with col_title:
    st.markdown("<h1 style='margin: 0;'>IRONMAN 70.3 Training Board</h1>", unsafe_allow_html=True)

# --- Load Data ---
#CSV_PATH = "/Users/ed9868/Downloads/workouts.csv"
#CSV_PATH = "workouts.csv"
@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    selected_columns = [
        'Title', 'WorkoutType', 'WorkoutDay', 'PlannedDuration', 'Rpe', 'Feeling', 'TSS', 'IF',
        'HeartRateAverage', 'DistanceInMeters', 'PlannedDistanceInMeters',
        'PowerAverage', 'TimeTotalInHours', 'CadenceAverage'
    ]
    df_sel = df[selected_columns].copy()
    df_sel['WorkoutDay'] = pd.to_datetime(df_sel['WorkoutDay'], errors='coerce')
    df_sel.insert(df_sel.columns.get_loc('WorkoutDay') + 1, 'DayOfWeek', df_sel['WorkoutDay'].dt.day_name())
    for col in ['TSS', 'IF', 'HeartRateAverage', 'DistanceInMeters', 'PlannedDistanceInMeters',
                'PowerAverage', 'TimeTotalInHours', 'CadenceAverage', 'PlannedDuration']:
        df_sel[col] = pd.to_numeric(df_sel[col], errors='coerce')
    return df_sel

df_selected = load_data(CSV_PATH)
df_selected = df_selected[df_selected['WorkoutType'].isin(['Swim', 'Run', 'Bike', 'Strength', 'Day Off'])].copy()

# --- Sidebar ---
st.sidebar.header("Filters")
workout_types = ['Swim', 'Run', 'Bike', 'Strength', 'Day Off']
selected_types = st.sidebar.pills("Workout Types", workout_types, selection_mode="multi", default=workout_types)

df_filtered = df_selected[
    df_selected['WorkoutType'].isin(selected_types)
].copy()

# --- Duration formatting helper ---
def fmt_hhmm(h):
    if pd.isna(h) or h == 0:
        return '0:00'
    sign = '-' if h < 0 else ''
    ah = abs(h)
    return f"{sign}{int(ah)}:{int(round((ah % 1) * 60)):02d}"

# =====================================================================
# Shared data: Training Plan (used by ATP + Discipline tabs)
# =====================================================================
race_date = pd.Timestamp('2026-09-20')
coach_plan = [
    ('2026-05-31', '2026-06-06', 'Base 1 - Week 1', 12.25),
    ('2026-06-07', '2026-06-13', 'Base 1 - Week 2', 7.25),
    ('2026-06-14', '2026-06-20', 'Base 1 - Week 4', 10.75),
    ('2026-06-21', '2026-06-27', 'Base 2 - Week 1', 13.0),
    ('2026-06-28', '2026-07-04', 'Base 2 - Week 2', 7.25),
    ('2026-07-05', '2026-07-11', 'Base 2 - Week 4', 11.75),
    ('2026-07-12', '2026-07-18', 'Base 3 - Week 1', 13.75),
    ('2026-07-19', '2026-07-25', 'Base 3 - Week 2', 15.25),
    ('2026-07-26', '2026-08-01', 'Base 3 - Week 3', 7.25),
    ('2026-08-02', '2026-08-08', 'Base 3 - Week 4', 13.0),
    ('2026-08-09', '2026-08-15', 'Build 1 - Week 1', 13.0),
    ('2026-08-16', '2026-08-22', 'Build 1 - Week 2', 7.25),
    ('2026-08-23', '2026-08-29', 'Build 1 - Week 4', 13.25),
    ('2026-08-30', '2026-09-05', 'Build 2 - Week 1', 12.25),
    ('2026-09-06', '2026-09-12', 'Build 2 - Week 2', 7.25),
    ('2026-09-13', '2026-09-19', 'Build 2 - Week 4', 7.25),
    ('2026-09-20', '2026-09-26', 'Race - 20/09', 0),
]

pre_rows = []
current = pd.Timestamp('2026-02-02')
base1_start = pd.Timestamp('2026-05-31')
while current + pd.Timedelta(days=6) < base1_start:
    week_end = current + pd.Timedelta(days=6)
    wte = int((race_date - current).days // 7)
    pre_rows.append((current, week_end, wte, 'Preparation', 0))
    current += pd.Timedelta(days=7)

all_rows = pre_rows + [
    (pd.Timestamp(s), pd.Timestamp(e), int((race_date - pd.Timestamp(s)).days // 7), p, h)
    for s, e, p, h in coach_plan
]

df_plan = pd.DataFrame(all_rows, columns=['WeekStart', 'WeekEnd', 'WeeksToEvent', 'Phase', 'CoachPlan'])
df_plan['WeekLabel'] = df_plan['WeekStart'].dt.strftime('%d/%m') + ' - ' + df_plan['WeekEnd'].dt.strftime('%d/%m')

df_actual = df_selected.dropna(subset=['WorkoutDay']).copy()
df_actual_srb = df_actual[df_actual['WorkoutType'].isin(['Swim', 'Run', 'Bike'])].copy()

planned_hrs, completed_hrs = [], []
for _, row in df_plan.iterrows():
    mask = (df_actual_srb['WorkoutDay'] >= row['WeekStart']) & (df_actual_srb['WorkoutDay'] <= row['WeekEnd'])
    planned_hrs.append(round(df_actual_srb.loc[mask, 'PlannedDuration'].sum(), 2))
    completed_hrs.append(round(df_actual_srb.loc[mask, 'TimeTotalInHours'].sum(), 2))

df_plan['Planned (hrs)'] = planned_hrs
df_plan['Completed (hrs)'] = completed_hrs
df_plan['PhaseGroup'] = df_plan['Phase'].str.extract(r'^(Preparation|Base \d|Build \d|Race)')

for sport in ['Swim', 'Run', 'Bike']:
    p_list, c_list = [], []
    df_sport = df_actual_srb[df_actual_srb['WorkoutType'] == sport]
    for _, row in df_plan.iterrows():
        mask = (df_sport['WorkoutDay'] >= row['WeekStart']) & (df_sport['WorkoutDay'] <= row['WeekEnd'])
        p_list.append(round(df_sport.loc[mask, 'PlannedDuration'].sum(), 2))
        c_list.append(round(df_sport.loc[mask, 'TimeTotalInHours'].sum(), 2))
    df_plan[f'{sport} Planned'] = p_list
    df_plan[f'{sport} Completed'] = c_list
    df_plan[f'{sport} Diff'] = df_plan[f'{sport} Completed'] - df_plan[f'{sport} Planned']

# =====================================================================
# TAB LAYOUT
# =====================================================================
df_plan_coach = df_plan[df_plan['PhaseGroup'] != 'Preparation'].copy().reset_index(drop=True)

tab1, tab2, tab1b, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview", "🏋️ Training Plan",
    "📊 Overview (Coach)",
    "🏊🚴🏃 Discipline Breakdown",
    "📈 TSS Analysis", "📋 Weekly Summary", "📋 Raw Data"
])

# =====================================================================
# TAB 1: Weekly Summary
# =====================================================================
with tab1:
    # ATP Chart (landing view)
    st.subheader("ATP — Planned vs Completed Hours")
    total_planned = df_plan['Planned (hrs)'].sum()
    total_coach = df_plan['CoachPlan'].sum()
    total_completed = df_plan['Completed (hrs)'].sum()

    # TrainingPeaks-style phase colors: (coach/light, planned/mid, completed/dark)
    phase_bar_colors = {
        'Preparation': ('#c0c0c0', '#999999', '#6b6b6b'),
        'Base 1':      ('#b0d4f1', '#6baadc', '#3a7cbd'),
        'Base 2':      ('#8dc4e8', '#4a9dcf', '#1a72a8'),
        'Base 3':      ('#6ba7d0', '#2e7eb5', '#0e4f7a'),
        'Build 1':     ('#a8e6a1', '#5cc455', '#2e9e28'),
        'Build 2':     ('#8fd48a', '#4cb848', '#2a8a26'),
        'Race':        ('#f5a675', '#e8752a', '#c85a10'),
    }
    phase_band_colors = {
        'Preparation': '#9e9e9e',
        'Base 1': '#6baadc', 'Base 2': '#4a9dcf', 'Base 3': '#2e7eb5',
        'Build 1': '#5cc455', 'Build 2': '#4cb848',
        'Race': '#e8752a',
    }

    coach_fmt = df_plan['CoachPlan'].apply(fmt_hhmm)
    planned_fmt = df_plan['Planned (hrs)'].apply(fmt_hhmm)
    completed_fmt = df_plan['Completed (hrs)'].apply(fmt_hhmm)

    # Assign per-bar colors based on phase
    coach_colors = [phase_bar_colors.get(pg, ('#ccc','#999','#666'))[0] for pg in df_plan['PhaseGroup']]
    planned_colors = [phase_bar_colors.get(pg, ('#ccc','#999','#666'))[1] for pg in df_plan['PhaseGroup']]
    completed_colors = [phase_bar_colors.get(pg, ('#ccc','#999','#666'))[2] for pg in df_plan['PhaseGroup']]

    fig_atp = go.Figure()
    fig_atp.add_trace(go.Bar(x=df_plan['WeekLabel'], y=df_plan['CoachPlan'],
        name='Coach Plan (Kony)', marker_color=coach_colors, opacity=0.7,
        customdata=coach_fmt, hovertemplate='%{x}<br>Coach Plan: %{customdata}<extra></extra>'))
    fig_atp.add_trace(go.Bar(x=df_plan['WeekLabel'], y=df_plan['Planned (hrs)'],
        name='Planned', marker_color=planned_colors, opacity=0.85,
        customdata=planned_fmt, hovertemplate='%{x}<br>Planned: %{customdata}<extra></extra>'))
    fig_atp.add_trace(go.Bar(x=df_plan['WeekLabel'], y=df_plan['Completed (hrs)'],
        name='Completed', marker_color=completed_colors, opacity=0.9,
        customdata=completed_fmt, hovertemplate='%{x}<br>Completed: %{customdata}<extra></extra>'))

    # Phase band labels below bars
    phase_weeks = df_plan[df_plan['PhaseGroup'].notna() & (df_plan['PhaseGroup'] != '')]
    if not phase_weeks.empty:
        phases = phase_weeks.groupby('PhaseGroup', sort=False).agg(
            first_idx=('WeekLabel', 'first'), last_idx=('WeekLabel', 'last')).reset_index()
        week_labels = df_plan['WeekLabel'].tolist()
        for _, phase in phases.iterrows():
            i0 = week_labels.index(phase['first_idx'])
            i1 = week_labels.index(phase['last_idx'])
            color = phase_band_colors.get(phase['PhaseGroup'], '#ddd')
            fig_atp.add_shape(type='rect', x0=i0-0.4, x1=i1+0.4, y0=-1.8, y1=-0.3,
                fillcolor=color, line=dict(color=color, width=1), xref='x', yref='y', layer='above')
            fig_atp.add_annotation(x=(i0+i1)/2, y=-1.05, text=f"<b>{phase['PhaseGroup']}</b>",
                showarrow=False, font=dict(size=9, color='white'), xref='x', yref='y')

    max_y = max(df_plan['CoachPlan'].max(), df_plan['Planned (hrs)'].max(), df_plan['Completed (hrs)'].max())
    fig_atp.update_layout(
        title=f'ATP — Coach: {fmt_hhmm(total_coach)} | Planned: {fmt_hhmm(total_planned)} | Completed: {fmt_hhmm(total_completed)}',
        barmode='overlay', xaxis_title='Week', yaxis_title='Hours',
        template='plotly_white', height=550, xaxis=dict(tickangle=-45),
        yaxis=dict(range=[-2.5, max_y + 3]),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0))
    event = st.plotly_chart(fig_atp, use_container_width=True, on_select="rerun", key="atp_click")

    # Show discipline breakdown on bar click
    if event and event.selection and event.selection.points:
        week_label = event.selection.points[0]['x']
        week_row = df_plan[df_plan['WeekLabel'] == week_label]
        if not week_row.empty:
            row = week_row.iloc[0]
            st.markdown(f"### 📅 {row['WeekLabel']}  —  {row['Phase']}")
            sport_lines = []
            for sport in ['Swim', 'Run', 'Bike']:
                p = row[f'{sport} Planned']
                c = row[f'{sport} Completed']
                d = row[f'{sport} Diff']
                if abs(d) >= 0.01 or p > 0 or c > 0:
                    icon = '✅' if abs(d) < 0.05 else ('🔺' if d > 0 else '🔻')
                    d_str = f"+{fmt_hhmm(d)}" if d > 0 else fmt_hhmm(d)
                    sport_lines.append(f"**{sport}**: Planned **{fmt_hhmm(p)}** → Completed **{fmt_hhmm(c)}** ({d_str}) {icon}")
            if sport_lines:
                for line in sport_lines:
                    st.markdown(line)
                total_diff = row['Completed (hrs)'] - row['Planned (hrs)']
                td_str = f"+{fmt_hhmm(total_diff)}" if total_diff > 0 else fmt_hhmm(total_diff)
                st.markdown(f"**Total**: Planned **{fmt_hhmm(row['Planned (hrs)'])}** → Completed **{fmt_hhmm(row['Completed (hrs)'])}** ({td_str})")
            else:
                st.info("No Swim/Run/Bike data for this week.")

# =====================================================================
# TAB 5: Weekly Summary
# =====================================================================
with tab5:
    st.header("Weekly Summary (Monday–Sunday)")
    df_work = df_filtered.dropna(subset=['WorkoutDay']).copy()
    df_work['WeekStart'] = df_work['WorkoutDay'].dt.to_period('W-SUN').apply(lambda p: p.start_time)
    df_work['WeekLabel'] = df_work['WeekStart'].dt.strftime('%b %d') + ' - ' + (df_work['WeekStart'] + pd.Timedelta(days=6)).dt.strftime('%b %d')
    df_work['DistanceKm'] = df_work['DistanceInMeters'] / 1000
    df_work['Hours'] = df_work['TimeTotalInHours']
    df_work['PlannedDistKm'] = df_work['PlannedDistanceInMeters'] / 1000
    df_work['PlannedDur'] = df_work['PlannedDuration']

    swim_weekly = df_work[df_work['WorkoutType'] == 'Swim'].groupby('WeekLabel')['DistanceKm'].sum()
    run_data = df_work[df_work['WorkoutType'] == 'Run'].groupby('WeekLabel')
    run_dist = run_data['DistanceKm'].sum()
    run_planned_dist = run_data['PlannedDistKm'].sum()
    run_planned_dur = run_data['PlannedDur'].sum()
    bike_data = df_work[df_work['WorkoutType'] == 'Bike'].groupby('WeekLabel')
    bike_hours = bike_data['Hours'].sum()
    bike_planned_dur = bike_data['PlannedDur'].sum()
    tss_weekly = df_work.groupby('WeekLabel')['TSS'].sum()

    weekly_summary = pd.DataFrame({
        'Swim (km)': swim_weekly, 'Run (km)': run_dist,
        'Run Planned Dist (km)': run_planned_dist, 'Run Planned Dur (hrs)': run_planned_dur,
        'Bike (hrs)': bike_hours, 'Bike Planned Dur (hrs)': bike_planned_dur,
        'Total TSS': tss_weekly
    }).fillna(0)
    weekly_summary['Total TSS'] = weekly_summary['Total TSS'].round(0).astype(int)
    weekly_summary = weekly_summary.round(2)
    week_order = df_work.drop_duplicates('WeekLabel').sort_values('WeekStart').set_index('WeekLabel').index
    weekly_summary = weekly_summary.reindex(week_order)
    for col in ['Run Planned Dur (hrs)', 'Bike (hrs)', 'Bike Planned Dur (hrs)']:
        weekly_summary[col] = weekly_summary[col].apply(fmt_hhmm)

    st.dataframe(weekly_summary, use_container_width=True)

    # Weekly TSS + Hours table
    st.subheader("Weekly TSS & Hours (Swim/Run/Bike)")
    df_tss = df_filtered.dropna(subset=['WorkoutDay']).copy()
    df_tss['WeekStart'] = df_tss['WorkoutDay'].dt.to_period('W-SUN').apply(lambda p: p.start_time)
    df_tss['WeekLabel'] = df_tss['WeekStart'].dt.strftime('%b %d') + ' - ' + (df_tss['WeekStart'] + pd.Timedelta(days=6)).dt.strftime('%b %d')
    df_srb = df_tss[df_tss['WorkoutType'].isin(['Swim', 'Run', 'Bike'])]
    hours_by_week = df_srb.groupby(['WeekStart', 'WeekLabel'])['TimeTotalInHours'].sum().reset_index()
    hours_by_week = hours_by_week.sort_values('WeekStart').set_index('WeekLabel').drop(columns='WeekStart')
    tss_by_week = df_tss.groupby(['WeekStart', 'WeekLabel'])['TSS'].sum().reset_index()
    tss_by_week = tss_by_week.sort_values('WeekStart').set_index('WeekLabel').drop(columns='WeekStart')
    tss_by_week['TSS'] = tss_by_week['TSS'].round(0).astype(int)
    tss_by_week['Total Hours (S/R/B)'] = hours_by_week['TimeTotalInHours'].apply(fmt_hhmm)
    st.dataframe(tss_by_week, use_container_width=True)

# =====================================================================
# TAB 4: TSS Analysis
# =====================================================================
with tab4:
    st.header("Performance Management Chart (PMC)")
    df_pmc = df_selected.dropna(subset=['WorkoutDay']).copy()
    df_pmc['TSS'] = df_pmc['TSS'].fillna(0)
    daily_tss = df_pmc.groupby('WorkoutDay')['TSS'].sum().reset_index()
    daily_tss = daily_tss.set_index('WorkoutDay').asfreq('D', fill_value=0).reset_index()
    daily_tss['CTL'] = daily_tss['TSS'].ewm(span=42, adjust=False).mean().round(0)
    daily_tss['ATL'] = daily_tss['TSS'].ewm(span=7, adjust=False).mean().round(0)
    daily_tss['TSB'] = (daily_tss['CTL'].shift(1) - daily_tss['ATL'].shift(1)).round(0)
    daily_tss['DayLabel'] = daily_tss['WorkoutDay'].dt.strftime('%A, %b %d')

    fig_pmc = go.Figure()
    fig_pmc.add_trace(go.Scatter(x=daily_tss['WorkoutDay'], y=daily_tss['CTL'],
        name='Fitness (CTL)', mode='lines', fill='tozeroy',
        line=dict(color='#2980b9', width=2), fillcolor='rgba(52,152,219,0.25)',
        customdata=daily_tss['DayLabel'],
        hovertemplate='%{customdata}<br>CTL: %{y:.0f}<extra></extra>'))
    fig_pmc.add_trace(go.Scatter(x=daily_tss['WorkoutDay'], y=daily_tss['ATL'],
        name='Fatigue (ATL)', mode='lines', line=dict(color='#e84393', width=2),
        customdata=daily_tss['DayLabel'],
        hovertemplate='%{customdata}<br>ATL: %{y:.0f}<extra></extra>'))
    fig_pmc.add_trace(go.Scatter(x=daily_tss['WorkoutDay'], y=daily_tss['TSB'],
        name='Form (TSB)', mode='lines', line=dict(color='#f39c12', width=2),
        customdata=daily_tss['DayLabel'],
        hovertemplate='%{customdata}<br>TSB: %{y:.0f}<extra></extra>'))
    fig_pmc.add_trace(go.Scatter(x=daily_tss['WorkoutDay'], y=daily_tss['TSS'],
        name='Stress (TSS)', mode='markers', marker=dict(color='#8b0000', size=4, opacity=0.6),
        customdata=daily_tss['DayLabel'],
        hovertemplate='%{customdata}<br>TSS: %{y:.0f}<extra></extra>'))
    fig_pmc.add_hline(y=0, line_dash='dash', line_color='gray', line_width=0.5)
    fig_pmc.update_layout(title='Performance Management Chart', xaxis_title='Date', yaxis_title='TSS / Load',
        template='plotly_white', height=500, hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0))
    st.plotly_chart(fig_pmc, use_container_width=True)

    # Weekly TSS line
    st.subheader("Weekly TSS Trend")
    df_wtss = df_selected.dropna(subset=['WorkoutDay']).copy()
    df_wtss['WeekStart'] = df_wtss['WorkoutDay'].dt.to_period('W-SUN').apply(lambda p: p.start_time)
    weekly_tss_plot = df_wtss.groupby('WeekStart')['TSS'].sum().round(0).reset_index()
    weekly_tss_plot.columns = ['WeekStart', 'TSS']

    fig_wtss = go.Figure()
    fig_wtss.add_trace(go.Scatter(
        x=weekly_tss_plot['WeekStart'], y=weekly_tss_plot['TSS'],
        mode='lines+markers+text', text=weekly_tss_plot['TSS'].astype(int).astype(str),
        textposition='top center', textfont=dict(size=9),
        line=dict(color='#e74c3c', width=2), marker=dict(size=8, color='#e74c3c')))
    fig_wtss.update_layout(title='Weekly TSS (Monday–Sunday)', xaxis_title='Week Starting',
        yaxis_title='Total TSS', template='plotly_white', height=400, hovermode='x unified')
    st.plotly_chart(fig_wtss, use_container_width=True)

# =====================================================================
# TAB 2: Training Plan
# =====================================================================
with tab2:
    st.header("Annual Training Plan")

    # Phase colors for table
    period_colors = {
        'Preparation': '#9e9e9e',
        'Base 1': '#6baadc', 'Base 2': '#4a9dcf', 'Base 3': '#2e7eb5',
        'Build 1': '#5cc455', 'Build 2': '#4cb848',
        'Race': '#e8752a'
    }
    period_text_colors = {
        'Preparation': '#fff', 'Base 1': '#fff', 'Base 2': '#fff', 'Base 3': '#fff',
        'Build 1': '#fff', 'Build 2': '#fff', 'Race': '#fff'
    }

    def hrs_to_hhmm(h):
        if pd.isna(h) or h == 0:
            return ''
        return f"{int(h)}:{int((h % 1) * 60):02d}"

    # Build HTML table
    html_rows = []
    prev_month = None
    for _, row in df_plan.iterrows():
        month = row['WeekStart'].strftime('%B')
        if month != prev_month:
            html_rows.append(f'<tr><td colspan="5" style="background:#2c3e50;color:#fff;font-weight:bold;padding:6px 10px;font-size:13px;">{month}</td></tr>')
            prev_month = month

        phase = row['Phase']
        phase_group = row['PhaseGroup'] if pd.notna(row['PhaseGroup']) else ''
        bg = period_colors.get(phase_group, '#eee')
        fg = period_text_colors.get(phase_group, '#333')

        coach_hrs = hrs_to_hhmm(row['CoachPlan'])
        completed_hrs_val = hrs_to_hhmm(row['Completed (hrs)'])
        completed_style = 'font-weight:bold;' if row['Completed (hrs)'] > 0 else ''

        html_rows.append(f'''<tr>
            <td style="padding:5px 10px;border-bottom:1px solid #eee;">{row['WeekLabel']}</td>
            <td style="padding:5px 10px;border-bottom:1px solid #eee;text-align:center;">{row['WeeksToEvent']}</td>
            <td style="padding:5px 10px;border-bottom:1px solid #eee;background:{bg};color:{fg};font-weight:600;font-size:12px;white-space:nowrap;">{phase}</td>
            <td style="padding:5px 10px;border-bottom:1px solid #eee;text-align:center;">{coach_hrs}</td>
            <td style="padding:5px 10px;border-bottom:1px solid #eee;text-align:center;{completed_style}">{completed_hrs_val}</td>
        </tr>''')

    table_html = f'''
    <div style="max-width:800px;">
    <table style="width:100%;border-collapse:collapse;font-family:sans-serif;font-size:13px;">
        <thead>
            <tr style="background:#34495e;color:#fff;">
                <th style="padding:8px 10px;text-align:left;">Week</th>
                <th style="padding:8px 10px;text-align:center;">Weeks to Event</th>
                <th style="padding:8px 10px;text-align:left;">Period</th>
                <th style="padding:8px 10px;text-align:center;">Hours</th>
                <th style="padding:8px 10px;text-align:center;">Completed</th>
            </tr>
        </thead>
        <tbody>
            {''.join(html_rows)}
        </tbody>
    </table>
    </div>
    '''
    st.markdown(table_html, unsafe_allow_html=True)



# =====================================================================
# TAB 3: Discipline Breakdown
# =====================================================================
with tab3:
    st.header("Planned vs Completed by Discipline")

    # Discipline breakdown table
    disc_cols = ['WeekLabel', 'WeeksToEvent', 'Phase',
                 'Swim Planned', 'Swim Completed', 'Swim Diff',
                 'Run Planned', 'Run Completed', 'Run Diff',
                 'Bike Planned', 'Bike Completed', 'Bike Diff']
    hour_cols = ['Swim Planned', 'Swim Completed', 'Swim Diff',
                 'Run Planned', 'Run Completed', 'Run Diff',
                 'Bike Planned', 'Bike Completed', 'Bike Diff']
    st.dataframe(df_plan[disc_cols].style.map(
        lambda v: 'color: green' if isinstance(v, (int, float)) and v > 0 else ('color: red' if isinstance(v, (int, float)) and v < 0 else ''),
        subset=['Swim Diff', 'Run Diff', 'Bike Diff']
    ).format({c: fmt_hhmm for c in hour_cols}), use_container_width=True)

    # Discipline charts — one per sport
    sports = ['Swim', 'Run', 'Bike']
    colors_p = ['#a9cce3', '#a9dfbf', '#f5cba7']
    colors_c = ['#2980b9', '#27ae60', '#e67e22']

    for idx, sport in enumerate(sports):
        st.subheader(f"{sport} — Planned vs Completed (hrs)")
        p_fmt = df_plan[f'{sport} Planned'].apply(fmt_hhmm).values
        c_fmt = df_plan[f'{sport} Completed'].apply(fmt_hhmm).values
        custom = list(zip(p_fmt, c_fmt))
        fig_sport = go.Figure()
        fig_sport.add_trace(go.Bar(
            x=df_plan['WeekLabel'], y=df_plan[f'{sport} Planned'],
            name='Planned', marker_color=colors_p[idx], opacity=0.8,
            customdata=custom,
            hovertemplate='%{x}<br>Planned: %{customdata[0]}<br>Completed: %{customdata[1]}<extra></extra>'
        ))
        fig_sport.add_trace(go.Bar(
            x=df_plan['WeekLabel'], y=df_plan[f'{sport} Completed'],
            name='Completed', marker_color=colors_c[idx], opacity=0.9,
            customdata=custom,
            hovertemplate='%{x}<br>Planned: %{customdata[0]}<br>Completed: %{customdata[1]}<extra></extra>'
        ))
        fig_sport.update_layout(
            barmode='group', template='plotly_white', height=350,
            xaxis=dict(tickangle=-45), yaxis_title='Hours',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
            bargap=0.3, bargroupgap=0.1, margin=dict(b=100)
        )
        st.plotly_chart(fig_sport, use_container_width=True)

# =====================================================================
# TAB 1b: Overview (Coach) — without Preparation
# =====================================================================
with tab1b:
    st.subheader("ATP — Coach Plan Only (No Prep)")
    total_planned_c = df_plan_coach['Planned (hrs)'].sum()
    total_coach_c = df_plan_coach['CoachPlan'].sum()
    total_completed_c = df_plan_coach['Completed (hrs)'].sum()

    phase_bar_colors_c = {
        'Base 1':  ('#b0d4f1', '#6baadc', '#3a7cbd'),
        'Base 2':  ('#8dc4e8', '#4a9dcf', '#1a72a8'),
        'Base 3':  ('#6ba7d0', '#2e7eb5', '#0e4f7a'),
        'Build 1': ('#a8e6a1', '#5cc455', '#2e9e28'),
        'Build 2': ('#8fd48a', '#4cb848', '#2a8a26'),
        'Race':    ('#f5a675', '#e8752a', '#c85a10'),
    }
    phase_band_colors_c = {
        'Base 1': '#6baadc', 'Base 2': '#4a9dcf', 'Base 3': '#2e7eb5',
        'Build 1': '#5cc455', 'Build 2': '#4cb848',
        'Race': '#e8752a',
    }

    coach_fmt_c = df_plan_coach['CoachPlan'].apply(fmt_hhmm)
    planned_fmt_c = df_plan_coach['Planned (hrs)'].apply(fmt_hhmm)
    completed_fmt_c = df_plan_coach['Completed (hrs)'].apply(fmt_hhmm)

    coach_colors_c = [phase_bar_colors_c.get(pg, ('#ccc','#999','#666'))[0] for pg in df_plan_coach['PhaseGroup']]
    planned_colors_c = [phase_bar_colors_c.get(pg, ('#ccc','#999','#666'))[1] for pg in df_plan_coach['PhaseGroup']]
    completed_colors_c = [phase_bar_colors_c.get(pg, ('#ccc','#999','#666'))[2] for pg in df_plan_coach['PhaseGroup']]

    fig_atp_c = go.Figure()
    fig_atp_c.add_trace(go.Bar(x=df_plan_coach['WeekLabel'], y=df_plan_coach['CoachPlan'],
        name='Coach Plan (Kony)', marker_color=coach_colors_c, opacity=0.7,
        customdata=coach_fmt_c, hovertemplate='%{x}<br>Coach Plan: %{customdata}<extra></extra>'))
    fig_atp_c.add_trace(go.Bar(x=df_plan_coach['WeekLabel'], y=df_plan_coach['Planned (hrs)'],
        name='Planned', marker_color=planned_colors_c, opacity=0.85,
        customdata=planned_fmt_c, hovertemplate='%{x}<br>Planned: %{customdata}<extra></extra>'))
    fig_atp_c.add_trace(go.Bar(x=df_plan_coach['WeekLabel'], y=df_plan_coach['Completed (hrs)'],
        name='Completed', marker_color=completed_colors_c, opacity=0.9,
        customdata=completed_fmt_c, hovertemplate='%{x}<br>Completed: %{customdata}<extra></extra>'))

    phase_weeks_c = df_plan_coach[df_plan_coach['PhaseGroup'].notna() & (df_plan_coach['PhaseGroup'] != '')]
    if not phase_weeks_c.empty:
        phases_c = phase_weeks_c.groupby('PhaseGroup', sort=False).agg(
            first_idx=('WeekLabel', 'first'), last_idx=('WeekLabel', 'last')).reset_index()
        week_labels_c = df_plan_coach['WeekLabel'].tolist()
        for _, phase in phases_c.iterrows():
            i0 = week_labels_c.index(phase['first_idx'])
            i1 = week_labels_c.index(phase['last_idx'])
            color = phase_band_colors_c.get(phase['PhaseGroup'], '#ddd')
            fig_atp_c.add_shape(type='rect', x0=i0-0.4, x1=i1+0.4, y0=-1.8, y1=-0.3,
                fillcolor=color, line=dict(color=color, width=1), xref='x', yref='y', layer='above')
            fig_atp_c.add_annotation(x=(i0+i1)/2, y=-1.05, text=f"<b>{phase['PhaseGroup']}</b>",
                showarrow=False, font=dict(size=9, color='white'), xref='x', yref='y')

    max_y_c = max(df_plan_coach['CoachPlan'].max(), df_plan_coach['Planned (hrs)'].max(),
                  max(df_plan_coach['Completed (hrs)'].max(), 1))
    fig_atp_c.update_layout(
        title=f'ATP (Coach) — Coach: {fmt_hhmm(total_coach_c)} | Planned: {fmt_hhmm(total_planned_c)} | Completed: {fmt_hhmm(total_completed_c)}',
        barmode='overlay', xaxis_title='Week', yaxis_title='Hours',
        template='plotly_white', height=550, xaxis=dict(tickangle=-45),
        yaxis=dict(range=[-2.5, max_y_c + 3]),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0))
    event_c = st.plotly_chart(fig_atp_c, use_container_width=True, on_select="rerun", key="atp_click_coach")

    if event_c and event_c.selection and event_c.selection.points:
        week_label = event_c.selection.points[0]['x']
        week_row = df_plan_coach[df_plan_coach['WeekLabel'] == week_label]
        if not week_row.empty:
            row = week_row.iloc[0]
            st.markdown(f"### 📅 {row['WeekLabel']}  —  {row['Phase']}")
            sport_lines = []
            for sport in ['Swim', 'Run', 'Bike']:
                p = row[f'{sport} Planned']
                c = row[f'{sport} Completed']
                d = row[f'{sport} Diff']
                if abs(d) >= 0.01 or p > 0 or c > 0:
                    icon = '✅' if abs(d) < 0.05 else ('🔺' if d > 0 else '🔻')
                    d_str = f"+{fmt_hhmm(d)}" if d > 0 else fmt_hhmm(d)
                    sport_lines.append(f"**{sport}**: Planned **{fmt_hhmm(p)}** → Completed **{fmt_hhmm(c)}** ({d_str}) {icon}")
            if sport_lines:
                for line in sport_lines:
                    st.markdown(line)
                total_diff = row['Completed (hrs)'] - row['Planned (hrs)']
                td_str = f"+{fmt_hhmm(total_diff)}" if total_diff > 0 else fmt_hhmm(total_diff)
                st.markdown(f"**Total**: Planned **{fmt_hhmm(row['Planned (hrs)'])}** → Completed **{fmt_hhmm(row['Completed (hrs)'])}** ({td_str})")
            else:
                st.info("No Swim/Run/Bike data for this week.")

    # Training Plan table (coach only, no prep) — below the chart
    st.subheader("Training Plan — Coach Only")

    period_colors_c = {
        'Base 1': '#6baadc', 'Base 2': '#4a9dcf', 'Base 3': '#2e7eb5',
        'Build 1': '#5cc455', 'Build 2': '#4cb848',
        'Race': '#e8752a'
    }

    html_rows_c = []
    prev_month_c = None
    for _, row in df_plan_coach.iterrows():
        month = row['WeekStart'].strftime('%B')
        if month != prev_month_c:
            html_rows_c.append(f'<tr><td colspan="5" style="background:#2c3e50;color:#fff;font-weight:bold;padding:6px 10px;font-size:13px;">{month}</td></tr>')
            prev_month_c = month

        phase = row['Phase']
        phase_group = row['PhaseGroup'] if pd.notna(row['PhaseGroup']) else ''
        bg = period_colors_c.get(phase_group, '#eee')

        coach_hrs = fmt_hhmm(row['CoachPlan']) if row['CoachPlan'] else ''
        completed_hrs_val = fmt_hhmm(row['Completed (hrs)']) if row['Completed (hrs)'] else ''
        completed_style = 'font-weight:bold;' if row['Completed (hrs)'] > 0 else ''

        html_rows_c.append(f'''<tr>
            <td style="padding:5px 10px;border-bottom:1px solid #eee;">{row['WeekLabel']}</td>
            <td style="padding:5px 10px;border-bottom:1px solid #eee;text-align:center;">{row['WeeksToEvent']}</td>
            <td style="padding:5px 10px;border-bottom:1px solid #eee;background:{bg};color:#fff;font-weight:600;font-size:12px;white-space:nowrap;">{phase}</td>
            <td style="padding:5px 10px;border-bottom:1px solid #eee;text-align:center;">{coach_hrs}</td>
            <td style="padding:5px 10px;border-bottom:1px solid #eee;text-align:center;{completed_style}">{completed_hrs_val}</td>
        </tr>''')

    table_html_c = f'''
    <div style="max-width:800px;">
    <table style="width:100%;border-collapse:collapse;font-family:sans-serif;font-size:13px;">
        <thead>
            <tr style="background:#34495e;color:#fff;">
                <th style="padding:8px 10px;text-align:left;">Week</th>
                <th style="padding:8px 10px;text-align:center;">Weeks to Event</th>
                <th style="padding:8px 10px;text-align:left;">Period</th>
                <th style="padding:8px 10px;text-align:center;">Hours</th>
                <th style="padding:8px 10px;text-align:center;">Completed</th>
            </tr>
        </thead>
        <tbody>
            {''.join(html_rows_c)}
        </tbody>
    </table>
    </div>
    '''
    st.markdown(table_html_c, unsafe_allow_html=True)

# =====================================================================
# TAB 6: Raw Data
# =====================================================================
with tab6:
    st.header("Raw Workout Data")
    st.dataframe(df_filtered, use_container_width=True)
    st.metric("Total Workouts", len(df_filtered))
