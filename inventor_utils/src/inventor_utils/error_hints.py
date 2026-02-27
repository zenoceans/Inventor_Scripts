"""Common error-hint lookup for structured tool log files."""

from __future__ import annotations


def error_hint(error_message: str) -> str:
    """Return a user-friendly hint for a known error pattern, or '' if unrecognised."""
    msg = error_message.lower()

    if "no revision table" in msg:
        return "The drawing template does not contain a revision table. Add a revision table to the template in Inventor."

    if "failed to open document" in msg or "could not open" in msg:
        return "Check that the file exists, is not open in another program, and is not checked out in Vault by another user."

    if "no idw file found" in msg or ("idw" in msg and "not found" in msg):
        return "DWG/PDF export requires an IDW drawing file with the same name as the part/assembly, in the same folder."

    if "no drawing template" in msg or "template" in msg:
        return "Configure a drawing template (.idw) in the tool settings."

    if "translator" in msg:
        return "The required Inventor translator add-in could not be found. Check that Inventor is installed correctly."

    if "not found in memory" in msg or "document not found" in msg:
        return "The document may have been closed or moved between scan and export. Try scanning again."

    if "simplif" in msg:
        return "The Simplify feature failed. Verify Inventor 2026 is running and Simplify is available for this document type."

    if "file not found" in msg or "not found" in msg:
        return "Check that the STEP file exists and the path is correct."

    if "save" in msg or "write" in msg:
        return "Check the output folder exists and you have write permissions."

    if "com error" in msg or "com_error" in msg or "rpc" in msg:
        return "COM communication error. Ensure Inventor is responsive and not showing a dialog."

    return ""
