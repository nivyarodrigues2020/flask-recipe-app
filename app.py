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

# -----------------------------
# CLEAN COLUMNS (parse lists if any, lowercase)
# -----------------------------
def clean_column_list_str(col):
    cleaned = []
    for val in df[col]:
        if pd.isna(val):
            cleaned.append("")
            continue
        try:
            parsed = ast.literal_eval(val)
            if isinstance(parsed, list):
                cleaned.append(", ".join(str(x).strip().lower() for x in parsed))
            else:
                cleaned.append(str(val).strip().lower())
        except:
            cleaned.append(str(val).strip().lower())
    return cleaned

df['Cleaned_Ingredients'] = clean_column_list_str('Cleaned_Ingredients')
df['Title_lower'] = df['Title'].fillna("").str.lower()
# If you have a 'Recipe' column (else use 'Instructions')
if 'Recipe' in df.columns:
    df['Recipe_lower'] = df['Recipe'].fillna("").str.lower()
else:
    df['Recipe_lower'] = df['Instructions'].fillna("").str.lower()

# -----------------------------
# BUILD MASTER KEYWORD LIST from Ingredients, Title, Recipe
# -----------------------------
all_keywords = set()

# from Cleaned_Ingredients column
for ingredients_str in df['Cleaned_Ingredients']:
    for ing in ingredients_str.split(','):
        ing = ing.strip()
        if ing:
            all_keywords.add(ing)

# from Title column (split on space and commas)
for title in df['Title_lower']:
    for word in title.replace(",", " ").split():
        word = word.strip()
        if word:
            all_keywords.add(word)

# from Recipe/Instructions column (split on space and commas)
for recipe_text in df['Recipe_lower']:
    for word in recipe_text.replace(",", " ").split():
        word = word.strip()
        if word:
            all_keywords.add(word)

keyword_list = list(all_keywords)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def extract_ingredients_from_text(text):
    """
    Extract words from user input that appear in master keyword list.
    """
    user_ings = [ing.strip().lower() for ing in text.split(",") if ing.strip()]
    extracted = [ing for ing in user_ings if ing in all_keywords]
    return extracted

def recommend_recipes(user_ingredients, top_n=5):
    user_ingredients = [ing.strip().lower() for ing in user_ingredients]

    def score(row):
        combined_text = row['Cleaned_Ingredients'] + " " + row['Title_lower'] + " " + row['Recipe_lower']
        score_val = 0
        for ing in user_ingredients:
            if ing in combined_text:
                score_val += 1
        return score_val

    df['score'] = df.apply(score, axis=1)
    results = df[df['score'] > 0].sort_values(by='score', ascending=False).head(top_n)

    # Find which user ingredients were matched in any recipe result
    matched = set()
    for ing in user_ingredients:
        if any(ing in (row['Cleaned_Ingredients'] + " " + row['Title_lower'] + " " + row['Recipe_lower']) for _, row in results.iterrows()):
            matched.add(ing)

    ignored = [ing for ing in user_ingredients if ing not in matched]

    # Clean output columns for display: capitalize ingredients, strip whitespace
    results_display = results.copy()
    results_display['Cleaned_Ingredients'] = results_display['Cleaned_Ingredients'].apply(
        lambda x: ", ".join([i.strip().capitalize() for i in x.split(",") if i.strip()])
    )
    results_display['Instructions'] = results_display['Instructions'].fillna("").str.strip()

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
