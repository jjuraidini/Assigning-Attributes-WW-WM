import arcpy
import os

# -------------------------------------------------------------------
# INPUTS
# -------------------------------------------------------------------
gdb = r"C:\Users\jjuraidini\Documents\ArcGIS\Projects\Assigning-Attributes-WW-WM\Assigning-Attributes-WW-WM.gdb"
fc = fr"{gdb}\SanitarySewerLines_ExportFeatures"
ASB_FIELD = "ASB_DATE"
SEARCH_RADIUS_FEET = 2     # distance to consider endpoints connected
MAX_ITERATIONS = 10        # max recursive passes

arcpy.env.workspace = gdb
arcpy.env.overwriteOutput = True

# -------------------------------------------------------------------
# FUNCTION: get ASB_DATE from nearest connected endpoint
# -------------------------------------------------------------------
def recursive_asb_assignment_near(fc):
    iteration = 0
    total_updated = 0

    print(f"\nProcessing: {fc}")

    while iteration < MAX_ITERATIONS:
        iteration += 1
        updated = 0

        # Make layers for missing and populated ASB_DATE
        missing_lyr = f"missing_asb_lyr_{iteration}"
        source_lyr = f"source_asb_lyr_{iteration}"

        arcpy.MakeFeatureLayer_management(fc, missing_lyr, f"{ASB_FIELD} IS NULL")
        arcpy.MakeFeatureLayer_management(fc, source_lyr, f"{ASB_FIELD} IS NOT NULL")

        missing_count = int(arcpy.GetCount_management(missing_lyr)[0])
        source_count = int(arcpy.GetCount_management(source_lyr)[0])

        if missing_count == 0 or source_count == 0:
            print(f"  Iteration {iteration}: No features to process (Missing: {missing_count}, Source: {source_count})")
            break

        # Convert lines to endpoints
        missing_pts = os.path.join(gdb, f"temp_missing_pts_{iteration}")
        source_pts = os.path.join(gdb, f"temp_source_pts_{iteration}")

        # Delete if they already exist
        for fc_temp in [missing_pts, source_pts]:
            if arcpy.Exists(fc_temp):
                arcpy.Delete_management(fc_temp)

        arcpy.management.FeatureVerticesToPoints(missing_lyr, missing_pts, "BOTH_ENDS")
        arcpy.management.FeatureVerticesToPoints(source_lyr, source_pts, "BOTH_ENDS")

        # Run Near to find nearest source point for each missing point
        arcpy.analysis.Near(missing_pts, source_pts, search_radius=f"{SEARCH_RADIUS_FEET} Feet", location="NO_LOCATION", angle="NO_ANGLE")

        # Build lookup: OBJECTID of missing line -> ASB_DATE from nearest source line
        # First map missing point to its parent line OBJECTID
        missing_point_to_line = {}
        with arcpy.da.SearchCursor(missing_pts, ["ORIG_FID", "OBJECTID", "NEAR_FID"]) as scur:
            for orig_fid, point_oid, near_fid in scur:
                if near_fid != -1:
                    missing_point_to_line[orig_fid] = near_fid  # map missing line to nearest source point

        # Get ASB_DATE from source line
        asb_lookup = {}
        if missing_point_to_line:
            source_fids = set(missing_point_to_line.values())
            with arcpy.da.SearchCursor(fc, ["OBJECTID", ASB_FIELD]) as scur:
                for oid, asb_date in scur:
                    if oid in source_fids and asb_date:
                        asb_lookup[oid] = asb_date

        # Update missing lines
        with arcpy.da.UpdateCursor(fc, ["OBJECTID", ASB_FIELD]) as ucur:
            for oid, asb_date in ucur:
                if asb_date is None and oid in missing_point_to_line:
                    source_oid = missing_point_to_line[oid]
                    if source_oid in asb_lookup:
                        ucur.updateRow([oid, asb_lookup[source_oid]])
                        updated += 1

        total_updated += updated
        skipped = missing_count - updated
        print(f"Iteration {iteration}: Missing ASB_DATE count: {missing_count} | Updated: {updated} | Skipped: {skipped}")

        # Cleanup temp feature classes
        for fc_temp in [missing_lyr, source_lyr, missing_pts, source_pts]:
            if arcpy.Exists(fc_temp):
                arcpy.Delete_management(fc_temp)

        # Stop if no updates in this iteration
        if updated == 0:
            break

    print(f"\nTotal updated features: {total_updated}")
    print("ASB_DATE recursive assignment complete.")

# -------------------------------------------------------------------
# RUN
# -------------------------------------------------------------------
recursive_asb_assignment_near(fc)
