import os, sqlite3, tempfile, pathlib, shutil, datetime, tkinter as tk
from tkinter import ttk, messagebox, filedialog

LOCAL = pathlib.Path(os.environ.get('LOCALAPPDATA', ''))
ROAM = pathlib.Path(os.environ.get('APPDATA', ''))
ROOTS = {'Chrome': LOCAL/'Google/Chrome/User Data', 'Edge': LOCAL/'Microsoft/Edge/User Data', 'Brave': LOCAL/'BraveSoftware/Brave-Browser/User Data', 'Firefox': ROAM/'Mozilla/Firefox/Profiles'}

def connect(path):
    return sqlite3.connect(pathlib.Path(path).resolve().as_uri()+'?mode=rw', uri=True, timeout=1)

def kind(db):
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if {'urls','visits'} <= tables: return 'chromium'
    if {'moz_places','moz_historyvisits'} <= tables: return 'firefox'
    raise ValueError('这不是支持的浏览器历史数据库。')

def matches(db, keyword, sensitive):
    table = 'urls' if kind(db)=='chromium' else 'moz_places'
    check = (lambda s: keyword in s) if sensitive else (lambda s: keyword.casefold() in s.casefold())
    clause = '' if table=='urls' else ' WHERE EXISTS (SELECT 1 FROM moz_historyvisits WHERE place_id=moz_places.id)'
    return [(i,u,t or '') for i,u,t in db.execute('SELECT id,url,title FROM '+table+clause) if u and check(u)]

def delete_records(path, rows):
    db = connect(path)
    backup = None
    try:
        db.execute('BEGIN EXCLUSIVE')
        k = kind(db)
        table = 'urls' if k=='chromium' else 'moz_places'
        for ident,url,title in rows:
            if db.execute('SELECT url FROM '+table+' WHERE id=?',(ident,)).fetchone() != (url,):
                raise ValueError('记录已经变化，请重新预览。')
        folder = LOCAL/'HistoryKeywordCleaner/backups'
        folder.mkdir(parents=True,exist_ok=True)
        backup = folder/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'-'+path.name)
        # Exclusive lock excludes writers; copy the full SQLite file and journal state.
        shutil.copy2(path, backup)
        for suffix in ('-wal','-shm'):
            src = pathlib.Path(str(path)+suffix)
            if src.exists(): shutil.copy2(src,str(backup)+suffix)
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for ident,url,title in rows:
            if k=='chromium':
                visitids = [v[0] for v in db.execute('SELECT id FROM visits WHERE url=?',(ident,))]
                for vid in visitids:
                    for extra in ('visit_source','content_annotations','context_annotations'):
                        if extra in tables:
                            cols = {r[1] for r in db.execute('PRAGMA table_info('+extra+')')}
                            col = 'id' if extra=='visit_source' else 'visit_id'
                            if col in cols: db.execute('DELETE FROM '+extra+' WHERE '+col+'=?',(vid,))
                    db.execute('UPDATE visits SET from_visit=0 WHERE from_visit=?',(vid,))
                db.execute('DELETE FROM visits WHERE url=?',(ident,))
                if 'keyword_search_terms' in tables: db.execute('DELETE FROM keyword_search_terms WHERE url_id=?',(ident,))
                db.execute('DELETE FROM urls WHERE id=?',(ident,))
            else:
                db.execute('UPDATE moz_historyvisits SET from_visit=0 WHERE from_visit IN (SELECT id FROM moz_historyvisits WHERE place_id=?)',(ident,))
                db.execute('DELETE FROM moz_historyvisits WHERE place_id=?',(ident,))
                # Keep places and bookmarks: places is also Firefox's bookmark URL store.
                db.execute('UPDATE moz_places SET visit_count=0,last_visit_date=NULL,frecency=-1 WHERE id=?',(ident,))
        db.commit()
        return backup
    except:
        db.rollback()
        raise
    finally: db.close()

class App:
    def __init__(self):
        self.root=tk.Tk(); self.root.title('网址历史清理工具'); self.root.geometry('1000x660')
        self.rows=[]; self.snapshot=None; self.paths={}
        box=ttk.Frame(self.root,padding=18); box.pack(fill='both',expand=True)
        ttk.Label(box,text='按网址关键词清理浏览器历史',font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w')
        ttk.Label(box,text='请先完全退出目标浏览器（包括后台进程）。删除前自动备份；仅处理本机所选配置。').pack(anchor='w',pady=10)
        row=ttk.Frame(box); row.pack(fill='x')
        self.browser=tk.StringVar(value='Edge'); menu=ttk.Combobox(row,textvariable=self.browser,values=list(ROOTS),state='readonly',width=12); menu.pack(side='left'); menu.bind('<<ComboboxSelected>>',lambda e:self.scan())
        self.profile=tk.StringVar(); self.profiles=ttk.Combobox(row,textvariable=self.profile,state='readonly',width=40); self.profiles.pack(side='left',padx=8)
        ttk.Button(row,text='刷新',command=self.scan).pack(side='left'); ttk.Button(row,text='手动选择数据库',command=self.choose).pack(side='left',padx=8)
        row=ttk.Frame(box); row.pack(fill='x',pady=14)
        ttk.Label(row,text='网址包含：').pack(side='left'); self.keyword=tk.StringVar(); ttk.Entry(row,textvariable=self.keyword,width=45).pack(side='left')
        self.sensitive=tk.BooleanVar(); ttk.Checkbutton(row,text='区分大小写',variable=self.sensitive).pack(side='left',padx=8)
        ttk.Button(row,text='预览匹配',command=self.preview).pack(side='left')
        self.tree=ttk.Treeview(box,columns=('url','title'),show='headings',selectmode='extended'); self.tree.heading('url',text='网址'); self.tree.heading('title',text='标题'); self.tree.column('url',width=610); self.tree.column('title',width=280)
        scroll=ttk.Scrollbar(box,orient='vertical',command=self.tree.yview); self.tree.configure(yscrollcommand=scroll.set); scroll.pack(side='right',fill='y'); self.tree.pack(fill='both',expand=True)
        self.status=tk.StringVar(value='请输入关键词，然后预览。'); ttk.Label(box,textvariable=self.status).pack(anchor='w',pady=8)
        row=ttk.Frame(box); row.pack(fill='x'); ttk.Button(row,text='删除选中记录',command=lambda:self.remove(False)).pack(side='left'); ttk.Button(row,text='删除全部匹配记录',command=lambda:self.remove(True)).pack(side='left',padx=10)
        ttk.Button(row,text='打开备份文件夹',command=self.open_backups).pack(side='right'); self.scan()
    def open_backups(self):
        p=LOCAL/'HistoryKeywordCleaner/backups'; p.mkdir(parents=True,exist_ok=True); os.startfile(p)
    def scan(self):
        base=ROOTS[self.browser.get()]; name='places.sqlite' if self.browser.get()=='Firefox' else 'History'
        self.paths={p.parent.name:p for p in base.glob('*/'+name)} if base.exists() else {}
        self.profiles['values']=list(self.paths); self.profile.set(next(iter(self.paths),'')); self.clear()
    def clear(self):
        self.rows=[]; self.snapshot=None; self.tree.delete(*self.tree.get_children())
    def choose(self):
        p=filedialog.askopenfilename(title='选择 History 或 places.sqlite 数据库')
        if p: self.paths={'手动选择':pathlib.Path(p)}; self.profiles['values']=list(self.paths); self.profile.set('手动选择'); self.clear()
    def preview(self):
        self.clear()
        try:
            word=self.keyword.get()
            if not word.strip(): raise ValueError('关键词不能为空或全为空格。')
            p=self.paths.get(self.profile.get())
            if not p: raise ValueError('请选择浏览器配置或手动选择数据库。')
            db=connect(p)
            try: self.rows=matches(db,word,self.sensitive.get())
            finally: db.close()
            self.snapshot=(p,word,self.sensitive.get())
            for n,r in enumerate(self.rows): self.tree.insert('', 'end',iid=str(n),values=r[1:])
            self.status.set('匹配 %d 条网址；支持 Ctrl / Shift 多选。'%len(self.rows))
        except Exception as e: messagebox.showerror('无法预览',str(e))
    def remove(self,all_rows):
        if not self.snapshot or self.snapshot!=(self.paths.get(self.profile.get()),self.keyword.get(),self.sensitive.get()):
            messagebox.showinfo('请重新预览','配置或关键词变化后，请先重新预览。'); return
        rows=self.rows if all_rows else [self.rows[int(i)] for i in self.tree.selection()]
        if not rows: messagebox.showinfo('没有记录','请先选择需要删除的记录。'); return
        if not messagebox.askyesno('确认删除','将删除 %d 条网址的全部本地访问记录。\n请确认浏览器已完全退出。\n继续？'%len(rows)): return
        try:
            p=delete_records(self.snapshot[0],rows); self.preview(); messagebox.showinfo('删除完成','已删除 %d 条网址的访问记录。\n备份：%s'%(len(rows),p))
        except Exception as e: messagebox.showerror('删除失败','没有提交删除。请完全退出浏览器后重试。\n'+str(e))

if __name__=='__main__':
    import sys
    if '--self-test' in sys.argv:
        app=App(); app.root.update(); app.root.destroy()
        db=sqlite3.connect(':memory:'); db.execute('SELECT 1'); db.close()
        pathlib.Path(sys.argv[sys.argv.index('--self-test')+1]).write_text('PASS: packaged Tk and SQLite',encoding='utf-8')
    else: App().root.mainloop()
