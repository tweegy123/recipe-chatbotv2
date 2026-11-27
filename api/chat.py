#!C:/Users/Jelly/AppData/Local/Python/pythoncore-3.14-64/python.exe
import json
import os
import sys
import random
import re
import difflib
from pathlib import Path

BASE = Path(os.path.abspath(__file__)).parent
RECIPES = json.loads((BASE / "database.json").read_text(encoding="utf-8"))

PANTRY = {"salt", "pepper", "oil", "water", "sugar"}
MEAT = {"chicken", "pork", "beef", "shrimp", "tuna", "bacon", "sausage", "ham", "fish", "salmon", "squid", "oyster", "bangus", "tilapia", "corned"}
DAIRY_EGG = {"egg", "cheese", "milk", "butter", "cream", "honey"}

# Added categories so the spellchecker ignores them
CATEGORY_WORDS = {"breakfast", "lunch", "dinner", "snack", "dessert", "spicy", "sweet", "savory", "sour", "creamy", "vegan", "vegetarian"}

HELP = ('Hi! Tell me what is in your kitchen. '
        'You can ask for a recipe by name, try "quick vegetarian meals", ask for a flavor like "spicy" or "creamy", or just say "surprise me".')

def norm(word):
    if word.endswith("ies"): return word[:-3] + "y"
    if word.endswith("oes"): return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3: return word[:-1]
    return word

def tokens(text):
    return [norm(w) for w in re.findall(r"[a-z]+", text.lower())]

KEYNAME = {}
for r in RECIPES:
    r["_name_words"] = set(tokens(r["name"]))
    for ing in r["ingredients"]:
        ing["_key"] = tokens(ing["name"])[0]
        KEYNAME.setdefault(ing["_key"], ing["name"])

for r in RECIPES:
    keys = {i["_key"] for i in r["ingredients"]}
    r["_vegetarian"] = not keys & MEAT
    r["_vegan"] = r["_vegetarian"] and not keys & DAIRY_EGG
    r["_spicy"] = bool(keys & {"chili", "cayenne", "sriracha", "paprika", "jalapeno", "pepper"})
    r["_savory"] = bool(keys & {"soy", "oyster", "shrimp", "fish", "cheese", "mushroom", "bacon"})
    r["_sour"] = bool(keys & {"vinegar", "lemon", "calamansi", "tamarind", "tomato"})
    r["_creamy"] = bool(keys & {"cream", "milk", "coconut", "cheese", "butter"})
    r["_sweet"] = bool(keys & {"sugar", "honey", "banana", "mango", "pineapple", "apple"})

VOCAB = {i["_key"] for r in RECIPES for i in r["ingredients"]} - PANTRY
ALL_INGREDIENTS = VOCAB.union(PANTRY)

def get_tools(r):
    text = (r["name"] + " " + " ".join(r["steps"])).lower()
    tools = set(["Knife & Chopping Board"])
    if any(w in text for w in ["boil", "simmer", "soup", "broth", "stew", "porridge", "congee", "blanch"]): tools.add("Pot / Saucepan")
    if any(w in text for w in ["fry", "stir-fry", "sear", "sauté", "pan-fry", "omelette", "scramble"]): tools.add("Frying Pan / Skillet")
    if any(w in text for w in ["bake", "roast", "oven"]): tools.add("Baking Sheet / Oven")
    if "steam" in text: tools.add("Steamer")
    if any(w in text for w in ["blend", "smoothie", "puree"]): tools.add("Blender")
    if any(w in text for w in ["mix", "whisk", "batter", "dough"]): tools.add("Mixing Bowl & Whisk")
    if any(w in text for w in ["grill", "bbq", "char"]): tools.add("Grill Pan / BBQ")
    if len(tools) == 1: tools.add("Frying Pan / Skillet")
    return sorted(list(tools))

def card(r, have=None):
    data = {
        "name": r["name"], "time": r["time"],
        "ingredients": [f'{i["qty"]} {i["name"]}' for i in r["ingredients"]], 
        "steps": r["steps"], "tools": get_tools(r)
    }
    if have is not None:
        needed = [i for i in r["ingredients"] if i["_key"] not in PANTRY]
        data["have"] = [i["name"] for i in needed if i["_key"] in have]
        data["missing"] = [i["name"] for i in needed if i["_key"] not in have]
    return data

def find_by_ingredients(have, pool):
    matches = []
    for r in pool:
        needed = [i for i in r["ingredients"] if i["_key"] not in PANTRY]
        hits = sum(i["_key"] in have for i in needed)
        
        if hits > 0:
            missing = len(needed) - hits
            matches.append((-hits, missing, r["time"], r))
            
    matches.sort(key=lambda t: t[:3])
    ready = [t[3] for t in matches if t[1] == 0]
    almost = [t[3] for t in matches if t[1] > 0]
    return ready, almost

def reply_to(message):
    toks = tokens(message)
    words = set(toks)
    
    have = set()
    for w in words:
        if w in ALL_INGREDIENTS:
            have.add(w)
        # FIX: Ignore category words so they don't get auto-corrected to ingredients
        elif w not in CATEGORY_WORDS: 
            matches = difflib.get_close_matches(w, ALL_INGREDIENTS, n=1, cutoff=0.75)
            if matches: have.add(matches[0])

    banned = set()
    for i, w in enumerate(toks):
        if w in ("no", "without", "dont", "got") and i + 1 < len(toks):
            next_w = toks[i+1]
            if next_w in ALL_INGREDIENTS:
                banned.add(next_w)
            else:
                matches = difflib.get_close_matches(next_w, ALL_INGREDIENTS, n=1, cutoff=0.75)
                if matches: banned.add(matches[0])
                
    have -= banned

    cue = bool(words & {"recipe", "make", "cook", "how", "show", "give", "want"})

    if not toks or (words & {"hi", "hello", "hey", "help"} and not have):
        return {"reply": HELP}

    pool = RECIPES
    if banned:
        pool = [r for r in pool if not any(b in {i["_key"] for i in r["ingredients"]} for b in banned)]

    for r in pool:
        distinct = {w for w in r["_name_words"] if w not in VOCAB and len(w) > 3}
        full = r["_name_words"] <= words
        if (full and (distinct or cue or not (have - r["_name_words"]))) or (distinct & words and (cue or not have)):
            return {"reply": f"Here is how to make {r['name']}:", "recipes": [card(r)], "full": True}

    filters = []
    
    category_found = False
    if "breakfast" in words:
        b_keys = {"egg", "bread", "milk", "bacon", "sausage", "banana", "oats"}
        pool = [r for r in pool if any(i["_key"] in b_keys for i in r["ingredients"]) and r["time"] <= 30]
        filters.append("breakfast")
        category_found = True
    elif "snack" in words:
        s_keys = {"bread", "tortilla", "potato", "banana", "flour", "cheese"}
        pool = [r for r in pool if any(i["_key"] in s_keys for i in r["ingredients"])]
        filters.append("snacks")
        category_found = True
    elif "dessert" in words:
        d_keys = {"sugar", "honey", "banana", "mango", "avocado", "strawberry", "pineapple", "milk"}
        pool = [r for r in pool if r["_sweet"] or any(i["_key"] in d_keys for i in r["ingredients"])]
        filters.append("dessert")
        category_found = True
    elif "lunch" in words or "dinner" in words:
        pool = [r for r in pool if r["_savory"] or any(i["_key"] in ["rice", "pasta", "noodles"] for i in r["ingredients"])]
        filters.append("main dishes")
        category_found = True

    if not category_found:
        for diet in ("vegan", "vegetarian"):    
            if diet in words:
                pool = [r for r in pool if r["_" + diet]]
                filters.append(diet)
                break

        if words & {"spicy", "hot", "kick", "spice"}:
            pool = [r for r in pool if r["_spicy"]]
            filters.append("spicy")
        if words & {"savory", "umami", "salty", "rich"}:
            pool = [r for r in pool if r["_savory"]]
            filters.append("savory")
        if words & {"sour", "tangy", "acidic"}:
            pool = [r for r in pool if r["_sour"]]
            filters.append("sour")
        if words & {"creamy"}:
            pool = [r for r in pool if r["_creamy"]]
            filters.append("creamy")
        if words & {"sweet"}:
            pool = [r for r in pool if r["_sweet"]]
            filters.append("sweet")

    m = re.search(r"(\d+)\s*(?:min|minute)", message.lower())
    limit = int(m.group(1)) if m else (30 if words & {"quick", "fast"} else None)
    if limit:
        pool = [r for r in pool if r["time"] <= limit]
        filters.append(f"under {limit} minutes")

    if words & {"surprise", "random"} and pool:
        return {"reply": "How about this one?", "recipes": [card(random.choice(pool))], "full": True}

    # Check if we ONLY have a category/filter and no ingredients
    if have:
        ready, almost = find_by_ingredients(have, pool)
        combined = ready + almost
        
        if combined:
            combined = combined[:10]
            
            names = sorted(KEYNAME.get(k, k) for k in have)
            text = ", ".join(names[:-1]) + (" and " if len(names) > 1 else "") + names[-1]
            
            if banned:
                ban_text = ", ".join(sorted(banned))
                filter_msg = f" (excluding {ban_text})"
            else:
                filter_msg = ""

            if ready and not almost:
                msg = f"With {text}{filter_msg}, you can cook these right now:"
            elif ready and almost:
                msg = f"With {text}{filter_msg}, you can cook these right now, plus a few you are close to:"
            else:
                msg = f"You don't have all the ingredients for a full recipe yet. But here are some ideas that use {text}{filter_msg}:"
                
            return {"reply": msg, "recipes": [card(r, have) for r in combined]}
            
        return {"reply": "I don't have any recipes with those ingredients. Try adding something else!"}

    # If they typed a category but NO ingredients
    if filters:
        if not pool:
            return {"reply": "No recipes match that combination. Try removing a filter."}
        picks = sorted(pool, key=lambda r: r["time"])
        return {"reply": f"Here are some {' and '.join(filters)} options:", "recipes": [card(r) for r in picks]}

    return {"reply": "I did not catch that. " + HELP}

def main():
    message = ""
    if os.environ.get("REQUEST_METHOD") == "POST":
        size = int(os.environ.get("CONTENT_LENGTH") or 0)
        try:
            message = json.loads(sys.stdin.buffer.read(size).decode("utf-8")).get("message", "").strip()
        except ValueError:
            message = ""
    body = json.dumps(reply_to(message[:300])).encode("utf-8")
    sys.stdout.buffer.write(b"Content-Type: application/json; charset=utf-8\r\n\r\n" + body)

if __name__ == "__main__":
    main()