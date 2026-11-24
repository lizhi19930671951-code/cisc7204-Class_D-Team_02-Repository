"""Date-level OLS, calendar-day HAC, prespecified sensitivity and figure data."""
from pathlib import Path
import argparse, json, math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
Z = 1.959963984540054

def design(d, spec="adjusted", case="group"):
    x = pd.DataFrame({"intercept": np.ones(len(d))}, index=d.index)
    if spec == "baseline":
        x["weekend"] = d.weekday.ge(5).astype(float)
    else:
        for field, categories in (("month", range(2, 13)), ("weekday", range(1, 7))):
            for k in categories:
                x[f"{field}_{k}"] = d[field].eq(k).astype(float)
    if spec != "calendar":
        x["temp10f"] = (d.temp_mid_f - 60) / 10
        if spec == "adjusted":
            x["temp10f_squared"] = x.temp10f ** 2
        if case == "raw":
            x["prcp_raw"] = d.prcp
        elif case == "positive":
            x["positive"] = d.prcp.gt(0).astype(float)
        elif case == "wet":
            x["wet_including_trace"] = d.prcp.gt(0).combine(d.precip_trace,np.logical_or).astype(float)
        elif case == "group":
            x["trace"] = d.precip_group.eq("Trace").astype(float)
            x["measurable"] = d.precip_group.eq("Measurable").astype(float)
        else:
            raise ValueError(case)
    return x

def fit(d, spec="adjusted", case="group", lag=7, response="ride_count", log=False):
    x_frame = design(d, spec, case)
    x = x_frame.to_numpy(float)
    y = d[response].to_numpy(float)
    if log:
        y = np.log1p(y)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Filter missing observations explicitly before fitting")
    b, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
    n, p = x.shape
    if rank != p:
        raise ValueError(f"Incomplete model rank {rank}/{p}")
    predicted = x @ b
    error = y - predicted
    inverse = np.linalg.inv(x.T@x)
    # Fill absent calendar dates with zero score. Lags remain actual days after exclusions.
    date_offsets = (d.date - d.date.min()).dt.days.to_numpy(int)
    score = np.zeros((date_offsets.max()+1,p))
    score[date_offsets] = x * error[:,None]
    meat = score.T @ score
    for day in range(1,min(lag+1,len(score))):
        cross = score[day:].T @ score[:-day]
        meat += (1-day/(lag+1))*(cross + cross.T)
    cov = n/(n-p)*inverse @ meat @ inverse
    cov = (cov+cov.T)/2
    sse = np.sum(error**2)
    r2 = 1-sse/np.sum((y-y.mean())**2)
    hat = np.einsum("ij,jk,ik->i",x,inverse,x)
    cook = error**2/(p*(sse/(n-p))) * hat / np.maximum((1-hat)**2,1e-12)
    vif = {}
    for j, name in enumerate(x_frame.columns):
        if name == "intercept":
            continue
        rest = np.delete(x,j,axis=1)
        err = x[:,j]-rest@np.linalg.lstsq(rest,x[:,j],rcond=None)[0]
        vif[name] = float(np.sum((x[:,j]-x[:,j].mean())**2)/np.sum(err**2))
    return {"b":b,"cov":cov,"x":x_frame,"date":d.date,"error":error,"predicted":predicted,
            "n":n,"p":p,"r2":float(r2),"adjusted_r2":float(1-(1-r2)*(n-1)/(n-p)),
            "mae":float(np.mean(np.abs(error))),"rmse":float(np.sqrt(sse/n)),"cook":cook,
            "condition_number":float(singular.max()/singular.min()),"vif":vif}

def contrast(model, weights):
    effect = float(weights@model["b"])
    se = float(np.sqrt(max(0,weights@model["cov"]@weights)))
    return {"estimate":effect,"lower":effect-Z*se,"upper":effect+Z*se,"se":se}

def temp_effect(model, d, spec, case, lower=50, upper=60):
    weights = (design(d.assign(temp_mid_f=upper),spec,case)-design(d.assign(temp_mid_f=lower),spec,case)).mean().to_numpy(float)
    return contrast(model, weights)

def precip_effect(model, case):
    term = {"group":"measurable","raw":"prcp_raw","positive":"positive","wet":"wet_including_trace"}[case]
    c = np.zeros(model["p"])
    c[model["x"].columns.get_loc(term)] = 1
    return contrast(model,c)

def temperature_support(d, lower, upper):
    """Report brackets and nearby data within the same calendar month."""
    rows = []
    for scope, dates in (("All precipitation groups", d),
                         ("Recorded zero", d.loc[d.precip_group.eq("Recorded zero")])):
        for month, days in dates.groupby("month"):
            values = days.temp_mid_f
            low_n = int(values.between(lower - 2.5, lower + 2.5).sum())
            high_n = int(values.between(upper - 2.5, upper + 2.5).sum())
            bracketed = bool(values.min() <= lower and upper <= values.max())
            rows.append({"from_f": lower, "to_f": upper, "scope": scope,
                         "month": int(month), "n": len(days),
                         "observed_min_f": float(values.min()), "observed_max_f": float(values.max()),
                         "near_from_n": low_n, "near_to_n": high_n,
                         "bracketed": bracketed,
                         "supported": bracketed and min(low_n, high_n) >= 2})
    return rows

def model_summary(model):
    return {k:model[k] for k in ("n","p","r2","adjusted_r2","mae","rmse","condition_number")}

def acf(error, lag):
    if lag >= len(error) or np.std(error)==0:
        return None
    z = error-error.mean()
    return float(z[lag:]@z[:-lag]/(z@z))

def run(results, weather_csv=None):
    d = pd.read_csv(results/"daily_2023.csv",parse_dates=["date"]).sort_values("date")
    assert len(d)==365 and d.date.is_unique and d.date.diff().dropna().dt.days.eq(1).all()
    d = d.dropna(subset=["temp_mid_f","prcp","ride_count"]).copy()
    assert d.precip_group.isin(["Recorded zero","Trace","Measurable"]).all()
    base = fit(d,"baseline","raw")
    calendar = fit(d,"calendar")
    adjusted = fit(d)
    linear = fit(d,"adjusted","raw")
    models = {"simple":base,"calendar":calendar,"adjusted":adjusted,"adjusted_amount":linear}
    coeff = []
    for label, m in models.items():
        for i,name in enumerate(m["x"].columns):
            unit = np.eye(m["p"])[i]
            coeff.append({"model":label,"term":name,**contrast(m,unit)})
    pd.DataFrame(coeff).to_csv(results/"coefficients.csv",index=False)
    sens = []
    def row(label, data, spec="adjusted", case="group", lag=7, response="ride_count", log=False):
        m=fit(data,spec,case,lag,response,log)
        temp=temp_effect(m,data,spec,case)
        precip=precip_effect(m,case)
        if log:
            trans=lambda a:{k:100*math.expm1(v) for k,v in a.items() if k!="se"}
            temp,precip=trans(temp),trans(precip)
        sens.append({"specification":label,"n":m["n"],"lag":lag,"r2":m["r2"],
                     "outcome_scale":"percent difference in modeled geometric mean of 1+rides" if log else "trip starts",
                     **{f"temp_{k}":v for k,v in temp.items()},
                     **{f"precip_{k}":v for k,v in precip.items()}})
    row("Primary categories",d)
    row("HAC lag 3",d,lag=3)
    row("HAC lag 14",d,lag=14)
    row("Continuous PRCP (per raw CSV unit)",d,case="raw")
    row("Any positive recorded precipitation",d,case="positive")
    row("Positive or trace (wet)",d,case="wet")
    row("Log daily starts",d,log=True)
    row("Exclude four recorded snowfall days",d.loc[~d.snow.gt(0)])
    row("Inside broad coordinate screen",d,response="rectangle_count")
    # High influence only as a transparent sensitivity. Keep all dates in the primary.
    strongest = np.argsort(adjusted["cook"])[-3:]
    row("Exclude three highest-Cook dates",d.iloc[np.setdiff1d(np.arange(len(d)),strongest)])
    if weather_csv is not None:
        from prepare_data import weather_table
        airport, _ = weather_table(weather_csv, "USW00014732")
        weather_fields = ["temp_mid_f", "prcp", "precip_group", "precip_trace"]
        alternative = d.drop(columns=weather_fields).merge(
            airport[["date", *weather_fields]], on="date", validate="one_to_one")
        alternative = alternative.dropna(subset=["temp_mid_f","prcp"]).sort_values("date")
        row("LaGuardia station",alternative)
    pd.DataFrame(sens).to_csv(results/"sensitivity.csv",index=False)
    # Keep each month's temperature range and weekday mix tied to its own zero-precipitation dates.
    curve = []
    for month, dry in d.loc[d.precip_group.eq("Recorded zero")].groupby("month"):
        lo, hi = dry.temp_mid_f.quantile([.10, .90])
        for temp in np.linspace(lo, hi, 51):
            weights = design(dry.assign(temp_mid_f=temp)).mean().to_numpy()
            curve.append({"month": int(month), "n_recorded_zero": len(dry),
                          "temp_f": float(temp), **contrast(adjusted, weights)})
    pd.DataFrame(curve).to_csv(results/"temperature_curve.csv",index=False)
    combined_support, contrasts = [], []
    for low in (30, 40, 50, 60, 70):
        high = low + 10
        support = temperature_support(d, low, high)
        combined_support.extend(support)
        all_months = [row["month"] for row in support
                      if row["scope"] == "All precipitation groups" and row["supported"]]
        dry_months = [row["month"] for row in support
                      if row["scope"] == "Recorded zero" and row["supported"]]
        contrasts.append({"from_f": low, "to_f": high,
                          "supported_months_all": ",".join(map(str, all_months)),
                          "supported_months_zero": ",".join(map(str, dry_months)),
                          "support_month_count": len(all_months),
                          **temp_effect(adjusted, d, "adjusted", "group", low, high)})
    pd.DataFrame(combined_support).to_csv(results/"temperature_support.csv", index=False)
    pd.DataFrame(contrasts).to_csv(results/"temperature_contrasts.csv", index=False)
    ordered_days=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    weekday=d.groupby("weekday").ride_count.agg(n="size",median="median",mean="mean",
        q25=lambda x:x.quantile(.25),q75=lambda x:x.quantile(.75)).reset_index()
    weekday["day_name"]=weekday.weekday.map(dict(enumerate(ordered_days)))
    weekday.to_csv(results/"weekday_profile.csv",index=False)
    bands=["<40°F","40–<55°F","55–<70°F","≥70°F"]
    groups_order=["Recorded zero","Trace","Measurable"]
    temp_band=pd.cut(d.temp_mid_f,[-np.inf,40,55,70,np.inf],right=False,labels=bands)
    joint=d.assign(temp_band=temp_band).groupby(["temp_band","precip_group"],observed=True).ride_count.agg(n="size",median="median")
    joint=joint.reindex(pd.MultiIndex.from_product([bands,groups_order],names=["temp_band","precip_group"]))
    joint["n"]=joint.n.fillna(0).astype(int)
    joint["shown"]=joint.n.ge(5)
    joint.to_csv(results/"joint_weather.csv")
    pd.DataFrame({"date":d.date,"residual":adjusted["error"],"fitted":adjusted["predicted"],
                  "cook_distance":adjusted["cook"]}).to_csv(results/"diagnostics.csv",index=False)
    compare = {k:model_summary(m) for k,m in models.items()}
    error=adjusted["error"]
    dw=float(np.sum(np.diff(error)**2)/np.sum(error**2))
    groups = d.groupby("precip_group").ride_count.agg(["size","mean","median","min","max"])
    groups.to_csv(results/"precip_summary.csv")
    data = {
        "n":len(d),"pearson":float(d.ride_count.corr(d.temp_mid_f)),"mean_daily":float(d.ride_count.mean()),
        "models":compare,"temp_50_to_60":temp_effect(adjusted,d,"adjusted","group"),
        "temp_70_to_80":temp_effect(adjusted,d,"adjusted","group",70,80),
        "measurable_vs_zero":precip_effect(adjusted,"group"),
        "trace_vs_zero":next({k:c[k] for k in ("estimate","lower","upper","se")} for c in coeff if c["model"]=="adjusted" and c["term"]=="trace"),
        "group_summary":groups.to_dict(orient="index"),"acf_lag1":acf(error,1),"acf_lag7":acf(error,7),
        "durbin_watson":dw,
        "temp_vif":adjusted["vif"]["temp10f"],"square_vif":adjusted["vif"]["temp10f_squared"],
        "high_cook_dates":[{"date":str(d.iloc[i].date.date()),"cook":float(adjusted["cook"][i])} for i in strongest[::-1]],
        "specification":"OLS with centered midpoint, its square, recorded precipitation categories, weekday and month. HAC 7 calendar-day lags, Bartlett weights, n/(n-p) correction, asymptotic normal pointwise 95% intervals.",
        "interpretation":"Temperature and precipitation associations conditional on controls. Each monthly curve uses the central 80% of that month's recorded-zero precipitation temperatures and averages over weekdays observed among those same dates. Contrast support audit requires the endpoints to be bracketed and at least two dates within 2.5°F of each endpoint in a month. This descriptive screen does not establish date-level overlap.",
    }
    (results/"model_summary.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    return data

if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--results",type=Path,default=ROOT/"results")
    ap.add_argument("--weather-csv",type=Path,default=ROOT/"data/raw/nyc_weather_2023.csv")
    args = ap.parse_args()
    print(json.dumps(run(args.results,args.weather_csv),indent=2))
