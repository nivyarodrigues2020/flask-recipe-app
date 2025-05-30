from flask import Flask, request, render_template
import pandas as pd
import requests
from io import StringIO
import unicodedata

app = Flask(__name__)

# -----------------------------
# LOAD THE DATASET
# -----------------------------
DATA_URL = "https://drive.google.com/uc?export=download&id=1FGgsRPERabERU9dh10dl6GxLaYzme5me"
response = requests.get(DATA_URL)
response.raise_for_status()
df = pd.read_csv(StringIO(response.text))

# -----------------------------
# CLEAN ENCODING ARTIFACTS FUNCTION
# -----------------------------
def fix_encoding(text):
    if pd.isna(text):
        return ""
    text = str(text)
    # Normalize Unicode characters to separate accents, etc.
    text = unicodedata.normalize("NFKD", text)
    # Replace common messed-up characters from encoding issues
    replacements = {
        "â€“": "-",
        "â€”": "-",
        "â€˜": "'",
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
        "Â¼": "1/4",
        "Â½": "1/2",
        "Â¾": "3/4",
        "Â": "",
        "Ã©": "e",
        "Ã": "a",
        "ƒ": "f",
    }
    for wrong, right in replacements.items():
        text = text.replace(wrong, right)
    return text

# Clean relevant text columns
for col in ["Cleaned_Ingredients", "Title", "Instructions"]:
    df[col] = df[col].apply(fix_encoding)

# -----------------------------
# BUILD MASTER KEYWORDS SET
# -----------------------------
master_texts = []
for _, row in df.iterrows():
    combined = " ".join([
        str(row["Cleaned_Ingredients"]) if pd.notna(row["Cleaned_Ingredients"]) else "",
        str(row["Title"]) if pd.notna(row["Title"]) else "",
        str(row["Instructions"]) if pd.notna(row["Instructions"]) else ""
    ]).lower()
    master_texts.append(combined)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def extract_ingredients_from_text(text):
    return [ing.strip().lower() for ing in text.split(",") if ing.strip()]

def recommend_recipes(user_ingredients, top_n=5):
    user_ingredients = [ingredient.strip().lower() for ingredient in user_ingredients]
    
    # Filter recipes where ALL user ingredients appear in the combined text
    df["combined_text"] = master_texts
    full_match_mask = df["combined_text"].apply(lambda txt: all(ing in txt for ing in user_ingredients))
    full_matches = df[full_match_mask]

    if not full_matches.empty:
        results = full_matches.head(top_n).copy()
        ignored = []
        message = ""
    else:
        # No full match, show message & no results
        results = pd.DataFrame()
        ignored = user_ingredients  # All ignored since no full match
        message = "No recipe found containing all ingredients entered. Please try different or fewer ingredients."

    if not results.empty:
        # Clean display fields
        for col in ["Cleaned_Ingredients", "Instructions", "Title"]:
            if col in results.columns:
                results[col] = results[col].fillna("").apply(str).str.strip()
    return results, ignored, message

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
            extracted = extract_ingredients_from_text(user_input)
            if not extracted:
                message = "No known ingredients found in your input."
            else:
                results, ignored, message = recommend_recipes(extracted)
                if not results.empty:
                    recipes = results[["Title", "Cleaned_Ingredients", "Instructions"]].to_dict(orient="records")
                elif not message:
                    message = "Sorry, no recipes found with those ingredients."

                if ignored and results.empty:
                    ignored_str = ", ".join(ignored)
                    message += f"<br><br>Ignored ingredients: {ignored_str}"

    return render_template("index.html", recipes=recipes, message=message)

# -----------------------------
# RUN THE APP
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
