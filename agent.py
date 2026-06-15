"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""
import re
from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }

def _parse_query(query: str) -> dict:
    """
    Extract search description, optional size, and optional max_price from a user
    given query.
    """
    result = {
        "description": "",
        "size": None,
        "max_price": None
    }

    if not query:
        return result

    cleaned_query = query.strip().lower()

    # Extract max_price
    price_patterns = [
        r'\$(\d+(?:\.\d{1,2})?)',  # $30 or $30.50
        r'(\d+(?:\.\d{1,2})?)\s*dollars?',  # 30 dollars
        r'under\s*\$?(\d+(?:\.\d{1,2})?)',  # under $30
        r'less than\s*\$?(\d+(?:\.\d{1,2})?)',  # less than 30
        r'max\s*\$?(\d+(?:\.\d{1,2})?)',  # max $30
        r'up to\s*\$?(\d+(?:\.\d{1,2})?)',  # up to $30
        r'budget of?\s*\$?(\d+(?:\.\d{1,2})?)',  # budget of $30
    ]

    for pattern in price_patterns:
        match = re.search(pattern, cleaned_query)
        if match:
            result["max_price"] = float(match.group(1))
            cleaned_query = cleaned_query.replace(match.group(0), "")
            break

    # Extract size
    size_map = {
        "small": "S", "medium": "M", "large": "L", "xlarge": "XL",
        "extra large": "XL", "xxlarge": "XXL", "extra small": "XS",
        "xxsmall": "XXS", "one size": "ONE SIZE", "onesize": "ONE SIZE",
        "os": "ONE SIZE"
    }
    size_patterns = [
        r' size\s*[:]?\s*([A-Z0-9/]+)',  # size M, size S/M, size 8
        r'\b(size|sized?)\s+([A-Z0-9/]+)\b',  # size medium, sized L
        r'\b(in|a)\s+([A-Z0-9/]+)\b',  # in M, a L
        r'\b(small|medium|large|xlarge|xl|xxl|xs|s|m|l|xl|xxs)\b',  # text sizes
    ]

    for pattern in size_patterns:
        # For patterns with capture groups
        match = re.search(pattern, cleaned_query)
        if match:
            # Get the captured size
            groups = match.groups()
            if groups:
                extracted_size = groups[-1].upper()
            else:
                extracted_size = match.group(0).upper()
            
            # Map text sizes to abbreviations
            if extracted_size.lower() in size_map:
                extracted_size = size_map[extracted_size.lower()]
            
            result["size"] = extracted_size
            cleaned_query = cleaned_query.replace(match.group(0), " ")
            break

    result["description"] = cleaned_query

    return result


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    session = _new_session(query, wardrobe)

    query_dict = _parse_query(query)
    session["parsed"] = query_dict

    listings = search_listings(
        description=query_dict["description"],
        size=query_dict["size"],
        max_price=query_dict["max_price"]
    )

    # If no results, set error and return early
    if not listings:
        error_msg = f"No listings found for '{query_dict['description']}'"
        if query_dict['size']:
            error_msg += f" in size {query_dict['size']}"
        if query_dict['max_price']:
            error_msg += f" under ${query_dict['max_price']}"
        session["error"] = error_msg
        return session

    session["search_results"] = listings
    session["selected_item"] = listings[0]

    suggestion = suggest_outfit(new_item=listings[0], wardrobe=wardrobe)
    session["outfit_suggestion"] = suggestion

    session["fit_card"] = create_fit_card(outfit=suggestion, new_item=listings[0])

    return session

# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
