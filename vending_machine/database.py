import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SEED_SUPPLEMENTS = [
    {
        "name": "Whey Protein",
        "category": "Protein",
        "description": "Dairy-based protein powder commonly used to help meet daily protein needs after resistance training.",
        "serving_size": "See product label",
        "protein_g": 24,
        "caffeine_mg": 0,
        "activity_tags": ["gym", "strength_training", "running", "walking"],
        "goal_tags": ["muscle_gain", "recovery", "general_fitness"],
        "dietary_tags": ["vegetarian"],
        "allergens": ["milk"],
        "warnings": ["Contains dairy; not suitable for people with a milk allergy."],
        "price": 29.99,
        "stock": 12,
    },
    {
        "name": "Plant Protein Blend",
        "category": "Protein",
        "description": "Pea and rice protein blend for people looking for a dairy-free way to add protein to their diet.",
        "serving_size": "See product label",
        "protein_g": 21,
        "caffeine_mg": 0,
        "activity_tags": ["gym", "strength_training", "running", "walking"],
        "goal_tags": ["muscle_gain", "recovery", "general_fitness"],
        "dietary_tags": ["vegan", "vegetarian", "dairy_free"],
        "allergens": [],
        "warnings": [],
        "price": 32.5,
        "stock": 8,
    },
    {
        "name": "Creatine Monohydrate",
        "category": "Performance",
        "description": "Single-ingredient creatine monohydrate, a widely researched sports supplement often used with strength training.",
        "serving_size": "See product label",
        "protein_g": 0,
        "caffeine_mg": 0,
        "activity_tags": ["gym", "strength_training"],
        "goal_tags": ["strength", "muscle_gain", "power"],
        "dietary_tags": ["vegan", "vegetarian", "dairy_free"],
        "allergens": [],
        "warnings": ["Ask a healthcare professional before use if you have a medical condition or take medication."],
        "price": 24.99,
        "stock": 10,
    },
    {
        "name": "Electrolyte Drink Mix",
        "category": "Hydration",
        "description": "Electrolyte drink mix intended to support fluid replacement during prolonged or sweaty exercise.",
        "serving_size": "See product label",
        "protein_g": 0,
        "caffeine_mg": 0,
        "activity_tags": ["running", "walking", "endurance", "cycling", "gym"],
        "goal_tags": ["hydration", "endurance", "recovery"],
        "dietary_tags": ["vegan", "vegetarian", "dairy_free"],
        "allergens": [],
        "warnings": ["Check the label for sodium and sugar content, especially if limiting either."],
        "price": 18.99,
        "stock": 15,
    },
    {
        "name": "Vitamin D3",
        "category": "Vitamins",
        "description": "Vitamin D supplement. Individual needs vary and are best discussed with a healthcare professional.",
        "serving_size": "See product label",
        "protein_g": 0,
        "caffeine_mg": 0,
        "activity_tags": ["walking", "running", "gym", "general"],
        "goal_tags": ["general_health"],
        "dietary_tags": ["vegetarian", "dairy_free"],
        "allergens": [],
        "warnings": ["Do not use to diagnose or treat a deficiency; ask a healthcare professional about testing and suitability."],
        "price": 12.99,
        "stock": 9,
    },
    {
        "name": "Daily Multivitamin",
        "category": "Vitamins",
        "description": "General multivitamin and mineral supplement; it does not replace a varied, balanced diet.",
        "serving_size": "See product label",
        "protein_g": 0,
        "caffeine_mg": 0,
        "activity_tags": ["walking", "running", "gym", "general"],
        "goal_tags": ["general_health"],
        "dietary_tags": ["vegetarian"],
        "allergens": [],
        "warnings": ["Check ingredients and ask a healthcare professional if pregnant, taking medication, or managing a condition."],
        "price": 15.99,
        "stock": 11,
    },
]


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    path = Path(os.getenv("VENDING_DATABASE_PATH", "data/sports_nutrition.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS supplements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                serving_size TEXT NOT NULL,
                protein_g REAL NOT NULL DEFAULT 0 CHECK (protein_g >= 0),
                caffeine_mg REAL NOT NULL DEFAULT 0 CHECK (caffeine_mg >= 0),
                activity_tags TEXT NOT NULL DEFAULT '[]',
                goal_tags TEXT NOT NULL DEFAULT '[]',
                dietary_tags TEXT NOT NULL DEFAULT '[]',
                allergens TEXT NOT NULL DEFAULT '[]',
                warnings TEXT NOT NULL DEFAULT '[]',
                price REAL NOT NULL CHECK (price > 0),
                stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS recommendation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_mode TEXT NOT NULL,
                activity TEXT,
                goal TEXT,
                recommendation_names TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplement_id INTEGER NOT NULL REFERENCES supplements(id),
                supplement_name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price REAL NOT NULL,
                total REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_supplements_category
                ON supplements(category);
            CREATE INDEX IF NOT EXISTS idx_purchases_created_at
                ON purchases(created_at);
            """
        )
        for item in SEED_SUPPLEMENTS:
            values = {
                **item,
                "activity_tags": json.dumps(item["activity_tags"]),
                "goal_tags": json.dumps(item["goal_tags"]),
                "dietary_tags": json.dumps(item["dietary_tags"]),
                "allergens": json.dumps(item["allergens"]),
                "warnings": json.dumps(item["warnings"]),
            }
            connection.execute(
                """
                INSERT OR IGNORE INTO supplements (
                    name, category, description, serving_size, protein_g, caffeine_mg,
                    activity_tags, goal_tags, dietary_tags, allergens, warnings, price, stock
                ) VALUES (
                    :name, :category, :description, :serving_size, :protein_g, :caffeine_mg,
                    :activity_tags, :goal_tags, :dietary_tags, :allergens, :warnings, :price, :stock
                )
                """,
                values,
            )


def serialize_supplement(row: sqlite3.Row) -> dict:
    item = dict(row)
    for field in ("activity_tags", "goal_tags", "dietary_tags", "allergens", "warnings"):
        item[field] = json.loads(item[field])
    return item
