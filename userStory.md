PageOneRelativityLoadFileTools: Technical Specification & Build Guide
1. Project Overview
PageOneRelativityLoadFileTools is a standalone Windows utility designed for e-discovery professionals. It provides rapid schema analysis, SQL field type estimation, and header remapping for large .csv and .dat (Concordance-style) load files.
________________________________________
2. userStory.md
As an E-Discovery Project Manager
I want a portable, high-performance GUI utility to analyze and manipulate large load files
So that I can identify data types, validate field lengths, and remap headers to Relativity standards without risking memory crashes or UI freezing.
Acceptance Criteria
•	Intelligent Detection: Auto-detects delimiters based on extension (.csv vs .dat).
•	Encoding Awareness: Detects and handles UTF-8, ANSI, and UTF-16 to prevent character corruption.
PageOneRelativityLoadFileTools	Schema Analysis: Identifies field names, estimates SQL types, and finds the longest string per column.
•	Header Mapping: Swaps original headers with values from a cross-reference CSV.
•	Asynchronous UI: Utilizes threading to ensure the Flet window remains responsive during large file I/O.
•	Portability: Compiles to a single-file .exe for use on forensics workstations.
________________________________________
3. Required Libraries & Dependencies
Install these via pip before beginning development:
Library	Version	Purpose
flet	Latest	GUI Framework (Flutter-based).
polars	Latest	High-speed data processing engine.
chardet	Latest	Automatic file encoding detection.
pyinstaller	Latest	Required by Flet to build the .exe.
________________________________________
4. Technical Constants
For e-discovery standard .dat files, use these ASCII character codes:
•	Column Delimiter (Thorn): chr(20) (¶)
•	Text Qualifier (Quote): chr(254) (þ)
________________________________________
5. Implementation Details
A. SQL Type Estimation Logic
When scanning columns, the application should follow this priority ladder:
1.	Integer: Check if all non-null values consist only of digits.
2.	Decimal: Check if values contain digits and exactly one period.
3.	Date/Time: Attempt to parse using common patterns (e.g., YYYY-MM-DD or MM/DD/YYYY).
4.	Varchar(Max): Default for any column containing alphabetic characters or symbols.
B. Longest String Display
•	Calculate max() of string length for every column.
•	In the UI Table, if len(value) > 250, display value[:250] + "...".
C. File Encoding Logic
Python
import chardet

def get_encoding(file_path):
    with open(file_path, 'rb') as f:
        # Read first 10k bytes to guess encoding
        raw_data = f.read(10000)
        return chardet.detect(raw_data)['encoding']
________________________________________
6. Project Structure
Plaintext
/PageOneRelativityLoadFileTools
¦
+-- main.py              # Main Flet application and UI logic
+-- processor.py         # Polars logic for analysis and header swapping
+-- userStory.md         # The project requirements
+-- assets/              # Icons or logos for the EXE
________________________________________
7. Build & Packaging Instructions
To create the standalone executable, run the following command from your terminal within the project directory:
Bash
flet pack main.py --name "PageOneRelativityLoadFileTools" --icon assets/icon.ico --noconsole --onefile
Build Flags Explained:
•	--name: Sets the name of the generated .exe.
•	--icon: Paths to your custom app icon.
•	--noconsole: Prevents a CMD window from opening behind the UI.
•	--onefile: Bundles everything (Python, libraries, assets) into a single executable.
________________________________________
8. Suggested UI Layout (Flet)
1.	Header: Title and "Open File" button.
2.	Configuration Bar: Dropdowns for Encoding and Delimiters (auto-filled but editable).
3.	Main View: A DataTable or ListView showing:
o	Column Name
o	Estimated Type
o	Max Length
o	Longest Value Example
4.	Footer: "Load Cross-Ref" button and "Export Final Load File" button.

