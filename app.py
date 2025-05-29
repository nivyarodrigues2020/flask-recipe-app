from flask import Flask, request, render_template
import pandas as pd
import requests
from io import StringIO

app = Flask(__name__)

# -----------------------------
# LOAD THE DATASET
# -----------------------------
DATA_URL = "https://drive.google.com/uc?export=download&id=1FGgsRPERabERU9dh10dl6GxLaYzme5me"
response = requests.get(DATA_URL)
response.raise_for_status()
df = pd.read_csv(StringIO(response.text))

# -----------------------------
# PREPARE MASTER KEYWORDS SET
# from ingredients, title, and recipe columns (lowercased)
# -----------------------------
all_keywords = set()

for idx, row in df.iterrows():
    # Ingredients
    ingredients = [ing.strip().lower() for ing in row['Cleaned_Ingredients'].split(",")]
    all_keywords.update(ingredients)

    # Title keywords
    title_words = [w.strip().lower() for w in row['Title'].split()]
    all_keywords.update(title_words)

    # Recipe / Instructions keywords
    recipe_words = [w.strip().lower() for w in str(row['Recipe']).split()]
    all_keywords.update(recipe_words)

ingredient_keywords = list(all_keywords)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def extract_ingredients_from_text(text):
    # Extract user input ingredients that appear in master keywords
    text_ings = [ing.strip().lower() for ing in text.split(",")]
    extracted = [ing for ing in text_ings if ing in ingredient_keywords]
    return extracted

def recommend_recipes(user_ingredients, top_n=5):
    user_ingredients = [ing.strip().lower() for ing in user_ingredients]

    def contains_all(row):
        combined_text = (
            row['Cleaned_Ingredients'].lower() + " " + 
            row['Title'].lower() + " " + 
            str(row['Recipe']).lower()
        )
        return all(ing in combined_text for ing in user_ingredients)

    filtered_df = df[df.apply(contains_all, axis=1)]

    if filtered_df.empty:
        # No full matches found
        return pd.DataFrame(), user_ingredients  # All ingredients considered ignored here

    results = filtered_df.head(top_n).copy()

    # Clean ingredients string for display
    results['Cleaned_Ingredients'] = results['Cleaned_Ingredients'].apply(
        lambda x: ", ".join([i.strip().capitalize() for i in x.split(",") if i.strip()])
    )
    results['Instructions'] = results['Instructions'].fillna("").str.strip()

    ignored = []  # No ignored ingredients since all matched

    return results
