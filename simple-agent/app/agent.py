# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from google.cloud import firestore, storage
from google import genai
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.agents.callback_context import CallbackContext
from google.adk.code_executors.agent_engine_sandbox_code_executor import AgentEngineSandboxCodeExecutor

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from .a2ui_utils import a2ui_callback



MODEL = "gemini-3.8-flash"
FIRESTORE_PROJECT = "qwiklabs-gcp-03-02befd0fcb65"
GCS_BUCKET_NAME = "greenhouse-catalog-qwiklabs-gcp-03-02befd0fcb65"
IMAGE_MODEL = "gemini-3.1-flash-lite-image"
AGENT_ENGINE_RESOURCE = "projects/116094222713/locations/us-east1/reasoningEngines/3350492305298554880"
SANDBOX_RESOURCE = "projects/116094222713/locations/us-east1/reasoningEngines/3350492305298554880/sandboxEnvironments/9130014703563571200"



_firestore_client: Optional[firestore.Client] = None

def get_firestore_client() -> firestore.Client:
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(project=FIRESTORE_PROJECT)
    return _firestore_client


def list_plants() -> List[Dict[str, Any]]:
    """List all plants available in the greenhouse catalog with their care requirements and pricing.

    Returns:
        A list of dictionaries representing plant catalog items.
    """
    db = get_firestore_client()
    plants_ref = db.collection("plants")
    docs = plants_ref.stream()
    return [doc.to_dict() for doc in docs]


def get_plant_details(plant_id_or_name: str) -> Dict[str, Any]:
    """Retrieve detailed information about a specific plant by its identifier or common name.

    Args:
        plant_id_or_name: The ID (e.g., 'monstera-deliciosa') or common name (e.g., 'Snake Plant') of the plant.

    Returns:
        A dictionary with the plant's details, or an error message if not found.
    """
    db = get_firestore_client()
    plants_ref = db.collection("plants")
    
    # Try direct document ID lookup
    doc = plants_ref.document(plant_id_or_name.lower().replace(" ", "-")).get()
    if doc.exists:
        return doc.to_dict()
    
    # Search by case-insensitive name match
    query_name = plant_id_or_name.lower()
    for plant in plants_ref.stream():
        data = plant.to_dict()
        if (
            data.get("name", "").lower() == query_name
            or query_name in data.get("name", "").lower()
            or query_name in data.get("scientific_name", "").lower()
        ):
            return data
            
    return {"error": f"Plant '{plant_id_or_name}' not found in the catalog."}


def add_plant(
    name: str,
    scientific_name: str,
    category: str,
    light: str,
    water_frequency_days: int,
    difficulty: str,
    price_usd: float,
    description: str,
) -> Dict[str, Any]:
    """Add a new plant to the greenhouse inventory.

    Args:
        name: Common name of the plant (e.g. 'ZZ Plant').
        scientific_name: Botanical name (e.g. 'Zamioculcas zamiifolia').
        category: Plant type category (e.g. 'Succulent', 'Tropical Foliage').
        light: Sunlight requirement description (e.g. 'Low to bright indirect light').
        water_frequency_days: Recommended watering interval in days.
        difficulty: Difficulty level (e.g. 'Very Easy', 'Easy', 'Moderate', 'Expert').
        price_usd: Price in USD.
        description: Informative description and care notes.

    Returns:
        A dictionary confirming the created plant details.
    """
    db = get_firestore_client()
    doc_id = name.lower().replace(" ", "-")
    plant_data = {
        "id": doc_id,
        "name": name,
        "scientific_name": scientific_name,
        "category": category,
        "light": light,
        "water_frequency_days": water_frequency_days,
        "difficulty": difficulty,
        "price_usd": price_usd,
        "description": description,
    }
    db.collection("plants").document(doc_id).set(plant_data)
    return {"status": "success", "message": f"Added plant '{name}' with ID '{doc_id}'", "plant": plant_data}


def record_watering_log(plant_id_or_name: str, notes: str = "") -> Dict[str, Any]:
    """Log a watering event for a plant.

    Args:
        plant_id_or_name: ID or name of the plant watered.
        notes: Optional notes about moisture or plant condition.

    Returns:
        A dictionary confirming the watering record.
    """
    db = get_firestore_client()
    log_id = f"{plant_id_or_name.lower().replace(' ', '-')}-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}"
    log_data = {
        "plant": plant_id_or_name,
        "watered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "notes": notes,
    }
    db.collection("watering_logs").document(log_id).set(log_data)
    return {"status": "success", "message": f"Recorded watering log for {plant_id_or_name}.", "log": log_data}


def search_plants_by_care(
    max_water_frequency_days: Optional[int] = None,
    light_keyword: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter plants by care requirements such as watering interval, light needs, or difficulty.

    Args:
        max_water_frequency_days: Maximum interval in days between waterings (e.g. 7 for plants watered once a week or more often).
        light_keyword: Keyword in light conditions (e.g. 'low', 'bright', 'indirect').
        difficulty: Care difficulty level (e.g. 'Easy', 'Very Easy', 'Moderate').

    Returns:
        A list of matching plants.
    """
    db = get_firestore_client()
    matches = []
    for doc in db.collection("plants").stream():
        plant = doc.to_dict()
        if max_water_frequency_days is not None and plant.get("water_frequency_days", 0) > max_water_frequency_days:
            continue
        if light_keyword and light_keyword.lower() not in plant.get("light", "").lower():
            continue
        if difficulty and difficulty.lower() not in plant.get("difficulty", "").lower():
            continue
        matches.append(plant)
    return matches


def get_local_plant_environment(city: str) -> Dict[str, Any]:
    """Fetch current real-world ambient weather, temperature, and humidity for a city to guide plant care.

    Args:
        city: City name (e.g. 'Seattle', 'San Francisco', 'Miami').

    Returns:
        A dictionary containing real ambient temperature, humidity, and location details.
    """
    import json
    import urllib.parse
    import urllib.request

    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "GreenhouseAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            geo = json.loads(resp.read().decode("utf-8"))
            if not geo.get("results"):
                return {"error": f"City '{city}' not found."}
            res = geo["results"][0]
            lat, lon = res["latitude"], res["longitude"]
            location_name = f"{res.get('name')}, {res.get('country', '')}"

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m"
        req2 = urllib.request.Request(weather_url, headers={"User-Agent": "GreenhouseAgent/1.0"})
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            weather = json.loads(resp2.read().decode("utf-8"))
            current = weather.get("current", {})
            return {
                "location": location_name,
                "temperature_celsius": current.get("temperature_2m"),
                "relative_humidity_percent": current.get("relative_humidity_2m"),
                "notes": "Higher humidity reduces watering frequency; lower humidity (<40%) indicates misting or pebble trays may be needed for tropicals.",
            }
    except Exception as e:
        return {"error": f"Failed to fetch environmental data: {str(e)}"}


def geocode_address(address: str) -> Dict[str, Any]:
    """Convert a human-readable street address or city into geographical latitude and longitude coordinates using Google Maps Geocoding API.

    Args:
        address: The street address, neighborhood, or city (e.g., '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        A dictionary with formatted address, latitude, and longitude.
    """
    import os
    import json
    import urllib.parse
    import urllib.request

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return {"error": "GOOGLE_MAPS_API_KEY is not configured in .env."}

    encoded_address = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") != "OK" or not data.get("results"):
                return {"error": f"Geocoding failed: {data.get('status')} - {data.get('error_message', 'No results found')}"}
            
            top_result = data["results"][0]
            loc = top_result["geometry"]["location"]
            return {
                "formatted_address": top_result.get("formatted_address"),
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
                "location_type": top_result.get("geometry", {}).get("location_type"),
            }
    except Exception as e:
        return {"error": f"Geocoding request failed: {str(e)}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "florist",
    radius_meters: float = 5000.0,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """Find nearby places of a given type around a coordinate using Google Maps Places API (New).

    Args:
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        place_type: Type of place to search for (e.g., 'florist', 'park', 'store', 'hardware_store').
        radius_meters: Search radius in meters (max 50000.0). Defaults to 5000.0 meters.
        max_results: Maximum number of places to return (between 1 and 20).

    Returns:
        A list of nearby places with name, formatted address, and location.
    """
    import os
    import json
    import urllib.request

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return [{"error": "GOOGLE_MAPS_API_KEY is not configured in .env."}]

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": min(max(max_results, 1), 20),
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": float(radius_meters),
            }
        },
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            places = []
            for item in data.get("places", []):
                places.append({
                    "name": item.get("displayName", {}).get("text", "Unknown"),
                    "address": item.get("formattedAddress", ""),
                    "location": item.get("location", {}),
                })
            return places
    except Exception as e:
        return [{"error": f"Places request failed: {str(e)}"}]


async def generate_and_save_plant_image(
    prompt: str,
    filename: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """Generate an image for a plant or greenhouse item using the gemini-3.1-flash-lite-image model in global region.

    Saves the image as an ADK artifact (so it appears in the Playground's Artifacts panel)
    and uploads the image bytes directly to the public Cloud Storage bucket, returning its public URL.

    Args:
        prompt: Detailed description of the image to generate (e.g. 'A lush green Monstera Deliciosa in a terracotta pot with sunlight').
        filename: Destination filename (e.g. 'monstera.png' or 'peace-lily.jpg').
        tool_context: Context provided by ADK containing session and artifact services.

    Returns:
        A dictionary containing the public Cloud Storage URL, filename, and artifact version.
    """
    if not filename.endswith((".png", ".jpg", ".jpeg")):
        filename = f"{filename}.png"

    # 1. Generate image using Vertex AI gemini-3.1-flash-lite-image in global region
    genai_client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT,
        location="global",
    )

    full_prompt = f"Generate an image: {prompt}"
    response = genai_client.models.generate_content(
        model=IMAGE_MODEL,
        contents=full_prompt,
    )

    image_part = None
    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                image_part = part
                break

    if not image_part:
        return {"error": "Failed to generate image from model response."}

    image_bytes = image_part.inline_data.data
    mime_type = image_part.inline_data.mime_type or "image/png"

    # 2. Save image with tool_context.save_artifact so it appears in Playground's Artifacts panel
    artifact_version = None
    try:
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        artifact_version = await tool_context.save_artifact(
            filename=filename,
            artifact=artifact_part,
        )
    except Exception as e:
        # Fallback if artifact service is not configured in current test runner
        pass

    # 3. Upload image bytes directly to public Cloud Storage bucket (without writing to local file)
    storage_client = storage.Client(project=FIRESTORE_PROJECT)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

    return {
        "status": "success",
        "public_url": public_url,
        "filename": filename,
        "artifact_version": artifact_version,
        "mime_type": mime_type,
    }


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are a helpful Greenhouse and Plant Care Assistant. "
        "You remember the user's stated plant preferences, care habits, facts, and especially any user allergies or sensitivities "
        "(such as pollen, mold, dust, plant sap, or pet-toxic plants) from previous conversations and strictly respect them to personalize your recommendations and keep the user safe. "
        "You help users manage and discover plants in their collection, search plants by care requirements, "
        "check care details, fetch real local environmental data (humidity and temperature) to advise on watering needs, "
        "find nearby local nurseries, plant shops, or parks using Maps geocoding and places search, "
        "generate plant images and visual guides (saved to cloud storage and artifacts), "
        "safely execute Python code in a secure sandbox environment for mathematical calculations, data analysis, or date/schedule forecasting, "
        "add new plants to the catalog, and record watering logs. "
        "Use your tools to query and update plant data in the database."
    ),
    workflow_description="Analyze the request, call appropriate tools to fetch or record data, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=AgentEngineSandboxCodeExecutor(
        sandbox_resource_name=SANDBOX_RESOURCE,
        agent_engine_resource_name=AGENT_ENGINE_RESOURCE,
    ),
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    tools=[
        PreloadMemoryTool(),
        list_plants,
        get_plant_details,
        search_plants_by_care,
        get_local_plant_environment,
        geocode_address,
        find_nearby_places,
        generate_and_save_plant_image,
        add_plant,
        record_watering_log,
    ],
)


app = App(
    root_agent=root_agent,
    name="app",
)




