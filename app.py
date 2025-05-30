from flask import Flask, request, render_template
import pandas as pd
import requests
from io import StringIO
import re

app = Flask(__name__)

# -----------------------------
# LOAD THE DATASET
# -----------------------------
DATA_URL = "https://drive.google.com/uc?export=download&id=1FGgsRPERabERU9dh10dl6GxLaYzme5me"
response = requests.get(DATA_URL)
response.raise_for_status()
df = pd.read_csv(StringIO(response.text))

# -----------------------------
# CLEAN DATASET
# -----------------------------
def clean_ingredient_text(text):
    if pd.isna(text):
        return ""
    # Remove unwanted characters and decode common artifacts
    text = str(text)
    text = re.sub(r"[\[\]\'\"]", "", text)  # Remove brackets and quotes
    text = text.encode("latin1").decode("utf-8", errors="ignore")  # Fix encoding
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    return text.lower()

for col in ['Cleaned_Ingredients', 'Title', 'Recipe']:
    df[col] = df[col].apply(clean_ingredient_text)

# -----------------------------
# PREPARE INGREDIENT KEYWORDS
# -----------------------------
all_ingredients = set()
for col in ['Cleaned_Ingredients', 'Title', 'Recipe']:
    for row in df[col].dropna():
        words = re.split(r'[,\s]+', str(row).lower())
        all_ingredients.update([word.strip() for word in words if word.strip().isalpha()])

ingredient_keywords = list(all_ingredients)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def extract_ingredients_from_text(text):
    text_ings = [ing.strip().lower() for ing in text.split(",")]
    extracted = [ing for ing in text_ings if ing in ingredient_keywords]
    return extracted, text_ings  # return both cleaned and raw list

def recommend_recipes(user_ingredients):
    # Match only recipes that include ALL user ingredients
    def recipe_has_all_ingredients(row):
        recipe_text = " ".join([
            str(row["Cleaned_Ingredients"]) if pd.notna(row["Cleaned_Ingredients"]) else "",
            str(row["Title"]) if pd.notna(row["Title"]) else "",
            str(row["Recipe"]) if pd.notna(row["Instructions"]) else ""
        ]).lower()
        return all(ing in recipe_text for ing in user_ingredients)

    matched_recipes = df[df.apply(recipe_has_all_ingredients, axis=1)].copy()

    return matched_recipes

# -----------------------------
# FLASK ROUTES
# -----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    recipes = []
    message = ""

    if request.method == "POST":
        user_input = request.form.get("ingredients", "")
        if user_input:
            extracted, original = extract_ingredients_from_text(user_input)

            if not extracted:
                message = "No known ingredients found in your input."
            else:
                results = recommend_recipes(extracted)

                if results.empty:
                    message = "No recipe found having all ingredients entered, please enter again."
                else:
                    recipes = results[["Title", "Cleaned_Ingredients", "Instructions"]].copy()
                    recipes["Cleaned_Ingredients"] = recipes["Cleaned_Ingredients"].apply(clean_ingredient_text)
                    recipes["Instructions"] = recipes["Instructions"].apply(clean_ingredient_text)
                    recipes = recipes.to_dict(orient="records")

                # Compute ignored ingredients
                ignored = [ing for ing in original if ing not in extracted]
                if ignored:
                    ignored_str = ", ".join(ignored)
                    message += f"<br>Note: These ingredients were not found and ignored: {ignored_str}"

    return render_template("index.html", recipes=recipes, message=message)

# -----------------------------
# RUN THE APP
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
