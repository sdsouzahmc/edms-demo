import streamlit as st
import streamlit.components.v1 as components
import db
import db_ext
import distribution as dist
import assistant
import icons
import theme

db.init_db()
theme.inject_css()
theme.sidebar_nav()
theme.topbar("16 · Ask EDMS — Search Assistant", "Type or speak a question · the assistant finds the documents and shows what matters about each one")

user = theme.current_user()
profile = theme.current_profile()
is_admin = theme.is_admin()
shared_ids = db_ext.shared_with(profile["dept"])


def allowed(d):
    return is_admin or d["department"] == profile["dept"] or d["status"] in ("Released", "Archived") or d["id"] in shared_ids


st.markdown("""<style>
.st-key-chatbox [data-testid="stChatMessage"] { background:#fff; border:1px solid #E2E6EC; border-radius:14px; padding:10px 14px; margin-bottom:8px; }
.dc { border:1px solid #E2E6EC; border-left:5px solid #2E8B8B; border-radius:12px; padding:10px 14px; margin:8px 0; background:#FBFCFE; }
.dc .t { font-weight:700; color:#1F3864; font-size:.98rem; } .dc .m { font-size:.8rem; color:#6B7280; margin-top:2px; }
.dc .g { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:6px 14px; margin-top:8px; font-size:.8rem; }
.dc .g b { display:block; color:#6B7280; font-weight:600; font-size:.68rem; text-transform:uppercase; letter-spacing:.03em; }
.dc .s { margin-top:8px; font-size:.84rem; color:#2B3445; background:#F1F5FA; border-radius:8px; padding:6px 10px; }
.st-key-sugg button { border-radius:20px !important; min-height:52px; } .st-key-sugg button p { white-space:normal !important; font-size:.76rem; line-height:1.15; }
</style>""", unsafe_allow_html=True)

if "chat" not in st.session_state:
    st.session_state["chat"] = [{"role": "assistant", "text": f"Hello {user.split()[0]} 👋 I can find documents for you. Ask in plain words — "
                                 "for example **pending finance invoices**, **scanned letters from MOPH**, **contracts expiring soon**, "
                                 "or **how many confidential documents are under legal hold**. You can also use the microphone (English or Arabic)."}]

# suggestions + voice
SUGG = ["Pending finance invoices", "Contracts expiring soon", "Latest HR policies", "Scanned regulatory letters",
        "Confidential documents", "How many are pending approval", "فاتورة"]
with st.container(key="sugg"):
  cols = st.columns(len(SUGG))
  for i, s in enumerate(SUGG):
    if cols[i].button(s, key=f"sg_{i}", use_container_width=True):
        st.session_state["pending_q"] = s

vc1, vc2 = st.columns([1, 3])
with vc1:
    _voice_html = """
    <div style="font-family:Source Sans Pro,Segoe UI,sans-serif;display:flex;gap:8px;align-items:center">
      <button id="mic" style="border:0;border-radius:24px;padding:9px 16px;background:linear-gradient(120deg,#1F3864,#2E8B8B);color:#fff;font-weight:700;cursor:pointer;font-size:14px">🎤 Speak</button>
      <select id="lg" style="border:1px solid #cbd5e1;border-radius:8px;padding:7px;font-size:13px"><option value="en-US">English</option><option value="ar-SA">العربية</option></select>
      <span id="st" style="font-size:12px;color:#6B7280"></span>
    </div>
    <script>
    const mic=document.getElementById('mic'), st=document.getElementById('st'), lg=document.getElementById('lg');
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR){ st.textContent='Voice input needs Chrome or Edge'; mic.disabled=true; mic.style.opacity=.5; }
    else{
      const r=new SR(); r.interimResults=false; r.maxAlternatives=1;
      mic.onclick=()=>{ r.lang=lg.value; try{ r.start(); st.textContent='🔴 Listening…'; }catch(e){} };
      r.onerror=e=>{ st.textContent = e.error==='not-allowed' ? 'Allow the microphone in the browser' : 'Voice error: '+e.error; };
      r.onend=()=>{ if(st.textContent.startsWith('🔴')) st.textContent=''; };
      r.onresult=e=>{
        const text=e.results[0][0].transcript; st.textContent='“'+text+'”';
        const doc=window.parent.document;
        const ta=doc.querySelector('[data-testid="stChatInput"] textarea');
        if(ta){
          const setter=Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype,'value').set;
          setter.call(ta,text); ta.dispatchEvent(new Event('input',{bubbles:true}));
          setTimeout(()=>{ const b=doc.querySelector('[data-testid="stChatInputSubmitButton"]'); if(b) b.click(); },250);
        }
      };
    }
    </script>"""
    try:
        st.iframe(_voice_html, height=64)
    except Exception:
        components.html(_voice_html, height=64)
with vc2:
    st.caption("🎤 Voice: press Speak, say your question, and it is sent automatically (Chrome / Edge, microphone permission required).")


def card(d, o=None):
    cur = db.get_workflow(d["id"])
    active = [w for w in cur if w["status"] == "active"]
    stage = active[0]["stage"] if active else ("Completed" if cur else "—")
    routed = [r for r in dist.log_rows(doc_id=d["id"], limit=4) if r["target_dept"] != "Unrouted"]
    route = ", ".join(r["target_dept"] for r in routed[:3]) or "—"
    aud = db.get_audit_log(d["id"], limit=1)
    last = f"{aud[0]['action']} · {aud[0]['actor']} · {str(aud[0]['ts'])[:10]}" if aud else "—"
    exp = d["expiry_date"] or "—"
    hold = " · ⚖️ <b style='color:#B00020'>Legal hold</b>" if d["legal_hold"] else ""
    snippet = (o["snippet"] if o and o.get("snippet") else (d["body_text"] or "")[:220])
    src = "📠 OCR scan" if d["source"] == "Scan" else (d["source"] or "Upload")
    return f"""<div class="dc"><div class="t">{d['doc_code']} — {d['title']}</div>
    <div class="m">{theme.pill(d['status'])} {src} · {d['doc_type']} · {d['language']} · v{d['current_version']}{hold}</div>
    <div class="g"><div><b>Department</b>{d['department']}</div><div><b>Security</b>{d['security_level']} · {d['classification']}</div>
    <div><b>Workflow stage</b>{stage}</div><div><b>Owner</b>{d['created_by']}</div><div><b>Created</b>{str(d['created_at'])[:10]}</div>
    <div><b>Expires</b>{exp}</div><div><b>Routed to</b>{route}</div><div><b>Retention</b>{d['retention_schedule'] or '—'}</div>
    <div><b>Last activity</b>{last}</div><div><b>Sender → recipient</b>{d['sender'] or '—'} → {d['recipient'] or '—'}</div></div>
    <div class="s">{snippet}</div></div>"""


def render_results(msg, idx):
    bm_ids = {b["id"] for b in db_ext.get_bookmarks(user)}
    for n, o in enumerate(msg["results"][:msg.get("shown", 5)]):
        d = db.get_document(o["doc"]["id"])
        st.markdown(card(d, o), unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
        if c1.button("👁 Open", key=f"o_{idx}_{n}"):
            db.log_audit(d["id"], user, "Viewed", "Opened via Ask EDMS assistant")
            db_ext.log_view(user, d["id"])
            st.toast(f"Access logged for {d['doc_code']}")
        if c2.button("⭐ Bookmark" if d["id"] not in bm_ids else "★ Saved", key=f"b_{idx}_{n}"):
            db_ext.toggle_bookmark(user, d["id"])
            st.toast("Bookmark updated")
        c3.download_button("⬇ Text", f"{d['doc_code']}\n{d['title']}\n{d['department']} · v{d['current_version']}\n\n{d['body_text'] or ''}",
                           f"{d['doc_code']}.txt", key=f"d_{idx}_{n}")
    extra = len(msg["results"]) - msg.get("shown", 5)
    if extra > 0:
        if st.button(f"Show {min(extra, 5)} more of {extra} remaining", key=f"more_{idx}"):
            msg["shown"] = msg.get("shown", 5) + 5
            st.rerun()


# handle input
q = st.chat_input("Ask for a document… e.g. “pending finance invoices” or press 🎤")
q = q or st.session_state.pop("pending_q", None)
if q:
    st.session_state["chat"].append({"role": "user", "text": q})
    f, res = assistant.answer(q, allowed)
    db_ext.log_search(user, q, len(res))
    if f["count"]:
        txt = f"There are **{len(res)}** document(s) {assistant.describe(f)} that you can access."
    elif res:
        txt = f"I found **{len(res)}** document(s) {assistant.describe(f)}." + (" Here are the best matches:" if len(res) > 1 else "")
    else:
        txt = (f"I couldn't find anything {assistant.describe(f)}. Try fewer words, a different spelling, or ask for a department, "
               "status (pending, released, archived) or a document type.")
    st.session_state["chat"].append({"role": "assistant", "text": txt, "results": res if not f["count"] else res[:3], "shown": 5})

with st.container(key="chatbox"):
    for i, m in enumerate(st.session_state["chat"]):
        with st.chat_message(m["role"], avatar="🧑‍💼" if m["role"] == "user" else "🤖"):
            st.markdown(m["text"])
            if m.get("results"):
                render_results(m, i)

if len(st.session_state["chat"]) > 1 and st.button("🧹 Clear conversation"):
    del st.session_state["chat"]
    st.rerun()
