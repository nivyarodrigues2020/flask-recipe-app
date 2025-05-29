from flask import Flask, request, render_template
import pandas as pd
import requests
from io import StringIO
import ast

app = Flask(__name__)

# -----------------------------
# LOAD THE DATASET
# -----------------------------
DATA_URL = "https://drive.google.com/uc?export=download&id=1FGgsRPERabERU9dh10dl6GxLaYzme5me"
response = requests.get(DATA_URL)
response.raise_for_status()
df = pd.read_csv(StringIO(response.text))

# Clean the dataset columns if they have list-like strings
def clean_column_list_str(col):
    cleaned = []
    for val in df[col]:
        if pd.isna(val):
            cleaned.append("")
            continue
        try:
            # Try to parse string representation of list
            parsed = ast.literal_eval(val)
            if isinstance(parsed, list):
                cleaned.append(", ".join(str(x).strip().lower() for x in parsed))
            else:
                cleaned.append(str(val).strip().lower())
        except:
            # If not a list, just lower and strip
            cleaned.append(str(val).strip().lower())
    return cleaned

# Apply cleaning to ingredients column
df['Cleaned_Ingredients'] = clean_column_list_str('Cleaned_Ingredients')
# Also clean Title column (to lowercase for searching)
df['Title_lower'] = df['Title'].fillna("").str.lower()
# If you have a 'recipe' or 'Instructions' column, you can add similar cleanups if needed

# -----------------------------
# PREPARE INGREDIENT KEYWORDS
# -----------------------------
all_ingredients = set()
for ingredients_str in df['Cleaned_Ingredients']:
    for ing in ingredients_str.split(','):
        ing = ing.strip()
        if ing:
            all_ingredients.add(ing)

ingredient_keywords = list(all_ingredients)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def extract_ingredients_from_text(text):
    # Extract user input ingredients, normalize to lowercase and strip spaces
    text_ings = [ing.strip().lower() for ing in text.split(",") if ing.strip()]
    # Only keep known ingredients
    extracted = [ing for ing in text_ings if ing in ingredient_keywords]
    return extracted

def recommend_recipes(user_ingredients, top_n=5):
    user_ingredients = [ingredient.strip().lower() for ingredient in user_ingredients]

    # Define scoring function: sum of matches in ingredients or in title
    def score(row):
        score = 0
        # Combine ingredients and title for matching
        combined_text = row['Cleaned_Ingredients'] + " " + row['Title_lower']
        for ing in user_ingredients:
            if ing in combined_text:
                score += 1
        return score

    df["score"] = df.apply(score, axis=1)
    results = df[df["score"] > 0].sort_values(by="score", ascending=False).head(top_n)

    # Determine ignored ingredients
    if results.empty:
        ignored = user_ingredients
    else:
        matched = set()
        for ing in user_ingredients:
            # Check if ingredient appears in any result's ingredients or title
            if any(ing in (row['Cleaned_Ingredients'] + " " + row['Title_lower']) for _, row in results.iterrows()):
                matched.add(ing)
        ignored = [ing for ing in user_ingredients if ing not in matched]

    # Clean columns for display (remove extra quotes/brackets if any)
    results_display = results.copy()
    # Ingredients already cleaned; just capitalize first letter for display maybe
    results_display["Cleaned_Ingredients"] = results_display["Cleaned_Ingredients"].apply(
        lambda x: ", ".join([i.strip().capitalize() for i in x.split(",")])
    )
    results_display["Instructions"] = results_display["Instructions"].fillna("").str.strip()

    return results_display, ignored

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
                        ignored_str = ", ".join(ing.capitalize() for ing in ignored)
                        message = f"Note: These ingredients were ignored in the best match: {ignored_str}<br><br>"

    return render_template("index.html", recipes=recipes, message=message)

# -----------------------------
# RUN THE APP
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)
