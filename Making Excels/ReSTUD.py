import requests
import pandas as pd
import time

# ----------------------------
# Networking/session settings
# ----------------------------
session = requests.Session()   # reuse TCP/TLS connections
TIMEOUT = 30                   # seconds
count = 100                    # try 100; if API rejects, change to 50 or 25
max_retries = 5

# ----------------------------
# Cleaning helpers (robust)
# ----------------------------
def extract_freetoread_label(obj):
    """
    Handles inconsistent shapes:
    - str
    - dict with "$" and/or "value"
    - list of dicts/strs
    """
    if not obj:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return ", ".join([(item.get("$", "") if isinstance(item, dict) else str(item)) for item in obj if item]) or ""
    if isinstance(obj, dict):
        v = obj.get("value")
        if v is None:
            return obj.get("$", "")
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return v.get("$", "") or v.get("value", "")
        if isinstance(v, list):
            return ", ".join([(item.get("$", "") if isinstance(item, dict) else str(item)) for item in v if item]) or ""
    return ""

def clean_authkeywords(obj):
    """
    Scopus often returns:
      - list of {"$": "..."} dicts
      - dict with "author-keyword"/"value"/"keywords"
      - plain string
    """
    if not obj:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return "; ".join([(kw.get("$", "") if isinstance(kw, dict) else str(kw)) for kw in obj if kw]) or ""
    if isinstance(obj, dict):
        items = obj.get("author-keyword") or obj.get("value") or obj.get("keywords") or []
        if isinstance(items, str):
            return items
        if isinstance(items, dict):
            return items.get("$", "") or items.get("value", "")
        if isinstance(items, list):
            return "; ".join([(kw.get("$", "") if isinstance(kw, dict) else str(kw)) for kw in items if kw]) or ""
    return ""

# ----------------------------
# API configuration
# ----------------------------
API_KEY = "86a2130ad0a23237c0619209d11f1305"  # Replace with your API key
headers = {
    "X-ELS-APIKey": API_KEY,
    "Accept": "application/json"
}

# Journal: Review of Economic Studies (ReSTUD)
issn = "0034-6527"

# Year range
start_year = 2000
end_year = 2025

base_url = "https://api.elsevier.com/content/search/scopus"

# Ask only for fields we actually use (reduces payload)
wanted_fields = ",".join([
    "eid","dc:title","prism:doi","subtype","subtypeDescription","dc:creator",
    "author","prism:coverDate","prism:coverDisplayDate","prism:publicationName",
    "prism:issn","source-id","prism:eIssn","prism:aggregationType","prism:volume",
    "prism:issueIdentifier","article-number","prism:pageRange","dc:description",
    "authkeywords","citedby-count","openaccess","freetoread","freetoreadLabel",
    "fund-acr","fund-no","fund-sponsor","pii","pubmed-id"
])

articles = []

# ----------------------------
# Main fetch loop
# ----------------------------
for year in range(start_year, end_year + 1):
    start_idx = 0
    page = 0
    while True:
        query = f'ISSN({issn}) AND PUBYEAR = {year}'
        params = {
            "query": query,
            "count": count,
            "start": start_idx,
            "view": "STANDARD",
            "field": wanted_fields
        }

        # Retry with exponential backoff ONLY on throttling/transient errors
        for attempt in range(max_retries):
            resp = session.get(base_url, headers=headers, params=params, timeout=TIMEOUT)
            if resp.status_code == 200:
                break
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.0 * (2 ** attempt))  # 1s, 2s, 4s, 8s, 16s
                continue
            else:
                resp.raise_for_status()
        else:
            print(f"[{year}] Persistent error at start={start_idx}. Skipping remainder of year.")
            break

        data = resp.json()
        entries = data.get("search-results", {}).get("entry", [])
        if not entries:
            if page == 0:
                print(f"[{year}] No entries returned.")
            break

        for result in entries:
            doi = result.get("prism:doi", "N/A")
            url = f"https://doi.org/{doi}" if doi and doi != "N/A" else "N/A"
            authors = result.get("author", [])
            # normalize authors to list
            if isinstance(authors, dict):
                authors = [authors]
            if not isinstance(authors, list):
                authors = []

            # Build record with defensive parsing for affiliations
            articles.append({
                "eid": result.get("eid", ""),
                "doi": doi,
                "url": url,
                "pii": result.get("pii", ""),
                "pubmed_id": result.get("pubmed-id", ""),
                "title": result.get("dc:title", ""),
                "subtype": result.get("subtype", ""),
                "subtypeDescription": result.get("subtypeDescription", ""),
                "creator": result.get("dc:creator", ""),

                "afid": "; ".join({
                    (aff.get("afid", "") if isinstance(aff, dict) else "")
                    for a in (authors or [])
                    for aff in (a.get("affiliation", []) if isinstance(a, dict) else [])
                }),
                "affilname": "; ".join({
                    (aff.get("affilname", "") if isinstance(aff, dict) else "")
                    for a in (authors or [])
                    for aff in (a.get("affiliation", []) if isinstance(a, dict) else [])
                }),
                "affiliation_city": "; ".join({
                    (aff.get("affiliation-city", "") if isinstance(aff, dict) else "")
                    for a in (authors or [])
                    for aff in (a.get("affiliation", []) if isinstance(a, dict) else [])
                }),
                "affiliation_country": "; ".join({
                    (aff.get("affiliation-country", "") if isinstance(aff, dict) else "")
                    for a in (authors or [])
                    for aff in (a.get("affiliation", []) if isinstance(a, dict) else [])
                }),

                "author_count": len(authors),
                "author_names": "; ".join([
                    (a.get("ce:indexed-name", "") if isinstance(a, dict) else "")
                    for a in authors
                ]),
                "author_ids": "; ".join([
                    (a.get("authid", "") if isinstance(a, dict) else "")
                    for a in authors
                ]),
                "author_afids": "; ".join([
                    (aff.get("afid", "") if isinstance(aff, dict) else "")
                    for a in (authors or [])
                    for aff in (a.get("affiliation", []) if isinstance(a, dict) else [])
                ]),

                "coverDate": result.get("prism:coverDate", ""),
                "coverDisplayDate": result.get("prism:coverDisplayDate", ""),
                "publicationName": result.get("prism:publicationName", ""),
                "issn": result.get("prism:issn", ""),
                "source_id": result.get("source-id", ""),
                "eIssn": result.get("prism:eIssn", ""),
                "aggregationType": result.get("prism:aggregationType", ""),
                "volume": result.get("prism:volume", ""),
                "issueIdentifier": result.get("prism:issueIdentifier", ""),
                "article_number": result.get("article-number", ""),
                "pageRange": result.get("prism:pageRange", ""),
                "description": result.get("dc:description", ""),

                "authkeywords": clean_authkeywords(result.get("authkeywords", "")),
                "citedby_count": result.get("citedby-count", "0"),
                "openaccess": result.get("openaccess", ""),
                "freetoread": extract_freetoread_label(result.get("freetoread", {})),
                "freetoreadLabel": extract_freetoread_label(result.get("freetoreadLabel", {})),

                "fund_acr": result.get("fund-acr", ""),
                "fund_no": result.get("fund-no", ""),
                "fund_sponsor": result.get("fund-sponsor", ""),
            })

        page += 1
        start_idx += count
        # no fixed sleep here; we only back off on errors

# ----------------------------
# Save results
# ----------------------------
df = pd.DataFrame(articles)
out_path = "/Users/zachklopping/Desktop/John List/MHT/Raw Excels/ReSTUD_2000-2025.xlsx"
df.to_excel(out_path, index=False)
print(f"Saved {len(df)} articles to '{out_path}'.")
