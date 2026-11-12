import sys, pathlib, tempfile, sqlite3, os
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import history_cleaner as h
with tempfile.TemporaryDirectory() as tmp:
    h.LOCAL=pathlib.Path(tmp)
    for firefox in (False,True):
        p=pathlib.Path(tmp)/('places.sqlite' if firefox else 'History')
        db=sqlite3.connect(p)
        if firefox:
            db.executescript("CREATE TABLE moz_places(id INTEGER PRIMARY KEY,url TEXT,title TEXT,visit_count INTEGER,last_visit_date INTEGER,frecency INTEGER); CREATE TABLE moz_historyvisits(id INTEGER PRIMARY KEY,place_id INTEGER,from_visit INTEGER); CREATE TABLE moz_bookmarks(fk INTEGER); INSERT INTO moz_places VALUES(1,'https://example.com/ABC','delete',1,1,1),(2,'https://keep.com','keep',1,1,1); INSERT INTO moz_historyvisits VALUES(1,1,0),(2,2,1); INSERT INTO moz_bookmarks VALUES(1);")
        else:
            db.executescript("CREATE TABLE urls(id INTEGER PRIMARY KEY,url TEXT,title TEXT); CREATE TABLE visits(id INTEGER PRIMARY KEY,url INTEGER,from_visit INTEGER); INSERT INTO urls VALUES(1,'https://example.com/ABC','delete'),(2,'https://keep.com','keep'); INSERT INTO visits VALUES(1,1,0),(2,2,1);")
        db.commit()
        assert not h.matches(db,'abc',True)
        rows=h.matches(db,'abc',False); assert len(rows)==1
        backup=h.delete_records(p,rows); assert backup.exists()
        assert not h.matches(db,'abc',False)
        assert len(h.matches(db,'keep',False))==1
        if firefox: assert db.execute('SELECT count(*) FROM moz_bookmarks').fetchone()[0]==1
        saved=sqlite3.connect(backup)
        assert len(h.matches(saved,'abc',False))==1
        saved.close()
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        db.close()
print('PASS: both schemas, literal matching, preserved history/bookmarks, backup, integrity')

