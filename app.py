from flask import Flask, request, render_template, jsonify, session
import pandas as pd
import requests
from io import StringIO
import ast
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

instruction_phrases = {
    "divided", "plus more", "melted", "room temperature", "torn into", "thinly sliced",
    "cut into", "cored", "minced", "chopped", "freshly ground", "pinch of", "about",
    "to taste", "as needed", "optional", "pinch", "sliced", "diced"
}

DATA_URL = "https://drive.google.com/uc?export=download&id=1FGgsRPERabERU9dh10dl6GxLaYzme5me"
response = requests.get(DATA_URL)
response.raise_for_status()
df = pd.read_csv(StringIO(response.text))

def parse_ingredient_list(ingredients_str):
    if pd.isna(ingredients_str) or not str(ingredients_str).strip():
        return []
    try:
        ingredients = ast.literal_eval(ingredients_str)
        if not isinstance(ingredients, list):
            return []
    except (ValueError, SyntaxError):
        ingredients = [str(ingredients_str)]
    cleaned = []
    for ing in ingredients:
        if isinstance(ing, str):
            ing_clean = ing.replace('\n', ' ').replace('\r', ' ').strip().lower()
            if ing_clean:
                if any(phrase in ing_clean for phrase in instruction_phrases):
                    continue
                cleaned.append(ing_clean)
    return cleaned

all_keywords = set()
for idx, row in df.iterrows():
    ingredients_list = parse_ingredient_list(row.get('Cleaned_Ingredients', ""))
    all_keywords.update(ingredients_list)
    title = row.get('Title', "")
    if pd.notna(title):
        for word in title.lower().split():
            all_keywords.add(word.strip())
    recipe_text = row.get('Instructions', "")
    if pd.notna(recipe_text):
        for word in recipe_text.lower().split():
            all_keywords.add(word.strip())
ingredient_keywords = list(all_keywords)

def extract_ingredients_from_text(text):
    text_ings = [ing.strip().lower() for ing in text.split(",")]
    extracted = [ing for ing in text_ings if ing in ingredient_keywords]
    ignored = [ing for ing in text_ings if ing not in ingredient_keywords]
    return extracted, ignored

def recommend_one_recipe(user_ingredients):
    user_ingredients = [ingredient.strip().lower() for ingredient in user_ingredients]

    def recipe_ingredients_list(row):
        return parse_ingredient_list(row['Cleaned_Ingredients'])

    def score(row):
        combined_text = " ".join([
            " ".join(recipe_ingredients_list(row)),
            str(row.get('Title', '')).lower(),
            str(row.get('Instructions', '')).lower()
        ])
        return sum(1 for ing in user_ingredients if ing in combined_text)

    df['score'] = df.apply(score, axis=1)
    scored_df = df[df['score'] > 0].sort_values(by='score', ascending=False)
    if scored_df.empty:
        return None, [], user_ingredients

    best = scored_df.iloc[0]
    combined_text = " ".join([
        " ".join(parse_ingredient_list(best['Cleaned_Ingredients'])),
        str(best.get('Title', '')).lower(),
        str(best.get('Instructions', '')).lower()
    ])
    matched_ings = [ing for ing in user_ingredients if ing in combined_text]
    ignored_ings = [ing for ing in user_ingredients if ing not in matched_ings]

    return {
        "Title": best.get('Title', ''),
        "Ingredients": parse_ingredient_list(best['Cleaned_Ingredients']),
        "Instructions": best.get('Instructions', '').strip()
    }, matched_ings, ignored_ings

@app.route("/")
def index():
    return render_template("chat.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "").strip().lower()
    if not user_input:
        return jsonify({"reply": "Please enter some ingredients."})

    state = session.get("state", "awaiting_ingredients")
    suggested_recipe = session.get("suggested_recipe")
    matched_ings = session.get("matched_ings")
    ignored_ings = session.get("ignored_ings")

    def reset_session():
        session.pop("state", None)
        session.pop("suggested_recipe", None)
        session.pop("matched_ings", None)
        session.pop("ignored_ings", None)

    if state == "awaiting_ingredients":
        extracted, initially_ignored = extract_ingredients_from_text(user_input)
        if not extracted:
            return jsonify({"reply": "No known ingredients found. Please try again with different ingredients."})

        recipe, matched_ings, ignored_ings = recommend_one_recipe(extracted)
        if not recipe:
            return jsonify({"reply": "Sorry, I couldn't find any recipe matching those ingredients."})

        reply_parts = []
        if matched_ings:
            reply_parts.append(f"I found a recipe using {', '.join(matched_ings)}.")
        if ignored_ings:
            reply_parts.append(f"But I couldn't find anything with: {', '.join(ignored_ings)}.")
        reply_parts.append(f"How about making {recipe['Title']} today? Please reply with 'ok' or 'no'.")

        session["suggested_recipe"] = recipe
        session["matched_ings"] = matched_ings
        session["ignored_ings"] = ignored_ings
        session["state"] = "awaiting_confirmation"

        return jsonify({"reply": "\n".join(reply_parts)})

    elif state == "awaiting_confirmation":
        if user_input in ["ok", "yes", "yeah", "yup", "sure"]:
            session["state"] = "awaiting_show_ingredients"
            recipe = suggested_recipe
            ingredients_text = "\n- ".join(recipe.get("Ingredients", []))
            return jsonify({"reply": f"Great! Here are the ingredients:\n- {ingredients_text}\n\nDo you want to see the recipe instructions now? (yes/no)"})
        elif user_input in ["no", "nah", "nope"]:
            reset_session()
            return jsonify({"reply": "Okay, no problem! What ingredients do you have instead?"})
        else:
            return jsonify({"reply": "Please reply with 'ok' or 'no'."})

    elif state == "awaiting_show_ingredients":
        if user_input in ["yes", "y", "sure", "yeah"]:
            recipe = suggested_recipe
            session["state"] = "done"
            return jsonify({"reply": f"Here are the instructions:\n{recipe.get('Instructions', '')}\n\nIf you'd like another recipe, just type your ingredients."})
        elif user_input in ["no", "n", "nope"]:
            reset_session()
            return jsonify({"reply": "Alright! If you want another recipe, just type your ingredients."})
        else:
            return jsonify({"reply": "Please reply with 'yes' or 'no'."})

    else:
        reset_session()
        return jsonify({"reply": "Let's start fresh! What ingredients do you have?"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
