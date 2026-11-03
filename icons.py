"""Inline SVG icon set + illustrations for the EDMS demo (no external assets; work offline and in dark/light)."""
P = {
    "document": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>',
    "inbox": '<path d="M4 13l2-8h12l2 8"/><path d="M4 13v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5h-5l-1 2h-4l-1-2z"/>',
    "scan": '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><path d="M4 12h16"/>',
    "version": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/><path d="M3 17.5l9 5 9-5" opacity=".5"/>',
    "workflow": '<rect x="3" y="4" width="6" height="5" rx="1"/><rect x="15" y="4" width="6" height="5" rx="1"/><rect x="9" y="15" width="6" height="5" rx="1"/><path d="M6 9v2a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V9M12 13v2"/>',
    "shield": '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.2-4.2"/>',
    "audit": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 12l2 2 4-4M9 17h6"/>',
    "archive": '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8M10 12h4"/>',
    "briefcase": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3 13h18"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>',
    "list": '<path d="M5 6h14M5 12h14M5 18h14"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
    "route": '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h6a3 3 0 0 1 0 6h-4a3 3 0 0 0 0 6h6"/>',
    "chart": '<path d="M4 20V4"/><path d="M4 20h16"/><rect x="7" y="12" width="3" height="5"/><rect x="12" y="8" width="3" height="9"/><rect x="17" y="5" width="3" height="12"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "edit": '<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17z"/><path d="M14 7l3 3"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "download": '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
    "print": '<path d="M7 9V4h10v5M7 17H5a1 1 0 0 1-1-1v-5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a1 1 0 0 1-1 1h-2"/><rect x="7" y="14" width="10" height="6"/>',
    "share": '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.2 11l7.6-4M8.2 13l7.6 4"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/>',
    "x": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "plus": '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "users": '<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.5a5 5 0 0 1 5 5"/>',
    "alert": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
    "trash": '<path d="M4 7h16M10 7V4h4v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "database": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3M14 9l2 2"/>',
    "home": '<path d="M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z"/>',
    "tag": '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.2"/>',
}

# action keyword -> (icon, colour)
ACTIONS = [
    ("Created", "plus", "#2E7D32"), ("Captur", "scan", "#2E8B8B"), ("Edited", "edit", "#B8860B"), ("Metadata", "tag", "#B8860B"),
    ("Corrected", "edit", "#B8860B"), ("Version Published", "shield", "#2E7D32"), ("Checked In", "version", "#1F3864"),
    ("Checked Out", "lock", "#1F3864"), ("Approved", "check", "#2E7D32"), ("Rejected", "x", "#B00020"), ("Denied", "alert", "#B00020"),
    ("Delegated", "route", "#6C4FA3"), ("Viewed", "eye", "#6B7280"), ("Downloaded", "download", "#4A90C2"), ("Printed", "print", "#4A90C2"),
    ("Shared", "share", "#2E8B8B"), ("Archived", "archive", "#6C4FA3"), ("Hold", "lock", "#B00020"), ("Disposal", "trash", "#B00020"),
    ("Distribution", "route", "#2E8B8B"), ("distribut", "route", "#2E8B8B"), ("Recycle", "trash", "#C0603C"), ("Signed", "edit", "#2E7D32"),
]

PAGE_ICON = {"home": "home", "1": "inbox", "2": "scan", "3": "version", "4": "workflow", "5": "shield", "6": "search", "7": "audit",
             "8": "archive", "9": "briefcase", "10": "settings", "11": "list", "12": "route", "13": "chart", "14": "users", "15": "key"}


def svg(name, size=20, color="currentColor", stroke=1.8):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" style="flex:none">{P.get(name, P["document"])}</svg>')


def chip(name, color="#2E8B8B", size=34):
    return (f'<span style="display:inline-flex;align-items:center;justify-content:center;width:{size}px;height:{size}px;border-radius:10px;'
            f'background:{color}1A;border:1px solid {color}40;flex:none">{svg(name, int(size * 0.55), color)}</span>')


def for_action(action):
    for k, ic, col in ACTIONS:
        if k.lower() in (action or "").lower():
            return ic, col
    return "document", "#6B7280"


def avatar(name, size=30, color=None):
    parts = [p for p in (name or "?").replace("-", " ").split() if p]
    ini = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
    pal = ["#1F3864", "#2E8B8B", "#C0603C", "#6C4FA3", "#2E7D32", "#4A90C2", "#B8860B"]
    c = color or pal[sum(map(ord, name or "?")) % len(pal)]
    return (f'<span style="display:inline-flex;align-items:center;justify-content:center;width:{size}px;height:{size}px;border-radius:50%;'
            f'background:{c};color:#fff;font-size:{int(size * .4)}px;font-weight:700;flex:none">{ini}</span>')


def hero_art():
    """Illustration for the hero banner: document stack, magnifier, shield, gears (pure SVG)."""
    return '''<svg viewBox="0 0 360 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<defs><linearGradient id="g1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity=".95"/><stop offset="1" stop-color="#DDEFEF" stop-opacity=".9"/></linearGradient></defs>
<circle cx="285" cy="48" r="70" fill="#FFFFFF" opacity=".06"/><circle cx="60" cy="170" r="60" fill="#FFFFFF" opacity=".05"/>
<g transform="translate(60 38) rotate(-8 60 70)"><rect width="118" height="150" rx="10" fill="url(#g1)" opacity=".55"/></g>
<g transform="translate(92 30) rotate(-2 60 70)"><rect width="118" height="150" rx="10" fill="url(#g1)" opacity=".8"/></g>
<g transform="translate(124 24)"><rect width="118" height="150" rx="10" fill="url(#g1)"/>
<rect x="14" y="16" width="52" height="8" rx="4" fill="#1F3864"/><rect x="14" y="34" width="90" height="5" rx="2.5" fill="#B5C3D6"/><rect x="14" y="46" width="82" height="5" rx="2.5" fill="#B5C3D6"/>
<rect x="14" y="58" width="88" height="5" rx="2.5" fill="#B5C3D6"/><rect x="14" y="70" width="60" height="5" rx="2.5" fill="#B5C3D6"/>
<rect x="14" y="88" width="42" height="26" rx="5" fill="#2E8B8B" opacity=".18"/><path d="M22 102l6 6 12-14" stroke="#2E8B8B" stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<rect x="66" y="92" width="38" height="5" rx="2.5" fill="#B5C3D6"/><rect x="66" y="104" width="30" height="5" rx="2.5" fill="#B5C3D6"/>
<rect x="14" y="126" width="26" height="14" rx="3" fill="#C0603C" opacity=".85"/><rect x="46" y="126" width="26" height="14" rx="3" fill="#2E8B8B" opacity=".85"/></g>
<g transform="translate(236 78)"><circle cx="34" cy="34" r="30" fill="#FFFFFF" fill-opacity=".14" stroke="#FFFFFF" stroke-width="7"/>
<path d="M56 56l26 26" stroke="#FFFFFF" stroke-width="9" stroke-linecap="round"/><path d="M22 36l9 9 16-18" stroke="#7FD1C7" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>
<g transform="translate(262 8)"><path d="M26 0l26 10v20c0 16-11 28-26 33C11 58 0 46 0 30V10z" fill="#2E8B8B"/><path d="M14 30l9 9 17-19" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>
<g transform="translate(30 20)" fill="none" stroke="#FFFFFF" stroke-width="3" opacity=".75"><circle cx="20" cy="20" r="9"/><path d="M20 3v6M20 31v6M3 20h6M31 20h6M8 8l4 4M28 28l4 4M32 8l-4 4M12 28l-4 4"/></g>
</svg>'''
