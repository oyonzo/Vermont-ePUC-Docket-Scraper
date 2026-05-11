import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from urllib.request import urlopen
from urllib.parse import urljoin
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser
from pathlib import Path
import re
from datetime import datetime


# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
VALID_CASE_URL = re.compile(
    r"^https://epuc\.vermont\.gov/\?q=node/64/\d+$"
)

def validate_case_url(url):
    if not VALID_CASE_URL.match(url):
        raise ValueError(
            f"Invalid URL:\n{url}\n\n"
            "Only URLs of this form are allowed:\n"
            "https://epuc.vermont.gov/?q=node/64/########"
        )
    return url

def normalize_case_url(url):
    m = re.match(r"(https://epuc\.vermont\.gov/\?q=node/64/\d+)", url)
    if m:
        return validate_case_url(m.group(1))
    raise ValueError("Invalid case URL")

def prompt_for_links():
    print("Paste case URLs (one per line).")
    print("Required format:")
    print("https://epuc.vermont.gov/?q=node/64/########")
    print("Press Enter on a blank line to start.\n")

    links = []

    while True:
        line = input().strip()
        if not line:
            break
        try:
            validated = normalize_case_url(line)
            links.append(validated)
        except ValueError as e:
            print(e)

    return links

BASE_URL = "https://epuc.vermont.gov"
START_URLS = prompt_for_links()

if not START_URLS:
    print("No URLs provided. Exiting.")
    exit()

# ROOT_DOWNLOAD_DIR = Path.home() / "Downloads" / "PUC Case 190855"
# ROOT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def clean_filename(text):
    text = re.sub(r"[^\w\s\-]", "", text)
    return re.sub(r"\s+", " ", text).strip()

def extract_date(text):
    m = re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", text)
    if not m:
        return None
    raw = m.group()
    fmt = "%m/%d/%Y" if len(raw.split("/")[-1]) == 4 else "%m/%d/%y"
    return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")

def save_html_snapshot(directory, name, html):
    filename = clean_filename(name) + ".html"
    path = directory / filename
    path.write_text(html, encoding="utf-8")

# ------------------------------------------------------------
# Case Header Parser
# ------------------------------------------------------------

class CaseHeaderParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.values = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "span" and attrs.get("class") == "caseheaderXLtext":
            self.capture = True
            self.current_text = ""

    def handle_data(self, data):
        if self.capture:
            self.current_text += data.strip()

    def handle_endtag(self, tag):
        if tag == "span" and self.capture:
            if self.current_text:
                self.values.append(self.current_text)
            self.capture = False

# ------------------------------------------------------------
# Tab parser
# ------------------------------------------------------------

class TabParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_tabs = False
        self.tabs = []
        self.current_href = None
        self.current_title = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and attrs.get("id") == "folderTabs":
            self.in_tabs = True
        elif self.in_tabs and tag == "a" and "href" in attrs:
            self.current_href = attrs["href"]
            self.current_title = ""

    def handle_data(self, data):
        if self.in_tabs and self.current_href:
            self.current_title += data.strip()

    def handle_endtag(self, tag):
        if tag == "a" and self.current_href:
            self.tabs.append({
                "title": self.current_title,
                "href": self.current_href
            })
            self.current_href = None
        elif tag == "div" and self.in_tabs:
            self.in_tabs = False


# ------------------------------------------------------------
# Document parser (same as before, layout-agnostic)
# ------------------------------------------------------------

class DownloadLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_tr = False
        self.in_td = False
        self.in_style = False
        self.current_row = []
        self.rows = []
        self.current_link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "style" or tag == "script":
            self.in_style = True

        elif tag == "tr":
            self.in_tr = True
            self.current_row = []
            self.current_link = None

        elif tag == "td" and self.in_tr:
            self.in_td = True
            self.current_text = ""

        elif tag == "a" and attrs.get("aria-label") == "Download document":
            self.current_link = attrs.get("href")

    def handle_data(self, data):
        if self.in_td and not self.in_style:
            self.current_text += data.strip() + " "

    def handle_endtag(self, tag):
        if tag == "style" or tag == "script":
            self.in_style = False

        elif tag == "td" and self.in_td:
            self.current_row.append(self.current_text.strip())
            self.in_td = False

        elif tag == "tr" and self.in_tr:
            if self.current_link and len(self.current_row) >= 4:
                self.rows.append({
                    "date": self.current_row[1],
                    "name": self.current_row[2],
                    "title": self.current_row[3],
                    "href": self.current_link
                })
            self.in_tr = False


# ------------------------------------------------------------
# Main logic
# ------------------------------------------------------------
for START_URL in START_URLS:
    print("\nProcessing:", START_URL)
    # existing logic follows unchanged

    print("Loading main page to discover tabs...")
    html = urlopen(START_URL).read().decode("utf-8")

    # ------------------------------------------------------------
    # Extract docket number + case name for root folder
    # ------------------------------------------------------------

    header_parser = CaseHeaderParser()
    header_parser.feed(html)

    if len(header_parser.values) >= 2:
        docket = clean_filename(header_parser.values[0])
        case_name = clean_filename(header_parser.values[1])
        root_folder_name = f"{docket} - {case_name}"
    else:
        # Fallback in case parsing ever fails
        root_folder_name = "PUC Case Files"

    ROOT_DOWNLOAD_DIR = Path.home() / "Downloads" / root_folder_name
    ROOT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    print("Root download folder:", ROOT_DOWNLOAD_DIR)


    # ------------------------------------------------------------
    # Find Tabs
    # ------------------------------------------------------------


    tab_parser = TabParser()
    tab_parser.feed(html)

    print(f"Found {len(tab_parser.tabs)} tabs")


    # ------------------------------------------------------------
    # Parse through each tab
    # ------------------------------------------------------------


    for tab in tab_parser.tabs:
        tab_title = clean_filename(tab["title"])
        tab_url = urljoin(BASE_URL, tab["href"])

        print(f"\n=== Processing tab: {tab_title} ===")

        tab_dir = ROOT_DOWNLOAD_DIR / tab_title
        tab_dir.mkdir(exist_ok=True)

        try:
            tab_html = urlopen(tab_url).read().decode("utf-8")
            # Save offline copy of tab HTML
            save_html_snapshot(tab_dir, tab_title, tab_html)
        except Exception as e:
            print("Failed to load tab:", e)
            continue

        doc_parser = DownloadLinkParser()
        doc_parser.feed(tab_html)
        print(f"Found {len(doc_parser.rows)} documents")

        for doc in doc_parser.rows:
            date_str = extract_date(doc["date"])
            if not date_str:
                continue

            name = clean_filename(doc["name"])
            title = clean_filename(doc["title"])

            filename = f"{date_str} {name} - {title}.pdf"
            filepath = tab_dir / filename
            file_url = urljoin(BASE_URL, doc["href"])

            try:
                data = urlopen(file_url).read()
                if data:
                    filepath.write_bytes(data)
                    print("Saved:", filename)
            except Exception as e:
                print("Failed:", filename, e)

    print("\n✅ All tabs processed in " + case_name)
    
print("\n✅ All cases processed.")
