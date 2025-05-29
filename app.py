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
all_ingredients = set()
for ingredients_str in df['Cleaned_Ingredients']:
    ingredients = [ing.strip().lower() for ing in ingredients_str.split(',')]
    all_ingredients.update(ingredients)

ingredient_keywords = list(all_ingredients)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def extract_ingredients_from_text(text):
    text_ings = [ing.strip().lower() for ing in text.split(",")]
    extracted = [ing for ing in text_ings if ing in ingredient_keywords]
    return extracted

def recommend_recipes(user_ingredients, top_n=5):
    user_ingredients = [ingredient.strip().lower() for ingredient in user_ingredients]

    def score(recipe_ingredients):
        recipe_ingredients = recipe_ingredients.lower()
        return sum(1 for ing in user_ingredients if ing in recipe_ingredients)

    df["score"] = df["Cleaned_Ingredients"].apply(score)
    results = df[df["score"] > 0].sort_values(by="score", ascending=False).head(top_n)

    best_score = results["score"].max() if not results.empty else 0
    if best_score == 0:
        ignored = user_ingredients
    else:
        matched = set()
        for ing in user_ingredients:
            if any(ing in r.lower() for r in results["Cleaned_Ingredients"]):
                matched.add(ing)
        ignored = [ing for ing in user_ingredients if ing not in matched]

    if not results.empty:
        results = results.copy()
        results["Cleaned_Ingredients"] = results["Cleaned_Ingredients"].apply(lambda x: x.strip())
        results["Instructions"] = results["Instructions"].apply(lambda x: x.strip())
    return results, ignored

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
                    message = "Sorry, no recipes found with those ingredients."
                else:
                    recipes = results[["Title", "Cleaned_Ingredients", "Instructions"]].to_dict(orient="records")
                    if ignored:
                        ignored_str = ", ".join(ignored)
                        message = f"Note: These ingredients were ignored in the best match: {ignored_str}<br><br>"

    return render_template("index.html", recipes=recipes, message=message)

# -----------------------------
# RUN THE APP
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
