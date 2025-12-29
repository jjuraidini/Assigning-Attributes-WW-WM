import arcpy
import os

# -------------------------------------------------------------------
# INPUTS
# -------------------------------------------------------------------
gdb = r"C:\Users\jjuraidini\Documents\ArcGIS\Projects\Assigning-Attributes-WW-WM\Assigning-Attributes-WW-WM.gdb"
fc = fr"{gdb}\SanitarySewerLines_ExportFeatures"
ASB_FIELD = "ASB_DATE"
EST_FIELD = "Estimated_ASB"
SEARCH_RADIUS_FEET = 2
MAX_ITERATIONS = 10

arcpy.env.workspace = gdb
arcpy.env.overwriteOutput = True

# Add Estimated_ASB field if it doesn't exist
if EST_FIELD not in [f.name for f in arcpy.ListFields(fc)]:
    arcpy.AddField_management(fc, EST_FIELD, "TEXT", field_length=1)

# -------------------------------------------------------------------
# FUNCTION: recursive ASB_DATE assignment with logging and flag
# -------------------------------------------------------------------
def recursive_asb_assignment_flag(fc):
    iteration = 0
    total_updated = 0

    print(f"\nProcessing: {fc}")

    while iteration < MAX_ITERATIONS:
        iteration += 1
        updated = 0

        missing_lyr = f"missing_asb_lyr_{iteration}"
        source_lyr = f"source_asb_lyr_{iteration}"

        arcpy.MakeFeatureLayer_management(fc, missing_lyr, f"{ASB_FIELD} IS NULL")
        arcpy.MakeFeatureLayer_management(fc, source_lyr, f"{ASB_FIELD} IS NOT NULL")

        missing_count = int(arcpy.GetCount_management(missing_lyr)[0])
        source_count = int(arcpy.GetCount_management(source_lyr)[0])

        if missing_count == 0 or source_count == 0:
            print(f"  Iteration {iteration}: No features to process (Missing: {missing_count}, Source: {source_count})")
            break

        # Convert to endpoints
        missing_pts = os.path.join(gdb, f"temp_missing_pts_{iteration}")
        source_pts = os.path.join(gdb, f"temp_source_pts_{iteration}")

        for fc_temp in [missing_pts, source_pts]:
            if arcpy.Exists(fc_temp):
                arcpy.Delete_management(fc_temp)

        arcpy.management.FeatureVerticesToPoints(missing_lyr, missing_pts, "BOTH_ENDS")
        arcpy.management.FeatureVerticesToPoints(source_lyr, source_pts, "BOTH_ENDS")

        # Near analysis
        arcpy.analysis.Near(missing_pts, source_pts, search_radius=f"{SEARCH_RADIUS_FEET} Feet")

        # Build lookup: missing line OBJECTID -> ASB_DATE
        missing_point_to_line = {}
        with arcpy.da.SearchCursor(missing_pts, ["ORIG_FID", "NEAR_FID"]) as scur:
            for orig_fid, near_fid in scur:
                if near_fid != -1:
                    missing_point_to_line[orig_fid] = near_fid

        asb_lookup = {}
        if missing_point_to_line:
            source_fids = set(missing_point_to_line.values())
            with arcpy.da.SearchCursor(fc, ["OBJECTID", ASB_FIELD]) as scur:
                for oid, asb_date in scur:
                    if oid in source_fids and asb_date:
                        asb_lookup[oid] = asb_date

        # Update missing lines and flag
        with arcpy.da.UpdateCursor(fc, ["OBJECTID", ASB_FIELD, EST_FIELD]) as ucur:
            for oid, asb_date, est_flag in ucur:
                if asb_date is None and oid in missing_point_to_line:
                    source_oid = missing_point_to_line[oid]
                    if source_oid in asb_lookup:
                        ucur.updateRow([oid, asb_lookup[source_oid], "Y"])
                        updated += 1

        total_updated += updated
        skipped = missing_count - updated
        print(f"Iteration {iteration}: Missing ASB_DATE count: {missing_count} | Updated: {updated} | Skipped: {skipped}")

        # Cleanup
        for fc_temp in [missing_lyr, source_lyr, missing_pts, source_pts]:
            if arcpy.Exists(fc_temp):
                arcpy.Delete_management(fc_temp)

        if updated == 0:
            break

    print(f"\nTotal updated features: {total_updated}")
    print("ASB_DATE recursive assignment complete.")

# -------------------------------------------------------------------
# RUN
# -------------------------------------------------------------------
recursive_asb_assignment_flag(fc)
