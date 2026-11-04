"""Per-user favourites and most-used pages (shortcuts shown at the top of the sidebar)."""
import db


def _c():
    conn = db.get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS page_favs (user TEXT, page_key TEXT, ts TEXT, PRIMARY KEY (user, page_key));
    CREATE TABLE IF NOT EXISTS page_usage (user TEXT, page_key TEXT, n INTEGER DEFAULT 0, last TEXT, PRIMARY KEY (user, page_key));
    """)
    return conn


def favs(user):
    conn = _c()
    rows = [r["page_key"] for r in conn.execute("SELECT page_key FROM page_favs WHERE user=? ORDER BY ts", (user,))]
    conn.close()
    return rows


def is_fav(user, key):
    return key in favs(user)


def toggle(user, key):
    conn = _c()
    if conn.execute("SELECT 1 FROM page_favs WHERE user=? AND page_key=?", (user, key)).fetchone():
        conn.execute("DELETE FROM page_favs WHERE user=? AND page_key=?", (user, key))
    else:
        conn.execute("INSERT INTO page_favs VALUES (?,?,?)", (user, key, db.now()))
    conn.commit()
    conn.close()


def track(user, key):
    conn = _c()
    conn.execute("INSERT INTO page_usage VALUES (?,?,1,?) ON CONFLICT(user,page_key) DO UPDATE SET n=n+1, last=excluded.last",
                 (user, key, db.now()))
    conn.commit()
    conn.close()


def most_used(user, limit=3, exclude=()):
    conn = _c()
    rows = [r["page_key"] for r in conn.execute(
        "SELECT page_key FROM page_usage WHERE user=? AND page_key!='home' ORDER BY n DESC, last DESC LIMIT 12", (user,))]
    conn.close()
    return [k for k in rows if k not in exclude][:limit]
