import os
from PySide6.QtWidgets import QMessageBox, QFileDialog
import importer

def show_import_summary(parent, missing_names, failed_racks, failed_miners, default_filename="missing_items.txt"):
    """
    Constructs a unified summary dialog and handles the export logic.
    Ensures all items are strings before joining to avoid TypeErrors.
    """
    # Safeguard: Convert all items to strings to prevent join() crashes
    missing_names = [str(x) for x in missing_names]
    failed_racks = [str(x) for x in failed_racks]
    failed_miners = [str(x) for x in failed_miners]

    report_text = []
    
    # 1. Build Informative HTML Text
    if missing_names:
        report_text.append(f"<b>Missing Database Items ({len(missing_names)}):</b><br/>" + 
                           ", ".join(missing_names[:10]) + ("..." if len(missing_names) > 10 else ""))
    if failed_racks:
        report_text.append(f"<b>Room Capacity Failures ({len(failed_racks)}):</b><br/>" + 
                           ", ".join(failed_racks[:10]) + ("..." if len(failed_racks) > 10 else ""))
    if failed_miners:
        report_text.append(f"<b>Rack Capacity Failures ({len(failed_miners)}):</b><br/>" + 
                           ", ".join(failed_miners[:10]) + ("..." if len(failed_miners) > 10 else ""))

    if not report_text:
        return # Nothing to report

    # 2. Build Detailed Text
    detailed_lines = []
    if missing_names:
        detailed_lines.append("MISSING FROM DATABASE:\n" + "\n".join(missing_names))
    if failed_racks:
        detailed_lines.append("ROOM FULL (Racks skipped):\n" + "\n".join(failed_racks))
    if failed_miners:
        detailed_lines.append("RACK FULL (Miners skipped):\n" + "\n".join(failed_miners))
    
    # 3. Construct Dialog
    msg = QMessageBox(parent)
    msg.setWindowTitle("Import Summary")
    msg.setText("Some items could not be processed during import.")
    msg.setInformativeText("<br/><br/>".join(report_text))
    msg.setDetailedText("\n\n".join(detailed_lines))
    
    ok_btn = msg.addButton(QMessageBox.StandardButton.Ok)
    export_btn = None
    
    # Add export button only if there are database mismatches
    if missing_names:
        export_btn = msg.addButton("Export Missing List", QMessageBox.ButtonRole.ActionRole)

    msg.exec()

    # 4. Handle Export Action
    if export_btn and msg.clickedButton() == export_btn:
        path, _ = QFileDialog.getSaveFileName(
            parent, 
            "Save Missing Items", 
            default_filename, 
            "Text Files (*.txt)"
        )
        if path:
            importer.export_missing_items_report(missing_names, path)