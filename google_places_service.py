import os
import httpx
import logging

logger = logging.getLogger(__name__)

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
PLACES_NEW_URL = "https://places.googleapis.com/v1/places"


async def fetch_place_details(place_id: str) -> dict:
    """
    Fetch place details from Google Places API (New) using a place_id.
    Returns dict with: latitude, longitude, rating, reviews, formatted_address, name
    Returns empty dict on failure.
    """
    if not place_id or not GOOGLE_MAPS_API_KEY:
        logger.warning("Missing place_id or GOOGLE_MAPS_API_KEY")
        return {}

    url = f"{PLACES_NEW_URL}/{place_id}"
    headers = {
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "id,displayName,formattedAddress,location,rating,userRatingCount,reviews",
        "Referer": os.environ.get("REACT_APP_BACKEND_URL", "https://senioradvisor.cl"),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            data = resp.json()

        if resp.status_code != 200:
            error_msg = data.get("error", {}).get("message", str(data))
            logger.error(f"Google Places API (New) error: {resp.status_code} - {error_msg}")
            return {"error": str(resp.status_code), "error_message": error_msg}

        location = data.get("location", {})
        
        google_reviews = []
        for r in data.get("reviews", []):
            original_text = r.get("originalText", r.get("text", {}))
            text = ""
            if isinstance(original_text, dict):
                text = original_text.get("text", "")
            elif isinstance(original_text, str):
                text = original_text

            google_reviews.append({
                "author_name": r.get("authorAttribution", {}).get("displayName", ""),
                "rating": r.get("rating", 0),
                "text": text,
                "relative_time_description": r.get("relativePublishTimeDescription", ""),
                "profile_photo_url": r.get("authorAttribution", {}).get("photoUri", ""),
            })

        display_name = data.get("displayName", {})
        name = display_name.get("text", "") if isinstance(display_name, dict) else str(display_name)

        return {
            "latitude": location.get("latitude", 0),
            "longitude": location.get("longitude", 0),
            "google_rating": data.get("rating", 0),
            "google_total_reviews": data.get("userRatingCount", 0),
            "google_reviews": google_reviews,
            "formatted_address": data.get("formattedAddress", ""),
            "google_name": name,
        }

    except Exception as e:
        logger.exception(f"Error fetching Google Place details: {e}")
        return {"error": "exception", "error_message": str(e)}
