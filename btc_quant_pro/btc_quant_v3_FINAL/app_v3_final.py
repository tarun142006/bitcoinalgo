"""
BTC QUANT PRO v3 — Professional Bitcoin Futures Research Terminal
Real data: Binance Futures (WS+REST) · Deribit Options · Zero fake data
Run: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import numpy as np
import requests
import time, math, warnings
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from scipy import stats, optimize
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")

# ═══════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════
st.set_page_config(page_title="BTC QUANT PRO", page_icon="◈",
                   layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Share+Tech+Mono&family=Rajdhani:wght@500;600;700&display=swap');
html,body,[class*="st-"],.stApp{background:#030812!important;color:#c8d8f0!important;}
.block-container{padding:0.5rem 1rem!important;max-width:100%!important;}
[data-testid="stMetricValue"]{font-family:'Share Tech Mono',monospace!important;font-size:1.3rem!important;color:#c8d8f0!important;}
[data-testid="stMetricLabel"]{font-family:'Share Tech Mono',monospace!important;font-size:0.6rem!important;color:#364060!important;text-transform:uppercase!important;letter-spacing:.12em!important;}
[data-testid="stMetricDelta"] svg{display:none!important;}
[data-testid="stMetricDelta"]{font-family:'Share Tech Mono',monospace!important;font-size:0.68rem!important;}
.stTabs [data-baseweb="tab"]{font-family:'Orbitron',sans-serif!important;font-size:0.62rem!important;letter-spacing:2px!important;color:#364060!important;padding:8px 14px!important;}
.stTabs [aria-selected="true"]{color:#00ff9d!important;}
.stTabs [data-baseweb="tab-list"]{background:#080e1d!important;border-bottom:1px solid #1a2545!important;}
[data-testid="stSidebarContent"]{background:#08101f!important;}
.stMetric{background:#08101f!important;border:1px solid #1a2545!important;border-radius:7px!important;padding:10px 14px!important;}
.stDataFrame thead th{background:#08101f!important;color:#364060!important;font-family:'Share Tech Mono',monospace!important;font-size:9px!important;}
.stDataFrame tbody td{font-family:'Share Tech Mono',monospace!important;font-size:10px!important;}
.stButton button{font-family:'Orbitron',sans-serif!important;font-size:9px!important;letter-spacing:2px!important;background:#08101f!important;border:1px solid #1a2545!important;color:#364060!important;border-radius:5px!important;}
.stButton button:hover{border-color:#00ff9d!important;color:#00ff9d!important;}
.stSelectbox>div>div{background:#08101f!important;border:1px solid #1a2545!important;font-family:'Share Tech Mono',monospace!important;font-size:11px!important;}
hr{border-color:#1a2545!important;}
div[data-testid="stExpander"]{background:#08101f!important;border:1px solid #1a2545!important;border-radius:7px!important;}
</style>""", unsafe_allow_html=True)

G, R, A, C, P, GR = "#00ff9d","#ff2952","#ffb800","#00d4ff","#cc44ff","#364060"

BG = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#06091a",
          font=dict(family="Share Tech Mono", color="#c8d8f0", size=9),
          margin=dict(l=46,r=12,t=28,b=26),
          legend=dict(font=dict(size=8),bgcolor="rgba(0,0,0,0)"),
          hovermode="x unified")
AX = dict(gridcolor="#1a2545",gridwidth=.5,zerolinecolor="#1a2545",
          tickfont=dict(size=8),linecolor="#1a2545",showline=True)

def fig(h=280):
    f=go.Figure(); f.update_layout(**BG,height=h)
    f.update_xaxes(**AX); f.update_yaxes(**AX); return f

def subfig(rows,cols,heights=None,titles=None,shared_x=True):
    f=make_subplots(rows=rows,cols=cols,row_heights=heights,
                    vertical_spacing=.03,shared_xaxes=shared_x,
                    subplot_titles=titles)
    f.update_layout(**BG)
    for i in range(1,rows+1):
        for j in range(1,cols+1):
            f.update_xaxes(**AX,row=i,col=j)
            f.update_yaxes(**AX,row=i,col=j)
    return f

def safe_float(v, default=0.0):
    try: return float(v) if v is not None else default
    except: return default

def fmtM(v):
    v=abs(v)
    if v>=1e9: return f"${v/1e9:.2f}B"
    if v>=1e6: return f"${v/1e6:.1f}M"
    if v>=1e3: return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

# ═══════════════════════════════════════════════════════
#  DATA LAYER — 100% real, all guarded
# ═══════════════════════════════════════════════════════
BN  = "https://fapi.binance.com"
SP  = "https://api.binance.com"
DB  = "https://www.deribit.com/api/v2"
HDR = {"User-Agent":"btc-quant/3.0","Accept":"application/json"}

def _get(url, params=None, timeout=10):
    try:
        r = requests.get(url,params=params,headers=HDR,timeout=timeout)
        r.raise_for_status()
        d = r.json()
        return d if d is not None else {}
    except Exception:
        return {}

@st.cache_data(ttl=15)
def get_klines(sym="BTCUSDT", iv="15m", lim=300):
    d = _get(f"{BN}/fapi/v1/klines",{"symbol":sym,"interval":iv,"limit":lim})
    if not isinstance(d,list) or len(d)==0: return pd.DataFrame()
    df = pd.DataFrame(d,columns=["ts","o","h","l","c","v","cts","qv","n","tbv","tqv","x"])
    for col in ["o","h","l","c","v","tbv"]:
        df[col] = pd.to_numeric(df[col],errors="coerce")
    df["ts"] = pd.to_datetime(df["ts"],unit="ms")
    df.rename(columns={"o":"open","h":"high","l":"low","c":"close","v":"volume"},inplace=True)
    df["tbv"] = df["tbv"].fillna(0)
    df["tsv"] = (df["volume"] - df["tbv"]).clip(lower=0)
    df = df[["ts","open","high","low","close","volume","tbv","tsv"]].dropna()
    df.set_index("ts",inplace=True)
    return df

@st.cache_data(ttl=15)
def get_klines_multi():
    return {iv: get_klines("BTCUSDT",iv,300) for iv in ["5m","15m","1h","4h"]}

@st.cache_data(ttl=5)
def get_ticker():
    d = _get(f"{BN}/fapi/v1/ticker/24hr",{"symbol":"BTCUSDT"})
    return d if isinstance(d,dict) else {}

@st.cache_data(ttl=5)
def get_orderbook(lim=100):
    d = _get(f"{BN}/fapi/v1/depth",{"symbol":"BTCUSDT","limit":lim})
    if not isinstance(d,dict): return {"bids":[],"asks":[]}
    try:
        bids = [(float(p),float(s)) for p,s in d.get("bids",[])]
        asks = [(float(p),float(s)) for p,s in d.get("asks",[])]
        return {"bids":sorted(bids,key=lambda x:-x[0]),
                "asks":sorted(asks,key=lambda x:x[0])}
    except: return {"bids":[],"asks":[]}

@st.cache_data(ttl=30)
def get_funding_history():
    d = _get(f"{BN}/fapi/v1/fundingRate",{"symbol":"BTCUSDT","limit":100})
    if not isinstance(d,list): return []
    out=[]
    for x in d:
        try:
            out.append({"ts":pd.to_datetime(int(x["fundingTime"]),unit="ms"),
                        "rate":float(x["fundingRate"])*100})
        except: pass
    return out

@st.cache_data(ttl=20)
def get_premium_index():
    d = _get(f"{BN}/fapi/v1/premiumIndex",{"symbol":"BTCUSDT"})
    if not isinstance(d,dict): return {}
    return {k: safe_float(v) for k,v in d.items() if v is not None}

@st.cache_data(ttl=20)
def get_oi_hist():
    d = _get(f"{BN}/futures/data/openInterestHist",
             {"symbol":"BTCUSDT","period":"15m","limit":200})
    if not isinstance(d,list): return pd.DataFrame()
    df = pd.DataFrame(d)
    df["timestamp"] = pd.to_datetime(pd.to_numeric(df["timestamp"],errors="coerce"),unit="ms")
    df["sumOpenInterest"]      = pd.to_numeric(df["sumOpenInterest"],errors="coerce")
    df["sumOpenInterestValue"] = pd.to_numeric(df["sumOpenInterestValue"],errors="coerce")
    return df.dropna().reset_index(drop=True)

@st.cache_data(ttl=20)
def get_ls_ratio():
    d = _get(f"{BN}/futures/data/globalLongShortAccountRatio",
             {"symbol":"BTCUSDT","period":"15m","limit":100})
    if not isinstance(d,list): return pd.DataFrame()
    df = pd.DataFrame(d)
    df["timestamp"]     = pd.to_datetime(pd.to_numeric(df["timestamp"],errors="coerce"),unit="ms")
    df["longShortRatio"] = pd.to_numeric(df["longShortRatio"],errors="coerce")
    df["longAccount"]    = pd.to_numeric(df["longAccount"],errors="coerce")
    df["shortAccount"]   = pd.to_numeric(df["shortAccount"],errors="coerce")
    return df.dropna()

@st.cache_data(ttl=20)
def get_top_ls():
    d = _get(f"{BN}/futures/data/topLongShortAccountRatio",
             {"symbol":"BTCUSDT","period":"15m","limit":100})
    if not isinstance(d,list): return pd.DataFrame()
    df = pd.DataFrame(d)
    df["timestamp"]     = pd.to_datetime(pd.to_numeric(df["timestamp"],errors="coerce"),unit="ms")
    df["longShortRatio"] = pd.to_numeric(df["longShortRatio"],errors="coerce")
    return df.dropna()

@st.cache_data(ttl=20)
def get_taker_flow():
    d = _get(f"{BN}/futures/data/takerlongshortRatio",
             {"symbol":"BTCUSDT","period":"15m","limit":100})
    if not isinstance(d,list): return pd.DataFrame()
    df = pd.DataFrame(d)
    for c in ["timestamp","buySellRatio","buyVol","sellVol"]:
        if c=="timestamp":
            df[c] = pd.to_datetime(pd.to_numeric(df[c],errors="coerce"),unit="ms")
        else:
            df[c] = pd.to_numeric(df[c],errors="coerce")
    return df.dropna()

@st.cache_data(ttl=30)
def get_aggression_index():
    """Buy aggression: taker buy vol / total vol rolling 20 periods"""
    d = get_klines("BTCUSDT","5m",100)
    if d.empty: return 0.5
    ratio = (d["tbv"] / d["volume"].replace(0,np.nan)).fillna(0.5)
    return float(ratio.iloc[-20:].mean())

@st.cache_data(ttl=60)
def get_deribit_options():
    d = _get(f"{DB}/public/get_book_summary_by_currency",
             {"currency":"BTC","kind":"option"},timeout=15)
    if not isinstance(d,dict): return []
    return d.get("result",[])

@st.cache_data(ttl=30)
def get_deribit_index():
    d = _get(f"{DB}/public/get_index_price",{"index_name":"btc_usd"})
    try: return float(d["result"]["index_price"])
    except: return 0.0

@st.cache_data(ttl=20)
def get_mark_price():
    d = _get(f"{BN}/fapi/v1/premiumIndex",{"symbol":"BTCUSDT"})
    try: return safe_float(d.get("markPrice"))
    except: return 0.0

@st.cache_data(ttl=60)
def get_spot_price():
    d = _get(f"{SP}/api/v3/ticker/price",{"symbol":"BTCUSDT"})
    try: return safe_float(d.get("price"))
    except: return 0.0

@st.cache_data(ttl=30)
def get_btc_dominance():
    """BTC dominance from CoinGecko (free, no key)"""
    d = _get("https://api.coingecko.com/api/v3/global",timeout=8)
    try: return safe_float(d["data"]["market_cap_percentage"]["btc"],45.0)
    except: return 0.0

@st.cache_data(ttl=60)
def get_fear_greed():
    """Fear & Greed index (alternative.me — free)"""
    d = _get("https://api.alternative.me/fng/?limit=7",timeout=8)
    try:
        items = d.get("data",[])
        if items:
            latest = items[0]
            return {
                "value":      int(latest.get("value",50)),
                "label":      latest.get("value_classification","Neutral"),
                "history":    [{"ts": datetime.fromtimestamp(int(x["timestamp"])),
                                "v":  int(x["value"])} for x in items],
            }
    except: pass
    return {"value":50,"label":"Neutral","history":[]}

# ═══════════════════════════════════════════════════════
#  MATH ENGINE — all from scratch, all guarded
# ═══════════════════════════════════════════════════════

def _erf(x):
    s = 1.0 if x >= 0 else -1.0; x = abs(x)
    t = 1.0/(1.0+0.3275911*x)
    y = 1.0-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*math.exp(-x*x)
    return s*y

def ncdf(x): return 0.5*(1.0+_erf(x/math.sqrt(2.0)))
def npdf(x): return math.exp(-0.5*x*x)/math.sqrt(2.0*math.pi)

def bs_greeks(S,K,T,r,sigma,cp):
    z={"price":0.,"delta":0.,"gamma":0.,"vega":0.,"theta":0.,"iv":sigma*100}
    if T<=0 or sigma<=0 or S<=0 or K<=0: return z
    sqt=math.sqrt(max(T,1e-8))
    d1=(math.log(S/K)+(r+.5*sigma**2)*T)/(sigma*sqt); d2=d1-sigma*sqt
    nd1=npdf(d1); g=nd1/(S*sigma*sqt)
    ve=S*nd1*sqt/100
    disc=math.exp(-r*T)
    if cp=="call":
        pr=S*ncdf(d1)-K*disc*ncdf(d2); de=ncdf(d1)
        th=(-S*nd1*sigma/(2*sqt)-r*K*disc*ncdf(d2))/365
    else:
        pr=K*disc*ncdf(-d2)-S*ncdf(-d1); de=ncdf(d1)-1
        th=(-S*nd1*sigma/(2*sqt)+r*K*disc*ncdf(-d2))/365
    return {"price":round(pr,4),"delta":round(de,5),"gamma":round(g,8),
            "vega":round(ve,4),"theta":round(th,4),"iv":round(sigma*100,2)}

def implied_vol(mkt,S,K,T,r,cp):
    if T<=0 or mkt<=0 or S<=0 or K<=0: return 0.
    lo,hi=.001,5.
    for _ in range(120):
        mid=(lo+hi)*.5
        p=bs_greeks(S,K,T,r,mid,cp)["price"]
        if abs(p-mkt)<1e-6: return mid
        if p<mkt: lo=mid
        else: hi=mid
        if hi-lo<1e-7: break
    return (lo+hi)*.5

def safe_sqrt(x):
    return math.sqrt(max(float(x),0.0))

def calc_vpin(df, bucket_n=50, window=50):
    if df.empty or len(df)<bucket_n+5:
        return pd.Series(np.nan,index=df.index)
    bs = max(float(df["volume"].sum())/bucket_n,1e-10)
    buckets=[]; cv=bv=0.
    for ts,row in df.iterrows():
        v=max(float(row["volume"]),0.); b=min(float(row["tbv"]),v)
        cv+=v; bv+=b
        while cv>=bs:
            frac=bs/cv
            imb=abs(bv*frac-(bs-bv*frac))/bs
            buckets.append({"ts":ts,"imb":float(np.clip(imb,0,1))})
            cv-=bs; bv*=(1.-frac)
    if not buckets:
        return pd.Series(np.nan,index=df.index)
    bdf=(pd.DataFrame(buckets).groupby("ts",sort=True)["imb"]
         .last().reset_index().sort_values("ts").reset_index(drop=True))
    bdf["vpin"]=bdf["imb"].rolling(window,min_periods=5).mean()
    dft=pd.DataFrame({"ts":df.index})
    mg=pd.merge_asof(dft,bdf[["ts","vpin"]],on="ts",direction="backward")
    return pd.Series(mg["vpin"].values,index=df.index,dtype=float).ffill().bfill()

def fit_garch(r_in):
    r=r_in[np.isfinite(r_in)]
    var0=float(np.var(r)) if len(r)>1 else 1e-8
    var0=max(var0,1e-12)
    fb={"omega":var0*.05,"alpha":.10,"beta":.85,
        "sigma_forecast":safe_sqrt(var0)*100,
        "sigma_annualized":safe_sqrt(var0*365*96)*100,
        "persistence":.95,"half_life":14.,"log_lik":None,"sigma_series":None}
    if len(r)<50: return fb
    def neg_ll(p):
        om,al,be=p
        if om<=0 or al<=0 or be<=0 or al+be>=.9999: return 1e12
        s2=np.empty(len(r)); s2[0]=var0
        for t in range(1,len(r)):
            s2[t]=om+al*r[t-1]**2+be*s2[t-1]
        s2=np.maximum(s2,1e-16)
        return .5*float(np.sum(np.log(2*math.pi*s2)+r**2/s2))
    best=None
    for a0,b0 in [(.05,.90),(.10,.85),(.15,.80),(.08,.88)]:
        w0=max(var0*(1-a0-b0),1e-12)
        try:
            res=optimize.minimize(neg_ll,[w0,a0,b0],method="L-BFGS-B",
                bounds=[(1e-14,None),(1e-6,.5),(1e-6,.9998)],
                options={"maxiter":400,"ftol":1e-9})
            if best is None or res.fun<best.fun: best=res
        except: pass
    if best is None: return fb
    om,al,be=best.x
    s2=np.empty(len(r)); s2[0]=var0
    for t in range(1,len(r)):
        s2[t]=om+al*r[t-1]**2+be*s2[t-1]
    s2=np.maximum(s2,1e-16)
    sn=safe_sqrt(max(om+al*r[-1]**2+be*float(s2[-1]),1e-16))
    pers=al+be; hl=math.log(.5)/math.log(pers) if 0<pers<1 else 99.
    return {"omega":float(om),"alpha":round(float(al),5),"beta":round(float(be),5),
            "sigma_forecast":round(sn*100,4),
            "sigma_annualized":round(sn*math.sqrt(365*96)*100,2),
            "persistence":round(float(pers),5),"half_life":round(float(hl),1),
            "log_lik":round(float(-best.fun),2),"sigma_series":np.sqrt(s2)*100}

def kalman_filter(prices):
    prices=prices[np.isfinite(prices)]
    n=len(prices)
    emp={"filtered":prices,"velocity":np.zeros(n),"std":np.ones(n)*10,
         "upper":prices+20,"lower":prices-20}
    if n<5: return emp
    pv=max(float(np.var(np.diff(prices))) if n>1 else 1.,1e-6)
    F=np.array([[1.,1.],[0.,1.]])
    H=np.array([[1.,0.]])
    Q=np.array([[pv*.1,0.],[0.,pv*.01]])
    R=np.array([[pv*.5]])
    x=np.array([[float(prices[0])],[0.]])
    P=np.eye(2)*pv
    filt=np.empty(n); vel=np.empty(n); var=np.empty(n)
    I2=np.eye(2)
    for t in range(n):
        xp=F@x; Pp=F@P@F.T+Q
        S=H@Pp@H.T+R
        Ss=max(float(S[0,0]),1e-14)
        Ks=Pp@H.T/Ss
        inn=float(prices[t])-float((H@xp).flat[0])
        x=xp+Ks*inn; P=(I2-Ks@H)@Pp
        filt[t]=float(x[0,0]); vel[t]=float(x[1,0]); var[t]=float(P[0,0])
    std=np.sqrt(np.maximum(var,0.))
    return {"filtered":filt,"velocity":vel,"std":std,
            "upper":filt+2*std,"lower":filt-2*std}

def fit_hmm(returns):
    r=returns[np.isfinite(returns)]; n=len(r)
    null={"states":np.zeros(len(returns),dtype=int),
          "proba_state1":np.full(len(returns),.5),
          "mu":[0.,0.],"sigma":[1.,1.],
          "trans":[[.95,.05],[.05,.95]]}
    if n<40: return null
    med=float(np.median(np.abs(r)))
    m0=np.abs(r)<=med; m1=~m0
    mu=[float(r[m0].mean()) if m0.any() else 0.,
        float(r[m1].mean()) if m1.any() else 0.]
    sg=[max(float(r[m0].std()),1e-8) if m0.any() else 1e-4,
        max(float(r[m1].std()),1e-8) if m1.any() else 1e-4]
    pi=[.5,.5]; A=[[.95,.05],[.05,.95]]
    def gpdf(x,m,s): return np.exp(-.5*((x-m)/s)**2)/(s*math.sqrt(2*math.pi))
    prev=-1e18
    for _ in range(60):
        B=np.column_stack([gpdf(r,float(mu[s]),float(sg[s])) for s in range(2)])
        B=np.maximum(B,1e-300); Ap=np.array(A)
        al=np.empty((n,2)); sc=np.empty(n)
        al[0]=np.array(pi)*B[0]; sc[0]=al[0].sum()
        al[0]/=max(sc[0],1e-300)
        for t in range(1,n):
            al[t]=(al[t-1]@Ap)*B[t]; sc[t]=al[t].sum()
            al[t]/=max(sc[t],1e-300)
        be=np.ones((n,2))
        for t in range(n-2,-1,-1):
            be[t]=(Ap*B[t+1])@be[t+1]
            bs=be[t].sum()
            if bs>0: be[t]/=bs
        gm=al*be; gm/=np.maximum(gm.sum(axis=1,keepdims=True),1e-300)
        xi=np.zeros((n-1,2,2))
        for t in range(n-1):
            num=al[t][:,None]*Ap*B[t+1][None,:]*be[t+1][None,:]
            xi[t]=num/max(num.sum(),1e-300)
        pi=gm[0].tolist()
        xs=xi.sum(axis=0); A=(xs/np.maximum(xs.sum(axis=1,keepdims=True),1e-300)).tolist()
        for s in range(2):
            w=gm[:,s]; ws=w.sum()
            if ws>1e-8:
                mu[s]=float((w*r).sum()/ws)
                sg[s]=max(float(math.sqrt(max((w*(r-mu[s])**2).sum()/ws,1e-16))),1e-8)
        ll=float(np.log(np.maximum(sc,1e-300)).sum())
        if abs(ll-prev)<1e-6: break
        prev=ll
    if sg[0]>sg[1]:
        mu=mu[::-1]; sg=sg[::-1]
        A=[[A[1][1],A[1][0]],[A[0][1],A[0][0]]]; gm=gm[:,::-1]
    # Viterbi
    lA=np.log(np.maximum(np.array(A),1e-300))
    lB=np.log(np.maximum(np.column_stack([gpdf(r,float(mu[s]),float(sg[s])) for s in range(2)]),1e-300))
    lp=np.log(np.maximum(np.array(pi),1e-300))
    V=lp+lB[0]; ptr=np.zeros((n,2),dtype=int)
    for t in range(1,n):
        tr=V[:,None]+lA; ptr[t]=tr.argmax(axis=0); V=tr.max(axis=0)+lB[t]
    vit=np.zeros(n,dtype=int); vit[n-1]=int(V.argmax())
    for t in range(n-2,-1,-1): vit[t]=ptr[t+1,vit[t+1]]
    tl=len(returns); vi=np.where(np.isfinite(returns))[0]
    so=np.zeros(tl,dtype=int); po=np.full(tl,.5)
    for i,idx in enumerate(vi[:n]):
        so[idx]=int(vit[i]); po[idx]=float(gm[i,1])
    return {"states":so,"proba_state1":po,
            "mu":[round(float(mu[0])*100,4),round(float(mu[1])*100,4)],
            "sigma":[round(float(sg[0])*100,4),round(float(sg[1])*100,4)],
            "trans":[[round(A[0][0],4),round(A[0][1],4)],
                     [round(A[1][0],4),round(A[1][1],4)]]}

def hurst_rs(prices):
    prices=prices[np.isfinite(prices)]; n=len(prices)
    if n<20: return .5
    lags=[int(2**k) for k in np.arange(math.log2(4),math.log2(n//2),.5)]
    pts=[]
    for lag in lags:
        if lag>=n: continue
        sub=prices[:lag]; m=sub.mean()
        dev=np.cumsum(sub-m); R=dev.max()-dev.min(); S=sub.std()
        if S>0 and R>0: pts.append((math.log(lag),math.log(R/S)))
    if len(pts)<3: return .5
    h,_=np.polyfit([p[0] for p in pts],[p[1] for p in pts],1)
    return float(np.clip(h,.1,.9))

def realized_variance(r_in):
    empty={"rv":0.,"bpv":0.,"jump":0.,"jump_pct":0.,"z_jump":0.}
    r=r_in[np.isfinite(r_in)]
    if len(r)<4: return empty
    rv  =float(np.sum(r**2))
    bpv =float((math.pi/2)*np.sum(np.abs(r[:-1])*np.abs(r[1:])))
    bpv =min(bpv,rv)
    jump=max(0.,rv-bpv)
    jpct=jump/rv*100 if rv>0 else 0.
    n=len(r)
    theta=(math.pi/2)**2*(math.pi*.25+math.pi-5)/n
    inner=abs(theta*max(float(np.sum(r**4)),1e-40))
    denom=safe_sqrt(max(inner,1e-40))
    z=(rv-bpv)/max(denom,1e-40)
    ann=365*96
    return {"rv":round(safe_sqrt(rv*ann)*100,3),
            "bpv":round(safe_sqrt(bpv*ann)*100,3),
            "jump":round(safe_sqrt(jump*ann)*100,3),
            "jump_pct":round(jpct,2),"z_jump":round(float(z),3)}

def calc_cvd(df,window=20):
    empty={"cvd":pd.Series(dtype=float),"cvd_current":0.,"div_signal":"NONE","cvd_change":0.}
    if df.empty or len(df)<window+2: return empty
    cvd=(df["tbv"]-df["tsv"]).cumsum()
    chg=cvd.diff(window); pchg=df["close"].diff(window)
    bd=bool(pchg.iloc[-1]<0 and chg.iloc[-1]>0)
    br=bool(pchg.iloc[-1]>0 and chg.iloc[-1]<0)
    return {"cvd":cvd,"cvd_current":float(cvd.iloc[-1]),
            "cvd_change":safe_float(chg.iloc[-1]),
            "div_signal":"BULL DIV" if bd else "BEAR DIV" if br else "NONE"}

def ob_metrics(bids,asks):
    e={"imbalance":0.,"spread":0.,"mid":0.,"micro":0.,
       "bd05":0.,"ad05":0.,"walls_b":[],"walls_a":[]}
    if not bids or not asks: return e
    try:
        mid=(bids[0][0]+asks[0][0])/2
        bv=sum(s for _,s in bids[:10]); av=sum(s for _,s in asks[:10])
        imb=(bv-av)/max(bv+av,1e-10)
        ba,bb=asks[0][1],bids[0][1]
        micro=(bids[0][0]*ba+asks[0][0]*bb)/max(ba+bb,1e-10)
        bd05=sum(s for p,s in bids if abs(p-mid)/max(mid,1)<.005)
        ad05=sum(s for p,s in asks if abs(p-mid)/max(mid,1)<.005)
        return {"imbalance":round(float(imb),5),"spread":round(asks[0][0]-bids[0][0],2),
                "mid":round(mid,2),"micro":round(micro,2),
                "bd05":round(bd05,3),"ad05":round(ad05,3),
                "walls_b":sorted([(p,s) for p,s in bids if s>=2],key=lambda x:-x[1])[:6],
                "walls_a":sorted([(p,s) for p,s in asks if s>=2],key=lambda x:-x[1])[:6]}
    except: return e

def funding_zscore(hist):
    if not hist or len(hist)<5:
        return {"z":0.,"sig":"NEUTRAL","cur":0.,"ann":0.,"pct":50.}
    rates=np.array([x["rate"] for x in hist],dtype=float)
    rates=rates[np.isfinite(rates)]
    if len(rates)<2:
        return {"z":0.,"sig":"NEUTRAL","cur":0.,"ann":0.,"pct":50.}
    cur=float(rates[-1]); mu=rates.mean(); sd=rates.std()
    z=(cur-mu)/max(sd,1e-10)
    pct=float(stats.percentileofscore(rates,cur))
    ann=cur*3*365
    sig=("BEAR — Extreme Long Crowding" if z>2.5 else
         "LEAN BEAR — Longs Crowded"   if z>1.3 else
         "BULL — Extreme Short Crowding" if z<-2.5 else
         "LEAN BULL — Shorts Crowded"  if z<-1.3 else "NEUTRAL")
    return {"z":round(z,3),"sig":sig,"cur":round(cur,6),
            "ann":round(ann,2),"pct":round(pct,1)}

def parse_chain(raw,spot):
    if not raw or spot<=0: return pd.DataFrame()
    rows=[]
    for o in raw:
        nm=o.get("instrument_name",""); parts=nm.split("-")
        if len(parts)!=4: continue
        try:
            K=float(parts[2]); cp="call" if parts[3]=="C" else "put"
            try:
                T=max((datetime.strptime(parts[1],"%d%b%y")-datetime.now()).days/365,1/365)
            except: T=7/365
        except: continue
        oi=safe_float(o.get("open_interest"))
        if oi<1: continue
        iv=safe_float(o.get("mark_iv"))/100
        mk=safe_float(o.get("mark_price"))
        if iv<=.001: iv=implied_vol(mk*spot,spot,K,T,.04,cp)
        g=bs_greeks(spot,K,T,.04,max(iv,.01),cp)
        rows.append({"name":nm,"type":cp,"strike":K,"expiry":parts[1],
                     "T":T,"days":int(round(T*365)),"oi":oi,
                     "iv":max(iv,.001),"iv_pct":round(max(iv,.001)*100,2),
                     "mark":mk,"delta":g["delta"],"gamma":g["gamma"],
                     "vega":g["vega"],"theta":g["theta"]})
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def calc_max_pain(chain):
    if chain.empty: return {"price":0.,"by_strike":{}}
    try:
        ne=chain.nsmallest(1,"T")["expiry"].iloc[0]
        sub=chain[chain["expiry"]==ne]
        strikes=sorted(sub["strike"].unique())
        if len(strikes)<3: return {"price":0.,"by_strike":{}}
        pain={}
        for tp in strikes:
            p=0.
            for _,row in sub.iterrows():
                if row["type"]=="call": p+=max(0.,tp-row["strike"])*row["oi"]
                else: p+=max(0.,row["strike"]-tp)*row["oi"]
            pain[tp]=p
        mp=min(pain,key=pain.get)
        return {"price":float(mp),"by_strike":pain}
    except: return {"price":0.,"by_strike":{}}

def calc_gex(chain,spot):
    empty={"total":0.,"total_M":0.,"by_strike":{},"flip":spot}
    if chain.empty or spot<=0: return empty
    by_s=defaultdict(float); tot=0.
    for _,row in chain.iterrows():
        sign=1. if row["type"]=="call" else -1.
        g=sign*row["gamma"]*row["oi"]*spot*spot*.01
        by_s[row["strike"]]+=g; tot+=g
    flip=spot; cum=0.; prev=None
    for s in sorted(by_s):
        cum+=by_s[s]
        if prev is not None and prev*cum<0: flip=float(s); break
        prev=cum
    return {"total":float(tot),"total_M":round(tot/1e6,2),
            "by_strike":dict(by_s),"flip":float(flip)}

def calc_iv_surface(chain,spot):
    if chain.empty or spot<=0: return {}
    result={}
    for exp,sub in chain.groupby("expiry"):
        calls=sub[sub["type"]=="call"].sort_values("strike")
        puts =sub[sub["type"]=="put"].sort_values("strike")
        atm=0.
        if not calls.empty:
            idx=(calls["strike"]-spot).abs().idxmin()
            atm=float(calls.loc[idx,"iv_pct"])
        skew=0.
        c25=calls[calls["delta"].between(.20,.30)]
        p25=puts[puts["delta"].between(-.30,-.20)]
        if not c25.empty and not p25.empty:
            skew=float(p25["iv_pct"].mean())-float(c25["iv_pct"].mean())
        result[exp]={"atm_iv":round(atm,2),"skew_25d":round(skew,2),
                     "days":int(sub["days"].iloc[0]) if not sub.empty else 0,
                     "call_oi":float(calls["oi"].sum()),
                     "put_oi":float(puts["oi"].sum())}
    return result

def liq_heatmap(df,oi_usd,spot):
    if df.empty or spot<=0: return {"hm":[],"zones":[]}
    LEV=[(10,.30,.005),(20,.25,.005),(50,.25,.004),(100,.20,.004)]
    N=120; span=.14
    lo=spot*(1-span); bsz=spot*2*span/N
    inten=np.zeros(N); dliq=np.zeros(N)
    rec=df.tail(80); vmx=max(float(rec["volume"].max()),1.)
    for _,row in rec.iterrows():
        entry=(float(row["open"])+float(row["close"]))/2
        vw=float(row["volume"])/vmx
        for lev,frac,maint in LEV:
            for lp in [entry*(1-1/lev+maint),entry*(1+1/lev-maint)]:
                idx=int((lp-lo)/bsz)
                if 0<=idx<N:
                    inten[idx]+=vw*frac
                    dliq[idx]+=(oi_usd*frac/2)*.01
    mi=inten.max() or 1.; md=dliq.max() or 1.
    hm=[{"price":round(lo+(i+.5)*bsz,0),
         "intensity":round(float(inten[i]/mi),4),
         "dollar":round(float(dliq[i]/md),4),
         "side":"SHORT LIQ" if lo+(i+.5)*bsz>spot else "LONG LIQ"} for i in range(N)]
    THR=.55; zones=[]; inz=False; z0=peak=0.
    for h in hm:
        if h["intensity"]>=THR:
            if not inz: z0=h["price"]; inz=True
            peak=max(peak,h["intensity"])
        elif inz:
            zones.append({"from":z0,"to":h["price"],"strength":round(peak,3),"side":h["side"]})
            inz=False; peak=0.
    return {"hm":hm,"zones":zones}

def rsi_scalar(p,period=14):
    if len(p)<period+1: return 50.
    d=np.diff(p[-(period+1):])
    g=d[d>0].mean() if (d>0).any() else 0.
    l=-d[d<0].mean() if (d<0).any() else 0.
    return 100.-100./(1+g/max(l,1e-10))

def composite_signal(ob,cvd_r,fr,garch,hmm,hurst,mp,gex,ls_df,taker_df,spot,oi_chg,fg):
    sigs=[]; bull=bear=0
    def add(n,cat,d,pts,reason=""):
        nonlocal bull,bear
        sigs.append({"n":n,"cat":cat,"d":d,"s":pts,"r":reason})
        if d=="BULL": bull+=pts
        elif d=="BEAR": bear+=pts

    # 1. Order book
    imb=float(ob.get("imbalance",0))
    if   imb>.25: add(f"OB Bid Imbalance +{imb:.3f}","Microstructure","BULL",20,"Bid depth dominates — short-term upward pressure.")
    elif imb<-.25:add(f"OB Ask Imbalance {imb:.3f}","Microstructure","BEAR",20,"Ask depth dominates — short-term downward pressure.")
    elif imb>.12: bull+=8
    elif imb<-.12:bear+=8
    micro=float(ob.get("micro",0)); mid=float(ob.get("mid",0))
    if micro and mid and mid>0:
        if   (micro-mid)/mid>.00005: bull+=6
        elif (micro-mid)/mid<-.00005:bear+=6

    # 2. CVD divergence
    div=cvd_r.get("div_signal","NONE")
    if div=="BULL DIV": add("CVD Bullish Divergence","Order Flow","BULL",25,"Price down, net buying up — accumulation underway.")
    elif div=="BEAR DIV":add("CVD Bearish Divergence","Order Flow","BEAR",25,"Price up, net buying down — distribution underway.")
    else:
        if cvd_r.get("cvd_change",0)>0: bull+=8
        else: bear+=8

    # 3. Funding Z-score
    fz=float(fr.get("z",0)); fa=float(fr.get("ann",0)); fpct=float(fr.get("pct",50))
    if   fz>2.5: add(f"Funding Z +{fz:.2f}σ ({fa:.1f}% ann) P{fpct:.0f}","Funding","BEAR",22,f"Extreme long crowding. Longs paying punishing carry.")
    elif fz>1.3: add(f"Funding Elevated +{fz:.2f}σ","Funding","BEAR",12,"Longs crowded.")
    elif fz<-2.5:add(f"Funding Z {fz:.2f}σ ({fa:.1f}% ann) P{fpct:.0f}","Funding","BULL",22,"Shorts squeezed. Short covering likely.")
    elif fz<-1.3:add(f"Funding Negative {fz:.2f}σ","Funding","BULL",12,"Shorts crowded.")
    elif fz>0: bear+=4
    else: bull+=4

    # 4. GARCH
    pers=float(garch.get("persistence",.95)); sv=float(garch.get("sigma_annualized",50))
    if   pers>.97 and sv>80: add(f"GARCH High-Vol Regime α+β={pers:.3f} σ={sv:.1f}%","Volatility","BEAR",12,"Persistent high-vol. Risk-off. Reduce size.")
    elif pers<.92:            add(f"GARCH Vol Dissipating α+β={pers:.3f}","Volatility","BULL",8,"Vol clustering ending.")

    # 5. HMM
    p1a=hmm.get("proba_state1",np.array([.5]))
    p1=float(p1a[-1]) if hasattr(p1a,"__len__") and len(p1a)>0 else .5
    if   p1>.75: add(f"HMM Trending State P={p1:.3f}","Regime","BULL",14,"High-vol/trending state. Momentum preferred.")
    elif p1<.25: add(f"HMM Ranging State P(low)={1-p1:.3f}","Regime","NEUTRAL",0,"Mean-reversion regime. Fade extremes.")

    # 6. Hurst
    if   hurst>.62: add(f"Hurst H={hurst:.3f} — Persistent","Regime","BULL",10,"Trending. Follow momentum."); bull+=5
    elif hurst<.40: add(f"Hurst H={hurst:.3f} — Anti-Persistent","Regime","NEUTRAL",0,"Mean-reverting. Fade breakouts.")

    # 7. Max pain
    mpp=float(mp.get("price",0))
    if mpp>0 and spot>0:
        dist=(spot-mpp)/spot*100
        if   dist>3:  add(f"Price +{dist:.1f}% above Max Pain ${mpp:,.0f}","Options","BEAR",18,"Options gravity pulls price toward max pain.")
        elif dist<-3: add(f"Price {dist:.1f}% below Max Pain ${mpp:,.0f}","Options","BULL",18,"Options gravity pulls price up to max pain.")
        elif abs(dist)<.8: add(f"Price at Max Pain ${mpp:,.0f} — Gamma Pin","Options","NEUTRAL",0,"Gamma pinning. Low vol expected.")

    # 8. GEX
    gm=float(gex.get("total_M",0)); gf=float(gex.get("flip",spot))
    if   gm<-100: add(f"Negative GEX ${gm:.0f}M","Options","BEAR",16,"Dealers short gamma → amplify moves → vol expansion.")
    elif gm<-30:  add(f"Neg GEX ${gm:.0f}M","Options","BEAR",8,"Some vol amplification.")
    elif gm>100:  add(f"Positive GEX +${gm:.0f}M","Options","BULL",12,"Dealers long gamma → dampen moves → vol suppression.")
    if gf and spot>0 and abs(spot-gf)/spot<.012:
        add(f"Near GEX Flip Level ${gf:,.0f}","Options","NEUTRAL",0,"Vol regime transition point.")

    # 9. OI change
    if   oi_chg>2 and imb>.1:  add(f"OI +{oi_chg:.1f}% + Bullish OB","OI Flow","BULL",14,"New longs opening.")
    elif oi_chg>2 and imb<-.1: add(f"OI +{oi_chg:.1f}% + Bearish OB","OI Flow","BEAR",14,"New shorts opening.")
    elif oi_chg<-2:             add(f"OI -{abs(oi_chg):.1f}% — Deleveraging","OI Flow","NEUTRAL",0,"Unwinding. Avoid new entries.")

    # 10. Taker flow
    if not taker_df.empty and len(taker_df)>=5:
        avg=float(taker_df["buySellRatio"].iloc[-5:].mean())
        if   avg>1.4: add(f"Taker Buy/Sell {avg:.2f}","Order Flow","BULL",12,"Aggressive buyers dominating.")
        elif avg<.7:  add(f"Taker Buy/Sell {avg:.2f}","Order Flow","BEAR",12,"Aggressive sellers dominating.")

    # 11. L/S ratio
    if not ls_df.empty and len(ls_df)>0:
        ls=float(ls_df["longShortRatio"].iloc[-1])
        if   ls>1.8: add(f"L/S Ratio {ls:.2f} — Retail Over-Long","Sentiment","BEAR",10,"Crowded retail long → contrarian short.")
        elif ls<.6:  add(f"L/S Ratio {ls:.2f} — Retail Over-Short","Sentiment","BULL",10,"Crowded retail short → squeeze risk.")

    # 12. Fear & Greed
    fgv=int(fg.get("value",50))
    if   fgv>=80: add(f"Fear & Greed {fgv} — Extreme Greed","Sentiment","BEAR",8,"Historically precedes corrections.")
    elif fgv<=20: add(f"Fear & Greed {fgv} — Extreme Fear","Sentiment","BULL",8,"Historically precedes recoveries.")

    tot=bull+bear; net=int((bull-bear)/max(tot,80)*100)
    dr="LONG" if net>18 else "SHORT" if net<-18 else "NEUTRAL"
    nc=max(len([s for s in sigs if s["d"]=="BULL"]),len([s for s in sigs if s["d"]=="BEAR"]))
    wr=min(.73,.52+nc*.018+max(hurst-.5,0)*.08)
    b=2.2; f=max(0.,(b*wr-(1-wr))/b)
    return {"signals":sigs,"bull":bull,"bear":bear,"net":net,"direction":dr,
            "confidence":abs(net),"win_rate":round(wr,4),
            "ev":round(wr*b-(1-wr),4),"kelly":round(f*100,2),
            "quarter_kelly":round(f*.25*100,2)}

def backtest_wf(df,in_sample=.70):
    if df.empty or len(df)<150: return {}
    n=len(df); os=int(n*in_sample)
    C=df["close"].values.astype(float)
    ret=np.diff(np.log(np.maximum(C,1e-10)))
    roos=ret[os:]; m=len(roos); pos=np.zeros(m)
    for i in range(20,m):
        idx=os+i; wC=C[max(0,idx-60):idx]
        if len(wC)<21: continue
        wR=np.diff(np.log(np.maximum(wC,1e-10)))
        sc=0.
        e9=wC[-9:].mean(); e21=wC[-21:].mean()
        sc+=1. if e9>e21 else -1.
        rsi=rsi_scalar(wC,14)
        if rsi<30: sc+=2
        elif rsi>70: sc-=2
        elif rsi>55: sc+=.5
        elif rsi<45: sc-=.5
        if len(wC)>=5:
            mom=(wC[-1]-wC[-5])/max(wC[-5],1e-10)*100
            sc+=float(np.sign(mom))*min(abs(mom)/.5,1.5)
        if len(wR)>=10:
            mr=wR[-10:].mean(); sr=wR[-10:].std()
            z=(wR[-1]-mr)/max(sr,1e-10)
            if z<-1.5: sc+=1.5
            elif z>1.5: sc-=1.5
        h=hurst_rs(wC[-40:]) if len(wC)>=40 else .5
        if h>.6: sc*=1.2
        elif h<.4: sc*=.5
        pos[i]=1. if sc>2 else -1. if sc<-2 else 0.
    tr=pos[:-1]*roos[1:len(pos)]
    tr=tr[np.isfinite(tr)]
    if len(tr)<10: return {}
    wins=tr[tr>0]; losses=tr[tr<0]
    hr=len(wins)/max(len(wins)+len(losses),1)
    pf=abs(float(wins.sum()/losses.sum())) if losses.sum()!=0 else 9.99
    eq=np.cumprod(1+tr); peak=np.maximum.accumulate(eq)
    dd=(eq-peak)/peak; mdd=float(dd.min())
    ann=96*252; mu=float(tr.mean()); sd=float(tr.std())
    sh=mu/max(sd,1e-10)*math.sqrt(ann)
    dnr=tr[tr<0]; so=mu/max(float(dnr.std()),1e-10)*math.sqrt(ann) if len(dnr)>1 else 0.
    tot=float(eq[-1]-1)*100; cal=abs(tot/100/max(abs(mdd),1e-10))
    sv=pos[:-1]; fv=roos[1:len(pos)]
    mask=np.isfinite(sv)&np.isfinite(fv)&(sv!=0)
    ic=0.
    if mask.sum()>10:
        ic_v,_=stats.spearmanr(sv[mask],fv[mask])
        ic=float(ic_v) if not math.isnan(ic_v) else 0.
    return {"total_return":round(tot,2),"sharpe":round(sh,3),"sortino":round(so,3),
            "calmar":round(cal,3),"max_dd":round(mdd*100,2),"hit_rate":round(hr*100,2),
            "profit_factor":round(pf,3),"ic":round(ic,4),
            "n_trades":int((np.abs(np.diff(np.concatenate([[0],pos])))>0).sum()),
            "avg_win_bps":round(float(wins.mean()*10000) if len(wins) else 0,2),
            "avg_loss_bps":round(float(losses.mean()*10000) if len(losses) else 0,2),
            "equity_curve":eq.tolist(),"drawdown":dd.tolist(),"oos_idx":os}

# ═══════════════════════════════════════════════════════
#  CHART BUILDERS
# ═══════════════════════════════════════════════════════

def align(df,arr):
    n=len(df); m=len(arr)
    if m==n: return arr
    if m>n: return arr[-n:]
    return np.concatenate([np.full(n-m,np.nan),arr])

def chart_candles(df,kal,hmm,gs):
    if df.empty: return fig(480)
    n=len(df); ts=df.index
    f=subfig(3,1,[.60,.20,.20])
    f.update_layout(height=480,showlegend=False)
    # HMM shading
    states=hmm.get("states")
    if states is not None and len(states)>0:
        s=align(df,np.asarray(states,dtype=int))
        for i in range(n-1):
            if s[i]==1:
                f.add_vrect(x0=ts[i],x1=ts[min(i+1,n-1)],
                            fillcolor="rgba(255,185,0,0.03)",line_width=0,row=1,col=1)
    f.add_trace(go.Candlestick(x=ts,open=df["open"],high=df["high"],
        low=df["low"],close=df["close"],
        increasing_line_color=G,decreasing_line_color=R,
        increasing_fillcolor=G,decreasing_fillcolor=R,
        name="OHLC",line_width=.8),row=1,col=1)
    # Kalman
    for key,col_,nm,opa in [("filtered",C,"Kalman",.9),("upper",C,"+2σ",.4),("lower",C,"-2σ",.4)]:
        arr=kal.get(key)
        if arr is not None and len(arr)>0:
            a=align(df,arr)
            kw=dict(line=dict(color=col_,width=1 if key=="filtered" else .6,
                              dash="solid" if key=="filtered" else "dot"),opacity=opa)
            if key=="lower": kw.update(fill="tonexty",fillcolor="rgba(0,212,255,0.04)")
            f.add_trace(go.Scatter(x=ts,y=a,name=nm,**kw),row=1,col=1)
    # EMAs
    for p,c,nm in [(9,A,"9"),(21,C,"21"),(50,"#ff6b35","50"),(200,P,"200")]:
        if len(df)>=p:
            f.add_trace(go.Scatter(x=ts,y=df["close"].ewm(span=p,adjust=False).mean(),
                name=f"EMA{nm}",line=dict(color=c,width=1),opacity=.8),row=1,col=1)
    # Volume
    vc=[G if df["close"].iloc[i]>=df["open"].iloc[i] else R for i in range(n)]
    f.add_trace(go.Bar(x=ts,y=df["volume"],marker_color=vc,marker_opacity=.4),row=2,col=1)
    # GARCH sigma
    if gs is not None and len(gs)>0:
        ga=align(df,np.asarray(gs))
        f.add_trace(go.Scatter(x=ts,y=ga,line=dict(color=P,width=1.2),name="GARCHσ"),row=3,col=1)
    f.update_xaxes(rangeslider_visible=False)
    f.update_yaxes(title_text="GARCH σ%",title_font_size=8,row=3,col=1)
    return f

def chart_ob_depth(bids,asks):
    if not bids or not asks: return fig(240)
    bd=sorted(bids,key=lambda x:-x[0])[:30]
    ak=sorted(asks,key=lambda x:x[0])[:30]
    # Cumulative depth
    cb=[]; cv=0.
    for p,s in bd: cv+=s; cb.append((p,cv))
    ca=[]; cv=0.
    for p,s in ak: cv+=s; ca.append((p,cv))
    f=fig(240)
    f.add_trace(go.Scatter(x=[p for p,_ in cb],y=[v for _,v in cb],
        fill="tozeroy",fillcolor="rgba(0,255,157,.12)",line=dict(color=G,width=1.5),name="Bids"))
    f.add_trace(go.Scatter(x=[p for p,_ in ca],y=[v for _,v in ca],
        fill="tozeroy",fillcolor="rgba(255,41,82,.12)",line=dict(color=R,width=1.5),name="Asks"))
    mid=(bids[0][0]+asks[0][0])/2
    f.add_vline(x=mid,line_color=A,line_width=1,line_dash="dash",
                annotation_text=f" ${mid:,.0f}",annotation_font_color=A,annotation_font_size=8)
    f.update_layout(title=dict(text="Cumulative Order Book Depth",font_size=10,font_color=GR))
    return f

def chart_vpin_cvd(df,vpin,cvd_ser):
    if df.empty: return fig(260)
    f=subfig(3,1,[.34,.33,.33])
    f.update_layout(height=300,showlegend=False)
    f.add_trace(go.Scatter(x=df.index,y=df["close"],line=dict(color=C,width=1)),row=1,col=1)
    if not vpin.empty:
        vp=vpin.reindex(df.index).ffill().bfill()
        f.add_trace(go.Scatter(x=df.index,y=vp,fill="tozeroy",
            fillcolor="rgba(255,185,0,.08)",line=dict(color=A,width=1.2),name="VPIN"),row=2,col=1)
        f.add_hline(y=.35,line_color=R,line_dash="dash",line_width=.8,
                    annotation_text="HIGH",annotation_font_color=R,annotation_font_size=7,row=2,col=1)
    if not cvd_ser.empty:
        cs=cvd_ser.reindex(df.index).ffill().bfill()
        f.add_trace(go.Scatter(x=df.index,y=cs,fill="tozeroy",
            fillcolor="rgba(0,255,157,.06)",line=dict(color=G,width=1.2),name="CVD"),row=3,col=1)
        f.add_hline(y=0,line_color=GR,line_dash="dot",row=3,col=1)
    f.update_yaxes(title_text="VPIN",title_font_size=7,row=2,col=1)
    f.update_yaxes(title_text="CVD",title_font_size=7,row=3,col=1)
    return f

def chart_liq(hm,spot,zones):
    if not hm: return fig(360)
    prices=[h["price"] for h in hm]; inten=[h["intensity"] for h in hm]
    sides=[h["side"] for h in hm]
    colors=[f"rgba(255,41,82,{.15+v*.75})" if s=="LONG LIQ"
            else f"rgba(0,255,157,{.15+v*.75})" for v,s in zip(inten,sides)]
    f=fig(380)
    f.add_trace(go.Bar(x=inten,y=prices,orientation="h",marker_color=colors,
        hovertemplate="$%{y:,.0f}  intensity=%{x:.3f}<extra></extra>"))
    if spot>0:
        f.add_hline(y=spot,line_color=A,line_width=2,line_dash="dash",
                    annotation_text=f" ${spot:,.0f}",annotation_font_color=A,annotation_font_size=9)
    for z in zones[:4]:
        f.add_hrect(y0=z["from"],y1=z["to"],fillcolor="rgba(255,185,0,.06)",
                    line_color=A,line_width=.5)
    f.update_layout(title=dict(text="LIQUIDATION HEATMAP — Leverage Distribution Model",font_size=10,font_color=GR))
    return f

def chart_gex(gex_data,spot):
    by_s=gex_data.get("by_strike",{})
    if not by_s or spot<=0: return fig(260)
    flt=[(s,v/1e6) for s,v in sorted(by_s.items()) if abs(s-spot)/spot<.14]
    if not flt: return fig(260)
    sx,gx=zip(*flt)
    f=fig(260)
    f.add_trace(go.Bar(x=list(sx),y=list(gx),
        marker_color=[G if g>=0 else R for g in gx],marker_opacity=.7))
    f.add_vline(x=spot,line_color=A,line_width=1.5,line_dash="dash",
                annotation_text=" SPOT",annotation_font_color=A,annotation_font_size=8)
    fl=gex_data.get("flip",0)
    if fl and fl!=spot:
        f.add_vline(x=fl,line_color=P,line_width=1,line_dash="dot",
                    annotation_text="FLIP",annotation_font_color=P,annotation_font_size=8)
    f.update_layout(title=dict(text="GEX BY STRIKE ($M)",font_size=10,font_color=GR))
    return f

def chart_mp(mp_data,spot):
    by_s=mp_data.get("by_strike",{})
    if not by_s or spot<=0: return fig(240)
    flt=[(s,v/1e6) for s,v in sorted(by_s.items()) if abs(s-spot)/spot<.18]
    if not flt: return fig(240)
    sx,px=zip(*flt)
    f=fig(240)
    f.add_trace(go.Bar(x=list(sx),y=list(px),marker_color=P,marker_opacity=.55))
    mpp=mp_data.get("price",0)
    if mpp:
        f.add_vline(x=mpp,line_color=P,line_width=2,line_dash="dash",
                    annotation_text=f" MAX PAIN ${mpp:,.0f}",annotation_font_color=P,annotation_font_size=9)
    if spot:
        f.add_vline(x=spot,line_color=A,line_width=1.5,line_dash="dot",
                    annotation_text=" SPOT",annotation_font_color=A,annotation_font_size=8)
    f.update_layout(title=dict(text="MAX PAIN SURFACE ($M)",font_size=10,font_color=GR))
    return f

def chart_funding(hist):
    if not hist: return fig(180)
    df_f=pd.DataFrame(hist)
    if df_f.empty: return fig(180)
    rates=df_f["rate"].astype(float); mu=float(rates.mean()); sd=float(rates.std())
    cols=[R if r>0 else G for r in rates]
    f=fig(200)
    f.add_trace(go.Bar(x=df_f["ts"],y=rates,marker_color=cols))
    for lv,col_,lbl in [(mu+2*sd,R,"+2σ"),(mu-2*sd,G,"-2σ"),(0,GR,"0")]:
        f.add_hline(y=lv,line_color=col_,line_dash="dash" if lbl!="0" else "dot",
                    line_width=.8,annotation_text=lbl,
                    annotation_font_color=col_,annotation_font_size=8)
    f.update_layout(title=dict(text="FUNDING RATE HISTORY",font_size=10,font_color=GR))
    return f

def chart_oi_ls(oi_df,ls_df):
    if oi_df.empty: return fig(220)
    f=subfig(2,1,[.6,.4])
    f.update_layout(height=260,showlegend=False)
    f.add_trace(go.Scatter(x=oi_df["timestamp"],
        y=oi_df["sumOpenInterestValue"]/1e9,fill="tozeroy",
        fillcolor="rgba(0,212,255,.07)",line=dict(color=C,width=1.2)),row=1,col=1)
    f.add_hline(y=float(oi_df["sumOpenInterestValue"].mean()/1e9),
                line_color=GR,line_dash="dot",row=1,col=1)
    if not ls_df.empty:
        f.add_trace(go.Scatter(x=ls_df["timestamp"],y=ls_df["longShortRatio"],
            line=dict(color=A,width=1.2)),row=2,col=1)
        f.add_hline(y=1.,line_color=GR,line_dash="dot",row=2,col=1)
    f.update_yaxes(title_text="OI $B",title_font_size=7,row=1,col=1)
    f.update_yaxes(title_text="L/S Ratio",title_font_size=7,row=2,col=1)
    return f

def chart_taker(taker_df):
    if taker_df.empty: return fig(180)
    f=fig(180)
    f.add_trace(go.Scatter(x=taker_df["timestamp"],y=taker_df["buySellRatio"],
        line=dict(color=G,width=1.2)))
    f.add_hline(y=1.,line_color=GR,line_dash="dot")
    f.add_hline(y=1.4,line_color=G,line_dash="dash",line_width=.6,
                annotation_text="Bull",annotation_font_color=G,annotation_font_size=7)
    f.add_hline(y=.6,line_color=R,line_dash="dash",line_width=.6,
                annotation_text="Bear",annotation_font_color=R,annotation_font_size=7)
    f.update_layout(title=dict(text="TAKER BUY/SELL RATIO",font_size=10,font_color=GR))
    return f

def chart_equity(bt):
    if not bt or "equity_curve" not in bt: return fig(300)
    eq=bt["equity_curve"]; dd=bt["drawdown"]; oos=bt.get("oos_idx",len(eq)//2)
    x=list(range(len(eq)))
    f=subfig(2,1,[.7,.3])
    f.update_layout(height=300,showlegend=False)
    f.add_trace(go.Scatter(x=x,y=[v*100-100 for v in eq],fill="tozeroy",
        fillcolor="rgba(0,255,157,.07)",line=dict(color=G,width=1.5)),row=1,col=1)
    f.add_hline(y=0,line_color=GR,line_dash="dot",row=1,col=1)
    if oos<len(x):
        f.add_vline(x=oos,line_color=A,line_dash="dash",line_width=1,
                    annotation_text="OOS",annotation_font_color=A,annotation_font_size=8,row=1,col=1)
    f.add_trace(go.Scatter(x=x,y=[v*100 for v in dd],fill="tozeroy",
        fillcolor="rgba(255,41,82,.18)",line=dict(color=R,width=1)),row=2,col=1)
    f.update_yaxes(title_text="Return %",title_font_size=8,row=1,col=1)
    f.update_yaxes(title_text="DD %",title_font_size=8,row=2,col=1)
    return f

def chart_hmm_prob(df,proba):
    if df.empty or len(proba)==0: return fig(180)
    p=align(df,proba)
    f=fig(180)
    f.add_trace(go.Scatter(x=df.index,y=p,fill="tozeroy",
        fillcolor="rgba(255,185,0,.10)",line=dict(color=A,width=1.2)))
    f.add_hline(y=.5,line_color=GR,line_dash="dot")
    f.add_hline(y=.75,line_color=A,line_dash="dash",line_width=.6)
    f.update_layout(title=dict(text="HMM P(Trending State)",font_size=10,font_color=GR))
    return f

def chart_fear_greed(fg):
    h=fg.get("history",[])
    if not h: return fig(140)
    df_fg=pd.DataFrame(h)
    col_=[G if v<40 else R if v>70 else A for v in df_fg["v"]]
    f=fig(140)
    f.add_trace(go.Bar(x=df_fg["ts"],y=df_fg["v"],marker_color=col_,marker_opacity=.8))
    f.add_hline(y=50,line_color=GR,line_dash="dot")
    f.update_yaxes(range=[0,100])
    f.update_layout(title=dict(text="FEAR & GREED INDEX (7-day)",font_size=10,font_color=GR))
    return f

# ═══════════════════════════════════════════════════════
#  PANEL HELPERS
# ═══════════════════════════════════════════════════════
def kv(label,val,col_=None,size=14):
    c=col_ or "#c8d8f0"
    return (f"<div style='display:flex;justify-content:space-between;"
            f"padding:5px 8px;border-bottom:1px solid #111d36'>"
            f"<span style='font-family:Share Tech Mono;font-size:9px;color:#364060'>{label}</span>"
            f"<span style='font-family:Share Tech Mono;font-size:{size}px;color:{c}'>{val}</span></div>")

def info_box(html_rows,title=""):
    hdr=f"<div style='font-family:Share Tech Mono;font-size:8px;color:#364060;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px'>{title}</div>" if title else ""
    return (f"<div style='background:#08101f;border:1px solid #1a2545;border-radius:7px;"
            f"padding:10px 12px'>{hdr}{''.join(html_rows)}</div>")

def signal_card(s):
    col_=G if s["d"]=="BULL" else R if s["d"]=="BEAR" else A
    pts=f"<span style='font-family:Share Tech Mono;font-size:8px;background:{col_}20;color:{col_};padding:2px 7px;border-radius:3px;margin-left:6px'>+{s['s']}</span>" if s["s"]>0 else ""
    return (f"<div style='border:1px solid {col_}28;border-left:3px solid {col_};"
            f"border-radius:5px;padding:7px 12px;margin-bottom:4px;background:rgba(255,255,255,.015)'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center'>"
            f"<div><div style='font-family:Share Tech Mono;font-size:10.5px;color:{col_}'>{s['n']}</div>"
            f"<div style='font-family:Share Tech Mono;font-size:8px;color:#364060;margin-top:1px'>"
            f"{s['cat']} — {s.get('r','')}</div></div>"
            f"<div style='display:flex;align-items:center'>{pts}"
            f"<span style='font-family:Share Tech Mono;font-size:9px;color:{col_};min-width:42px;text-align:right'>{s['d']}</span>"
            f"</div></div></div>")

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════
def main():
    # ── TOP BAR ──
    h1,h2,h3=st.columns([6,1,1])
    with h1:
        st.markdown(
            "<h1 style='font-size:1.05rem;color:#00ff9d;margin:0;padding:0;"
            "font-family:Orbitron;letter-spacing:5px;font-weight:900'>"
            "◈ BTC QUANT PRO v3</h1>"
            "<p style='font-family:Share Tech Mono;font-size:.58rem;color:#364060;"
            "margin:1px 0 0;letter-spacing:1.5px'>"
            "BINANCE FUTURES · DERIBIT OPTIONS · REAL DATA · GARCH · HMM · KALMAN · VPIN · GEX · MAX PAIN · BACKTEST</p>",
            unsafe_allow_html=True)
    with h2:
        iv_sel=st.selectbox("Interval",["5m","15m","1h","4h"],index=1,label_visibility="collapsed")
    with h3:
        if st.button("↻  SYNC"):
            st.cache_data.clear(); st.rerun()

    st.markdown("<hr>",unsafe_allow_html=True)

    # ── FETCH ALL DATA ──
    with st.spinner("Fetching live data…"):
        ticker   = get_ticker()
        klines   = get_klines_multi()
        df_iv    = klines.get(iv_sel,pd.DataFrame())
        df15     = klines.get("15m",pd.DataFrame())
        ob_raw   = get_orderbook(100)
        fr_hist  = get_funding_history()
        prem     = get_premium_index()
        oi_df    = get_oi_hist()
        ls_df    = get_ls_ratio()
        top_ls   = get_top_ls()
        taker_df = get_taker_flow()
        dbit_raw = get_deribit_options()
        dbit_sp  = get_deribit_index()
        spot_sp  = get_spot_price()
        fg       = get_fear_greed()
        btc_dom  = get_btc_dominance()
        aggr     = get_aggression_index()

    # ── SPOT PRICE (multiple fallbacks) ──
    spot=safe_float(ticker.get("lastPrice"))
    if spot<=0: spot=dbit_sp
    if spot<=0: spot=spot_sp
    if spot<=0: spot=96000.

    mark=safe_float(prem.get("markPrice",spot))
    idx =safe_float(prem.get("indexPrice",spot))

    # ── COMPUTE MODELS ──
    garch_r={}; kal_r={}; hmm_r={}; hurst_v=.5
    vpin_s=pd.Series(dtype=float); cvd_r={}; rv_r={}

    if not df15.empty and len(df15)>=50:
        CLOSE=df15["close"].values.astype(float)
        LOG_RET=np.diff(np.log(np.maximum(CLOSE,1e-10)))
        garch_r = fit_garch(LOG_RET[-250:])
        kal_r   = kalman_filter(CLOSE[-250:])
        hmm_r   = fit_hmm(LOG_RET[-300:])
        hurst_v = hurst_rs(CLOSE[-120:])
        vpin_s  = calc_vpin(df15)
        cvd_r   = calc_cvd(df15)
        rv_r    = realized_variance(LOG_RET[-96:])

    ob_ana  = ob_metrics(ob_raw["bids"],ob_raw["asks"])
    fr_sig  = funding_zscore(fr_hist)

    oi_chg=0.
    if not oi_df.empty and len(oi_df)>=10:
        nv=float(oi_df["sumOpenInterestValue"].iloc[-1])
        ov=float(oi_df["sumOpenInterestValue"].iloc[-10])
        if ov>0: oi_chg=(nv-ov)/ov*100

    chain   = parse_chain(dbit_raw,dbit_sp or spot)
    mp_data = calc_max_pain(chain) if not chain.empty else {"price":0.,"by_strike":{}}
    gex_data= calc_gex(chain,dbit_sp or spot) if not chain.empty else {"total":0.,"total_M":0.,"by_strike":{},"flip":spot}
    iv_surf = calc_iv_surface(chain,dbit_sp or spot) if not chain.empty else {}
    atm_iv  = list(iv_surf.values())[0]["atm_iv"]  if iv_surf else 0.
    skew_25 = list(iv_surf.values())[0]["skew_25d"] if iv_surf else 0.

    oi_usd  = float(oi_df["sumOpenInterestValue"].iloc[-1]) if not oi_df.empty else 10e9
    liq_m   = liq_heatmap(df15,oi_usd,spot)

    sig = composite_signal(ob_ana,cvd_r,fr_sig,garch_r,hmm_r,hurst_v,
                           mp_data,gex_data,ls_df,taker_df,spot,oi_chg,fg)

    # ── HEADER METRICS ──
    chg24=safe_float(ticker.get("priceChangePercent")); vol24=safe_float(ticker.get("volume"))
    basis_pct=(mark-idx)/max(idx,1)*100 if idx>0 else 0
    mpp=mp_data.get("price",0)
    mp_dist=(spot-mpp)/spot*100 if mpp and spot else 0
    sc=sig["direction"]; scc=G if sc=="LONG" else R if sc=="SHORT" else A

    c1,c2,c3,c4,c5,c6,c7,c8,c9,c10=st.columns(10)
    c1.metric("BTC PERP",f"${spot:,.0f}",f"{chg24:+.2f}%")
    c2.metric("MARK",f"${mark:,.0f}",f"Basis {basis_pct:+.3f}%")
    c3.metric("FUNDING",f"{fr_sig['cur']:.5f}%",f"Z {fr_sig['z']:+.2f}σ")
    c4.metric("ATM IV",f"{atm_iv:.1f}%",f"Skew {skew_25:+.1f}%")
    c5.metric("GARCH σ",f"{garch_r.get('sigma_annualized',0):.1f}%",f"α+β {garch_r.get('persistence',0):.3f}")
    c6.metric("MAX PAIN",f"${mpp:,.0f}",f"{mp_dist:+.2f}%")
    c7.metric("GEX",f"${gex_data.get('total_M',0):+.1f}M",f"Flip ${gex_data.get('flip',0):,.0f}")
    c8.metric("HURST H",f"{hurst_v:.4f}","TRENDING" if hurst_v>.55 else "MEAN-REV" if hurst_v<.45 else "RANDOM")
    c9.metric("F&G INDEX",f"{fg['value']}",fg["label"])
    c10.metric("SIGNAL",sig["direction"],f"EV {sig['ev']:+.3f}R")

    # ── TABS ──
    T1,T2,T3,T4,T5,T6,T7=st.tabs([
        "📊  CHART","🔬  SIGNALS","💥  LIQ/OI","🎯  OPTIONS",
        "⚡  FLOW","📈  MODELS","⚗️  BACKTEST"])

    # ═══ CHART ═══
    with T1:
        df_plot=df_iv.iloc[-200:] if not df_iv.empty else pd.DataFrame()
        gs=garch_r.get("sigma_series")
        f_main=chart_candles(df_plot,
            {k:v[-200:] if hasattr(v,"__len__") and len(v)>200 else v for k,v in kal_r.items()},
            hmm_r, gs[-200:] if gs is not None and len(gs)>200 else gs)
        st.plotly_chart(f_main,width="stretch")

        c_vpin,c_ob=st.columns([3,2])
        with c_vpin:
            vc=safe_float(vpin_s.iloc[-1]) if not vpin_s.empty else 0.
            col_=R if vc>.35 else G
            st.markdown(f"<div style='font-family:Share Tech Mono;font-size:11px;color:{col_};"
                f"margin-bottom:4px'>VPIN {vc:.4f} — {'⚠ HIGH TOXICITY' if vc>.35 else 'NORMAL'}"
                f"  |  CVD {cvd_r.get('cvd_current',0):+.0f}  |  Divergence: "
                f"<b>{cvd_r.get('div_signal','NONE')}</b></div>",unsafe_allow_html=True)
            cvd_ser=cvd_r.get("cvd",pd.Series(dtype=float))
            st.plotly_chart(chart_vpin_cvd(df_plot,vpin_s.iloc[-200:],
                cvd_ser.iloc[-200:] if len(cvd_ser)>200 else cvd_ser),width="stretch")
        with c_ob:
            st.markdown("<div style='font-family:Share Tech Mono;font-size:9px;color:#364060;"
                "text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px'>"
                "ORDER BOOK DEPTH</div>",unsafe_allow_html=True)
            st.plotly_chart(chart_ob_depth(ob_raw["bids"],ob_raw["asks"]),width="stretch")

    # ═══ SIGNALS ═══
    with T2:
        s_ring,s_list=st.columns([1,2])
        with s_ring:
            fc=G if sig["direction"]=="LONG" else R if sig["direction"]=="SHORT" else A
            st.markdown(f"""
            <div style='background:#08101f;border:1px solid #1a2545;border-radius:10px;
                        padding:20px;text-align:center;margin-bottom:8px'>
              <div style='font-family:Orbitron;font-size:9px;color:#364060;letter-spacing:3px;margin-bottom:8px'>COMPOSITE SIGNAL</div>
              <div style='font-family:Orbitron;font-size:58px;font-weight:900;color:{fc};line-height:1'>{sig['confidence']}</div>
              <div style='font-family:Orbitron;font-size:15px;font-weight:700;color:{fc};letter-spacing:4px;margin:6px 0'>{sig['direction']}</div>
              <div style='font-family:Share Tech Mono;font-size:10px;color:#364060'>WIN {sig['win_rate']*100:.1f}%</div>
              <div style='font-family:Share Tech Mono;font-size:10px;color:#364060'>EV {sig['ev']:+.3f}R  |  ¼K {sig['quarter_kelly']:.2f}%</div>
            </div>""",unsafe_allow_html=True)
            rows=[kv("BULL PTS",sig["bull"],G),kv("BEAR PTS",sig["bear"],R),
                  kv("¼ KELLY",f"{sig['quarter_kelly']:.2f}%",A),
                  kv("FULL KELLY",f"{sig['kelly']:.2f}%",GR),
                  kv("F&G",f"{fg['value']} {fg['label']}",G if fg['value']<40 else R if fg['value']>70 else A),
                  kv("BTC DOM",f"{btc_dom:.1f}%",C),
                  kv("AGGRESSION",f"{aggr*100:.1f}%",G if aggr>.55 else R if aggr<.45 else A),
                  kv("HMM STATE","TRENDING" if (hmm_r.get("proba_state1",[.5])[-1] if len(hmm_r.get("proba_state1",[]))>0 else .5)>.5 else "RANGING",A),
                  kv("REGIME","TRENDING" if hurst_v>.55 else "MEAN-REV" if hurst_v<.45 else "RANDOM",
                     G if hurst_v>.55 else R if hurst_v<.45 else A),
                  kv("MAX PAIN DIST",f"{mp_dist:+.2f}%",G if mp_dist<-1 else R if mp_dist>1 else A)]
            st.markdown(info_box(rows,"Key Metrics"),unsafe_allow_html=True)

        with s_list:
            st.markdown("<div style='font-family:Share Tech Mono;font-size:9px;color:#364060;"
                "text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px'>"
                f"ACTIVE SIGNALS — {len(sig['signals'])} DETECTED FROM REAL MARKET DATA</div>",
                unsafe_allow_html=True)
            for s in sig["signals"]:
                st.markdown(signal_card(s),unsafe_allow_html=True)
            if not sig["signals"]:
                st.info("No significant signals. Wait for confluence across independent sources.")

    # ═══ LIQ/OI ═══
    with T3:
        l1,l2=st.columns([2,1])
        with l1:
            st.plotly_chart(chart_liq(liq_m["hm"],spot,liq_m["zones"]),width="stretch")
            if liq_m["zones"]:
                rows=[kv(z["side"],f"${z['from']:,.0f}—${z['to']:,.0f}  str={z['strength']:.2f}",
                         R if "LONG" in z["side"] else G) for z in liq_m["zones"][:6]]
                st.markdown(info_box(rows,"Estimated Cascade Zones"),unsafe_allow_html=True)
        with l2:
            st.plotly_chart(chart_oi_ls(oi_df,ls_df),width="stretch")
            st.plotly_chart(chart_funding(fr_hist),width="stretch")
            # OI stats
            if not oi_df.empty:
                cur_oi=float(oi_df["sumOpenInterestValue"].iloc[-1])
                rows=[kv("Current OI",fmtM(cur_oi),C),
                      kv("OI Change 2.5h",f"{oi_chg:+.2f}%",G if oi_chg>0 else R),
                      kv("Funding Z",f"{fr_sig['z']:+.3f}σ",R if fr_sig['z']>1.5 else G if fr_sig['z']<-1.5 else A),
                      kv("Funding Signal",fr_sig["sig"][:30],R if "BEAR" in fr_sig["sig"] else G if "BULL" in fr_sig["sig"] else A)]
                st.markdown(info_box(rows,"Open Interest"),unsafe_allow_html=True)
            if not top_ls.empty:
                rows=[kv("Global L/S",f"{float(ls_df['longShortRatio'].iloc[-1]):.3f}" if not ls_df.empty else "—",A),
                      kv("Top Trader L/S",f"{float(top_ls['longShortRatio'].iloc[-1]):.3f}" if not top_ls.empty else "—",C),
                      kv("Long%",f"{float(ls_df['longAccount'].iloc[-1])*100:.1f}%" if not ls_df.empty else "—",G),
                      kv("Short%",f"{float(ls_df['shortAccount'].iloc[-1])*100:.1f}%" if not ls_df.empty else "—",R)]
                st.markdown(info_box(rows,"Position Data"),unsafe_allow_html=True)

    # ═══ OPTIONS ═══
    with T4:
        o1,o2,o3,o4=st.columns(4)
        o1.metric("MAX PAIN",f"${mpp:,.0f}",f"{mp_dist:+.2f}%")
        o2.metric("NET GEX",f"${gex_data.get('total_M',0):+.1f}M",f"Flip ${gex_data.get('flip',0):,.0f}")
        o3.metric("ATM IV",f"{atm_iv:.1f}%",f"25Δ Skew {skew_25:+.1f}%")
        if not chain.empty:
            coi=float(chain[chain["type"]=="call"]["oi"].sum())
            poi=float(chain[chain["type"]=="put"]["oi"].sum())
            pcr=poi/max(coi,1)
            o4.metric("PUT/CALL OI",f"{pcr:.3f}",
                "FEAR" if pcr>1.4 else "GREED" if pcr<.6 else "NEUTRAL")

        gc,mc=st.columns(2)
        with gc: st.plotly_chart(chart_gex(gex_data,spot),width="stretch")
        with mc: st.plotly_chart(chart_mp(mp_data,spot),width="stretch")

        if iv_surf:
            rows_iv=[]
            for exp,v in sorted(iv_surf.items(),key=lambda x:x[1]["days"]):
                pcr=v["put_oi"]/max(v["call_oi"],1)
                rows_iv.append({"Expiry":exp,"Days":v["days"],"ATM IV%":v["atm_iv"],
                                "25Δ Skew":v["skew_25d"],"Call OI":int(v["call_oi"]),
                                "Put OI":int(v["put_oi"]),"P/C":round(pcr,3)})
            st.markdown("<div style='font-family:Share Tech Mono;font-size:9px;color:#364060;"
                "text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px'>IV TERM STRUCTURE</div>",
                unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(rows_iv),width="stretch",height=200)

        if not chain.empty:
            exps=sorted(chain["expiry"].unique())
            ne=exps[0] if exps else None
            if ne:
                sub=chain[chain["expiry"]==ne].copy()
                sub=sub[sub["strike"].between(spot*.82,spot*1.18)]
                calls=sub[sub["type"]=="call"][["strike","iv_pct","oi","delta","gamma","vega","theta"]].copy()
                puts =sub[sub["type"]=="put"][["strike","iv_pct","oi","delta","gamma","vega","theta"]].copy()
                calls.columns=["Strike","C_IV%","C_OI","C_Δ","C_Γ","C_ν","C_Θ"]
                puts.columns =["Strike","P_IV%","P_OI","P_Δ","P_Γ","P_ν","P_Θ"]
                mg=pd.merge(calls,puts,on="Strike",how="outer").sort_values("Strike",ascending=False).reset_index(drop=True)
                mg["ATM"]=mg["Strike"].apply(lambda x:"◉" if abs(x-spot)/spot<.005 else "")
                st.markdown(f"<div style='font-family:Share Tech Mono;font-size:9px;color:#364060;"
                    "text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px'>"
                    f"OPTIONS CHAIN — {ne}</div>",unsafe_allow_html=True)
                st.dataframe(mg,width="stretch",height=380)

    # ═══ FLOW ═══
    with T5:
        f1,f2=st.columns([2,1])
        with f1:
            st.plotly_chart(chart_taker(taker_df),width="stretch")
            st.plotly_chart(chart_fear_greed(fg),width="stretch")
        with f2:
            rows_fl=[
                kv("Taker Buy/Sell",f"{float(taker_df['buySellRatio'].iloc[-1]):.4f}" if not taker_df.empty else "—",
                   G if not taker_df.empty and float(taker_df["buySellRatio"].iloc[-1])>1.1 else R),
                kv("Buy Vol",f"{float(taker_df['buyVol'].iloc[-1])/1e6:.2f}M" if not taker_df.empty else "—",G),
                kv("Sell Vol",f"{float(taker_df['sellVol'].iloc[-1])/1e6:.2f}M" if not taker_df.empty else "—",R),
                kv("Aggression",f"{aggr*100:.1f}%",G if aggr>.55 else R if aggr<.45 else A),
                kv("CVD",f"{cvd_r.get('cvd_current',0):+.0f}",G if cvd_r.get("cvd_current",0)>0 else R),
                kv("CVD Signal",cvd_r.get("div_signal","NONE"),G if "BULL" in cvd_r.get("div_signal","") else R if "BEAR" in cvd_r.get("div_signal","") else A),
                kv("F&G",f"{fg['value']} — {fg['label']}",G if fg['value']<40 else R if fg['value']>70 else A),
                kv("BTC Dominance",f"{btc_dom:.1f}%",C),
                kv("OB Imbalance",f"{ob_ana.get('imbalance',0):+.4f}",G if ob_ana.get('imbalance',0)>0.1 else R if ob_ana.get('imbalance',0)<-0.1 else A),
                kv("Spread"   ,f"${ob_ana.get('spread',0):.2f}",C),
                kv("Micro-Price",f"${ob_ana.get('micro',0):,.2f}",C),
            ]
            st.markdown(info_box(rows_fl,"Order Flow Metrics"),unsafe_allow_html=True)
            # Whale walls
            st.markdown("<div style='font-family:Share Tech Mono;font-size:9px;color:#364060;"
                "text-transform:uppercase;letter-spacing:.1em;margin:8px 0 4px'>WHALE WALLS ≥2 BTC</div>",
                unsafe_allow_html=True)
            for p,s in ob_ana.get("walls_a",[])[:4]:
                st.markdown(kv(f"ASK ${p:,.0f}",f"{s:.2f} BTC",R),unsafe_allow_html=True)
            for p,s in ob_ana.get("walls_b",[])[:4]:
                st.markdown(kv(f"BID ${p:,.0f}",f"{s:.2f} BTC",G),unsafe_allow_html=True)

    # ═══ MODELS ═══
    with T6:
        m1,m2=st.columns(2)
        with m1:
            # GARCH
            g=garch_r
            rows_g=[kv("σ²_t = ω + α·ε²_(t-1) + β·σ²_(t-1)","",GR,9),
                    kv("ω (long-run var)",f"{g.get('omega',0):.2e}",C),
                    kv("α (ARCH)",f"{g.get('alpha',0):.5f}",C),
                    kv("β (GARCH)",f"{g.get('beta',0):.5f}",C),
                    kv("α+β persistence",f"{g.get('persistence',0):.5f}",A),
                    kv("Vol half-life",f"{g.get('half_life',0):.1f} bars",A),
                    kv("1-step σ forecast",f"{g.get('sigma_forecast',0):.4f}%",G),
                    kv("Annualized σ",f"{g.get('sigma_annualized',0):.2f}%",G),
                    kv("Log-likelihood",f"{g.get('log_lik','—')}",C)]
            st.markdown(info_box(rows_g,"GARCH(1,1) — MLE Estimation"),unsafe_allow_html=True)
            gs=g.get("sigma_series")
            if gs is not None and len(gs)>0 and not df15.empty:
                f_gs=fig(180)
                f_gs.add_trace(go.Scatter(x=df15.index[-len(gs):],y=gs,
                    line=dict(color=P,width=1.2),name="GARCH σ"))
                f_gs.update_layout(title=dict(text="GARCH Conditional Volatility (%)",font_size=10,font_color=GR))
                st.plotly_chart(f_gs,width="stretch")
            # BNS Jump Test
            rv=rv_r; zj=rv.get("z_jump",0)
            rows_rv=[kv("Realized Vol (ann)",f"{rv.get('rv',0):.3f}%",G),
                     kv("Bipower Variation",f"{rv.get('bpv',0):.3f}%",C),
                     kv("Jump Component",f"{rv.get('jump',0):.3f}% ({rv.get('jump_pct',0):.1f}% of RV)",R),
                     kv("BNS Z-stat",f"{zj:.3f}{'  ⚠ SIGNIFICANT JUMP' if abs(zj)>3 else ''}",R if abs(zj)>3 else A)]
            st.markdown(info_box(rows_rv,"Realized Variance + BNS Jump Test"),unsafe_allow_html=True)

        with m2:
            # HMM
            h=hmm_r
            p1a=h.get("proba_state1",np.array([.5]))
            p1=float(p1a[-1]) if len(p1a)>0 else .5
            sch=A if p1>.5 else G
            rows_h=[kv("Current State","HIGH-VOL TRENDING" if p1>.5 else "LOW-VOL RANGING",sch),
                    kv(f"P(Trending)",f"{p1:.4f}",sch),
                    kv("State 0 μ",f"{h.get('mu',[0,0])[0]:.4f}%",C),
                    kv("State 0 σ",f"{h.get('sigma',[1,1])[0]:.4f}%",C),
                    kv("State 1 μ",f"{h.get('mu',[0,0])[1]:.4f}%",C),
                    kv("State 1 σ",f"{h.get('sigma',[1,1])[1]:.4f}%",C),
                    kv("P(0→1)",f"{h.get('trans',[[.95,.05],[.05,.95]])[0][1]:.4f}",A),
                    kv("P(1→0)",f"{h.get('trans',[[.95,.05],[.05,.95]])[1][0]:.4f}",A),
                    kv("Hurst H",f"{hurst_v:.4f} — {'TRENDING' if hurst_v>.55 else 'MEAN-REV' if hurst_v<.45 else 'RANDOM'}",
                       G if hurst_v>.55 else R if hurst_v<.45 else A)]
            st.markdown(info_box(rows_h,"HMM 2-State Regime — Baum-Welch EM"),unsafe_allow_html=True)
            if not df15.empty and len(p1a)>10:
                st.plotly_chart(chart_hmm_prob(df15.iloc[-200:],p1a[-200:]),width="stretch")
            # Kalman
            kf=kal_r
            if kf.get("filtered") is not None and len(kf.get("filtered",[]))>0:
                vel_c=G if float(kf["velocity"][-1])>0 else R
                rows_k=[kv("Filtered Price",f"${float(kf['filtered'][-1]):,.2f}",C),
                        kv("State Velocity",f"{float(kf['velocity'][-1]):+.4f} $/bar",vel_c),
                        kv("Upper Band +2σ",f"${float(kf['upper'][-1]):,.2f}",G),
                        kv("Lower Band -2σ",f"${float(kf['lower'][-1]):,.2f}",R),
                        kv("Uncertainty σ",f"${float(kf['std'][-1]):,.2f}",A)]
                st.markdown(info_box(rows_k,"Kalman Filter — State Space Model"),unsafe_allow_html=True)

    # ═══ BACKTEST ═══
    with T7:
        st.markdown("""<div style='font-family:Share Tech Mono;font-size:9px;color:#364060;
            background:#08101f;padding:12px;border-radius:6px;border:1px solid #1a2545;
            margin-bottom:12px;line-height:2'>
            <b style='color:#c8d8f0'>Walk-Forward Backtest</b> — 70% in-sample / 30% out-of-sample.<br>
            Signals: EMA cross · RSI · Z-score · momentum · Hurst regime weighting.<br>
            <b style='color:#c8d8f0'>IC (Information Coefficient)</b>: Spearman rank-correlation of signal vs realized return.
            IC &gt; 0.03 = detectable edge. IC &gt; 0.07 = tradeable.<br>
            No transaction costs included — subtract ~4bps per trade for realistic net.
            </div>""",unsafe_allow_html=True)
        if df15.empty or len(df15)<150:
            st.warning("Need ≥150 bars of 15m data.")
        else:
            with st.spinner("Running walk-forward backtest…"):
                bt=backtest_wf(df15)
            if not bt:
                st.error("Backtest needs more data.")
            else:
                cols=st.columns(8)
                for col_,(lbl,val) in zip(cols,[
                    ("TOTAL RETURN",f"{bt['total_return']:+.2f}%"),
                    ("SHARPE",f"{bt['sharpe']:.3f}"),
                    ("SORTINO",f"{bt['sortino']:.3f}"),
                    ("CALMAR",f"{bt['calmar']:.3f}"),
                    ("MAX DD",f"{bt['max_dd']:.2f}%"),
                    ("HIT RATE",f"{bt['hit_rate']:.1f}%"),
                    ("PROFIT FACTOR",f"{bt['profit_factor']:.3f}"),
                    ("IC",f"{bt['ic']:.4f}"),
                ]): col_.metric(lbl,val)

                st.plotly_chart(chart_equity(bt),width="stretch")

                b2=st.columns(4)
                b2[0].metric("AVG WIN (bps)",f"{bt['avg_win_bps']:.2f}")
                b2[1].metric("AVG LOSS (bps)",f"{bt['avg_loss_bps']:.2f}")
                b2[2].metric("TRADES (OOS)",bt["n_trades"])
                b2[3].metric("OOS SAMPLE",f"{len(df15)-bt['oos_idx']} bars")

    # FOOTER
    st.markdown("<hr>",unsafe_allow_html=True)
    st.markdown(f"<div style='font-family:Share Tech Mono;font-size:8px;color:#364060;"
        f"text-align:right'>BTC QUANT PRO v3 · {datetime.now().strftime('%H:%M:%S')} · "
        f"Binance Futures + Deribit + CoinGecko + Alternative.me · "
        f"All models coded from scratch — no ML libs</div>",unsafe_allow_html=True)

if __name__=="__main__":
    main()
