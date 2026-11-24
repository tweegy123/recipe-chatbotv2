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
MEAT = {"chicken", "pork", "beef", "shrimp", "tuna", "bacon", "sausage", "ham", "fish", "salmon", "squid", "oyster"}
DAIRY_EGG = {"egg", "cheese", "milk", "butter", "cream", "honey"}

HELP = ('Hi! Tell me what is in your kitchen. '
        'You can also ask for a recipe by name, try "quick vegetarian meals", ask for a flavor like "spicy" or "creamy", or just say "surprise me". '
        'I assume you always have salt, pepper, oil, water and sugar.')

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

# --- NEW: Automatically tag flavors based on ingredients ---
for r in RECIPES:
    keys = {i["_key"] for i in r["ingredients"]}
    r["_vegetarian"] = not keys & MEAT
    r["_vegan"] = r["_vegetarian"] and not keys & DAIRY_EGG
    
    # Flavor Tagging
    r["_spicy"] = bool(keys & {"chili", "cayenne", "sriracha", "paprika", "jalapeno", "pepper"})
    r["_savory"] = bool(keys & {"soy", "oyster", "shrimp", "fish", "cheese", "mushroom", "bacon"})
    r["_sour"] = bool(keys & {"vinegar", "lemon", "calamansi", "tamarind", "tomato"})
    r["_creamy"] = bool(keys & {"cream", "milk", "coconut", "cheese", "butter"})
    r["_sweet"] = bool(keys & {"sugar", "honey", "banana", "mango", "pineapple", "apple"})
# -----------------------------------------------------------

VOCAB = {i["_key"] for r in RECIPES for i in r["ingredients"]} - PANTRY

def card(r, have=None):
    data = {"name": r["name"], "time": r["time"],
            "ingredients": [f'{i["qty"]} {i["name"]}' for i in r["ingredients"]], "steps": r["steps"]}
    if have is not None:
        needed = [i for i in r["ingredients"] if i["_key"] not in PANTRY]
        data["have"] = [i["name"] for i in needed if i["_key"] in have]
        data["missing"] = [i["name"] for i in needed if i["_key"] not in have]
    return data

def find_by_ingredients(have, pool):
    ready, close = [], []
    for r in pool:
        needed = [i for i in r["ingredients"] if i["_key"] not in PANTRY]
        hits = sum(i["_key"] in have for i in needed)
        if hits:
            missing = len(needed) - hits
            (ready if missing == 0 else close).append((-hits, missing, r["time"], r))
    ready.sort(key=lambda t: t[:3])
    close.sort(key=lambda t: t[:3])
    ready = [t[3] for t in ready]
    close = [t[3] for t in close]
    return ready, close

def reply_to(message):
    toks = tokens(message)
    words = set(toks)
    
    have = set()
    for w in words:
        if w in VOCAB:
            have.add(w)
        else:
            matches = difflib.get_close_matches(w, VOCAB, n=1, cutoff=0.75)
            if matches: have.add(matches[0])

    cue = bool(words & {"recipe", "make", "cook", "how", "show"})

    if not toks or (words & {"hi", "hello", "hey", "help"} and not have):
        return {"reply": HELP}

    # 1. the name of Recipe
    for r in RECIPES:
        distinct = {w for w in r["_name_words"] if w not in VOCAB and len(w) > 3}
        full = r["_name_words"] <= words
        if (full and (distinct or cue or not (have - r["_name_words"]))) or (distinct & words and (cue or not have)):
            return {"reply": f"Here is how to make {r['name']}:", "recipes": [card(r)], "full": True}

    pool, filters = RECIPES, []
    
    # 2. Diet filters
    for diet in ("vegan", "vegetarian"):    
        if diet in words:
            pool = [r for r in pool if r["_" + diet]]
            filters.append(diet)
            break

    # --- NEW: Flavor Filters ---
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
    # ---------------------------

    m = re.search(r"(\d+)\s*(?:min|minute)", message.lower())
    limit = int(m.group(1)) if m else (30 if words & {"quick", "fast"} else None)
    if limit:
        pool = [r for r in pool if r["time"] <= limit]
        filters.append(f"under {limit} minutes")

    # 3. Surprise me
    if words & {"surprise", "random"} and pool:
        return {"reply": "How about this one?", "recipes": [card(random.choice(pool))], "full": True}

    # 4. Search by ingredients
    if have:
        ready, close = find_by_ingredients(have, pool)
        if ready or close:
            names = sorted(KEYNAME[k] for k in have)
            text = ", ".join(names[:-1]) + (" and " if len(names) > 1 else "") + names[-1]
            flavor_txt = f" ({', '.join(filters)})" if filters else ""
            
            if ready and close:
                msg = f"With {text}{flavor_txt}, you can cook these right now, plus a few you are close to:"
            elif ready:
                msg = f"With {text}{flavor_txt}, you can cook these right now:"
            else:
                msg = f"Nothing is fully ready yet, but these use {text} and only need a few more ingredients:"
            return {"reply": msg, "recipes": [card(r, have) for r in ready + close]}
        return {"reply": "None of my recipes match those yet. Try adding another ingredient or changing the flavor."}

    # 5. Browse by filter only
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