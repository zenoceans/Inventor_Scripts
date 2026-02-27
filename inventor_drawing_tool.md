
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
