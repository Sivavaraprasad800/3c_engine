"""
zone_utils.py — Detection zone polygon & face pose angle utilities
"""

def point_in_polygon(px, py, polygon):
    """Ray casting — check if point is inside polygon. Points as % (0-100)."""
    if not polygon or len(polygon) < 3:
        return True
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside

def bbox_in_zone(bbox, zone, frame_w, frame_h):
    """Check if face bbox center is inside detection zone."""
    if not zone or len(zone) < 3:
        return True
    cx = ((bbox[0] + bbox[2]) / 2) / frame_w * 100
    cy = ((bbox[1] + bbox[3]) / 2) / frame_h * 100
    return point_in_polygon(cx, cy, zone)

def estimate_face_angles(landmarks):
    """
    Estimate Yaw (left-right turn) and Pitch (up-down tilt) in degrees from 5 facial landmarks.
    Landmarks: [[eye_l_x, eye_l_y], [eye_r_x, eye_r_y], [nose_x, nose_y], [mouth_l_x, mouth_l_y], [mouth_r_x, mouth_r_y]]
    Returns (yaw_deg, pitch_deg)
    """
    if not landmarks or len(landmarks) < 5:
        return 0.0, 0.0

    eye_l, eye_r, nose, mouth_l, mouth_r = landmarks[:5]

    # Yaw: horizontal offset of nose relative to eye midpoint
    eye_center_x = (eye_l[0] + eye_r[0]) / 2.0
    eye_dist = abs(eye_r[0] - eye_l[0])
    if eye_dist < 1e-4:
        return 0.0, 0.0

    horizontal_offset = (nose[0] - eye_center_x) / eye_dist
    yaw_deg = horizontal_offset * 75.0

    # Pitch: vertical offset of nose relative to eye-mouth distance
    eye_center_y = (eye_l[1] + eye_r[1]) / 2.0
    mouth_center_y = (mouth_l[1] + mouth_r[1]) / 2.0
    eye_mouth_dist = abs(mouth_center_y - eye_center_y)
    if eye_mouth_dist < 1e-4:
        return yaw_deg, 0.0

    vertical_ratio = (nose[1] - eye_center_y) / eye_mouth_dist
    pitch_deg = (vertical_ratio - 0.45) * 80.0

    return yaw_deg, pitch_deg

def pose_in_range(landmarks, min_yaw=-35, max_yaw=35, min_pitch=-15, max_pitch=15):
    """Check if face yaw & pitch angles are within configured thresholds."""
    if not landmarks:
        return True
    yaw, pitch = estimate_face_angles(landmarks)
    if min_yaw is not None and yaw < min_yaw:
        return False
    if max_yaw is not None and yaw > max_yaw:
        return False
    if min_pitch is not None and pitch < min_pitch:
        return False
    if max_pitch is not None and pitch > max_pitch:
        return False
    return True
