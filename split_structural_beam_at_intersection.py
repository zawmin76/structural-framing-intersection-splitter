import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')
clr.AddReference('ProtoGeometry')
clr.AddReference("RevitNodes")
from Autodesk.Revit.DB import *
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager
from Autodesk.DesignScript.Geometry import Point, Geometry
import Revit
clr.ImportExtensions(Revit.Elements)
clr.ImportExtensions(Revit.GeometryConversion)

report = []

def log(message):
    report.append(message)

def get_curve(beam):
    try:
        return beam.Location.Curve
    except:
        return None

def find_real_intersections(curve1, curve2, beam_id_1=None, beam_id_2=None, tolerance=300, z_tolerance=0, verbose=True):
    intersection_points = []
    try:
        start_pt = curve1.GetEndPoint(0).ToPoint()
        end_pt = curve1.GetEndPoint(1).ToPoint()
        start_z = start_pt.Z

        curve1_proto = curve1.ToProtoType()
        curve2_proto = curve2.ToProtoType()

        curve1_start = curve1.GetEndPoint(0).ToPoint()
        curve1_end = curve1.GetEndPoint(1).ToPoint()
        curve2_start = curve2.GetEndPoint(0).ToPoint()
        curve2_end = curve2.GetEndPoint(1).ToPoint()

        if verbose:
            log("  Beam {} curve: ({}, {}, {}) to ({}, {}, {})".format(
                beam_id_1,
                round(curve1_start.X, 1), round(curve1_start.Y, 1), round(curve1_start.Z, 1),
                round(curve1_end.X, 1), round(curve1_end.Y, 1), round(curve1_end.Z, 1)))
            log("  Beam {} curve: ({}, {}, {}) to ({}, {}, {})".format(
                beam_id_2,
                round(curve2_start.X, 1), round(curve2_start.Y, 1), round(curve2_start.Z, 1),
                round(curve2_end.X, 1), round(curve2_end.Y, 1), round(curve2_end.Z, 1)))

        raw_intersections = Geometry.Intersect(curve1_proto, curve2_proto)

        points = []
        if raw_intersections is None:
            if verbose:
                log("Beam {} to {}: No raw intersections found (None)".format(beam_id_1, beam_id_2))
            return intersection_points
        elif isinstance(raw_intersections, Point):
            points = [raw_intersections]
            if verbose:
                log("Beam {} to {}: Found 1 raw intersection point".format(beam_id_1, beam_id_2))
        elif hasattr(raw_intersections, '__iter__'):
            points = [item for item in raw_intersections if isinstance(item, Point)]
            if verbose:
                log("Beam {} to {}: Found {} raw intersection points".format(beam_id_1, beam_id_2, len(points)))
        else:
            if verbose:
                log("Beam {} to {}: Raw intersections type not recognized".format(beam_id_1, beam_id_2))
            return intersection_points

        curve2_start = curve2.GetEndPoint(0).ToPoint()
        curve2_end = curve2.GetEndPoint(1).ToPoint()

        for pt in points:
            xy_distance_to_curve1_start = Point.ByCoordinates(pt.X, pt.Y, 0).DistanceTo(Point.ByCoordinates(start_pt.X, start_pt.Y, 0))
            xy_distance_to_curve1_end = Point.ByCoordinates(pt.X, pt.Y, 0).DistanceTo(Point.ByCoordinates(end_pt.X, end_pt.Y, 0))
            xy_distance_to_curve2_start = Point.ByCoordinates(pt.X, pt.Y, 0).DistanceTo(Point.ByCoordinates(curve2_start.X, curve2_start.Y, 0))
            xy_distance_to_curve2_end = Point.ByCoordinates(pt.X, pt.Y, 0).DistanceTo(Point.ByCoordinates(curve2_end.X, curve2_end.Y, 0))

            if verbose:
                log("  Point ({}, {}, {}): dist_to_curve1_start={}, dist_to_curve1_end={}, dist_to_curve2_start={}, dist_to_curve2_end={}".format(
                    round(pt.X, 2), round(pt.Y, 2), round(pt.Z, 2),
                    round(xy_distance_to_curve1_start, 2), round(xy_distance_to_curve1_end, 2),
                    round(xy_distance_to_curve2_start, 2), round(xy_distance_to_curve2_end, 2)))

            curve1_endpoint_close = (xy_distance_to_curve1_start < tolerance or xy_distance_to_curve1_end < tolerance)
            curve2_endpoint_close = (xy_distance_to_curve2_start < tolerance or xy_distance_to_curve2_end < tolerance)

            if verbose:
                log("    Curve1 endpoint close: {}, Curve2 endpoint close: {}".format(curve1_endpoint_close, curve2_endpoint_close))

            if curve1_endpoint_close and curve2_endpoint_close:
                if verbose:
                    log("    REJECTED (point close to endpoints of both curves)")
            else:
                if z_tolerance > 0:
                    z_diff = abs(pt.Z - start_z)
                    if verbose:
                        log("    Z check: z_diff={}, z_tolerance={}".format(round(z_diff, 2), z_tolerance))
                    if z_diff <= z_tolerance:
                        intersection_points.append(pt)
                        if verbose:
                            log("    ACCEPTED (in middle of at least one curve, Z within tolerance)")
                    else:
                        if verbose:
                            log("    REJECTED (Z out of tolerance)")
                else:
                    intersection_points.append(pt)
                    if verbose:
                        log("    ACCEPTED (in middle of at least one curve, no Z tolerance check)")

        if verbose and len(intersection_points) > 0:
            log("Beam {} to {}: Found {} valid intersections".format(beam_id_1, beam_id_2, len(intersection_points)))

    except Exception as e:
        log("Error checking Beam {} to {}: {}".format(beam_id_1, beam_id_2, str(e)))

    return intersection_points

# Initialize
doc = DocumentManager.Instance.CurrentDBDocument
uidoc = DocumentManager.Instance.CurrentUIDocument
view = uidoc.ActiveView

tolerance = IN[2] if len(IN) > 2 else 300
z_tolerance = IN[3] if len(IN) > 3 else 0
split_enabled = bool(IN[1]) if len(IN) > 1 else False

log("Active view: {}".format(view.Name))
log("Tolerance: {}".format(tolerance))
log("Z tolerance: {}".format(z_tolerance))

# Collect structural framing elements
collector = FilteredElementCollector(doc, view.Id)
struct_framing_filter = ElementCategoryFilter(BuiltInCategory.OST_StructuralFraming)
beams = collector.WherePasses(struct_framing_filter).WhereElementIsNotElementType().ToElements()

log("Total beams found: {}".format(len(beams)))
log("Split enabled: {}".format(split_enabled))

# Extract curves
curves = []
beam_curve_map = []
for b in beams:
    if b.Location and hasattr(b.Location, 'Curve'):
        curve = get_curve(b)
        if curve:
            curves.append(curve)
            beam_curve_map.append(b)

log("Total curves extracted: {}".format(len(curves)))

# Find all intersections
beam_intersections = {}
for i in range(len(beam_curve_map)):
    beam_intersections[i] = []

if not split_enabled:
    log("Checking for intersections between {} curves".format(len(curves)))

checked_pairs = set()
pair_count = 0
for i in range(len(curves)):
    for j in range(len(curves)):
        if i != j:
            pair_key = tuple(sorted([i, j]))
            if pair_key not in checked_pairs:
                checked_pairs.add(pair_key)
                pair_count += 1
                beam_id_i = beam_curve_map[i].Id if i < len(beam_curve_map) else None
                beam_id_j = beam_curve_map[j].Id if j < len(beam_curve_map) else None
                intersections = find_real_intersections(curves[i], curves[j], beam_id_i, beam_id_j, tolerance, z_tolerance, verbose=not split_enabled)
                if intersections:
                    if i not in beam_intersections:
                        beam_intersections[i] = []
                    if j not in beam_intersections:
                        beam_intersections[j] = []

                    for pt in intersections:
                        try:
                            xyz_pt = pt.ToXyz()
                        except:
                            xyz_pt = pt

                        # Verify point validity on beam i
                        try:
                            proj_i = curves[i].Project(xyz_pt)
                            if proj_i is not None:
                                start_i = curves[i].GetEndParameter(0)
                                end_i = curves[i].GetEndParameter(1)
                                norm_i = (proj_i.Parameter - start_i) / (end_i - start_i)
                                if 0.0001 < norm_i < 0.9999:
                                    beam_intersections[i].append(pt)
                        except:
                            pass

                        # Verify point validity on beam j
                        try:
                            proj_j = curves[j].Project(xyz_pt)
                            if proj_j is not None:
                                start_j = curves[j].GetEndParameter(0)
                                end_j = curves[j].GetEndParameter(1)
                                norm_j = (proj_j.Parameter - start_j) / (end_j - start_j)
                                if 0.0001 < norm_j < 0.9999:
                                    beam_intersections[j].append(pt)
                        except:
                            pass

# Log summary
total_intersections = sum(len(pts) for pts in beam_intersections.values())
if split_enabled:
    log("Total intersections found (for split): {}".format(total_intersections))
else:
    log("Total intersections found: {}".format(total_intersections))
    log("Total unique pairs checked: {}".format(pair_count))

# Detection mode: output intersections with curve for preview
if not split_enabled:
    beam_intersection_pairs = []
    for beam_idx in range(len(beam_curve_map)):
        beam = beam_curve_map[beam_idx]
        beam_id = beam.Id
        intersections = beam_intersections.get(beam_idx, [])

        # Get dynamo curve for preview
        dynamo_curve = None
        if beam_idx < len(curves):
            curve = curves[beam_idx]
            dynamo_curve = curve.ToProtoType()

        if intersections:
            beam_intersection_pairs.append([beam, beam_id, dynamo_curve, intersections])
            log("Beam {}: {} intersections found".format(beam_id, len(intersections)))
        else:
            beam_intersection_pairs.append([beam, beam_id, dynamo_curve, []])

    OUT = [beam_intersection_pairs, report]

# Split mode: split beams at intersections
else:
    log("Starting beam splitting analysis...")
    log("Total beams to process: {}".format(len(beam_curve_map)))

    beams_with_intersections = sum(1 for pts in beam_intersections.values() if len(pts) > 0)
    log("Total beams with intersection points: {}".format(beams_with_intersections))

    split_data = []

    for beam_idx, beam in enumerate(beam_curve_map):
        if beam_idx < len(curves):
            curve = curves[beam_idx]
            beam_id = beam.Id
            split_pts = beam_intersections.get(beam_idx, [])

            if len(split_pts) > 0:
                log("Beam {}: Has {} intersection points for split".format(beam_id, len(split_pts)))

                split_params = []
                for pt_idx, pt in enumerate(split_pts):
                    try:
                        pt_type = type(pt).__name__
                        if pt_idx == 0:
                            log("  Point type in beam_intersections: {}".format(pt_type))

                        try:
                            xyz_pt = pt.ToXyz()
                        except:
                            xyz_pt = pt

                        proj = curve.Project(xyz_pt)
                        if proj is not None:
                            start_param = curve.GetEndParameter(0)
                            end_param = curve.GetEndParameter(1)
                            param = proj.Parameter
                            normalized_param = (param - start_param) / (end_param - start_param)

                            log("  Point ({}, {}, {}): raw_param={}, normalized={}, start={}, end={}".format(
                                round(pt.X, 1), round(pt.Y, 1), round(pt.Z, 1),
                                round(param, 2), round(normalized_param, 4), round(start_param, 2), round(end_param, 2)))

                            tolerance_buffer = 0.0001
                            if tolerance_buffer < normalized_param < (1.0 - tolerance_buffer):
                                split_params.append(normalized_param)
                                log("    -> ACCEPTED (param in range 0-1)")
                            else:
                                log("    -> REJECTED (param={}, outside valid range)".format(round(normalized_param, 4)))
                        else:
                            log("  WARNING: Could not project point ({}, {}, {}) onto beam {}".format(
                                round(pt.X, 1), round(pt.Y, 1), round(pt.Z, 1), beam_id))
                    except Exception as e:
                        log("  ERROR: Exception projecting point onto beam {}: {}".format(beam_id, str(e)))

                if len(split_params) > 0:
                    split_params = sorted(split_params)
                    log("Beam {}: {} split points".format(beam_id, len(split_params)))
                    split_data.append([beam, beam_id, split_params])

    log("Total beams with split points: {}".format(len(split_data)))

    TransactionManager.Instance.EnsureInTransaction(doc)

    split_results = []
    beams_split = 0

    for beam, beam_id, split_params in split_data:
        # Prepare output
        current_beam = doc.GetElement(beam_id)
        dynamo_curve = None
        if current_beam is not None and current_beam.Location and hasattr(current_beam.Location, 'Curve'):
            beam_curve = current_beam.Location.Curve
            dynamo_curve = beam_curve.ToProtoType()

        beam_idx = beam_curve_map.index(beam) if beam in beam_curve_map else -1
        raw_points = beam_intersections.get(beam_idx, []) if beam_idx >= 0 else []

        # Remove duplicates
        unique_points = []
        seen_coords = set()
        for pt in raw_points:
            pt_key = (round(pt.X, 2), round(pt.Y, 2), round(pt.Z, 2)) if hasattr(pt, 'X') else None
            if pt_key and pt_key not in seen_coords:
                unique_points.append(pt)
                seen_coords.add(pt_key)

        split_results.append([dynamo_curve, unique_points, beam_id])
        log("Output: Beam {} -> curve (Dynamo), {} unique intersection points (was {})".format(
            beam_id, len(unique_points), len(raw_points)))

        # Perform splits with dynamic beam tracking
        sorted_pts_reverse = sorted(unique_points, key=lambda pt: pt.X if hasattr(pt, 'X') else 0, reverse=True)
        current_beams = [beam.Id]

        for int_point in sorted_pts_reverse:
            try:
                try:
                    xyz_pt = int_point.ToXyz()
                except:
                    xyz_pt = int_point

                target_beam_id = None
                normalized_param = None

                for candidate_beam_id in current_beams:
                    candidate_beam = doc.GetElement(candidate_beam_id)
                    if candidate_beam is not None:
                        candidate_curve = candidate_beam.Location.Curve

                        pt_x = int_point.X if hasattr(int_point, 'X') else 0
                        pt_y = int_point.Y if hasattr(int_point, 'Y') else 0
                        pt_z = int_point.Z if hasattr(int_point, 'Z') else 0

                        proj = candidate_curve.Project(xyz_pt)

                        if proj is not None:
                            start_param = candidate_curve.GetEndParameter(0)
                            end_param = candidate_curve.GetEndParameter(1)
                            param = proj.Parameter
                            norm_param = (param - start_param) / (end_param - start_param)

                            if 0.0001 < norm_param < 0.9999:
                                target_beam_id = candidate_beam_id
                                normalized_param = norm_param
                                log("  Point ({}, {}, {}) -> belongs to beam {} (param={})".format(
                                    round(pt_x, 1), round(pt_y, 1), round(pt_z, 1),
                                    candidate_beam_id, round(norm_param, 6)))
                                break
                            else:
                                log("  Point ({}, {}, {}) on beam {} param={} (outside range)".format(
                                    round(pt_x, 1), round(pt_y, 1), round(pt_z, 1),
                                    candidate_beam_id, round(norm_param, 6)))
                        else:
                            log("  Point ({}, {}, {}) - projection on beam {} returned None".format(
                                round(pt_x, 1), round(pt_y, 1), round(pt_z, 1), candidate_beam_id))

                if target_beam_id is not None and normalized_param is not None:
                    try:
                        beam_to_split = doc.GetElement(target_beam_id)
                        if beam_to_split is not None:
                            new_beam_id = beam_to_split.Split(normalized_param)
                            beams_split += 1
                            log("  SPLIT: Beam {} at param {} -> new beam {}".format(
                                target_beam_id, round(normalized_param, 6), new_beam_id))
                            current_beams.append(new_beam_id)
                    except Exception as e:
                        log("  ERROR splitting beam {} at param {}: {}".format(target_beam_id, round(normalized_param, 6), str(e)))
                else:
                    log("  Point ({}, {}, {}) -> NOT found on any current beam segment".format(
                        round(int_point.X, 1) if hasattr(int_point, 'X') else 0,
                        round(int_point.Y, 1) if hasattr(int_point, 'Y') else 0,
                        round(int_point.Z, 1) if hasattr(int_point, 'Z') else 0))

            except Exception as e:
                log("  ERROR processing intersection point: {}".format(str(e)))

    log("Total output entries: {}".format(len(split_results)))
    log("Total beams split: {}".format(beams_split))

    TransactionManager.Instance.TransactionTaskDone()

    OUT = [split_results, report]
