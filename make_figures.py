"""Draw the final charts and generate a portable browser demo from frozen results."""
from pathlib import Path
import json, html
from calendar import month_abbr
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import pandas as pd

INK="#122a3d"; MUTED="#4e6272"; TEAL="#007a77"; ORANGE="#ad532c"; GRID="#dce5ea"; BLUE="#2b5b89"
FIGURES = {
 "daily": ("Daily Citi Bike starts in 2023", "365 NYC-release dates", "Exact daily totals and a labeled trailing 7-day mean.", "Monthly ticks and rides in thousands show variation through the year.", "A muted daily series and thick teal mean avoid competing colors.", "Seasonal structure motivates adjustment for month and weekday."),
 "scatter": ("Warmer dates tend to have more starts", "Raw data before calendar adjustment", "Every point is one date. Pearson r is a descriptive statistic.", "The axes show the temperature proxy in °F and starts in thousands.", "Small teal dots make overlap visible without obscuring the cloud.", "The upward pattern motivates an adjusted comparison."),
 "precip": ("Fewer starts on measurable precipitation days", "Central Park recorded groups", "All 365 days and group sizes are shown, together with group means.", "Recorded zero, trace and measurable days have separate labels.", "A common scale and sparse marks keep the comparison readable.", "Trace and recorded zero look similar descriptively, while measurable days are lower."),
 "curve": ("Calendar-adjusted temperature by month", "Central 80% of recorded-zero temperatures within each month", "Each panel uses its month's observed range and shows pointwise 95% HAC intervals.", "Shared axes compare the °F proxy and modeled mean starts across months.", "Teal curves and light bands distinguish estimates from uncertainty.", "Monthly panels show where the annual model has local temperature support."),
 "residual": ("Residuals still vary across the year", "Adjusted model, ordered by calendar date", "All 365 residuals are shown relative to zero.", "The time axis helps locate unusual periods and the sign of errors.", "A thin baseline and a single data color keep attention on departures.", "Runs above and below zero motivate daily dependence checks."),
 "weekday": ("Daily starts vary by day of week", "Descriptive medians and interquartile ranges", "The line spans the middle 50% of dates, not a confidence interval.", "Days follow calendar order and each sample size is printed.", "A shared scale and sparse marks make groups easy to compare.", "Different day profiles motivate separate weekday controls."),
 "joint": ("Temperature and precipitation together", "Raw median starts by weather group and temperature band", "Sample sizes appear in every cell. Medians are hidden when n < 5.", "A common color scale and numerical labels show the median starts.", "Muted shading leaves room for the cell labels.", "Readers can see which combinations have limited support before interpreting the raw differences."),
 "contrasts": ("Adjusted changes in daily starts", "Primary model contrasts, pointwise 95% HAC intervals", "All plotted intervals come from the same primary model.", "The zero line separates higher from lower modeled starts.", "The chart uses one unit and simple interval marks.", "Readers can compare magnitudes and distinguish the less precise trace result."),
}
def font(size,bold=False):
    for name in (["arialbd.ttf","DejaVuSans-Bold.ttf"] if bold else ["arial.ttf","DejaVuSans.ttf"]):
        for loc in (str(Path("C:/Windows/Fonts")/name),name):
            try: return ImageFont.truetype(loc,size)
            except OSError: pass
    return ImageFont.load_default()

def run(results):
    d=pd.read_csv(results/"daily_2023.csv",parse_dates=["date"])
    curve=pd.read_csv(results/"temperature_curve.csv")
    residual=pd.read_csv(results/"diagnostics.csv")
    weekday=pd.read_csv(results/"weekday_profile.csv")
    joint=pd.read_csv(results/"joint_weather.csv")
    m=json.loads((results/"model_summary.json").read_text(encoding="utf-8"))
    target=results/"figures";target.mkdir(exist_ok=True)
    def plot(key,xrange,yrange,xticks,yticks,xlabel,ylabel):
        title,sub,*_=FIGURES[key]
        im=Image.new("RGB",(1440,850),"white"); dr=ImageDraw.Draw(im)
        dr.text((58,37),title,fill=INK,font=font(43,True))
        dr.text((60,97),sub,fill=MUTED,font=font(28))
        x0,y0,x1,y1=139,177,1365,706
        def xy(x,y):return (x0+(x-xrange[0])/(xrange[1]-xrange[0])*(x1-x0),y1-(y-yrange[0])/(yrange[1]-yrange[0])*(y1-y0))
        for y,l in yticks:
            _,yy=xy(xrange[0],y);dr.line((x0,yy,x1,yy),fill=GRID,width=2)
            dr.text((x0-17,yy),l,anchor="rm",fill=MUTED,font=font(24))
        dr.line((x0,y0,x0,y1,x1,y1),fill=MUTED,width=2)
        for x,l in xticks:
            xx,_=xy(x,yrange[0]);dr.text((xx,y1+16),l,anchor="mt",fill=MUTED,font=font(24))
        dr.text((58,143),ylabel,fill=MUTED,font=font(22))
        dr.text(((x0+x1)/2,785),xlabel,anchor="mt",fill=INK,font=font(27))
        return im,dr,xy
    def lines(dr,xy,x,y,col,width):dr.line([xy(a,b) for a,b in zip(x,y) if np.isfinite(b)],fill=col,width=width,joint="curve")
    def points(dr,xy,x,y,col,r):
        for a,b in zip(x,y):
            xx,yy=xy(a,b);dr.ellipse((xx-r,yy-r,xx+r,yy+r),fill=col)
    def finish(im,key):im.save(target/f"{key}.png",optimize=True)
    days=np.arange(len(d)); months=[(int(i),dt.strftime("%b")) for i,dt in enumerate(d.date) if dt.day==1]
    ticks=[(i,str(i)) for i in range(0,161,40)]
    im,dr,xy=plot("daily",(0,364),(0,165),months,ticks,"New York source date","Daily starts (thousands)")
    lines(dr,xy,days,d.ride_count/1000,"#9fbbcd",2);lines(dr,xy,days,d.ride_count.rolling(7).mean()/1000,TEAL,5)
    dr.text((990,193),"Daily / trailing 7-day mean",fill=TEAL,font=font(23));finish(im,"daily")
    temp_ticks=[(i,str(i)) for i in range(20,101,20)]
    im,dr,xy=plot("scatter",(10,100),(0,165),temp_ticks,ticks,"Daily high–low midpoint (°F)","Daily starts (thousands)")
    points(dr,xy,d.temp_mid_f,d.ride_count/1000,TEAL,4)
    dr.text((990,195),f"Pearson r = {m['pearson']:.3f}",fill=INK,font=font(29,True));finish(im,"scatter")
    groups=["Recorded zero","Trace","Measurable"]
    im,dr,xy=plot("precip",(-.6,2.6),(0,165),[(j,f"{g}  (n={sum(d.precip_group==g)})") for j,g in enumerate(groups)],ticks,"Recorded precipitation group","Daily starts (thousands)")
    for j,g in enumerate(groups):
        v=d.loc[d.precip_group.eq(g),"ride_count"].to_numpy()/1000
        jitter=np.random.default_rng(2023+j).uniform(-.18,.18,len(v))
        points(dr,xy,j+jitter,v,["#7ba3b2","#78939d","#c77b54"][j],4)
        xa,yy=xy(j-.23,v.mean());xb,_=xy(j+.23,v.mean())
        dr.line((xa,yy,xb,yy),fill=INK,width=6)
    dr.text((940,190),"Horizontal lines show means",fill=MUTED,font=font(23));finish(im,"precip")
    im=Image.new("RGB",(1440,850),"white")
    dr=ImageDraw.Draw(im)
    dr.text((58,35),FIGURES["curve"][0],fill=INK,font=font(42,True))
    dr.text((60,95),FIGURES["curve"][1],fill=MUTED,font=font(27))
    dr.text((60,143),"Modeled daily starts (thousands) · shaded 95% HAC intervals",fill=MUTED,font=font(23))
    y_max=max(150,int(np.ceil(curve.upper.max()/50000))*50)
    for i,(month,segment) in enumerate(curve.groupby("month")):
        row,col=divmod(i,4)
        left,top=76+col*347,185+row*200
        x0,y0,x1,y1=left+39,top+33,left+303,top+154
        def local_xy(t,y):
            return x0+(t-25)/60*(x1-x0),y1-y/y_max*(y1-y0)
        n=int(segment.n_recorded_zero.iloc[0])
        dr.text((left+35,top),f"{month_abbr[month]}  (n={n})",fill=INK,font=font(23,True))
        for tick in range(0,y_max+1,50):
            _,yy=local_xy(25,tick)
            dr.line((x0,yy,x1,yy),fill=GRID,width=2)
            if col==0:
                dr.text((x0-7,yy),str(tick),anchor="rm",fill=MUTED,font=font(17))
        for tick in [30,50,70,85]:
            xx,_=local_xy(tick,0)
            dr.text((xx,y1+9),str(tick),anchor="mt",fill=MUTED,font=font(17))
        poly=[local_xy(t,y/1000) for t,y in zip(segment.temp_f,segment.lower)]
        poly += [local_xy(t,y/1000) for t,y in zip(segment.temp_f[::-1],segment.upper[::-1])]
        dr.polygon(poly,fill="#c6e8e4")
        lines(dr,local_xy,segment.temp_f,segment.estimate/1000,TEAL,5)
    dr.text((720,810),"Daily high–low midpoint (°F)",anchor="mt",fill=INK,font=font(24))
    finish(im,"curve")
    ymax=max(60,int(np.ceil(max(abs(residual.residual))/20000))*20)
    im,dr,xy=plot("residual",(0,364),(-ymax,ymax),months,[(i,str(i)) for i in range(-ymax,ymax+1,20)],"New York source date","Observed − fitted starts (thousands)")
    lines(dr,xy,days,np.zeros(len(d)),MUTED,3);lines(dr,xy,days,residual.residual/1000,BLUE,3);finish(im,"residual")
    labels=[(j,f"{v.day_name} (n={v.n})") for j,v in enumerate(weekday.itertuples())]
    im,dr,xy=plot("weekday",(-.6,6.6),(0,165),labels,ticks,"Day of week","Daily starts (thousands)")
    for j,v in enumerate(weekday.itertuples()):
        dr.line([xy(j,v.q25/1000),xy(j,v.q75/1000)],fill=TEAL,width=6)
        points(dr,xy,[j],[v.median/1000],INK,9)
    finish(im,"weekday")
    im=Image.new("RGB",(1440,850),"white")
    dr=ImageDraw.Draw(im)
    dr.text((58,37),FIGURES["joint"][0],fill=INK,font=font(43,True))
    dr.text((60,97),FIGURES["joint"][1],fill=MUTED,font=font(28))
    shown=joint.loc[joint.shown,"median"]
    lo,hi=shown.min(),shown.max()
    for j,label in enumerate(groups):
        dr.text((548+j*240,190),label,anchor="mm",fill=INK,font=font(25,True))
    for i, label in enumerate(joint.temp_band.unique()):
        dr.text((412,266+i*108),label,anchor="rm",fill=INK,font=font(25))
        for j,one in enumerate(joint.loc[joint.temp_band.eq(label)].itertuples()):
            left,top=430+j*240,220+i*108
            ratio=(one.median-lo)/(hi-lo) if one.shown else 0
            fill=tuple(round(a+(b-a)*ratio) for a,b in zip((229,244,242),(87,168,159))) if one.shown else "#f0f2f4"
            dr.rectangle((left,top,left+235,top+103),fill=fill)
            caption=f"{one.median/1000:.1f}k" if one.shown else "Suppressed"
            dr.text((left+118,top+40),caption,anchor="mm",fill=INK,font=font(28,True))
            dr.text((left+118,top+77),f"n = {one.n}",anchor="mm",fill=INK,font=font(20))
    dr.text((430,683),"Median starts (thousands)",fill=MUTED,font=font(22))
    for x in range(470):
        ratio=x/469
        fill=tuple(round(a+(b-a)*ratio) for a,b in zip((229,244,242),(87,168,159)))
        dr.line((430+x,716,430+x,737),fill=fill)
    dr.text((430,746),f"{lo/1000:.0f}k",fill=MUTED,font=font(20))
    dr.text((900,746),f"{hi/1000:.0f}k",anchor="ra",fill=MUTED,font=font(20))
    finish(im,"joint")
    im,dr,xy=plot("contrasts",(-30000,20000),(-.5,3.5),[(x,f"{x/1000:.0f}k") for x in range(-30000,20001,10000)],[],"Difference in daily starts","95% HAC interval")
    xx,_=xy(0,0)
    dr.line((xx,177,xx,706),fill=GRID,width=3)
    for i,(name,key) in enumerate([("50°F to 60°F","temp_50_to_60"),("70°F to 80°F","temp_70_to_80"),("Measurable vs. zero","measurable_vs_zero"),("Trace vs. zero","trace_vs_zero")]):
        value=m[key]; y=3-i
        dr.line([xy(value["lower"],y),xy(value["upper"],y)],fill=TEAL,width=6)
        points(dr,xy,[value["estimate"]],[y],INK,8)
        dr.text((165,xy(0,y)[1]-35),name,fill=INK,font=font(24))
    finish(im,"contrasts")
    (results/"figure_guide.json").write_text(json.dumps(FIGURES,ensure_ascii=False,indent=2),encoding="utf-8")
    sections=[]
    for k,(title,sub,*why) in FIGURES.items():
        li="".join(f"<li><b>{a}</b> {html.escape(b)}</li>" for a,b in zip(["Truthful","Functional","Beautiful","Insightful"],why))
        sections.append(f'<section><img src="figures/{k}.png" alt="{title}"><ul>{li}</ul></section>')
    e=m["temp_50_to_60"]; q=m["measurable_vs_zero"]
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Citi Bike and weather</title>
<style>body{font:18px Arial,sans-serif;color:#122a3d;background:#f3f7f8;margin:0}main{max-width:1000px;margin:auto;padding:35px 24px}section{background:white;padding:15px;margin:18px 0}img{width:100%;display:block}button{padding:10px;margin:5px;cursor:pointer}h1{font-size:40px}</style><main>
<h1>Weather and Citi Bike starts</h1><p>2023 daily records · Class D Team 02</p>'''
    page+=f"<p>Adjusted 50°F to 60°F contrast: <strong>{e['estimate']:+,.0f}</strong> starts. Measurable versus recorded-zero precipitation: <strong>{q['estimate']:+,.0f}</strong> starts.</p>"
    page+='<nav aria-label="Charts">'+''.join(f'<button onclick="show({i})">{html.escape(FIGURES[k][0])}</button>' for i,k in enumerate(FIGURES))+'</nav>'+''.join(sections)
    page+='<p>Sources: <a href="https://citibikenyc.com/system-data">Citi Bike system data</a> and <a href="https://www.ncei.noaa.gov/cdo-web/datasets/GHCND">NOAA Daily Summaries</a>.</p><p>Relationships are observational. The total describes the supplied non-JC release.</p></main><script>function show(i){document.querySelectorAll("section").forEach((s,j)=>s.hidden=i!==j)}show(0)</script></html>'
    (results/"demo.html").write_text(page,encoding="utf-8")

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--results",type=Path,default=Path(__file__).resolve().parent/"results")
    run(p.parse_args().results)
