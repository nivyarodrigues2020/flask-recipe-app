from flask import Flask, request, render_template
import pandas as pd
import requests
from io import StringIO


app = Flask(__name__)
stemmer = PorterStemmer()

# ----------------------------- #
#           HELPERS            #
# ----------------------------- #

def clean_ingredient_string(ingredient_str):
    try:
        ingredient_str = ingredient_str.encode('latin1').decode('utf-8')
    except:
        pass
    garbage_chars = ['Â', '½', '¼', '¾', '–', '”', '“', '™']
    for char in garbage_chars:
        ingredient_str = ingredient_str.replace(char, '')
    return ingredient_str

def stem_words(text):
    return " ".join([stemmer.stem(word) for word in text.split()])

# ----------------------------- #
#       LOAD THE DATASET       #
# ----------------------------- #

DATA_URL = "https://drive.google.com/uc?export=download&id=1FGgsRPERabERU9dh10dl6GxLaYzme5me"
response = requests.get(DATA_URL)
response.raise_for_status()
df = pd.read_csv(StringIO(response.text))

# Clean and collect ingredient keywords
all_ingredients = set()
for ingredients_str in df['Cleaned_Ingredients']:
    ingredients_str = clean_ingredient_string(ingredients_str)
    ingredients = [ing.strip().lower() for ing in ingredients_str.split(',')]
    all_ingredients.update(ingredients)

ingredient_keywords = list(all_ingredients)

# ----------------------------- #
#        CORE FUNCTIONS        #
# ----------------------------- #

def extract_ingredients_from_text(text):
    text_ings = [ing.strip().lower() for ing in text.split(",")]
    stemmed_keywords = [stem_words(ing) for ing in ingredient_keywords]
    extracted = []
    for user_ing in text_ings:
        stemmed_user_ing = stem_words(user_ing)
        if stemmed_user_ing in stemmed_keywords:
            extracted.append(user_ing)
    return extracted

def recommend_recipes(user_ingredients, top_n=5):
    user_ingredients = [ingredient.strip().lower() for ingredient in user_ingredients]
    user_ingredients_stemmed = [stem_words(ing) for ing in user_ingredients]

    def score(recipe_ingredients):
        recipe_ingredients = clean_ingredient_string(recipe_ingredients.lower())
        recipe_ingredients_stemmed = stem_words(recipe_ingredients)
        return sum(1 for ing in user_ingredients_stemmed if ing in recipe_ingredients_stemmed)

    df["score"] = df["Cleaned_Ingredients"].apply(score)
    results = df[df["score"] > 0].sort_values(by="score", ascending=False).head(top_n)

    matched = set()
    for ing in user_ingredients:
        ing_stem = stem_words(ing)
        if any(ing_stem in stem_words(clean_ingredient_string(r.lower())) for r in results["Cleaned_Ingredients"]):
            matched.add(ing)
    ignored = [ing for ing in user_ingredients if ing not in matched]

    if not results.empty:
        results = results.copy()
        results["Cleaned_Ingredients"] = results["Cleaned_Ingredients"].apply(lambda x: x.strip())
        results["Instructions"] = results["Instructions"].apply(lambda x: x.strip())
    return results, ignored

# ----------------------------- #
#           FLASK              #
# ----------------------------- #

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
                    if extracted:
                        ignored_str = ", ".join(extracted)
                        message += f"<br>Note: All ingredients were ignored or unmatched: {ignored_str}"
                else:
                    recipes = results[["Title", "Cleaned_Ingredients", "Instructions"]].to_dict(orient="records")
                    if ignored:
                        ignored_str = ", ".join(ignored)
                        message = f"Note: These ingredients were ignored in the best match: {ignored_str}<br><br>"

    return render_template("index.html", recipes=recipes, message=message)

if __name__ == "__main__":
    app.run(debug=True)
