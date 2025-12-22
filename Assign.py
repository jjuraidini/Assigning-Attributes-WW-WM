import arcpy

# -------------------------------------------------------------------
# FEATURE CLASS PATHS
# -------------------------------------------------------------------
layers = [
    r"C:\Users\jjuraidini\Documents\ArcGIS\Projects\missing attributes"
    r"\missing attributes.gdb\WaterLines_ExportFeatures",

    r"C:\Users\jjuraidini\Documents\ArcGIS\Projects\missing attributes"
    r"\missing attributes.gdb\SanitarySewerLines_ExportFeatures"
]

asb_field = "ASB_DATE"

arcpy.env.overwriteOutput = True

# -------------------------------------------------------------------
# FUNCTION
# -------------------------------------------------------------------
def fill_asb_date_by_endpoint(fc):
    print(f"\nProcessing: {fc}")

    # Feature layers
    missing_lyr = "missing_asb_lyr"
    source_lyr = "source_asb_lyr"

    arcpy.MakeFeatureLayer_management(
        fc, missing_lyr, f"{asb_field} IS NULL"
    )

    arcpy.MakeFeatureLayer_management(
        fc, source_lyr, f"{asb_field} IS NOT NULL"
    )

    if int(arcpy.GetCount_management(missing_lyr)[0]) == 0:
        print("No missing ASB_DATE values found.")
        return

    # -------------------------------------------------------------------
    # Create endpoints for both groups
    # -------------------------------------------------------------------
    missing_pts = "in_memory\\missing_pts"
    source_pts = "in_memory\\source_pts"

    arcpy.management.FeatureVerticesToPoints(
        missing_lyr, missing_pts, "BOTH_ENDS"
    )

    arcpy.management.FeatureVerticesToPoints(
        source_lyr, source_pts, "BOTH_ENDS"
    )

    # Spatial join: match touching endpoints
    sj_output = "in_memory\\endpoint_join"

    arcpy.analysis.SpatialJoin(
        target_features=missing_pts,
        join_features=source_pts,
        out_feature_class=sj_output,
        join_operation="JOIN_ONE_TO_ONE",
        match_option="INTERSECT"
    )

    # Build lookup: missing line OID → ASB_DATE
    asb_lookup = {}

    with arcpy.da.SearchCursor(
        sj_output,
        ["ORIG_FID", "ASB_DATE"]
    ) as scur:
        for missing_oid, asb_date in scur:
            if asb_date:
                asb_lookup[missing_oid] = asb_date

    # -------------------------------------------------------------------
    # Update missing ASB_DATE
    # -------------------------------------------------------------------
    updated = 0
    with arcpy.da.UpdateCursor(
        missing_lyr, ["OBJECTID", asb_field]
    ) as ucur:
        for oid, asb_date in ucur:
            if oid in asb_lookup:
                ucur.updateRow([oid, asb_lookup[oid]])
                updated += 1

    print(f"Updated {updated} segmented pipe records.")

    # Cleanup
    arcpy.Delete_management(missing_lyr)
    arcpy.Delete_management(source_lyr)
    arcpy.Delete_management("in_memory")

# -------------------------------------------------------------------
# RUN
# -------------------------------------------------------------------
for fc in layers:
    fill_asb_date_by_endpoint(fc)

print("\nASB_DATE endpoint-based fill completed.")
