# Structural Framing Intersection Splitter for Revit Dynamo

This Python script is designed to work within Dynamo for Revit to automatically find structural framing elements in the active view, calculate their intersection points, and split the beams at those intersection points.

## Overview

The script processes structural framing elements (beams) in the active view of a Revit model. It identifies points where beams intersect and splits the beams at those points, creating new beam segments that maintain the original properties (type and level) of the parent beam.

## Features

- **Automatic Detection**: Finds all structural framing elements in the active view
- **Intersection Calculation**: Identifies intersection points between beams
- **Smart Splitting**: Splits beams at intersection points while respecting Revit's minimum curve tolerance
- **Property Preservation**: New beam segments maintain the original type and level properties
- **Tolerance Handling**: Properly handles Revit's minimum curve length requirements to prevent errors

## Requirements

- Revit 2023 (or compatible version)
- Dynamo for Revit
- Structural framing elements in the active view

## Usage

1. Open your Revit model and navigate to the view containing structural framing elements
2. Open Dynamo and create a new Python script node
3. Copy the contents of `split_structural_beam_at_intersection.py` into the Python node
4. Connect three inputs:
   - **IN[1]**: Boolean (False for detection, True for splitting)
   - **IN[2]**: Tolerance value (default 300)
   - **IN[3]**: Z tolerance value (default 0)
5. Connect the output to a viewer node to see results with curves and intersection points
6. Run the script in Dynamo

## How It Works

1. **Element Collection**: The script uses `FilteredElementCollector` to gather structural framing elements in the active view
2. **Intersection Detection**: For each pair of beams, it uses Dynamo's `Geometry.Intersect()` to find intersection points
3. **Smart Filtering**: Filters intersection points using smart endpoint detection (T-junctions vs L-junctions)
4. **Beam-Specific Assignment**: Projects each intersection point back onto the curves to determine which beams it actually belongs to (only beams where 0.0001 < normalized_param < 0.9999)
5. **Duplicate Removal**: Removes duplicate intersection points (same coordinates) that occur when multiple beams meet at one point
6. **Beam Splitting**: For each beam with intersection points:
   - Sorts points from highest to lowest X coordinate (or by proximity)
   - For each point, checks which current beam segment it belongs to
   - Recalculates normalized parameter on the current segment
   - Uses Revit's native `FamilyInstance.Split()` method
   - Tracks newly created beam segments for subsequent splits
7. **Output**: Returns `[dynamo_curve, [intersection_points], beam_id]` for each beam with splits

## Important Notes

- **Unit Conversion**: Uses `.ToXyz()` for Dynamo Point → Revit XYZ conversion and `.ToPoint()` for reverse conversion to handle mm↔feet properly. **NEVER use `.X, .Y, .Z` directly with Revit API**
- **Intersection Point Validation**: Each intersection point is verified to actually project onto a beam's curve (not just at the endpoint)
- **Duplicate Handling**: When multiple beams intersect at the same point, duplicates are automatically removed (identified by rounded coordinates to 2 decimal places)
- **Dynamic Beam Tracking**: After each split, newly created beam segments are tracked so subsequent splits find the correct segment
- The script performs all modifications within a single transaction for proper Revit integration
- All new beams maintain the same type and level as the original beam they came from
- Split parameters are strictly between 0 and 1 (excludes endpoints, with 0.0001 tolerance buffer)
- Multiple splits on the same beam are handled by checking which segment each point belongs to

## Intersection Detection Logic

The script uses **Dynamo's native Geometry.Intersect method** for accurate intersection detection with smart endpoint filtering.

### Detection Method:
1. **Find raw intersections**: Uses Dynamo's `Geometry.Intersect()` on both curves to find all potential intersection points
2. **Normalize return value**: Handles single point, multiple points, or None return from Geometry.Intersect()
3. **Calculate endpoint distances**: For each raw intersection point:
   - Calculate XY distance from point to curve1's start endpoint
   - Calculate XY distance from point to curve1's end endpoint
   - Calculate XY distance from point to curve2's start endpoint
   - Calculate XY distance from point to curve2's end endpoint
4. **Smart endpoint filtering**: Check if point is close to endpoints (within IN[2] tolerance):
   - If point is close to BOTH curves' endpoints → **REJECT** (L-junction, endpoint-to-endpoint)
   - If point is close to at least one curve's endpoints but NOT the other → **ACCEPT** (T-junction, endpoint-to-middle)
   - If point is far from both curves' endpoints → **ACCEPT** (X-junction, middle-to-middle)
5. **Z tolerance filtering** (optional): If IN[3] > 0, check if point's Z elevation is within tolerance of curve1's start Z

### Endpoint Filtering Logic:
The decision logic for accepting/rejecting intersection points:

1. **Check curve1**: Is the point's XY position close to curve1's start or end? (within IN[2] tolerance)
2. **Check curve2**: Is the point's XY position close to curve2's start or end? (within IN[2] tolerance)
3. **Decision**:
   - **REJECT**: Only if point is close to BOTH curves' endpoints
   - **ACCEPT**: If point is far from at least ONE curve's endpoints (in the middle of at least one beam)
4. **Z filter** (if enabled): Check if |point.Z - curve1_start.Z| ≤ IN[3]

This allows endpoint-to-middle intersections (T-junctions) and middle-to-middle (X-junctions) while filtering out pure endpoint-to-endpoint connections (L-junctions).

### Key Features:
- **Smart Endpoint Filtering**: Accepts intersections that are valid for at least one beam (IN[2]) - rejects only if both curves are at their endpoints
- **Z Tolerance**: Accepts intersections within elevation tolerance for beams on same level (IN[3])
- **Accurate Geometry**: Uses Dynamo's proven `Geometry.Intersect()` algorithm
- **Proper Unit Handling**: Uses `.ToXyz()` and `.ToPoint()` for correct Dynamo↔Revit coordinate conversion
- **Native Splitting**: Uses Revit's `FamilyInstance.Split()` method for reliable beam splitting

## Usage

### Input Parameters:
- **IN[1]**: Boolean - Enable split mode (False = detection only, True = split beams)
- **IN[2]**: Number - Tolerance distance to exclude from curve endpoints (default: 300 units, in model units)
- **IN[3]**: Number - Z elevation tolerance for accepting intersections on same level (default: 0 units, in model units)

### Mode 1: Detection Only (IN[1] = False)
- **Output**: `[[beam, beam_id, dynamo_curve, [intersection_points]], ...]` plus detailed report
- Use this to verify intersection detection is working before splitting
- Shows all detected intersection points with detailed analysis logs
- Includes dynamo_curve for preview in Dynamo viewer
- Set IN[2] to adjust endpoint tolerance
- Set IN[3] to filter intersections by Z elevation

### Mode 2: Split Beams (IN[1] = True)
- **Output**: `[[dynamo_curve, [intersection_points], beam_id], ...]` plus execution report
- Automatically splits beams at intersection points using `FamilyInstance.Split()`
- Maintains beam type and level properties automatically
- Removes duplicate intersection points before splitting (when multiple beams meet at same point)
- Splits are performed by checking which beam segment each point belongs to after each split
- Produces detailed split logs showing which beam segments were split and at what parameters

## Troubleshooting

- **No structural framing found**: Ensure you're in a view that shows structural framing elements
- **No intersections detected**: Check beam positions; verify beams actually intersect in 3D space. Use detection mode (IN[1]=False) first to verify
- **Too many intersection points**: Adjust IN[2] (tolerance) to exclude points closer to endpoints. Higher values = fewer intersections
- **Unwanted endpoint-to-endpoint intersections**: These are automatically rejected by the smart endpoint filtering logic
- **Z elevation issues**: Use IN[3] to set Z tolerance if beams on different elevations are incorrectly intersecting
- **No splits performed**: Check the output report for "Point type in beam_intersections" to verify intersection points are being found
- **Coordinate/projection errors**: Ensure `.ToXyz()` is used for Dynamo→Revit conversion (not direct `.X, .Y, .Z` access)

## Files

- `split_structural_beam_at_intersection.py`: The main production Python script for Dynamo
- `structural_framing_intersections.py`: Original development version (reference only)
- `structural_framing_intersections Test.py`: Test version with alternative detection method
- `README.md`: This documentation file

## Technical Implementation Details

### Unit Conversion (Critical!)
- **Dynamo**: Works in millimeters (mm)
- **Revit API**: Works in feet
- **Proper Conversion**:
  - Dynamo Point → Revit XYZ: Use `.ToXyz()` method
  - Revit XYZ → Dynamo Point: Use `.ToPoint()` method
  - **DO NOT** use direct `.X`, `.Y`, `.Z` access with Revit API methods

### Parameter Normalization
- Curve parameters in Revit are not necessarily 0-1
- `GetEndParameter(0)` returns start parameter, `GetEndParameter(1)` returns end parameter
- Normalized parameter = `(actual_param - start_param) / (end_param - start_param)`
- `Split()` method expects normalized parameter (0.0 to 1.0, exclusive)

### Intersection Point Validation
- After `Geometry.Intersect()` finds raw intersection points, each is projected back onto the original curves
- Only points with valid normalized parameters (0.0001 < param < 0.9999) are kept
- A point is only added to a beam's intersection list if it actually projects onto that beam
- This prevents duplicate points that don't belong to a specific beam

### Duplicate Point Removal
- When multiple beams meet at the same location, the same intersection point may be added to multiple beams
- Before splitting, duplicates are identified by rounding coordinates to 2 decimal places
- Only unique points (by rounded coordinates) are used for splitting
- Example: If beams A, B, C all meet at point P, only one copy of P is kept

### Multi-Split Strategy (Dynamic Beam Tracking)
When multiple split points exist on a single beam:
1. Sort points by X coordinate (highest to lowest)
2. Maintain a list of current beam segments (starts with just the original beam)
3. For each point (in order):
   - Check which segment it belongs to by projecting onto all current beams
   - Recalculate normalized parameter for that specific segment
   - Split the correct segment using `FamilyInstance.Split()`
   - Add newly created beam to the current segments list
4. Example with beam A and points at 0.25, 0.5, 0.75:
   - Initial: `current_beams = [A]`
   - Process 0.75: Split A at 0.75 → A, A_new. Now: `current_beams = [A, A_new]`
   - Process 0.5: Point belongs to A, split A at 0.5 → A, A_mid. Now: `current_beams = [A, A_mid, A_new]`
   - Process 0.25: Point belongs to A, split A at 0.25 → A, A_start. Now: `current_beams = [A, A_start, A_mid, A_new]`
   - Result: 4 segments with correct proportions

### Intersection Detection
- Uses `Geometry.Intersect()` on original (unextended) curves
- Projects intersection points back to curves using `curve.Project(xyz_pt)`
- Tolerance buffer of 0.0001 prevents floating-point precision issues near endpoints
- Returns actual Dynamo Point objects (not XYZ)
- All points are converted using `.ToXyz()` for Revit API compatibility

## Author

Created for Revit Dynamo workflow optimization. Created by me :) I'm Zaw.

## License

This script is provided as-is for use in Revit projects. Modify as needed for your specific requirements.
