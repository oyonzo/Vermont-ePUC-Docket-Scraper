# Vermont PUC Case Downloader

## Requirements

*   Python 3.x  
    (Python included with Thonny is sufficient)
*   Internet access to `https://epuc.vermont.gov`

***

## Dependencies

This script uses **only Python’s standard library**.

No third‑party packages are required.  
No `pip` installations are needed.

***

## How to Run

1.  Run the script using Python or Thonny.

2.  When prompted, paste one or more case URLs, **one per line**, in this format:

        https://epuc.vermont.gov/?q=node/64/########

3.  Press **Enter on a blank line** to begin processing.

The script will process each case automatically.

***

## Where Files Are Saved

All files are saved to your **Downloads** folder.

For each case, the script creates:

*   A main folder named using the case docket number and case name
*   Subfolders for each available case tab
*   Downloaded documents stored in the appropriate tab folders
*   A saved HTML file for each tab for offline reference

***
