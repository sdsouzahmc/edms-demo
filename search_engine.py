"""Full-text search engine for the EDMS demo.

SQLite FTS5 index over document text (including OCR'd text), with BM25 relevance
ranking, highlighted snippets, Boolean operators, phrase and wildcard queries,
typo correction ("did you mean"), natural-language expansion and facet counts.
The index is rebuilt automatically whenever the repository changes.
"""
import difflib
import html
import re
import db

TOK = re.compile(r'"[^"]*"|\(|\)|[^\s()]+')
STOP = {"the", "a", "an", "of", "for", "to", "and", "about", "in", "on", "is", "are", "what", "which", "that",
        "with", "any", "me", "find", "show", "all", "from", "my", "documents", "document", "please"}
SYNONYMS = {
    "money": ["invoice", "payment", "budget", "qar", "purchase", "amount"], "pay": ["invoice", "payment", "qar"],
    "staff": ["employee", "hr", "nursing", "contract", "leave", "appraisal"], "people": ["employee", "hr", "staff"],
    "safety": ["fire", "inspection", "security", "incident", "hvac"], "building": ["hvac", "floor", "plan", "electrical", "facility"],
    "licence": ["license", "certificate", "moph", "accreditation"], "license": ["licence", "certificate", "moph"],
    "patient": ["medical", "admission", "clinical", "intake", "discharge"], "rules": ["policy", "procedure", "sop"],
    "supplier": ["vendor", "tender", "purchase", "contract"], "accreditation": ["carf", "iso", "audit", "evidence"],
    "network": ["server", "switch", "firewall", "outage", "system"], "bill": ["invoice", "payment"],
    "agreement": ["contract", "sla", "liability"], "scanned": ["ocr"],
}
_cache = {"sig": None}


def _conn():
    return db.get_conn()


def ensure_index(force=False):
    """(Re)build the FTS5 index if the repository has changed since the last build."""
    conn = _conn()
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS search_idx USING fts5("
                 "code, title, body, meta, tokenize='unicode61 remove_diacritics 2', prefix='2 3')")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS search_vocab USING fts5vocab(search_idx, 'row')")
    conn.execute("CREATE TABLE IF NOT EXISTS search_state (id INTEGER PRIMARY KEY, sig TEXT, built_at TEXT)")
    sig = conn.execute("SELECT COUNT(*) || '|' || COALESCE(MAX(modified_at),'') || '|' || COALESCE(SUM(LENGTH(COALESCE(body_text,'')) + LENGTH(title)),0) "
                       "|| '|' || COALESCE(SUM(LENGTH(status)),0) FROM documents").fetchone()[0]
    row = conn.execute("SELECT sig FROM search_state WHERE id=1").fetchone()
    if force or not row or row[0] != sig:
        conn.execute("DELETE FROM search_idx")
        docs = conn.execute("SELECT * FROM documents WHERE status NOT IN ('Disposed','Deleted')").fetchall()
        for d in docs:
            meta = " ".join(str(d[k] or "") for k in ("department", "doc_type", "sender", "recipient", "classification",
                                                       "language", "source", "retention_schedule"))
            conn.execute("INSERT INTO search_idx(rowid, code, title, body, meta) VALUES (?,?,?,?,?)",
                         (d["id"], d["doc_code"], d["title"], d["body_text"] or "", meta))
        conn.execute("INSERT OR REPLACE INTO search_state (id, sig, built_at) VALUES (1,?,?)", (sig, db.now()))
        conn.commit()
    stats = {
        "docs": conn.execute("SELECT COUNT(*) FROM search_idx").fetchone()[0],
        "terms": conn.execute("SELECT COUNT(*) FROM search_vocab").fetchone()[0],
        "built": conn.execute("SELECT built_at FROM search_state WHERE id=1").fetchone()[0],
        "ocr_docs": conn.execute("SELECT COUNT(*) FROM documents WHERE source='Scan' AND status NOT IN ('Disposed','Deleted')").fetchone()[0],
    }
    conn.close()
    return stats


def _vocab(conn):
    return [r[0] for r in conn.execute("SELECT term FROM search_vocab")]


def _expand_wild(tok, vocab):
    rx = re.compile("^" + re.escape(tok.lower()).replace(r"\*", ".*").replace(r"\?", ".") + "$")
    hits = [t for t in vocab if rx.match(t)][:30]
    return "(" + " OR ".join(f'"{h}"' for h in hits) + ")" if hits else '"zzznomatchzzz"'


def build_query(q, vocab, mode="smart"):
    """Translate a user query to an FTS5 MATCH expression."""
    toks = TOK.findall(q)
    out = []
    for t in toks:
        if t in ("AND", "OR", "NOT", "(", ")"):
            out.append(t)
        elif t.startswith('"'):
            out.append(t)
        elif "?" in t or "*" in t[:-1] or ("*" in t and "?" in t):
            out.append(_expand_wild(t, vocab))
        elif t.endswith("*") and len(t) > 1:
            out.append(f'"{t[:-1]}"*')
        else:
            out.append('"' + t.replace('"', "") + '"')
    # a leading NOT is meaningless in FTS5
    while out and out[0] == "NOT":
        out.pop(0)
    # FTS5 needs explicit AND between operands
    fixed = []
    for t in out:
        if fixed:
            prev = fixed[-1]
            if prev not in ("AND", "OR", "NOT", "(") and t not in ("AND", "OR", "NOT", ")"):
                fixed.append("AND")
        fixed.append(t)
    return " ".join(fixed)


def nl_query(q):
    terms = [w for w in re.findall(r"\w+", q.lower()) if w not in STOP]
    exp = []
    for t in terms:
        for e in [t] + SYNONYMS.get(t, []):
            if e not in exp:
                exp.append(e)
    return " OR ".join(f'"{e}"' for e in exp), exp


def _mark(text):
    """Escape then turn our sentinel markers into <mark> tags."""
    s = html.escape(text)
    return s.replace("[[[", "<mark>").replace("]]]", "</mark>")


def _run(conn, expr, limit=300):
    sql = ("SELECT rowid AS id, -bm25(search_idx, 4.0, 6.0, 1.0, 0.6) AS score, "
           "snippet(search_idx, 2, '[[[', ']]]', ' … ', 28) AS snip, "
           "highlight(search_idx, 1, '[[[', ']]]') AS title_hl, "
           "highlight(search_idx, 0, '[[[', ']]]') AS code_hl, "
           "(highlight(search_idx, 2, '[[[', ']]]') LIKE '%[[[%') AS in_body, "
           "(highlight(search_idx, 1, '[[[', ']]]') LIKE '%[[[%') AS in_title "
           "FROM search_idx WHERE search_idx MATCH ? ORDER BY score DESC LIMIT ?")
    return conn.execute(sql, (expr, limit)).fetchall()


def search(query, mode="smart", allow=None, filters=None):
    """Run a ranked search.

    mode: 'smart' (Boolean/phrase/wildcard aware) or 'nl' (natural language).
    allow: optional predicate(doc_row) -> bool for security trimming.
    filters: dict of simple equality filters on the documents table.
    Returns dict(results=[...], corrected=None|str, expr=str, error=None|str, expanded=[...]).
    """
    ensure_index()
    conn = _conn()
    vocab = _vocab(conn)
    info = {"results": [], "corrected": None, "expr": "", "error": None, "expanded": []}
    rows, expr = [], ""
    q = (query or "").strip()
    try:
        if not q:
            info["expr"] = "(all documents)"
            docs = conn.execute("SELECT id FROM documents WHERE status NOT IN ('Disposed','Deleted') ORDER BY id DESC").fetchall()
            rows = [{"id": d["id"], "score": 0.0, "snip": None, "title_hl": None, "code_hl": None, "in_body": 0, "in_title": 0}
                    for d in docs]
        else:
            if mode == "nl":
                expr, exp = nl_query(q)
                info["expanded"] = exp
            else:
                expr = build_query(q, vocab)
            info["expr"] = expr
            rows = _run(conn, expr) if expr else []
            if not rows and mode != "nl" and not re.search(r"\b(AND|OR|NOT)\b", q):
                # typo tolerance: replace unknown words with the closest vocabulary term
                fixed, changed = [], False
                for t in TOK.findall(q):
                    base = t.strip('"').rstrip("*").lower()
                    if t.startswith('"') or "*" in t or "?" in t or len(base) < 4 or base in vocab:
                        fixed.append(t)
                        continue
                    m = difflib.get_close_matches(base, vocab, n=1, cutoff=0.74)
                    if m:
                        fixed.append(m[0])
                        changed = True
                    else:
                        fixed.append(t)
                if changed:
                    info["corrected"] = " ".join(fixed)
                    info["expr"] = build_query(info["corrected"], vocab)
                    rows = _run(conn, info["expr"])
    except Exception as e:  # malformed boolean expression etc.
        info["error"] = f"Could not parse the query ({e}). Check quotes and brackets."
        rows = []
    out = []
    for r in rows:
        d = conn.execute("SELECT * FROM documents WHERE id=?", (r["id"],)).fetchone()
        if not d or d["status"] in ("Disposed", "Deleted"):
            continue
        if allow and not allow(d):
            continue
        if filters and any(v not in (None, "All", "") and d[k] != v for k, v in filters.items()):
            continue
        snip = r["snip"] if r["snip"] and "[[[" in r["snip"] else (r["snip"] or (d["body_text"] or "")[:200])
        out.append({"doc": d, "score": float(r["score"] or 0), "snippet": _mark(snip or ""),
                    "title_html": _mark(r["title_hl"] or d["title"]), "code_html": _mark(r["code_hl"] or d["doc_code"]),
                    "in_body": bool(r["in_body"]), "in_title": bool(r["in_title"])})
    conn.close()
    top = max([o["score"] for o in out], default=0) or 1
    for o in out:
        o["rel"] = max(0.05, o["score"] / top) if q else 0
    info["results"] = out
    return info


def facets(results):
    f = {"Department": {}, "Document type": {}, "Status": {}, "Source": {}, "Language": {}}
    for o in results:
        d = o["doc"]
        src = {"Scan": "OCR scan", "Postal": "Postal mail", "Email": "Email", "Upload": "Upload"}.get(d["source"], d["source"] or "Other")
        for k, v in (("Department", d["department"]), ("Document type", d["doc_type"]), ("Status", d["status"]),
                     ("Source", src), ("Language", d["language"])):
            f[k][v] = f[k].get(v, 0) + 1
    return {k: dict(sorted(v.items(), key=lambda x: (-x[1], x[0]))) for k, v in f.items()}


def source_label(src):
    return {"Scan": "OCR scan", "Postal": "Postal mail", "Email": "Email", "Upload": "Upload"}.get(src, src or "Other")
