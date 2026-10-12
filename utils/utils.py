def get_status_color(val):
    if isinstance(val, (int, float)):
        if val >= 80:
            return "Healthy", "#16A34A"  # Green
        elif val >= 60:
            return "Slight Wear", "#2563EB" # Blue
        elif val >= 40:
            return "Moderate Wear", "#F59E0B" # Orange
        else:
            return "Critical", "#DC2626" # Red
    else:
        status_str = str(val)
        if status_str == "Healthy":
            return "Healthy", "#16A34A"
        elif status_str == "Slight Wear":
            return "Slight Wear", "#2563EB"
        elif status_str == "Moderate Wear":
            return "Moderate Wear", "#F59E0B"
        elif status_str == "Warning":
            return "Warning", "#D97706"
        else:
            return "Critical", "#DC2626"

def get_status_markdown(health_pct):
    status, color = get_status_color(health_pct)
    return f"<h3 style='color: {color}; margin-top: 0px;'>{status}</h3>"

