"""Danica Tools single-window launcher. Copyright The Superior Mind-Zone."""
import os, sys, queue, threading, subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

TOOLS = ("DFF.exe", "TXD.exe", "IFP.exe", "Texture.exe")

def root():
    p = getattr(sys, "_MEIPASS", None)
    return Path(p) if p else Path(__file__).resolve().parent

def tool(name):
    return root() / "Convert" / name

def self_test():
    base = root()
    lines = ["Danica Tools standalone self-test", f"Resource root: {base}"]
    ok = True
    for name in TOOLS:
        p = base / "Convert" / name
        valid = p.is_file() and p.stat().st_size > 10000 and p.read_bytes()[:2] == b"MZ"
        lines.append(f"{'PASS' if valid else 'FAIL'}: {name}")
        ok &= valid
    pack = base / "Packs" / "Convert" / "GTA_PS2_TO_VC.pack"
    valid = pack.is_file() and b"[RECIPE:DFF]" in pack.read_bytes() and b"[RECIPE:TXD]" in pack.read_bytes()
    lines.append(f"{'PASS' if valid else 'FAIL'}: GTA_PS2_TO_VC.pack")
    ok &= valid
    lines.append("RESULT: " + ("PASS" if ok else "FAIL"))
    Path.cwd().joinpath("Danica-self-test.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1

class FileBatch(ttk.Frame):
    def __init__(self, app, label, ext, exe, dff=False):
        super().__init__(app.tabs, padding=12)
        self.app, self.ext, self.exe, self.dff = app, ext, exe, dff
        self.files = []
        ttk.Label(self, text=f"Select source {ext} files. Multiple files are supported.", wraplength=760).pack(anchor="w", pady=(0,8))
        row = ttk.Frame(self); row.pack(fill="both", expand=True)
        self.lst = tk.Listbox(row, height=6, selectmode="extended", exportselection=False)
        sb = ttk.Scrollbar(row, orient="vertical", command=self.lst.yview); self.lst.configure(yscrollcommand=sb.set)
        self.lst.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y", padx=(4,8))
        controls = ttk.Frame(row); controls.pack(side="left", fill="y")
        ttk.Button(controls, text="Add files…", command=self.add).pack(fill="x", pady=3)
        ttk.Button(controls, text="Remove selected", command=self.remove).pack(fill="x", pady=3)
        ttk.Button(controls, text="Clear", command=self.clear).pack(fill="x", pady=3)
        self.out = tk.StringVar()
        self._pathrow("Output folder", self.out, self.pick_out)
        opts = ttk.LabelFrame(self, text="Conversion options", padding=8); opts.pack(fill="x", pady=10)
        self.version = tk.StringVar(value="34003"); self.platform = tk.StringVar(value="d3d8")
        ttk.Label(opts, text="RW version").grid(row=0,column=0,sticky="w",padx=4,pady=4)
        ttk.Entry(opts,textvariable=self.version,width=12).grid(row=0,column=1,sticky="w",padx=4,pady=4)
        ttk.Label(opts,text="Output platform").grid(row=0,column=2,sticky="w",padx=(18,4),pady=4)
        ttk.Combobox(opts,textvariable=self.platform,values=("d3d8","d3d9","ps2","xbox","mobile"),state="readonly",width=10).grid(row=0,column=3,sticky="w",padx=4,pady=4)
        if dff:
            self.uninstance = tk.BooleanVar(value=True)
            ttk.Checkbutton(opts,text="Uninstance geometry (-u; GTA PS2 → VC preset)",variable=self.uninstance).grid(row=1,column=0,columnspan=3,sticky="w",padx=4,pady=4)
        else:
            self.action = tk.StringVar(value="Convert")
            ttk.Label(opts,text="Action").grid(row=1,column=0,sticky="w",padx=4,pady=4)
            ttk.Combobox(opts,textvariable=self.action,values=("Convert","Extract textures (-x)","List textures (-l)"),state="readonly",width=22).grid(row=1,column=1,columnspan=2,sticky="w",padx=4,pady=4)
            self.palette = tk.BooleanVar(value=False); self.gamma = tk.BooleanVar(value=False)
            ttk.Checkbutton(opts,text="Palette to 32-bit (-t)",variable=self.palette).grid(row=2,column=0,columnspan=2,sticky="w",padx=4,pady=4)
            ttk.Checkbutton(opts,text="LCS/VCS gamma (-g; D3D8 only)",variable=self.gamma).grid(row=2,column=2,columnspan=2,sticky="w",padx=4,pady=4)
        ttk.Button(self,text=f"Process {ext} files",command=self.run).pack(anchor="e",pady=(4,0))

    def _pathrow(self,label,var,cmd):
        r=ttk.Frame(self); r.pack(fill="x",pady=5)
        ttk.Label(r,text=label,width=15).pack(side="left")
        ttk.Entry(r,textvariable=var).pack(side="left",fill="x",expand=True,padx=(0,6))
        ttk.Button(r,text="Browse…",command=cmd).pack(side="left")
    def add(self):
        for s in filedialog.askopenfilenames(title=f"Choose {self.ext} files",filetypes=((f"{self.ext} files",f"*{self.ext}"),("All files","*.*"))):
            p=Path(s)
            if p not in self.files: self.files.append(p)
        self.refresh()
        if self.files and not self.out.get(): self.out.set(str(self.files[0].parent / "Danica Output"))
    def remove(self):
        inds=set(self.lst.curselection()); self.files=[p for i,p in enumerate(self.files) if i not in inds]; self.refresh()
    def clear(self): self.files=[]; self.refresh()
    def refresh(self):
        self.lst.delete(0,tk.END)
        for p in self.files: self.lst.insert(tk.END,str(p))
    def pick_out(self):
        p=filedialog.askdirectory(title="Choose output folder")
        if p: self.out.set(p)
    def run(self):
        if not self.files or not self.out.get().strip(): return self.app.warn("Choose source files and an output folder.")
        if not self.version.get().strip().isdigit(): return self.app.warn("RW version must be numeric, e.g. 34003.")
        outdir=Path(self.out.get()); outdir.mkdir(parents=True,exist_ok=True); jobs=[]
        for src in self.files:
            if src.suffix.lower()!=self.ext: continue
            args=[]
            if self.dff:
                if self.uninstance.get(): args.append("-u")
            else:
                act=self.action.get()
                if act.startswith("Extract"): args.append("-x")
                elif act.startswith("List"): args.append("-l")
                if self.palette.get(): args.append("-t")
                if self.gamma.get():
                    if self.platform.get()!="d3d8": return self.app.warn("Gamma option -g works with D3D8 only.")
                    args.append("-g")
            args += ["-v",self.version.get().strip(),"-o",self.platform.get(),str(src)]
            if not self.dff and self.action.get()!="Convert":
                wd=outdir/(src.stem+("_textures" if self.action.get().startswith("Extract") else "_texture_list"))
                wd.mkdir(parents=True,exist_ok=True)
                jobs.append((f"{self.exe}: {src.name}",self.exe,args,wd,None))
            else:
                dst=outdir/(src.stem+self.ext)
                if src.resolve()==dst.resolve(): return self.app.warn(f"Output would overwrite source: {src}")
                args.append(str(dst)); jobs.append((f"{self.exe}: {src.name}",self.exe,args,src.parent,dst))
        self.app.run_jobs(jobs)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Danica Tools — The Superior Mind-Zone"); self.geometry("900x720"); self.minsize(760,620)
        self.events=queue.Queue(); self.busy=False
        s=ttk.Style(self)
        if "vista" in s.theme_names(): s.theme_use("vista")
        ttk.Label(self,text="Danica Tools",font=("Segoe UI",18,"bold")).pack(anchor="w",padx=12,pady=(10,0))
        ttk.Label(self,text="GTA RenderWare conversion tools • original converter binaries bundled in one EXE").pack(anchor="w",padx=12,pady=(0,8))
        self.tabs=ttk.Notebook(self); self.tabs.pack(fill="both",expand=True,padx=8,pady=4)
        self.dff=FileBatch(self,"DFF Models",".dff","DFF.exe",True); self.tabs.add(self.dff,text="DFF Models")
        self.txd=FileBatch(self,"TXD Textures",".txd","TXD.exe",False); self.tabs.add(self.txd,text="TXD Textures")
        self._build_ifp(); self._build_img(); self._build_batch()
        bottom=ttk.LabelFrame(self,text="Activity log",padding=6); bottom.pack(fill="both",expand=False,padx=8,pady=6)
        self.log=tk.Text(bottom,height=6,wrap="word",state="disabled",font=("Consolas",9)); sb=ttk.Scrollbar(bottom,command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set); self.log.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
        self.status=tk.StringVar(value="Ready.")
        ttk.Label(self,textvariable=self.status).pack(anchor="w",padx=12,pady=(0,6))
        ttk.Label(self,text="PS2 → VC preset uses DFF -u -v 34003 -o d3d8 and TXD -v 34003 -o d3d8. Back up important files.",wraplength=860).pack(anchor="w",padx=12,pady=(0,8))

    def addlog(self,s):
        self.log.configure(state="normal"); self.log.insert(tk.END,s.rstrip()+"\n"); self.log.see(tk.END); self.log.configure(state="disabled")
    def warn(self,s): messagebox.showwarning("Danica Tools",s,parent=self)
    def row(self,tab,label,var,cmd):
        r=ttk.Frame(tab); r.pack(fill="x",pady=5); ttk.Label(r,text=label,width=15).pack(side="left"); ttk.Entry(r,textvariable=var).pack(side="left",fill="x",expand=True,padx=(0,6)); ttk.Button(r,text="Browse…",command=cmd).pack(side="left")
    def _build_ifp(self):
        t=ttk.Frame(self.tabs,padding=12); self.tabs.add(t,text="IFP Animations")
        self.ifp_in=tk.StringVar(); self.ifp_merge=tk.StringVar(); self.ifp_out=tk.StringVar()
        self.row(t,"Input .ifp",self.ifp_in,self.pick_ifp_in); self.row(t,"Merge .ifp",self.ifp_merge,self.pick_merge); self.row(t,"Output .ifp",self.ifp_out,self.pick_ifp_out)
        ttk.Label(t,text="Optional merge replaces matching animation entries, following the original IFP utility.",wraplength=760).pack(anchor="w",pady=10)
        ttk.Button(t,text="Convert / merge IFP",command=self.run_ifp).pack(anchor="e",pady=8)
    def pick_ifp_in(self):
        p=filedialog.askopenfilename(filetypes=(("IFP files","*.ifp"),("All files","*.*")))
        if p:
            self.ifp_in.set(p)
            if not self.ifp_out.get(): q=Path(p); self.ifp_out.set(str(q.with_name(q.stem+"_converted.ifp")))
    def pick_merge(self):
        p=filedialog.askopenfilename(filetypes=(("IFP files","*.ifp"),("All files","*.*")))
        if p: self.ifp_merge.set(p)
    def pick_ifp_out(self):
        p=filedialog.asksaveasfilename(defaultextension=".ifp",filetypes=(("IFP files","*.ifp"),("All files","*.*")))
        if p: self.ifp_out.set(p)
    def run_ifp(self):
        a=self.ifp_in.get().strip(); o=self.ifp_out.get().strip(); m=self.ifp_merge.get().strip()
        if not a or not Path(a).is_file() or not o: return self.warn("Choose valid input and output IFP paths.")
        if Path(a).resolve()==Path(o).resolve(): return self.warn("Output must not overwrite the source.")
        args=[]
        if m:
            if not Path(m).is_file(): return self.warn("The merge IFP file does not exist.")
            args += ["-m",m]
        Path(o).parent.mkdir(parents=True,exist_ok=True); args += ["-o",o,a]
        self.run_jobs([(f"IFP: {Path(a).name}","IFP.exe",args,Path(a).parent,Path(o))])
    def _build_img(self):
        t=ttk.Frame(self.tabs,padding=12); self.tabs.add(t,text="IMG Archive")
        self.img_in=tk.StringVar(); self.img_out=tk.StringVar()
        self.row(t,"Input .img",self.img_in,self.pick_img_in); self.row(t,"Output .img",self.img_out,self.pick_img_out)
        ttk.Label(t,text="The Texture utility rewrites the selected IMG archive. Keep a backup of important archives.",wraplength=760).pack(anchor="w",pady=10)
        ttk.Button(t,text="Convert IMG",command=self.run_img).pack(anchor="e",pady=8)
    def pick_img_in(self):
        p=filedialog.askopenfilename(filetypes=(("IMG archives","*.img"),("All files","*.*")))
        if p:
            self.img_in.set(p)
            if not self.img_out.get(): q=Path(p); self.img_out.set(str(q.with_name(q.stem+"_converted.img")))
    def pick_img_out(self):
        p=filedialog.asksaveasfilename(defaultextension=".img",filetypes=(("IMG archives","*.img"),("All files","*.*")))
        if p: self.img_out.set(p)
    def run_img(self):
        a=self.img_in.get().strip(); o=self.img_out.get().strip()
        if not a or not Path(a).is_file() or not o: return self.warn("Choose valid input and output IMG paths.")
        if Path(a).resolve()==Path(o).resolve(): return self.warn("Output must not overwrite the source.")
        Path(o).parent.mkdir(parents=True,exist_ok=True)
        self.run_jobs([(f"IMG: {Path(a).name}","Texture.exe",[a,o],Path(a).parent,Path(o))])
    def _build_batch(self):
        t=ttk.Frame(self.tabs,padding=12); self.tabs.add(t,text="Batch PS2 → VC")
        ttk.Label(t,text="Batch preset based on GTA_PS2_TO_VC.pack. Processes .dff and .txd files in the selected folder (top level).",wraplength=760).pack(anchor="w",pady=(0,10))
        self.bin=tk.StringVar(); self.bout=tk.StringVar(); self.bver=tk.StringVar(value="34003"); self.bplat=tk.StringVar(value="d3d8")
        self.row(t,"Input folder",self.bin,self.pick_batch_in); self.row(t,"Output folder",self.bout,self.pick_batch_out)
        r=ttk.Frame(t); r.pack(fill="x",pady=8); ttk.Label(r,text="RW version").pack(side="left"); ttk.Entry(r,textvariable=self.bver,width=12).pack(side="left",padx=6); ttk.Label(r,text="Platform").pack(side="left",padx=(18,4)); ttk.Combobox(r,textvariable=self.bplat,values=("d3d8","d3d9","ps2","xbox","mobile"),state="readonly",width=10).pack(side="left")
        ttk.Button(t,text="Run batch conversion",command=self.run_batch).pack(anchor="e",pady=12)
    def pick_batch_in(self):
        p=filedialog.askdirectory()
        if p:
            self.bin.set(p)
            if not self.bout.get(): self.bout.set(str(Path(p)/"Danica Output"))
    def pick_batch_out(self):
        p=filedialog.askdirectory()
        if p: self.bout.set(p)
    def run_batch(self):
        a=self.bin.get().strip(); o=self.bout.get().strip()
        if not a or not Path(a).is_dir() or not o: return self.warn("Choose valid input and output folders.")
        if not self.bver.get().strip().isdigit(): return self.warn("RW version must be numeric, e.g. 34003.")
        indir=Path(a); out=Path(o); jobs=[]
        for src in sorted(indir.iterdir(),key=lambda p:p.name.lower()):
            if not src.is_file(): continue
            if src.suffix.lower()==".dff":
                dst=out/"DFF"/(src.stem+".dff"); args=["-u","-v",self.bver.get().strip(),"-o",self.bplat.get(),str(src),str(dst)]; jobs.append((f"Batch DFF: {src.name}","DFF.exe",args,src.parent,dst))
            elif src.suffix.lower()==".txd":
                dst=out/"TXD"/(src.stem+".txd"); args=["-v",self.bver.get().strip(),"-o",self.bplat.get(),str(src),str(dst)]; jobs.append((f"Batch TXD: {src.name}","TXD.exe",args,src.parent,dst))
        if not jobs: return self.warn("No DFF or TXD files found in the input folder.")
        for _,_,_,_,dst in jobs:
            if dst: dst.parent.mkdir(parents=True,exist_ok=True)
        self.run_jobs(jobs)
    def run_jobs(self,jobs):
        if self.busy: return self.warn("A conversion is already running.")
        if not jobs: return self.warn("No supported files to process.")
        missing=[n for n in TOOLS if not tool(n).is_file()]
        if missing: return self.warn("Missing bundled converter(s): "+", ".join(missing))
        out=[str(j[4]) for j in jobs if j[4] and j[4].exists()]
        if out and not messagebox.askyesno("Danica Tools",f"{len(out)} output file(s) exist. Overwrite?",parent=self): return
        self.busy=True; self.status.set(f"Processing {len(jobs)} job(s)…"); self.addlog(f"--- Starting {len(jobs)} job(s) ---")
        threading.Thread(target=self.worker,args=(jobs,),daemon=True).start(); self.after(100,self.poll)
    def worker(self,jobs):
        ok=bad=0
        for i,(label,name,args,cwd,expected) in enumerate(jobs,1):
            self.events.put(("log",f"[{i}/{len(jobs)}] {label}"))
            try:
                cwd.mkdir(parents=True,exist_ok=True)
                p=subprocess.run([str(tool(name)),*args],cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                if p.stdout.strip(): self.events.put(("log",p.stdout.rstrip()))
                valid=p.returncode==0 and (expected is None or (expected.is_file() and expected.stat().st_size>0))
                if valid: ok+=1; self.events.put(("log","SUCCESS: "+label))
                else: bad+=1; self.events.put(("log",f"FAILED: {label} (exit={p.returncode}; output={expected})"))
            except Exception as e:
                bad+=1; self.events.put(("log",f"FAILED: {label} ({type(e).__name__}: {e})"))
        self.events.put(("done",(ok,bad,len(jobs))))
    def poll(self):
        try:
            while True:
                event,payload=self.events.get_nowait()
                if event=="log": self.addlog(payload)
                else:
                    ok,bad,total=payload; self.busy=False; self.status.set(f"Finished: {ok} succeeded, {bad} failed (total {total})."); self.addlog(f"--- Finished: {ok} succeeded, {bad} failed ---")
                    (messagebox.showinfo if not bad else messagebox.showwarning)("Danica Tools",f"Completed. Success: {ok}; failed: {bad}. Check Activity log for details.",parent=self)
        except queue.Empty: pass
        if self.busy: self.after(100,self.poll)

if __name__=="__main__":
    if "--self-test" in sys.argv: raise SystemExit(self_test())
    App().mainloop()
