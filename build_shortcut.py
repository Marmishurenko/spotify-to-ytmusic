#!/usr/bin/env python3
"""Generate the 'Spotify to YT Music' iOS Shortcut (unsigned plist).

Usage: build_shortcut.py OUT.shortcut [--test]
  --test: read the link from a .txt input file, pick list item 2 instead of
          asking, and output a diagnostic report instead of opening YouTube Music
          (for headless runs via `shortcuts run NAME -i link.txt -o out`).
Sign afterwards: shortcuts sign -m anyone -i OUT.shortcut -o SIGNED.shortcut

Lessons learned (verified with probe_shortcut.py on macOS Shortcuts):
- Text parameters (Match Text's `text`, Replace's `WFInput`, ...) must be passed
  as a WFTextTokenString. A bare WFTextTokenAttachment is ignored and Shortcuts
  pops up an empty "Text" prompt instead.
- A downloaded HTML page coerces to *rendered* text (~2k chars, no <meta> tags).
  Renaming it to page.txt and then Get Text from Input yields the raw source.
- No Get Group at Index: values are extracted with regex Replace ($1, $2).
"""
import plistlib, sys, uuid

TEST = "--test" in sys.argv
OBJ = "￼"
actions = []


def U():
    return str(uuid.uuid4()).upper()


def out(uid, name):
    return {"Type": "ActionOutput", "OutputUUID": uid, "OutputName": name}


def var(name):
    return {"Type": "Variable", "VariableName": name}


def att(ref):
    return {"Value": ref, "WFSerializationType": "WFTextTokenAttachment"}


def tstr(*parts):
    """Text with embedded variables; parts are str or ref dicts."""
    s, ranges = "", {}
    for p in parts:
        if isinstance(p, str):
            s += p
        else:
            ranges[f"{{{len(s)}, 1}}"] = p
            s += OBJ
    return {"Value": {"string": s, "attachmentsByRange": ranges},
            "WFSerializationType": "WFTextTokenString"}


def act(ident, params):
    u = U()
    params = dict(params, UUID=u)
    actions.append({"WFWorkflowActionIdentifier": "is.workflow.actions." + ident,
                    "WFWorkflowActionParameters": params})
    return u


def gettext(item):
    return out(act("detect.text", {"WFInput": att(item)}), "Text")


SAFARI_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_1 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1")


def fetch_source(url_param, user_agent=None):
    """Download a URL and return its raw HTML source as text."""
    params = {"WFURL": url_param, "WFHTTPMethod": "GET"}
    if user_agent:  # YouTube Music returns no results to non-browser user agents
        params["ShowHeaders"] = True
        params["WFHTTPHeaders"] = {"Value": {"WFDictionaryFieldValueItems": [
            {"WFItemType": 0, "WFKey": tstr("User-Agent"), "WFValue": tstr(user_agent)}]},
            "WFSerializationType": "WFDictionaryFieldValue"}
    d = act("downloadurl", params)
    r = act("setitemname", {"WFInput": att(out(d, "Contents of URL")), "WFName": "page.txt",
                            "WFDontIncludeFileExtension": False})
    return gettext(out(r, "Renamed Item"))


def match(inp, pattern):
    return out(act("text.match", {"text": tstr(inp), "WFMatchTextPattern": pattern,
                                  "ShowWhenRun": False}), "Matches")


def replace(inp, find, repl, regex=False):
    return out(act("text.replace", {"WFInput": tstr(inp), "WFReplaceTextFind": find,
                                    "WFReplaceTextReplace": repl,
                                    "WFReplaceTextRegularExpression": regex}), "Updated Text")


def extract(inp, pattern, template):
    """First regex match of `pattern` in inp, rewritten with `template` ($1, $2...)."""
    m = match(inp, pattern)
    first = out(act("getitemfromlist", {"WFInput": att(m), "WFItemSpecifier": "First Item"}),
                "Item from List")
    return replace(first, pattern, template, regex=True)


def setvar(name, inp):
    act("setvariable", {"WFVariableName": name, "WFInput": att(inp)})


def text(*parts):
    return out(act("gettext", {"WFTextActionText": tstr(*parts)}), "Text")


# 0. The shared link
INPUT = {"Type": "ExtensionInput"}
if TEST:
    INPUT = gettext(INPUT)  # CLI passes the link as a .txt file
setvar("Link", INPUT)

# 1. Raw source of the shared Spotify page (follows spotify.link redirects)
page = fetch_source(tstr(var("Link")))
page = replace(page, "&amp;", "&")
page = replace(page, "&#x27;", "'")
page = replace(page, "&quot;", '"')
setvar("Page", page)

# 2. Link type (track/album/playlist) and id, from og:url
OGURL = r'og:url" content="https://open\.spotify\.com/(\w+)/(\w+)"'
setvar("Kind", extract(var("Page"), OGURL, "$1"))
setvar("ID", extract(var("Page"), OGURL, "$2"))

g_if = U()
act("conditional", {"GroupingIdentifier": g_if, "WFControlFlowMode": 0,
                    "WFCondition": 4, "WFConditionalActionString": "track",
                    "WFInput": {"Type": "Variable", "Variable": att(var("Kind"))}})
# --- Track: search "<song> <artist>"
title = extract(var("Page"), r'og:title" content="([^"]+)"', "$1")
artist = extract(var("Page"), r'og:description" content="([^·"]+?) ·', "$1")
setvar("Query", text(title, " ", artist))

act("conditional", {"GroupingIdentifier": g_if, "WFControlFlowMode": 1})
# --- Album / playlist: list its tracks from the embed page and let the user pick
embed = fetch_source(tstr("https://open.spotify.com/embed/", var("Kind"), "/", var("ID")))
embed = replace(embed, "\\u0026", "&")
ITEM = r'"title":"([^"]+)","subtitle":"([^"]+)"'
items = match(embed, ITEM)
g_rep = U()
act("repeat.each", {"GroupingIdentifier": g_rep, "WFControlFlowMode": 0, "WFInput": att(items)})
replace(var("Repeat Item"), ITEM, "$1 — $2", regex=True)
rep_end = act("repeat.each", {"GroupingIdentifier": g_rep, "WFControlFlowMode": 2})
lst = out(rep_end, "Repeat Results")
if TEST:
    chosen = out(act("getitemfromlist", {"WFInput": att(lst), "WFItemSpecifier": "Item At Index",
                                         "WFItemIndex": 2}), "Item from List")
else:
    chosen = out(act("choosefromlist", {"WFInput": att(lst),
                                        "WFChooseFromListActionPrompt": "Open in YouTube Music"}),
                 "Chosen Item")
setvar("Query", replace(chosen, " — ", " "))
act("conditional", {"GroupingIdentifier": g_if, "WFControlFlowMode": 2})

# 3. Find the top YouTube Music result for the query and open it directly
enc = out(act("urlencode", {"WFInput": tstr(var("Query")), "WFEncodeMode": "Encode"}),
          "URL Encoded Text")
setvar("SearchURL", text("https://music.youtube.com/search?q=", enc))
ytm = fetch_source(tstr(var("SearchURL")), user_agent=SAFARI_UA)
VID = r'videoId(?:\\x22|")\s*:\s*(?:\\x22|")([A-Za-z0-9_-]{11})'
setvar("VideoID", extract(ytm, VID, "$1"))

g_v = U()
act("conditional", {"GroupingIdentifier": g_v, "WFControlFlowMode": 0, "WFCondition": 100,
                    "WFInput": {"Type": "Variable", "Variable": att(var("VideoID"))}})
setvar("Final", text("https://music.youtube.com/watch?v=", var("VideoID")))
act("conditional", {"GroupingIdentifier": g_v, "WFControlFlowMode": 1})
setvar("Final", text(var("SearchURL")))  # no result found: fall back to the search page
act("conditional", {"GroupingIdentifier": g_v, "WFControlFlowMode": 2})

if TEST:
    act("output", {"WFOutput": tstr("KIND=", var("Kind"), " | QUERY=", var("Query"),
                                    " | FINAL=", var("Final")),
                   "WFNoOutputSurfaceBehavior": "Respond"})
else:
    act("openurl", {"WFInput": tstr(var("Final"))})

wf = {
    "WFWorkflowClientVersion": "2607.0.2",
    "WFWorkflowMinimumClientVersion": 900,
    "WFWorkflowMinimumClientVersionString": "900",
    "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4292093695, "WFWorkflowIconGlyphNumber": 61440},
    "WFWorkflowImportQuestions": [],
    "WFWorkflowTypes": ["ActionExtension"],
    "WFWorkflowInputContentItemClasses": ["WFURLContentItem", "WFStringContentItem"],
    "WFWorkflowOutputContentItemClasses": [],
    "WFWorkflowHasShortcutInputVariables": True,
    "WFWorkflowNoInputBehavior": {"Name": "WFWorkflowNoInputBehaviorGetClipboard", "Parameters": {}},
    "WFWorkflowActions": actions,
}
with open(sys.argv[1], "wb") as f:
    plistlib.dump(wf, f, fmt=plistlib.FMT_BINARY)
print(f"wrote {sys.argv[1]} ({len(actions)} actions, test={TEST})")
