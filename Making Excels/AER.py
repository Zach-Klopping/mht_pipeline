import requests
import pandas as pd
import time

# Cleaning functions
def extract_freetoread_label(obj):
    # Handles str, dict with "value" (str/list/dict), or list of dicts/strs
    if not obj:
        return ""
    if isinstance(obj, str):
        return obj

    if isinstance(obj, list):
        return ", ".join([(item.get("$", "") if isinstance(item, dict) else str(item)) for item in obj if item]) or ""

    if isinstance(obj, dict):
        v = obj.get("value")
        if v is None:
            # sometimes the payload is under "$" directly
            return obj.get("$", "")
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return v.get("$", "") or v.get("value", "")
        if isinstance(v, list):
            return ", ".join([(item.get("$", "") if isinstance(item, dict) else str(item)) for item in v if item]) or ""
    return ""

def clean_authkeywords(obj):
    # Scopus often returns {'author-keyword': [{'$', '...'}, ...]}
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

# API configuration
API_KEY = "86a2130ad0a23237c0619209d11f1305"  # Replace with your key
headers = {
    "X-ELS-APIKey": API_KEY,
    "Accept": "application/json"
}

# ISSN for American Economic Review
issn = "0002-8282"

# Year range
start_year = 2000
end_year = 2025

base_url = "https://api.elsevier.com/content/search/scopus"

session = requests.Session()
TIMEOUT = 30

count = 50
max_retries = 5
articles = []

for year in range(start_year, end_year + 1):
    start = 0
    while True:
        query = f'ISSN({issn}) AND PUBYEAR = {year}'
        params = {
            "query": query,
            "count": count,
            "start": start,
            "view": "STANDARD"
        }

        for attempt in range(max_retries):
            response = requests.get(base_url, headers=headers, params=params)
            if response.status_code == 200:
                break
        else:
            print("Persistent error. Abandoning attempt.")
            break

        data = response.json()
        entries = data.get("search-results", {}).get("entry", [])
        if not entries:
            break

        for result in entries:
            doi = result.get("prism:doi", "N/A")
            url = f"https://doi.org/{doi}" if doi != "N/A" else "N/A"
            authors = result.get("author", [])

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
                "afid": "; ".join({aff.get("afid", "") for author in authors for aff in author.get("affiliation", [])}) if authors else "",
                "affilname": "; ".join({aff.get("affilname", "") for author in authors for aff in author.get("affiliation", [])}) if authors else "",
                "affiliation_city": "; ".join({aff.get("affiliation-city", "") for author in authors for aff in author.get("affiliation", [])}) if authors else "",
                "affiliation_country": "; ".join({aff.get("affiliation-country", "") for author in authors for aff in author.get("affiliation", [])}) if authors else "",
                "author_count": len(authors),
                "author_names": "; ".join([a.get("ce:indexed-name", "") for a in authors]),
                "author_ids": "; ".join([a.get("authid", "") for a in authors]),
                "author_afids": "; ".join([aff.get("afid", "") for a in authors for aff in a.get("affiliation", [])]) if authors else "",
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

        start += count

# Save results
df = pd.DataFrame(articles)

# Save to a new file
df.to_excel("/Users/zachklopping/Desktop/John List/MHT/Raw Excels/AER_2000-2025.xlsx", index=False)

print(f"Saved {len(df)} articles to 'AER_2000_2025.xlsx'.")
