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
# PREPARE INGREDIENT KEYWORDS
# -----------------------------
all_keywords = set()

for idx, row in df.iterrows():
    ingredients_str = str(row['Cleaned_Ingredients']) if pd.notna(row['Cleaned_Ingredients']) else ""
    ingredients = [ing.strip().lower() for ing in ingredients_str.split(",") if ing.strip()]
    all_keywords.update(ingredients)

    title_str = str(row['Title']) if pd.notna(row['Title']) else ""
    title_words = [w.strip().lower() for w in title_str.split() if w.strip()]
    all_keywords.update(title_words)

    recipe_str = str(row['Instructions']) if pd.notna(row['Instructions']) else ""
    recipe_words = [w.strip().lower() for w in recipe_str.split() if w.strip()]
    all_keywords.update(recipe_words)

ingredient_keywords = list(all_keywords)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def extract_ingredients_from_text(text):
    text_ings = [ing.strip().lower() for ing in text.split(",") if ing.strip()]
    extracted = [ing for ing in text_ings if ing in ingredient_keywords]
    ignored = [ing for ing in text_ings if ing not in ingredient_keywords]
    return extracted, ignored

def recommend_recipes(user_ingredients, top_n=5):
    user_ingredients = [ingredient.strip().lower() for ingredient in user_ingredients]

    def score(row):
        recipe_ings = str(row['Cleaned_Ingredients']).lower() if pd.notna(row['Cleaned_Ingredients']) else ""
        return all(ing in recipe_ings for ing in user_ingredients)

    matches = df[df.apply(score, axis=1)]

    if matches.empty:
        return pd.DataFrame(), user_ingredients
    
    matches = matches.copy()
    matches["Cleaned_Ingredients"] = matches["Cleaned_Ingredients"].apply(lambda x: str(x).strip())
    matches["Instructions"] = matches["Instructions"].apply(lambda x: str(x).strip())
    return matches.head(top_n), []

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
            extracted, truly_ignored = extract_ingredients_from_text(user_input)

            if not extracted:
                message = "No known ingredients found in your input."
            else:
                results, unmatched = recommend_recipes(extracted)

                if results.empty:
                    message = "No recipe found having all ingredients entered. Please enter again."
                else:
                    recipes = results[["Title", "Cleaned_Ingredients", "Instructions"]].to_dict(orient="records")
                    ignored = truly_ignored + unmatched
                    if ignored:
                        ignored_str = ", ".join(set(ignored))
                        message = f"Note: These ingredients were not matched in any recipe: {ignored_str}<br><br>"

    return render_template("index.html", recipes=recipes, message=message)

# -----------------------------
# RUN THE APP
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
