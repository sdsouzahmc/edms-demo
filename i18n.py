"""Automatic Arabic translation layer: wraps Streamlit text/label functions and translates through ar_dict."""
import functools
import re
import streamlit as st
from ar_dict import AR_MAP

_KEYS = sorted(AR_MAP, key=len, reverse=True)
_RX = re.compile("|".join(r"(?<![A-Za-z0-9])" + re.escape(k) + r"(?![A-Za-z0-9])" for k in _KEYS))
_TAG = re.compile(r"(<[^>]*>)")
_installed = False
import os
_DEBUG = bool(os.environ.get('I18N_LOG'))


def is_ar():
    try:
        return st.session_state.get("lang", "en") == "ar"
    except Exception:
        return False


@functools.lru_cache(maxsize=8192)
def _tx(s):
    if s in AR_MAP:
        return AR_MAP[s]
    out = []
    for part in _TAG.split(s):
        if part.startswith("<") and part.endswith(">"):
            out.append(part)
        elif "{" in part and ";" in part:      # inline CSS
            out.append(part)
        else:
            out.append(_RX.sub(lambda m: AR_MAP[m.group(0)], part))
    return "".join(out)


_LOG = set()


def translate(s):
    if not isinstance(s, str) or not s.strip() or not re.search(r"[A-Za-z]", s):
        return s
    r = _tx(s)
    if _DEBUG:
        txt = re.sub(r"<[^>]*>", " ", r)
        if re.search(r"[A-Za-z]{3,}", txt) and not ("{" in txt and ";" in txt):
            _LOG.add(s.strip())
    return r


def _txall(a):
    return tuple(translate(x) if isinstance(x, str) else x for x in a)


def _spec_body(a, k):
    k = {kk: (translate(v) if kk in ("body", "help", "label") and isinstance(v, str) else v) for kk, v in k.items()}
    return _txall(a), k


def _spec_label(a, k):
    a = list(a)
    if a and isinstance(a[0], str):
        a[0] = translate(a[0])
    for kk in ("label", "placeholder", "help"):
        if isinstance(k.get(kk), str):
            k = dict(k)
            k[kk] = translate(k[kk])
    return tuple(a), k


def _spec_choice(a, k):
    a, k = _spec_label(a, k)
    if "format_func" not in k:
        k = dict(k)
        k["format_func"] = lambda x: translate(str(x))
    return a, k


def _spec_tabs(a, k):
    a = list(a)
    if a and isinstance(a[0], (list, tuple)):
        a[0] = [translate(x) if isinstance(x, str) else x for x in a[0]]
    return tuple(a), k


def _spec_page_link(a, k):
    a = list(a)
    if len(a) > 1 and isinstance(a[1], str):
        a[1] = translate(a[1])
    if isinstance(k.get("label"), str):
        k = dict(k)
        k["label"] = translate(k["label"])
    return tuple(a), k


def _spec_df(a, k):
    try:
        import pandas as pd
        if a and isinstance(a[0], pd.DataFrame):
            df = a[0].rename(columns=lambda c: translate(str(c)) if isinstance(c, str) else c)
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].map(lambda v: AR_MAP.get(v, v) if isinstance(v, str) else v)
            return (df,) + tuple(a[1:]), k
    except Exception:
        pass
    return a, k


def _spec_plot(a, k):
    try:
        fig = a[0]
        lay = fig.layout
        if lay.title and lay.title.text:
            fig.update_layout(title_text=translate(lay.title.text))
        for ax in ("xaxis", "yaxis"):
            t = getattr(lay, ax).title
            if t and t.text:
                fig.update_layout(**{ax: dict(title_text=translate(t.text))})
        for tr in fig.data:
            if getattr(tr, "name", None):
                tr.name = translate(tr.name)
            for attr in ("x", "y", "labels"):
                v = getattr(tr, attr, None)
                if v is not None and len(v) and isinstance(v[0], str):
                    nv = [AR_MAP.get(i, i) for i in v]
                    if nv != list(v):
                        setattr(tr, attr, nv)
    except Exception:
        pass
    return a, k


SPECS = {
    "markdown": _spec_body, "write": _spec_body, "caption": _spec_body, "title": _spec_body, "header": _spec_body, "subheader": _spec_body,
    "info": _spec_body, "success": _spec_body, "warning": _spec_body, "error": _spec_body,
    "button": _spec_label, "download_button": _spec_label, "form_submit_button": _spec_label, "checkbox": _spec_label, "toggle": _spec_label,
    "text_input": _spec_label, "text_area": _spec_label, "number_input": _spec_label, "slider": _spec_label, "date_input": _spec_label,
    "file_uploader": _spec_label, "color_picker": _spec_label, "expander": _spec_label, "metric": _spec_label,
    "selectbox": _spec_choice, "multiselect": _spec_choice, "radio": _spec_choice, "select_slider": _spec_choice,
    "tabs": _spec_tabs, "page_link": _spec_page_link, "dataframe": _spec_df, "plotly_chart": _spec_plot,
}


def install():
    global _installed
    if _installed:
        return
    from streamlit.delta_generator import DeltaGenerator
    main = st._main
    for name, spec in SPECS.items():
        orig = getattr(DeltaGenerator, name, None)
        if orig is None:
            continue

        def make(orig, spec):
            @functools.wraps(orig)
            def w(self, *a, **k):
                if is_ar():
                    a, k = spec(a, k)
                return orig(self, *a, **k)
            return w
        wrapped = make(orig, spec)
        setattr(DeltaGenerator, name, wrapped)
        if hasattr(st, name):
            setattr(st, name, functools.partial(wrapped, main))
    orig_sp = st.spinner

    @functools.wraps(orig_sp)
    def sp(text="In progress...", *a, **k):
        return orig_sp(translate(text) if is_ar() else text, *a, **k)
    st.spinner = sp
    _installed = True
