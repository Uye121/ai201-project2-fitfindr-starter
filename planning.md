# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Searches the listings dataset for secondhand items matching the user's description, then filters by an optional size and price ceiling. Returns the matches sorted by how well they fit the description, best first.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): keywords describing the desired item (e.g. "vintage graphic tee")
- `size` (str | None): clothing size to filter by; `None` skips size filtering. Matching is case-insensitive (e.g. "M" matches "S/M")
- `max_price` (float | None): maximum price, inclusive; `None` skips price filtering

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
Returns a matching listing, sorted by relevance (best match first). Each listing dict has the fields that live in the dataset:
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

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
It returns an empty list [] when nothing matches, then stop without moving to the next step. It will return a helpful error message with the given constraints and store it in session["error"].

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Takes the selected thrift item and the user's wardrobe to suggest complete outfit combinations, naming specific wardrobe pieces to pair with the new item.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): a listing dictionary
- `wardrobe` (dict): the user's clothing inventory that can be empty.

**What it returns:**
<!-- Describe the return value -->
Returns a string containing the outfit suggestion.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If wardrobe is empty, it falls back to general styling advice for the new item (what kinds of pieces pair well, what vibe it suits) instead of naming specific wardrobe items. If the LLM call itself errors, the tool catches the exception and returns a short descriptive message string so the loop can surface it and stop.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Generates a short, social-media-ready caption (the kind you'd post with an OOTD photo) from the outfit suggestion and the thrifted item.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): the outfit suggestion
- `new_item` (dict): the selected listing dict

**What it returns:**
<!-- Describe the return value -->
Returns a casual caption that names the item / price / platform once each, and captures the outfit's vibe.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
It first guards against an empty or whitespace-only outfit string. If the input is missing/incomplete it returns a short descriptive error-message string. If the LLM call errors, it is caught and likewise returned as a message string so the loop can report it.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
The loop runs in a sequence, i.e. it only advances to the next tool if the previous tool produced usable output. 

**Step 1 - parse the query to extract the description, size, max_price.

**Step 2 - Call search_listings() and store result into session["search_results"].

- If empty (=[]), create a helpful error message with the given constraints and store it into session["error"]. Stop immediately.

- If not empty, set session["selected_item"] = search_results[0] and move to the next step.

**Step 3 - Call suggest_outfit() and store the returned string in session["outfit_suggestion"]. This tool internally branches on whether the wardrobe is empty. It will always return some sort of string.

**Step 4 - Call create_fit_card() and store result in session["fit_card"].

**Step 5 - Return session.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
All state for a single interaction lives in one `session` dict created by `_new_session()` in [agent.py](agent.py). It is the single source of truth for the run. Every tool read and write to it in order to preserve state data across tools.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query (returns `[]`) | Loop detects the empty list, writes a helpful `session["error"]` witht the given constraints, and returns early **before** calling `suggest_outfit`. |
| suggest_outfit | Wardrobe is empty (`wardrobe["items"] == []`) | Not treated as a failure; the tool returns general styling advice for the new item instead of naming specific pieces, and the run continues to the fit card. If the LLM call itself raises, it's caught and returned as a message string. |
| create_fit_card | Outfit input is missing or incomplete (empty/whitespace `outfit`) | Tool guards the input and returns a short descriptive message string instead of a caption. LLM errors are caught the same way. The loop stores it in `session["fit_card"]` so the user still sees what went wrong. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->
User query  +  wardrobe choice
    │
    ▼
Parse query ──► session["parsed"] = {description, size, max_price}
    │
    ▼
Planning Loop ───────────────────────────────────────────────────────┐
    │                                                                 │
    ├─► search_listings(description, size, max_price)                 │
    │        │                                                        │
    │        │ results == []                                          │
    │        ├──► session["error"] = "No listings found using …"      │
    │        │     return session  ──► fit_card stays None  [ERROR ✗] │
    │        │                                                        │
    │        │ results == [item, …]                                   │
    │        ▼                                                        │
    │   session["selected_item"] = results[0]                         │
    │        │                                                        │
    ├─► suggest_outfit(selected_item, wardrobe)                       │
    │        │   (internal branch: if empty wardrobe → general        │
    │        │    advice; else → outfit naming wardrobe pieces)       │
    │        ▼                                                        │
    │   session["outfit_suggestion"] = "…"                            │
    │        │                                                        │
    └─► create_fit_card(outfit_suggestion, selected_item)             │
             │   (if empty outfit → error string)                     │
             ▼                                                        │
        session["fit_card"] = "…"                                     │
             │                                  error path returns ───┘
             ▼
        Return session (shared state dictionary that tools write to and read from)

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
I use Claude as an assistant to go through each tool in Tools section at a time. For each tool, we follow an iterative cycle: the AI create an initial implementation, I tweak and fix it, then I ask the AI to suggest improvements, and I handle the final fixes. I run several test events to ensure proper output.

**Milestone 4 — Planning loop and state management:**
I share the Planning Loop, State Management, and Architecture sections of this planning.md with Claude, and we work through run_agent() together. We talk through each decision point — especially the empty-results branch and how the session dict carries selected_item and outfit_suggestion between tools — and I review the generated loop to confirm it branches on the search result and doesn't just call all three tools in a fixed order before we keep it.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:** The user query is parsed and passed into the tool search_listings("vintage graphic tee", size="M", max_price=30.0). The tool returns the top 3 matching listings sorted by relevance. The top listing is stored into session["selected_item"].

**Step 2:** FitFindr calls suggest_outfit(new_item=session["selected_item"], wardrobe=<user's wardrobe>), which would generate some output description "Pair this with your wide-leg jeans and platform Docs for a classic 90s grunge look. Roll the sleeves once and tuck the front corner slightly for shape." It is stored into session["outfit_suggestion"].

**Step 3:** FitFindr calls create_fit_card(outfit=session["outfit_suggestion"], new_item=<new item>). It returns some casual description such as "thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories", which is stored in session["fit_card"].

**Final output to user:** "thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"

