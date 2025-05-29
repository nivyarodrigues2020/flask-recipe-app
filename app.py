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
   ingredients_str = str(row['Cleaned_Ingredients']) if pd.notna(row['Cleaned_Ingredients']) else ""
    ingredients = [ing.strip().lower() for ing in ingredients_str.split(",") if ing.strip()]
    all_keywords.update(ingredients)

    # Title keywords
   title_str = str(row['Title']) if pd.notna(row['Title']) else ""
    title_words = [w.strip().lower() for w in title_str.split() if w.strip()]
    all_keywords.update(title_words)

    # Recipe / Instructions keywords
    recipe_str = str(row['Recipe']) if pd.notna(row['Instructions']) else ""
recipe_words = [w.strip().lower() for w in recipe_str.split() if w.strip()]
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
            str(row['Instructions']).lower()
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
                results, ignored = recommend_recipes(extracted)
                if results.empty:
                    message = "No recipe found having all ingredients entered, please enter again."
                else:
                    recipes = results[["Title", "Cleaned_Ingredients", "Instructions"]].to_dict(orient="records")
                    # ignored will be empty here because all matched

    return render_template("index.html", recipes=recipes, message=message)

# -----------------------------
# RUN THE APP
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
