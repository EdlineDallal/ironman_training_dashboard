import os
import io
import zipfile
import base64
import gzip
from analytics import prepare, pmc, weekly, compare_halves
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

st.set_page_config(page_title="IM 70.3 Training Dashboard", layout="wide", page_icon=os.path.join(BASE_DIR, "logo.png"))

# --- Load Data ---
CSV_PATH = os.path.join(BASE_DIR, "workouts.csv")
LATEST_PATH = os.path.join(BASE_DIR, "workouts_latest.b64")
upload = st.sidebar.file_uploader("Replace workouts export (CSV or ZIP)", type=["csv", "zip"])
if upload is not None:
    content = upload.getvalue()
    if upload.name.lower().endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            csv_names = [name for name in archive.namelist() if name.lower().endswith('workouts.csv')]
            if not csv_names:
                st.error("ZIP does not contain workouts.csv")
                st.stop()
            content = archive.read(csv_names[0])
    data_source = io.BytesIO(content)
else:
    # The latest export is stored losslessly as gzip + base64 to preserve all
    # TrainingPeaks CSV quoting, multiline descriptions, and Unicode.
    if os.path.exists(LATEST_PATH):
        with open(LATEST_PATH, "r", encoding="ascii") as latest_file:
            data_source = io.BytesIO(gzip.decompress(base64.b64decode(latest_file.read().strip())))
    else:
        data_source = CSV_PATH
try:
    raw_df = prepare(data_source)
except Exception as err:
    st.error(f"Could not load workout export: {err}")
    st.stop()

# Analytics: use actual workout data, not the retired race training plan.
perf = raw_df[raw_df.WorkoutDay.notna()].copy()
all_weeks = weekly(perf)
loads = pmc(perf)
week_options = all_weeks.index.sort_values(ascending=False).tolist() if not all_weeks.empty else []

def report_insights(week_start):
    week_end = week_start + pd.Timedelta(days=6)
    wd = perf[perf.WorkoutDay.between(week_start, week_end)]
    row = all_weeks.loc[week_start]
    reports = []
    missing=int(row.MissingTSS)
    if missing:
        reports.append(f"⚠️ {missing} completed workouts have no TSS. The weekly load and CTL/ATL/TSB estimates are **incomplete**.")
    du=int(row.PossibleDuplicates)
    if du:
        reports.append(f"⚠️ {du} same-day record(s) resemble plan/actual duplicates. They are excluded from adjusted TSS and require manual validation.")
    previous = week_start-pd.Timedelta(days=7)
    if previous in all_weeks.index:
        prev=all_weeks.loc[previous]
        hours_delta=row.Hours-prev.Hours
        reports.append(f"Training time changed by **{hours_delta:+.2f} h** versus the previous week ({prev.Hours:.2f} → {row.Hours:.2f} h).")
        if prev.MissingTSS==0 and missing==0:
            reports.append(f"Known TSS changed by **{row.KnownTSS-prev.KnownTSS:+.0f}** vs last week.")
    for sport in ['Swim','Bike','Run']:
        s=wd[wd.WorkoutType.eq(sport)]
        if s.empty: continue
        done=s.AdjustedHours.sum(); planned=s.PlannedDuration.sum()
        if planned>0:
            reports.append(f"**{sport}**: {done:.2f} of {planned:.2f} planned hours ({done/planned*100:.0f}%).")
    swims=wd[wd.WorkoutType.eq('Swim') & wd.DistanceInMeters.gt(0) & wd.ActualHours.gt(0)]
    if not swims.empty:
        long=swims.loc[swims.DistanceInMeters.idxmax()]
        pace=long.ActualHours*3600/(long.DistanceInMeters/100)
        reports.append(f"Longest recorded swim: **{long.DistanceKm:.2f} km** in {long.ActualHours*60:.0f} min (~{pace/60:.2f} min/100 m including recorded pauses).")
    if wd[wd.WorkoutType.eq('Bike')].HeartRateAverage.isna().any():
        reports.append("Some cycling records have no heart-rate data; do not interpret heart-rate drift or efficiency from this export.")
    return reports

# Lean dashboard: no hero title, no Overview or Training Plan.
st.markdown("""<style>
.block-container {padding-top: 0.65rem; padding-bottom: 2rem; max-width: 1440px;}
[data-testid="stMetric"] {padding: 0.6rem 0.85rem; border: 1px solid rgba(128,128,128,.2); border-radius: 10px;}
h1 {display:none;}
</style>""",unsafe_allow_html=True)
if week_options:
    w = st.sidebar.selectbox("Week (Sunday–Saturday)", week_options,
        format_func=lambda x: f"{x:%d %b %Y} – {(x+pd.Timedelta(days=6)):%d %b %Y}")
else:
    w = None
last_recorded_day = perf["WorkoutDay"].max() if not perf.empty else pd.NaT
if pd.notna(last_recorded_day):
    st.caption(f"📅 Analysis through {last_recorded_day:%d/%m/%Y}  ·  "
               + ("Uploaded workout export" if upload is not None else "Latest saved TrainingPeaks export"))
tab_week, tab_load, tab_perf = st.tabs([
    "📊 Weekly pulse", "💓 Load & recovery", "📈 Performance"
])

with tab_week:
    if w is not None:
        st.caption(f"Training week: {w:%d/%m/%Y} – {(w + pd.Timedelta(days=6)):%d/%m/%Y}")
        row = all_weeks.loc[w]
        p = all_weeks.loc[w-pd.Timedelta(days=7)] if w-pd.Timedelta(days=7) in all_weeks.index else None
        cols = st.columns(4)
        cols[0].metric("Training hours", f"{row.Hours:.1f} h",
            f"{row.Hours-p.Hours:+.1f} h vs prior week" if p is not None else None)
        cols[1].metric("Known TSS", f"{row.KnownTSS:.0f}",
            help="Lower bound if TSS is missing for completed workouts")
        cols[2].metric("Completed workouts", f"{int(row.Workouts-row.PossibleDuplicates)}")
        cols[3].metric("Missing TSS", f"{int(row.MissingTSS)}")
        sport_cols = st.columns(3)
        for col, sport in zip(sport_cols, ["Swim","Bike","Run"]):
            col.metric(f"{sport} distance",f"{row[sport+'Km']:.1f} km")
        if row.MissingTSS:
            st.caption(f"⚠️ {int(row.MissingTSS)} completed workouts without TSS; load metrics are incomplete.")
        left,right=st.columns([1.3,1])
        with left:
            recent=all_weeks.tail(10)
            fig=go.Figure()
            fig.add_bar(x=recent.index,y=recent.Hours,name="Completed hours",marker_color="#3285a8")
            fig.update_layout(title="Weekly training volume",template="plotly_white",height=320,
                margin=dict(l=10,r=10,t=48,b=10),yaxis_title="Hours",showlegend=False)
            st.plotly_chart(fig,use_container_width=True)
        with right:
            wd=perf[perf.WorkoutDay.between(w,w+pd.Timedelta(days=6)) & ~perf.PossibleDuplicate]
            by_sport=wd.groupby("WorkoutType",as_index=False)["AdjustedHours"].sum()
            fig=go.Figure(go.Bar(x=by_sport.WorkoutType,y=by_sport.AdjustedHours,
                marker_color="#63a3a0"))
            fig.update_layout(title="Hours by discipline",template="plotly_white",height=320,
                margin=dict(l=10,r=10,t=48,b=10),yaxis_title="Hours")
            st.plotly_chart(fig,use_container_width=True)
        st.subheader("Coach insights")
        for note in report_insights(w): st.markdown("- "+note)
        with st.expander("Workout records for selected week"):
            st.dataframe(wd[["WorkoutDay","WorkoutType","Title","AdjustedHours","DistanceKm",
                "HeartRateAverage","PowerAverage","IF","TSS","MissingTSS"]],hide_index=True,use_container_width=True)
    else:
        st.info("No workout dates available.")

with tab_load:
    st.caption("Training load estimates and recovery trends")
    st.caption("CTL (42-day exponential), ATL (7-day exponential), TSB = prior-day CTL − ATL. 28-day CTL change included. Estimates are affected by missing TSS and the unknown pre-export load history.")
    if not loads.empty:
        end=loads.iloc[-1]
        z=st.columns(4)
        z[0].metric('CTL estimate',f"{end.CTL:.1f}")
        z[1].metric('ATL estimate',f"{end.ATL:.1f}")
        z[2].metric('TSB estimate',f"{end.TSB:.1f}" if pd.notna(end.TSB) else 'N/A')
        z[3].metric('CTL change / 28d',f"{end.CTL_28d_change:+.1f}" if pd.notna(end.CTL_28d_change) else 'N/A')
        chart=go.Figure()
        for name in ['CTL','ATL','TSB']:
            chart.add_scatter(x=loads.index,y=loads[name],mode='lines',name=name)
        chart.update_layout(title='Daily training load | adjusted TSS',template='plotly_white',hovermode='x unified')
        st.plotly_chart(chart,use_container_width=True)
        st.plotly_chart(go.Figure(data=[go.Bar(x=loads.index,y=loads.TSS,name='Recorded TSS')]).update_layout(title='Daily known TSS (missing TSS is not zero)',template='plotly_white'),use_container_width=True)
        st.warning(f"{int(loads.iloc[-7:].MissingTSS.sum())} unscored workouts in the past seven days. Treat fitness/form levels as indicative, not exact.")
    with st.expander('Garmin / wellness diary (optional)'):
        st.caption('The workouts export has no HRV, resting HR, sleep, or Body Battery. Upload a wellness CSV or enter values and download it to keep the changes.')
        wellness_path=os.path.join(BASE_DIR,'wellness.csv')
        wellness_up=st.file_uploader('Wellness CSV: Date, HRV, RestingHR, SleepHours, BodyBattery, Notes',type=['csv'],key='wellness_upload')
        try:
            wellness=pd.read_csv(wellness_up if wellness_up is not None else wellness_path)
        except Exception:
            wellness=pd.DataFrame(columns=['Date','HRV','RestingHR','SleepHours','BodyBattery','Notes'])
        expected=['Date','HRV','RestingHR','SleepHours','BodyBattery','Notes']
        for field in expected:
            if field not in wellness: wellness[field]=np.nan
        new_w=st.data_editor(wellness[expected],num_rows='dynamic',use_container_width=True,key='wellness_editor')
        st.download_button('Download wellness CSV',new_w.to_csv(index=False).encode('utf-8-sig'),file_name='wellness.csv',mime='text/csv')
        if len(new_w):
            wm=new_w.copy();wm['Date']=pd.to_datetime(wm.Date,errors='coerce')
            for k in ['HRV','RestingHR','SleepHours','BodyBattery']:
                wm[k]=pd.to_numeric(wm[k],errors='coerce')
            wm=wm.dropna(subset=['Date']).sort_values('Date')
            if not wm.empty:
                fig=go.Figure()
                for name in ['HRV','RestingHR','SleepHours','BodyBattery']:
                    if wm[name].notna().any():fig.add_scatter(x=wm.Date,y=wm[name],mode='lines+markers',name=name)
                fig.update_layout(template='plotly_white',title='Recovery trends (different units; compare each metric to its own baseline)')
                st.plotly_chart(fig,use_container_width=True)
                if len(wm)>=7:
                    st.info('Check persistent changes relative to your individual baseline, alongside fatigue, subjective feeling and training load; a single reading is not decisive.')
    

with tab_perf:
    st.caption('Compare trends and inspect data quality')
    st.caption('Session averages are not within-session drift. For NP, VI, EF, hill segments and cardiac drift upload actual FIT/TCX time-series in a future extension.')
    valid=perf[(perf.ActualHours>0) & ~perf.PossibleDuplicate].copy()
    sport=st.selectbox('Discipline',['Bike','Run','Swim'],key='sport_perf')
    sample=valid[valid.WorkoutType.eq(sport)].copy()
    if not sample.empty:
        if sport=='Run':
            sample['PaceMin1000']=(sample.ActualHours*60/sample.DistanceKm).where(sample.DistanceKm.gt(0))
            sample.loc[~sample.PaceMin1000.between(2.5,15),'PaceMin1000']=np.nan
            metrics=['PaceMin1000','HeartRateAverage','CadenceAverage']
            labels=['Running pace (min/km)','Average heart rate (bpm)','Cadence']
        elif sport=='Swim':
            sample['PaceMin100']=(sample.ActualHours*60/(sample.DistanceKm*10)).where(sample.DistanceKm.gt(0))
            sample.loc[~sample.PaceMin100.between(.7,8),'PaceMin100']=np.nan
            metrics=['PaceMin100','HeartRateAverage']
            labels=['Swim elapsed pace (min/100m)','Average heart rate (bpm)']
        else:
            metrics=['PowerAverage','HeartRateAverage','IF','CadenceAverage']
            labels=['Average power (W)','Average heart rate (bpm)','IF','Cadence']
        chosen=st.selectbox('Metric',metrics,format_func=lambda x:labels[metrics.index(x)])
        fig=go.Figure()
        fig.add_scatter(x=sample.WorkoutDay,y=sample[chosen],mode='lines+markers',customdata=sample.Title,hovertemplate='%{x|%d %b}: %{y:.2f}<br>%{customdata}<extra></extra>')
        fig.update_layout(template='plotly_white',title=f'{sport}: {labels[metrics.index(chosen)]}',xaxis_title='Date')
        if chosen.startswith('Pace'):fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig,use_container_width=True)
        with st.expander('Workout details'):
            st.dataframe(sample[['WorkoutDay','Title','ActualHours','DistanceKm','PowerAverage','HeartRateAverage','CadenceAverage','IF','ValidTSS','Rpe','Feeling']],hide_index=True,use_container_width=True)
    with st.expander('Data-quality flags / records requiring review'):
        flags=perf[(perf.MissingTSS | perf.PossibleDuplicate | (perf.ActualHours.gt(0) & perf.WorkoutType.eq('Bike') & perf.PowerAverage.isna()))].copy()
        if len(flags):
            st.dataframe(flags[['WorkoutDay','WorkoutType','Title','ActualHours','DistanceKm','TSS','MissingTSS','PossibleDuplicate','PowerAverage','HeartRateAverage']],hide_index=True,use_container_width=True)
    st.caption('Interpret suspicious large running PowerAverage/PowerMax values and device elevation anomalies cautiously. FTP/weight are not validated in this export.')
