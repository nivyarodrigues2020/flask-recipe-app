from flask import Flask, request, render_template, jsonify
import pandas as pd
import requests
from io import StringIO
import ast

app = Flask(__name__)

# -----------------------------
# INSTRUCTION PHRASES TO IGNORE IN INGREDIENTS
# -----------------------------
instruction_phrases = {
    "divided", "plus more", "melted", "room temperature", "torn into", "thinly sliced",
    "cut into", "cored", "minced", "chopped", "freshly ground", "pinch of", "about",
    "to taste", "as needed", "optional", "pinch", "sliced", "diced"
}

# -----------------------------
# LOAD THE DATASET
# -----------------------------
DATA_URL = "https://drive.google.com/uc?export=download&id=1FGgsRPERabERU9dh10dl6GxLaYzme5me"
response = requests.get(DATA_URL)
response.raise_for_status()
df = pd.read_csv(StringIO(response.text))

# -----------------------------
# HELPER FUNCTION TO PARSE INGREDIENT LIST STRINGS
# -----------------------------
def parse_ingredient_list(ingredients_str):
    """
    Parses stringified Python list of ingredients into a clean Python list.
    Cleans newlines, extra spaces, and filters out instruction-like words.
    """
    if pd.isna(ingredients_str) or not str(ingredients_str).strip():
        return []

    try:
        ingredients = ast.literal_eval(ingredients_str)
        if not isinstance(ingredients, list):
            return []
    except (ValueError, SyntaxError):
        # fallback to treating as plain string
        ingredients = [str(ingredients_str)]

    cleaned = []
    for ing in ingredients:
        if isinstance(ing, str):
            ing_clean = ing.replace('\n', ' ').replace('\r', ' ').strip().lower()
            if ing_clean:
                # Skip if contains any instruction phrase
                if any(phrase in ing_clean for phrase in instruction_phrases):
                    continue
                cleaned.append(ing_clean)
    return cleaned

# -----------------------------
# PREPARE MASTER KEYWORD LIST FROM INGREDIENTS + TITLE + RECIPE COLUMNS
# -----------------------------
all_keywords = set()

for idx, row in df.iterrows():
    # Ingredients
    ingredients_list = parse_ingredient_list(row.get('Cleaned_Ingredients', ""))
    all_keywords.update(ingredients_list)

    # Title
    title = row.get('Title', "")
    if pd.notna(title):
        for word in title.lower().split():
            all_keywords.add(word.strip())

    # Recipe (Instructions)
    recipe_text = row.get('Instructions', "")
    if pd.notna(recipe_text):
        for word in recipe_text.lower().split():
            all_keywords.add(word.strip())

ingredient_keywords = list(all_keywords)

# -----------------------------
# EXTRACT INGREDIENTS FROM USER INPUT
# -----------------------------
def extract_ingredients_from_text(text):
    # split on commas and strip
    text_ings = [ing.strip().lower() for ing in text.split(",")]
    extracted = [ing for ing in text_ings if ing in ingredient_keywords]
    return extracted

# -----------------------------
# RECOMMENDATION FUNCTION
# -----------------------------
def recommend_recipes(user_ingredients, top_n=5):
    user_ingredients = [ingredient.strip().lower() for ingredient in user_ingredients]

    def recipe_ingredients_list(row):
        return parse_ingredient_list(row['Cleaned_Ingredients'])

    # Filter rows that contain **all** user ingredients in their ingredients list
    def contains_all_ingredients(row):
        recipe_ings = recipe_ingredients_list(row)
        return all(ing in recipe_ings for ing in user_ingredients)

    full_match_df = df[df.apply(contains_all_ingredients, axis=1)]

    if not full_match_df.empty:
        results = full_match_df.head(top_n)
        ignored = []
    else:
        # No full match found, fallback to partial matches
        # Score how many user ingredients appear in ingredients + title + instructions combined
        def score(row):
            combined_text = " ".join([
                " ".join(recipe_ingredients_list(row)),
                str(row.get('Title', '')).lower(),
                str(row.get('Instructions', '')).lower()
            ])
            return sum(1 for ing in user_ingredients if ing in combined_text)

        df['score'] = df.apply(score, axis=1)
        partial_matches = df[df['score'] > 0].sort_values(by='score', ascending=False).head(top_n)

        # Identify matched and ignored ingredients in partial matches
        matched = set()
        for ing in user_ingredients:
            for _, r in partial_matches.iterrows():
                combined_text = " ".join([
                    " ".join(recipe_ingredients_list(r)),
                    str(r.get('Title', '')).lower(),
                    str(r.get('Instructions', '')).lower()
                ])
                if ing in combined_text:
                    matched.add(ing)
                    break
        ignored = [ing for ing in user_ingredients if ing not in matched]

        results = partial_matches

    # Clean up ingredients and instructions for display
    display_results = []
    for _, row in results.iterrows():
        ing_list = parse_ingredient_list(row['Cleaned_Ingredients'])
        display_results.append({
            "Title": row.get('Title', ''),
            "Cleaned_Ingredients": ", ".join(ing_list),
            "Instructions": str(row.get('Instructions', '')).strip()
        })

    return display_results, ignored

# -----------------------------
# FLASK ROUTES
# -----------------------------
@app.route("/")
def index():
    return render_template("chat.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    if not user_input.strip():
        return jsonify({"reply": "Please enter some ingredients."})

    extracted = extract_ingredients_from_text(user_input)
    if not extracted:
        return jsonify({"reply": "No known ingredients found. Please try again."})

    results, ignored = recommend_recipes(extracted)
    if not results:
        return jsonify({"reply": "No recipes found with those ingredients."})

    reply = ""
    if ignored:
        reply += f"Note: These ingredients were ignored: {', '.join(ignored)}.\n\n"

    for i, recipe in enumerate(results, 1):
        reply += f"{i}. {recipe['Title']}\nIngredients: {recipe['Cleaned_Ingredients']}\nInstructions: {recipe['Instructions']}\n\n"

    return jsonify({"reply": reply.strip()})

# -----------------------------
# RUN THE APP
# -----------------------------
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
