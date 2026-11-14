import numpy as np, warnings, csv, json, os
def d341(nu50,nu100):
    T1,T2=323.15,373.15
    y1=np.log10(np.log10(nu50+0.7)); y2=np.log10(np.log10(nu100+0.7))
    B=(y1-y2)/(np.log10(T2)-np.log10(T1)); A=y1+B*np.log10(T1)
    return A,B
def nu_of(T,A,B):  # T in C, returns m2/s
    return (10**(10**(A-B*np.log10(T+273.15)))-0.7)*1e-6
NZ=120
np.seterr(all='ignore')
def pipe(m,Tin,Ta,Uo,D,L,rho,cp,k,A,B,nz=NZ):
    """vectorized: arrays. returns Tout, dp(Pa)"""
    m,Tin,Ta,Uo,D,L,rho,cp,k,A,B=np.broadcast_arrays(*[np.asarray(v,float) for v in (m,Tin,Ta,Uo,D,L,rho,cp,k,A,B)])
    u=4*m/(np.pi*D**2*rho)
    def rhs(z,y):
        x=L*z**3; dxdz=3*L*z**2
        dT0=np.exp(y); Tb=Ta+dT0
        nub=nu_of(Tb,A,B); Re=u*D/nub; Pr=nub*rho*cp/k
        Gz=Re*Pr*D/np.maximum(x,1e-300)
        g=(1.077*np.cbrt(Gz)-0.7)
        N0=np.cbrt(3.66**3+0.7**3+g**3)
        r=0.5
        for _ in range(6):
            nuw=nu_of(Ta+r*dT0,A,B)
            h=N0*(nub/nuw)**0.14*k/D
            r=h/(h+Uo)          # (Tw-Ta)/(Tb-Ta)
        nuw=nu_of(Ta+r*dT0,A,B)
        dy=-np.pi*D*Uo*r/(m*cp)*dxdz
        f=64/Re*(nuw/nub)**0.5
        dp=f*rho*u**2/(2*D)*dxdz
        return dy,dp
    h=1.0/nz; Y=np.log(Tin-Ta); P=np.zeros_like(Y); z=0.0
    for i in range(nz):
        z0=max(z,1e-9)
        a1,b1=rhs(z0,Y); a2,b2=rhs(z+h/2,Y+h/2*a1); a3,b3=rhs(z+h/2,Y+h/2*a2); a4,b4=rhs(z+h,Y+h*a3)
        Y=Y+h/6*(a1+2*a2+2*a3+a4); P=P+h/6*(b1+2*b2+2*b3+b4); z+=h
    T=Ta+np.exp(Y)
    return T,P
import sys, re, subprocess
def fitU(m,Tin,Tout,Ta,pr):
    lo=np.full(len(m),0.01);hi=np.full(len(m),1000.)
    for _ in range(45):
        mid=np.sqrt(lo*hi); T,_=pipe(m,Tin,Ta,mid,*pr,nz=24)
        hot=T>Tout; lo=np.where(hot,mid,lo); hi=np.where(hot,hi,mid)
    return np.sqrt(lo*hi)
COVER=re.compile(r'cover|lag|insulat|clad|jacket',re.I)
NOTWORK=re.compile(r'inspect|check|survey|paint|clean|photograph|measured',re.I)
def main(P,out):
    oils={r['oil']:r for r in csv.DictReader(open(os.path.join(P,'oils.csv')))}
    lines={r['line']:r for r in csv.DictReader(open(os.path.join(P,'lines.csv')))}
    site=json.load(open(os.path.join(P,'site.json')))
    allow=int(site.get('survey_allowance',0))
    S=list(csv.DictReader(open(os.path.join(P,'surveys.csv'))))
    W=list(csv.DictReader(open(os.path.join(P,'work_log.csv'))))
    R=list(csv.DictReader(open(os.path.join(P,'records.csv'))))
    def props(line):
        ln=lines[line]; o=oils[ln['oil']]; A,B=d341(float(o['nu50_cSt']),float(o['nu100_cSt']))
        return (float(ln['bore_mm'])/1000,float(ln['length_m']),float(o['density_kg_m3']),
                float(o['cp_J_kgK']),float(o['k_W_mK']),A,B)
    pipes=[l+'-'+s for l in lines for s in ('AB'[:int(lines[l]['pipes'])])]
    lastwork={}
    for w in W:
        if COVER.search(w['job']) and not NOTWORK.search(w['job']):
            p=w['pipe'].strip(); lastwork[p]=max(lastwork.get(p,''),w['date'])
    # fit all surveys
    def fit_rows(rows):
        if not rows: return np.array([])
        pr=[np.array(v) for v in zip(*[props(r['pipe'].strip()[:-2]) for r in rows])]
        g=lambda c:np.array([float(r[c]) for r in rows])
        return fitU(g('flow_t_h')/3.6,g('t_in_C'),g('t_out_C'),g('t_amb_C'),pr)
    U=fit_rows(S); vals={}
    for r,u in zip(S,U):
        p=r['pipe'].strip()
        if r['date']>lastwork.get(p,''): vals.setdefault(p,[]).append(u)
    oldv={}
    for r,u in zip(S,U): oldv.setdefault(r['pipe'].strip(),[]).append((r['date'],u))
    need=[p for p in pipes if p not in vals]
    # prioritise by number of records on the line
    cnt={}
    for r in R: cnt[r['line']]=cnt.get(r['line'],0)+1
    need.sort(key=lambda p:-cnt.get(p[:-2],0))
    order=need[:allow]
    if order:
        try:
            o=subprocess.run(['heatsurvey',P]+order,capture_output=True,text=True,timeout=40)
            rows=[x for x in csv.DictReader(o.stdout.splitlines()) if x.get('pipe')]
            for r,u in zip(rows,fit_rows(rows)): vals[r['pipe'].strip()]=[u]
            if o.returncode or not rows: sys.stderr.write(o.stdout+o.stderr)
        except Exception as e: sys.stderr.write('heatsurvey failed: %s\n'%e)
    Uo={}
    for p in pipes:
        if p in vals: Uo[p]=float(np.mean(vals[p]))
        else:
            sys.stderr.write('no current survey for %s, using latest on file\n'%p)
            Uo[p]=sorted(oldv[p])[-1][1]
    n=len(R)
    pr=[np.array(v) for v in zip(*[props(r['line']) for r in R])]
    M=np.array([float(r['flow_t_h']) for r in R])/3.6
    Tin=np.array([float(r['t_in_C']) for r in R]); Ta=np.array([float(r['t_amb_C']) for r in R])
    pair=np.array([lines[r['line']]['pipes'].strip()=='2' for r in R])
    UA=np.array([Uo[r['line']+'-A'] for r in R])
    UB=np.array([Uo.get(r['line']+'-B',1.0) for r in R])
    TA,PA=pipe(M,Tin,Ta,UA,*pr,nz=40)
    dp=PA.copy(); Tout=TA.copy()
    idx=np.where(pair)[0]
    if len(idx):
        sub=[a[idx] for a in pr]; m=M[idx]; ti=Tin[idx]; ta=Ta[idx]; ua=UA[idx]; ub=UB[idx]
        def G(a,ii,nz=32):
            s=[q[ii] for q in sub]
            T1,P1=pipe(a*m[ii],ti[ii],ta[ii],ua[ii],*s,nz=nz); T2,P2=pipe((1-a)*m[ii],ti[ii],ta[ii],ub[ii],*s,nz=nz)
            return np.log(P1/P2),T1,T2,P1
        e_=np.geomspace(1e-4,0.04,24); grid=np.unique(np.concatenate([e_,np.linspace(0.04,0.96,70),1-e_])); NG=len(grid); nP=len(idx)
        ii=np.repeat(np.arange(nP),NG); gg=np.tile(grid,nP)
        Gv=G(gg,ii,nz=24)[0].reshape(nP,NG)
        # sequential relaxation along each line's run
        order_=sorted(range(nP),key=lambda j:(R[idx[j]]['line'],float(R[idx[j]]['hour'])))
        lo=np.zeros(nP); hi=np.zeros(nP); prev={}
        for j in order_:
            ln=R[idx[j]]['line']; a0=prev.get(ln,0.5)
            g=Gv[j]; k=int(np.clip(np.searchsorted(grid,a0)-1,0,NG-2))
            # value at a0 by interpolation
            ga=g[k]+(g[k+1]-g[k])*(a0-grid[k])/(grid[k+1]-grid[k])
            if ga>0:   # A overloaded: a decreases until g<=0
                kk=k
                while kk>=0 and g[kk]>0: kk-=1
                if kk<0: lo[j],hi[j]=1e-6,grid[0]
                else: lo[j],hi[j]=grid[kk],min(grid[kk+1],a0) if kk==k else grid[kk+1]
            else:
                kk=k+1
                while kk<NG and g[kk]<=0: kk+=1
                if kk>=NG: lo[j],hi[j]=grid[-1],1-1e-6
                else: lo[j],hi[j]=max(grid[kk-1],a0) if kk==k+1 else grid[kk-1],grid[kk]
            kl=int(np.clip(np.searchsorted(grid,lo[j])-1,0,NG-2))
            gl=g[kl]+(g[kl+1]-g[kl])*(lo[j]-grid[kl])/(grid[kl+1]-grid[kl])
            kh=int(np.clip(np.searchsorted(grid,hi[j])-1,0,NG-2))
            gh=g[kh]+(g[kh+1]-g[kh])*(hi[j]-grid[kh])/(grid[kh+1]-grid[kh])
            prev[ln]=lo[j]+(hi[j]-lo[j])*(gl/(gl-gh) if gl!=gh and gl<=0<=gh else 0.5)
        L_=lo.copy(); H_=hi.copy()
        for _ in range(36):
            mid=0.5*(L_+H_); gm=G(mid,np.arange(nP),nz=32)[0]
            H_=np.where(gm>0,mid,H_); L_=np.where(gm>0,L_,mid)
        lo,hi=L_,H_
        x=0.5*(lo+hi); all_=np.arange(nP)
        f,T1,T2,P1=G(x,all_)
        dp[idx]=P1; Tout[idx]=x*T1+(1-x)*T2
    with open(out,'w',newline='') as fh:
        w=csv.writer(fh); w.writerow(['record','dp_kPa','t_out_C'])
        for r,d,t in zip(R,dp,Tout): w.writerow([r['record'],'%.4f'%(d/1000),'%.3f'%t])
if __name__=='__main__': main(sys.argv[1],sys.argv[2])
