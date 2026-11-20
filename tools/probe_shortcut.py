#!/usr/bin/env python3
"""Diagnostic shortcut: tries several ways to turn a downloaded Spotify page into
text and reports, for each, the character count and whether og:title is found.
No Get Group / Ask steps, so it never shows a 'Text' prompt."""
import plistlib, sys, uuid
OBJ = "￼"; actions = []
U = lambda: str(uuid.uuid4()).upper()
out = lambda u, n: {"Type": "ActionOutput", "OutputUUID": u, "OutputName": n}
att = lambda r: {"Value": r, "WFSerializationType": "WFTextTokenAttachment"}
def tstr(*parts):
    s, rg = "", {}
    for p in parts:
        if isinstance(p, str): s += p
        else: rg[f"{{{len(s)}, 1}}"] = p; s += OBJ
    return {"Value": {"string": s, "attachmentsByRange": rg}, "WFSerializationType": "WFTextTokenString"}
def act(i, p):
    u = U(); p = dict(p); p["UUID"] = u
    actions.append({"WFWorkflowActionIdentifier": "is.workflow.actions." + i, "WFWorkflowActionParameters": p})
    return u
def probe(label, item):
    c = act("count", {"Input": att(item), "WFCountType": "Characters"})
    m = act("text.match", {"text": tstr(item), "WFMatchTextPattern": r'og:title" content="[^"]+"', "ShowWhenRun": False})
    return [f"\n{label}: chars=", out(c, "Count"), " match=", out(m, "Matches")]

d = act("downloadurl", {"WFURL": tstr("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"), "WFHTTPMethod": "GET"})
D = out(d, "Contents of URL")
parts = ["PROBE"]
parts += probe("A_direct", D)
b = act("detect.text", {"WFInput": att(D)}); parts += probe("B_gettext", out(b, "Text"))
r = act("setitemname", {"WFInput": att(D), "WFName": "page.txt", "WFDontIncludeFileExtension": False})
rc = act("detect.text", {"WFInput": att(out(r, "Renamed Item"))}); parts += probe("C_rename_txt", out(rc, "Text"))
e = act("base64encode", {"WFInput": att(D), "WFEncodeMode": "Encode", "WFBase64LineBreakMode": "None"})
dd = act("base64encode", {"WFInput": att(out(e, "Base64 Encoded")), "WFEncodeMode": "Decode"})
dt = act("detect.text", {"WFInput": att(out(dd, "Base64 Decoded"))}); parts += probe("D_base64", out(dt, "Text"))
act("output", {"WFOutput": tstr(*parts), "WFNoOutputSurfaceBehavior": "Respond"})
wf = {"WFWorkflowClientVersion": "2607.0.2", "WFWorkflowMinimumClientVersion": 900,
      "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4292093695, "WFWorkflowIconGlyphNumber": 61440},
      "WFWorkflowImportQuestions": [], "WFWorkflowTypes": [], "WFWorkflowInputContentItemClasses": [],
      "WFWorkflowOutputContentItemClasses": [], "WFWorkflowActions": actions}
plistlib.dump(wf, open(sys.argv[1], "wb"), fmt=plistlib.FMT_BINARY); print("wrote", sys.argv[1])
