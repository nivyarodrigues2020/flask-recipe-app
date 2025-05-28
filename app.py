import pandas as pd
from flask import Flask, request

# === 1. Load dataset from Google Drive ===
DATASET_URL = "https://drive.google.com/uc?id=1FGgsRPERabERU9dh10dl6GxLaYzme5me&export=download"
df = pd.read_csv(DATASET_URL)
df = df.dropna(subset=["Cleaned_Ingredients", "Instructions", "Title"])

# === 2. Extract known ingredients ===
all_ingredients = set()
for ingredients_str in df['Cleaned_Ingredients']:
    ingredients = [ing.strip().lower() for ing in ingredients_str.split(',')]
    all_ingredients.update(ingredients)

ingredient_keywords = list(all_ingredients)

# === 3. Extract valid ingredients from input ===
def extract_ingredients_from_text(text):
    text_ings = [ing.strip().lower() for ing in text.split(",")]
    extracted = [ing for ing in text_ings if ing in ingredient_keywords]
    return extracted

# === 4. Recommend recipes using best matching score ===
def recommend_recipes(user_ingredients, top_n=5):
    user_ingredients_set = set(ing.strip().lower() for ing in user_ingredients)

    def get_match_score(recipe_ingredients_str):
        recipe_ings = set(i.strip().lower() for i in recipe_ingredients_str.split(","))
        return len(user_ingredients_set.intersection(recipe_ings))

    df["score"] = df["Cleaned_Ingredients"].apply(get_match_score)
    best_score = df["score"].max()

    if best_score == 0:
        return pd.DataFrame(), user_ingredients_set  # No match at all

    results = df[df["score"] == best_score].sort_values(by="score", ascending=False).head(top_n)

    matched_ingredients = set()
    for ingredients_str in results["Cleaned_Ingredients"]:
        recipe_ings = set(i.strip().lower() for i in ingredients_str.split(","))
        matched_ingredients.update(user_ingredients_set.intersection(recipe_ings))

    unmatched_ingredients = user_ingredients_set - matched_ingredients

    return results, unmatched_ingredients

# === 5. Flask App ===
app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    recipes = []
    message = ""

    if request.method == "POST":
        user_input = request.form.get("ingredients")

        if user_input:
            input_ingredients = [i.strip().lower() for i in user_input.split(",")]
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
                        message = f"Note: These ingredients were ignored in the best match: {', '.join(ignored)}<br><br>"

    html = """
    <form method="POST">
        <label>Enter ingredients (comma-separated):</label><br>
        <input type="text" name="ingredients" style="width:300px;">
        <input type="submit" value="Search">
    </form><br>
    """

    html += f"<h3>{message}</h3>"

    for r in recipes:
        html += f"<b>{r['Title']}</b><br>"
        html += f"Ingredients: {r['Cleaned_Ingredients']}<br>"
        html += f"Instructions: {r['Instructions'][:200]}...<br><br>"

    return html

# === 6. Run locally (optional) ===
if __name__ == "__main__":
    app.run(debug=True)
