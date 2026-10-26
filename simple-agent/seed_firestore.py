#!/usr/bin/env python3
"""Seed script for Firestore plant collection."""

from google.cloud import firestore

FIRESTORE_PROJECT = "qwiklabs-gcp-03-02befd0fcb65"

PLANTS = [
    {
        "id": "monstera-deliciosa",
        "name": "Monstera Deliciosa",
        "scientific_name": "Monstera deliciosa",
        "category": "Tropical Foliage",
        "light": "Bright indirect light",
        "water_frequency_days": 7,
        "difficulty": "Easy",
        "price_usd": 34.99,
        "description": "Famous for its natural leaf holes (fenestrations). Thrives in warm, humid rooms.",
    },
    {
        "id": "snake-plant",
        "name": "Snake Plant",
        "scientific_name": "Sansevieria trifasciata",
        "category": "Succulent",
        "light": "Low to bright indirect light",
        "water_frequency_days": 14,
        "difficulty": "Very Easy",
        "price_usd": 24.99,
        "description": "Indestructible architectural plant that tolerates low light and drought.",
    },
    {
        "id": "fiddle-leaf-fig",
        "name": "Fiddle Leaf Fig",
        "scientific_name": "Ficus lyrata",
        "category": "Indoor Tree",
        "light": "Bright filtered light",
        "water_frequency_days": 8,
        "difficulty": "Moderate",
        "price_usd": 59.99,
        "description": "Stately tree with large violin-shaped leaves. Sensitive to drafts and overwatering.",
    },
    {
        "id": "pothos-golden",
        "name": "Golden Pothos",
        "scientific_name": "Epipremnum aureum",
        "category": "Vining Foliage",
        "light": "Low to medium indirect light",
        "water_frequency_days": 7,
        "difficulty": "Very Easy",
        "price_usd": 18.99,
        "description": "Fast-growing trailing vine with heart-shaped leaves variegated with gold.",
    },
    {
        "id": "peace-lily",
        "name": "Peace Lily",
        "scientific_name": "Spathiphyllum",
        "category": "Flowering Houseplant",
        "light": "Medium to low indirect light",
        "water_frequency_days": 5,
        "difficulty": "Easy",
        "price_usd": 28.99,
        "description": "Lush foliage with elegant white spathes. Tells you when it's thirsty by drooping gently.",
    },
]

def seed_database():
    print(f"Connecting to Firestore for project: {FIRESTORE_PROJECT}")
    db = firestore.Client(project=FIRESTORE_PROJECT)
    collection_ref = db.collection("plants")
    
    for item in PLANTS:
        doc_id = item["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(item)
        print(f"  ✓ Seeded plant: {item['name']} ({doc_id})")
    
    print("\nFirestore seeding complete! Seeded 5 items in 'plants' collection.")

if __name__ == "__main__":
    seed_database()
