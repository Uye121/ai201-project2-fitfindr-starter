# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py     # then open the URL printed in your terminal
```

Run the tests:

```bash
pytest tests/ -v
```

---

## Tool Inventory
All tools live inside [tools.py](tools.py). Below are the type signature and specs on them.

### 1. `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

Searches the listings dataset for secondhand items matching the user's description, then filters by an optional size and price ceiling. Returns the matches sorted by how well they fit the description, best first.

**Input parameters:**
- `description` (str): keywords describing the desired item (e.g. "vintage graphic tee")
- `size` (str | None): clothing size to filter by; `None` skips size filtering. Matching is case-insensitive (e.g. "M" matches "S/M")
- `max_price` (float | None): maximum price, inclusive; `None` skips price filtering

**Returns:** a matching listing, sorted by relevance (best match first). Each listing dict has the fields that live in the dataset:
- id (str): unique listing identifier
- title (str): listing title
- description (str): full item description
- category (str): one of tops, bottoms, outerwear, shoes, accessories
- style_tags (list[str]): style descriptors used for scoring
- size (str): item size
- condition (str): excellent, good, or fair
- price (float): listed price
- colors (list[str]): colors present in the item
- brand (str | None): brand, or `None`
- platform (str): the listing source

---

### 2. `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

Takes the selected thrift item and the user's wardrobe to suggest complete outfit combinations, naming specific wardrobe pieces to pair with the new item.

**Input parameters:**
- `new_item` (dict): a listing dictionary
- `wardrobe` (dict): the user's clothing inventory that can be empty.

**Returns:** a string containing the outfit suggestion.

---

### 3. `create_fit_card(outfit: str, new_item: dict) -> str`

Generates a short, social-media-ready caption (the kind you'd post with an OOTD photo) from the outfit suggestion and the thrifted item.

**Input parameters:**
- `outfit` (str): the outfit suggestion
- `new_item` (dict): the selected listing dict

**Returns:** a casual caption that names the item / price / platform once each, and captures the outfit's vibe.

---

## Planning Loop

`run_agent(query, wardrobe)` in [agent.py](agent.py) runs a sequence of decisions, using the session state to choose the next course of action.

1. Parse the query to extract the description, size, max_price.

2. Call search_listings() and store result into session["search_results"].

- If empty (=[]), create a helpful error message with the given constraints and store it into session["error"]. Stop immediately.

- If not empty, set session["selected_item"] = search_results[0] and move to the next step.

3. Call suggest_outfit() and store the returned string in session["outfit_suggestion"]. This tool internally branches on whether the wardrobe is empty. It will always return some sort of string.

4. Call create_fit_card() and store result in session["fit_card"].

5. Return session.

---

## State Management

All state for a single interaction lives in one `session` dict created by `_new_session()` in [agent.py](agent.py). It is the single source of truth for the run. Every tool read and write to it in order to preserve state data across tools.

---

## Error Handling

| Tool | Failure mode | What the agent does | Tested example |
|------|--------------|---------------------|----------------|
| `search_listings` | no matches | returns `[]`; loop sets a specific error and stops | `search_listings("nightgown", "XXL", 50)` → `[]`. Agent outputs: "No listings found for '  nightgown under ' in size XXL under $50.0" |
| `suggest_outfit` | empty wardrobe | returns general styling advice instead of crashing | `suggest_outfit(item, <empty wardrobe>)`. Agent outputs general advice paragraph for the item |
| `create_fit_card` | empty/missing outfit | returns a descriptive error string | `create_fit_card("", item)` → *"Couldn't generate a fit card because no outfit suggestion was available."* |

---

## Spec Reflection

- Front loading most of the effort into planning every tool and their interaction helps think about how to handle edge cases and a better idea of how everything fits together before actually generating the code mindlessly.

- Common stop words were removed from the description in search_listings in order to better search for the right listing else it will match the wrong things due to the way its implemented.

---

## AI Usage

I gave Claude my tool specs from planning.md one at a time and tested each. For each tool, I used Claude as an assistant to iteratively fix and update the code until it is doing what I specified in planning.md.

I asked Claude to generate a query parser using regex, keeping in mind the type of data I am using (e.g., clothing). I tested the parsing with different commonly used text from online. However, Claude overcomplicated the regex patterns, so I had to simplify them and optimize the way it removes pricing and clothing size from the query text. The original approach used separate loops that handled them inefficiently.