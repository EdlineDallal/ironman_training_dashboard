"""Training analytics for TrainingPeaks workout CSV exports.
Daily load estimates are only trustworthy with complete TSS and adequate history.
"""
import numpy as np
import pandas as pd

SPORTS = ['Swim', 'Bike', 'Run', 'Strength', 'Brick', 'Other', 'Walk', 'Day Off']

def prepare(csv_source):
    df = pd.read_csv(csv_source)
    for col in ['WorkoutDay','WorkoutType','Title']:
        if col not in df: raise ValueError(f'Missing required column: {col}')
    df['WorkoutDay'] = pd.to_datetime(df['WorkoutDay'], errors='coerce').dt.normalize()
    numeric = ['PlannedDuration','PlannedDistanceInMeters','DistanceInMeters','TimeTotalInHours','TSS','IF',
               'HeartRateAverage','PowerAverage','PowerMax','HeartRateMax','CadenceAverage','Rpe','Feeling', 'VelocityAverage']
    for c in numeric:
        if c not in df: df[c]=np.nan
        df[c]=pd.to_numeric(df[c],errors='coerce')
    # Athlete-confirmed TSS corrections for TrainingPeaks export records where TSS is blank.
    # Only fill a missing value on an exact date, sport and title match; never
    # overwrite measured TSS in a later export or add a second workout.
    df['TSSSource'] = np.where(df['TSS'].notna(), 'TrainingPeaks export', 'Missing')
    confirmed_tss = [
        ('2026-11-13', 'Merubah Climbs 3h | Israman Watts', 175.0),
        ('2026-11-14', 'Volume Ride 3h30 | 2x30 70.3 Watts', 164.0),
    ]
    normalized_titles = df['Title'].astype('string').str.strip().str.casefold()
    for date, title, tss in confirmed_tss:
        match = (df['WorkoutDay'].eq(pd.Timestamp(date)) &
                 df['WorkoutType'].eq('Bike') &
                 normalized_titles.eq(title.casefold()) &
                 df['TSS'].isna())
        if match.sum() == 1:
            df.loc[match, 'TSS'] = tss
            df.loc[match, 'TSSSource'] = 'Athlete-confirmed correction'
    df['DistanceKm'] = df['DistanceInMeters']/1000
    df['ActualHours'] = df['TimeTotalInHours'].fillna(0).clip(lower=0)
    df['WeekStart'] = df.WorkoutDay.dt.to_period('W-SAT').dt.start_time  # Sunday to Saturday
    # Conservative duplicate candidate: another same-day/sport activity has actual distance and sensors
    # and this record has neither distance, heart rate nor power, but has a matching planned duration.
    df['PossibleDuplicate'] = False
    for (_, _), group in df.groupby(['WorkoutDay','WorkoutType'],dropna=True):
        if len(group)<2: continue
        instrumented = group['DistanceInMeters'].notna() & (group['DistanceInMeters']>0)
        if not instrumented.any(): continue
        placeholder = (group['DistanceInMeters'].isna() & group['HeartRateAverage'].isna() &
                       group['PowerAverage'].isna() & group['PlannedDuration'].notna() &
                       (group['ActualHours']-group['PlannedDuration']).abs().lt(0.02))
        df.loc[group.index[placeholder], 'PossibleDuplicate']=True
    df['ValidTSS'] = df['TSS'].where(~df['PossibleDuplicate'])
    df['AdjustedHours'] = df['ActualHours'].where(~df['PossibleDuplicate'], 0)
    df['MissingTSS'] = (df.ActualHours>0) & df.ValidTSS.isna() & ~df.PossibleDuplicate
    return df.sort_values('WorkoutDay').reset_index(drop=True)

def pmc(df, days=42, short_days=7):
    valid=df.dropna(subset=['WorkoutDay']).copy()
    daily = valid.groupby('WorkoutDay').agg(TSS=('ValidTSS','sum'),Hours=('ActualHours','sum'),
                                            MissingTSS=('MissingTSS','sum')).sort_index()
    if daily.empty: return daily
    daily = daily.asfreq('D', fill_value=0)
    # TrainingPeaks-style exponentially weighted impulse response: 1-exp(-1/tau)
    # CTL and ATL start at zero because preceding history is unavailable in the export.
    for name,tau in [('CTL',days),('ATL',short_days)]:
        alpha=1-np.exp(-1/tau)
        daily[name]=daily['TSS'].ewm(alpha=alpha,adjust=False).mean()
        # Recalculate zero-initialized instead of initializing to first observed day.
        prev=0.0; out=[]
        for val in daily['TSS']:
            prev=prev+(val-prev)*alpha
            out.append(prev)
        daily[name]=out
    daily['TSB']=daily['CTL'].shift(1)-daily['ATL'].shift(1)
    daily['CTL_28d_change']=daily['CTL']-daily['CTL'].shift(28)
    daily['HistoryDays']=np.arange(1,len(daily)+1)
    daily['TSS_7d']=daily['TSS'].rolling(7,min_periods=1).sum()
    daily['MissingTSS_7d']=daily['MissingTSS'].rolling(7,min_periods=1).sum()
    daily['TSS_28d']=daily['TSS'].rolling(28,min_periods=1).sum()
    return daily

def weekly(df):
    d=df.dropna(subset=['WorkoutDay']).copy()
    return d.groupby('WeekStart').agg(Hours=('AdjustedHours','sum'),KnownTSS=('ValidTSS','sum'),
                                      MissingTSS=('MissingTSS','sum'),
                                      PossibleDuplicates=('PossibleDuplicate','sum'),
                                      Workouts=('WorkoutType','size'),SwimKm=('DistanceKm',lambda x: x[d.loc[x.index,'WorkoutType'].eq('Swim')].sum()),
                                      BikeKm=('DistanceKm',lambda x: x[d.loc[x.index,'WorkoutType'].eq('Bike')].sum()),
                                      RunKm=('DistanceKm',lambda x: x[d.loc[x.index,'WorkoutType'].eq('Run')].sum())).sort_index()

def compare_halves(df,sport='Bike'):
    """Compare first/second half of weekly sessions, not within-session drift."""
    v=df[(df.WorkoutType==sport)&df.ActualHours.gt(0)].copy()
    return v[['WorkoutDay','Title','ActualHours','PowerAverage','HeartRateAverage','CadenceAverage','IF','TSS','DistanceKm']]