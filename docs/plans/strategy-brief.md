# Strategy Brief: Inventor Workflow Automation

## Problem Statement

Two mechanical engineers spend significant time on repetitive, low-judgment data entry when creating assemblies and releasing documentation in Autodesk Inventor. The friction of copy-pasting between vendor websites, an internal parts database (Excel, moving to Grist), and Inventor's iProperties causes data quality to degrade over time — fields get skipped, descriptions get sloppy, and the database drifts. During drawing releases of 10-100 drawings, typing identical revision data into each one destroys engineering flow state.

## Target User

Mechanical engineers (currently 2, growing) working in Autodesk Inventor, creating assemblies with 10-20 new components and releasing documentation packages every few weeks. Comfortable running .exe tools with standard GUIs.

## Jobs to be Done

- **Functional**: Add new components to assemblies and release documentation packages without repetitive manual data entry
- **Emotional**: Stay in engineering flow — focus on design decisions, not copy-paste chores
- **Social**: Maintain a reliable, complete parts database that the growing team can trust

## Vision

Eliminate repetitive data entry between vendor sites, the parts database, and Inventor so engineers spend their time on engineering, not copy-pasting.

## Key Differentiators

1. Pulls component data directly from vendor APIs — no manual copy-paste
2. Engineer reviews and approves all data in a table before committing — stays in control
3. Batch operations for drawing setup and revision entry — handles 100 drawings as easily as 1

## Success Metrics

- **Primary**: Non-engineering data entry time per release cycle drops from ~1-2 hours to under 10 minutes
- **Secondary**: Database completeness — percentage of parts with all fields filled (MPN, description, weight, link) stays above 95%
- **Usage tracking**: Built-in tracking of how many drawings/parts are processed and how often each tool is used. If usage drops, the tool isn't solving the problem well enough.
- **Kill metric**: If the tool goes unused for multiple release cycles, stop investing and investigate why

## Assumptions to Validate

- Inventor COM API can reliably create drawings, insert views, and write revision table data in batch
- RS Components, Digikey, and Phoenix Contact have accessible APIs for component data (weight, description, links)
- MPN from downloaded STEP filename is reliable enough as an API lookup key
- Drawing template handles ISO formatting of dimensions (decimals, hole crosses) so the script doesn't need to
- Grist database is set up and accessible via API when the component import tool is built

## Open Questions

- Which GUI framework bundles best as a Windows .exe (tkinter, PyQt, etc.)?
- How to handle vendors that don't have APIs — manual fallback in the GUI?
- Should usage tracking be local (log file) or stored in the Grist database?

---

## Goal 1: Batch Drawing Release Tool

### Problem It Solves

When releasing documentation, the engineer must open each drawing (10-100 per release), double-click the revision table, and type the same rev number, description, "made by," and approver into every single one. This is pure tedium with zero engineering judgment. It breaks flow state during what should be a focused documentation task. Additionally, creating drawings for parts that don't have them yet requires repetitive setup — inserting standard views, which is boilerplate.

### What It Does

1. Scans an assembly or folder for parts (ipt files) that don't have an associated drawing (idw/dwg)
2. Creates drawing files for those parts using the existing drawing template
3. Inserts standard views into each new drawing
4. For all drawings being released (new and existing): opens the revision table and writes:
   - Rev number (user enters once)
   - Rev description (user enters once)
   - Made by (user enters once)
   - Approved by (user enters once)
5. Presents a review table in the GUI showing all drawings and what will be written
6. Engineer approves, script executes in batch
7. Logs usage (number of drawings processed, date)

### Builds On

Existing import/export scripts already built by the team.

### Assumptions to Test

- Inventor COM API can write to revision table fields programmatically
- Standard views can be inserted via API using the drawing template's settings
- The drawing template already handles dimension formatting (ISO standards, decimal precision, hole crosses)

### Definition of Done

- Used successfully for one real release cycle
- Handles both new drawing creation and revision table entry
- Review table lets engineer change any field before committing
- Usage is logged

---

## Goal 2: Component Import from Vendors

### Problem It Solves

Adding 10-20 new components to an assembly requires the engineer to: find the component on vendor websites, check if it already exists in the internal database by MPN, copy MPN/description/link into the database, download the STEP file, import it into Inventor, copy the description into iProperties, look up weight in the datasheet and enter it, copy the MPN into iProperties. This tab-switching and copy-pasting is tedious and error-prone. Over time, engineers take shortcuts — skipping fields, writing bad descriptions — and the database quality degrades.

### What It Does

1. Engineer provides a list of MPNs (or selects downloaded STEP files whose filenames contain MPNs)
2. For each MPN, the script:
   - Checks the internal database (Grist) for duplicates
   - Queries vendor APIs (RS Components, Digikey, Phoenix Contact) for component data: description, weight, web link
   - Assigns the next available internal part number
   - Imports the STEP file into Inventor, simplifies it, saves as .ipt with internal part number as filename
   - Writes iProperties (description, weight, MPN)
   - Creates the entry in the Grist database
3. If the MPN is not found on any predefined vendor API, the GUI prompts the engineer to enter description and weight manually
4. Presents a review table showing all components and their data before committing
5. Engineer can edit any field in the table
6. On approval, script writes everything to Inventor and the database
7. Optionally copies the new .ipt files into a selected assembly
8. Logs usage (number of components processed, date, which vendors were used)

### Depends On

- Grist database being set up and accessible
- Vendor API access confirmed for RS Components, Digikey, Phoenix Contact

### Assumptions to Test

- RS Components, Digikey, and Phoenix Contact have public or partner APIs that return weight, description, and product links for a given MPN
- MPN extracted from STEP filenames is reliable enough for API lookups
- Inventor COM API can import STEP, simplify, save as ipt, and write iProperties programmatically
- Auto-incrementing part numbers from the Grist database is reliable with concurrent users

### Definition of Done

- Used successfully for one real assembly with 10+ new components
- At least one vendor API is integrated and returning correct data
- Review table allows editing before commit
- Database entries are complete (MPN, description, weight, link, internal part number)
- Usage is logged

---

## Goal 3: Unified Workflow GUI

### Problem It Solves

As more automation scripts are built (import, export, drawing release, component entry), having separate tools becomes its own friction. A unified GUI wrapping all tools gives the team one place to go, with consistent review tables, usage tracking visible in one dashboard, and the ability to extend with new vendor sources or workflows over time.

### What It Does

1. Single .exe application with tabs or sections for each tool:
   - Import/Export (existing)
   - Batch Drawing Release (Goal 1)
   - Component Import from Vendors (Goal 2)
2. Shared usage tracking dashboard showing:
   - How many drawings/parts processed per week/month
   - Which tools are used most
   - Which vendors are queried most
3. Shared settings:
   - Vendor API keys
   - Default approver, default rev description
   - Path to Grist database
   - Part number counter

### Depends On

- Goals 1 and 2 working as standalone tools first
- Understanding which GUI framework works best from building Goals 1 and 2

### Definition of Done

- All tools accessible from one application
- Usage dashboard shows meaningful data
- Team uses it as the default workflow tool for at least one full release cycle
