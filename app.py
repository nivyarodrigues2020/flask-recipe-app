import pandas as pd
from flask import Flask, request

# Google Drive direct download URL for your dataset
DATASET_URL = "https://drive.google.com/uc?id=1FGgsRPERabERU9dh10dl6GxLaYzme5me&export=download"

# Load dataset from URL
df = pd.read_csv(DATASET_URL)
df = df.dropna(subset=["Cleaned_Ingredients", "Instructions", "Title"])

# Build list of all unique ingredients from dataset (lowercase, stripped)
all_ingredients = set()
for ingredients_str in df['Cleaned_Ingredients']:
    ingredients = [ing.strip().lower() for ing in ingredients_str.split(',')]
    all_ingredients.update(ingredients)

ingredient_keywords = list(all_ingredients)

def extract_ingredients_from_text(text):
    text_ings = [ing.strip().lower() for ing in text.split(",")]
    extracted = [ing for ing in text_ings if ing in ingredient_keywords]
    return extracted  # returns list

def recommend_recipes(user_ingredients, top_n=5):
    user_ingredients = [ingredient.strip().lower() for ingredient in user_ingredients]
    def score(recipe_ingredients):
        recipe_ingredients = recipe_ingredients.lower()
        return sum(1 for ing in user_ingredients if ing in recipe_ingredients)
    df["score"] = df["Cleaned_Ingredients"].apply(score)
    results = df[df["score"] > 0].sort_values(by="score", ascending=False).head(top_n)
    results["Image_Name"] = results["Image_Name"].apply(lambda x: x + ".jpg")
    return results

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
                known_ings = extracted
                unknown_ings = [i for i in input_ingredients if i not in known_ings]

                warning = f"Note: These ingredients were ignored: {', '.join(unknown_ings)}<br><br>" if unknown_ings else ""

                results = recommend_recipes(known_ings)
                if results.empty:
                    message = "Sorry, no recipes found with those ingredients."
                else:
                    recipes = results[["Title", "Cleaned_Ingredients", "Instructions"]].to_dict(orient="records")
                    message = warning

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

if __name__ == "__main__":
    app.run(debug=True)
