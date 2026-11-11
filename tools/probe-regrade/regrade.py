import sys, os, csv, importlib.util, json
root="/home/claude/bpprobe"
def load(path, name):
    spec=importlib.util.spec_from_file_location(name, path); m=importlib.util.module_from_spec(spec); sys.modules[name]=m; spec.loader.exec_module(m); return m
rows=[]
for d in sorted(os.listdir(root)):
    sealed=os.path.join(root,d,"rig","sealed"); sheet=os.path.join(root,d,"app","output","diagnosis.csv")
    if not os.path.exists(sheet) or not os.path.exists(sealed+"/fleet.py"): continue
    for k in ["bpphys","fleet"]: sys.modules.pop(k,None)
    sys.path.insert(0,sealed)
    P=load(sealed+"/bpphys.py","bpphys"); F=load(sealed+"/fleet.py","fleet")
    sys.path.pop(0)
    st=json.load(open(os.path.join(root,d,"rig","state","state.json"))) if os.path.exists(os.path.join(root,d,"rig","state","state.json")) else {}
    order=" ".join("%s/%s/%s"%(t["chamber"],t["test"],t.get("pumping_time_h","")) for t in st.get("tests",[]))
    ans={r["chamber"].strip():r for r in csv.DictReader(open(sheet))}
    res={}
    for cid in F.CHAMBER_IDS:
        t=F.truth(F.BY[cid]); a=ans.get(cid)
        if not a: res[cid]="-"; continue
        q=float(a["q_total_mbarl_s"])/t["q_total"]-1; s=float(a["s_eff_l_s"])/t["s_eff"]-1
        ok=a["cause"].strip()==t["cause"] and abs(q)<=0.04 and abs(s)<=0.035
        res[cid]="ok" if ok else "X"
    n=sum(v=="ok" for v in res.values())
    rows.append((d,order,n,res))
for d,o,n,res in rows:
    print("%-3s %-22s %2d  %s"%(d,o,n," ".join("%s:%s"%(c[2:],res[c]) for c in sorted(res))))
