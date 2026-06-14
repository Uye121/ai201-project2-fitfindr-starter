"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings, get_example_wardrobe, get_empty_wardrobe

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    all_listings = load_listings()
    
    # Filter by max_price
    filtered_listings = all_listings
    if max_price is not None:
        filtered_listings = [
            item for item in filtered_listings 
            if item.get("price", float('inf')) <= max_price
        ]
    
    # Filter by size (case-insensitive)
    if size is not None:
        size_lower = size.lower()
        filtered_listings = [
            item for item in filtered_listings 
            if size_lower in item.get("size", "").lower()
        ]
    
    # Score each remaining listing by keyword overlap
    # Clean and tokenize the description
    description_lower = description.lower()
    # Split into words, remove common stop words and punctuation
    stop_words = {'a', 'an', 'and', 'the', 'of', 'for', 'to', 'in', 'on', 'at', 'with', 'by', 'is', 'are', 'was', 'were'}
    keywords = set(
        word.strip('.,!?;:()[]{}"\'')
        for word in description_lower.split()
        if word not in stop_words and len(word) > 2
    )
    
    scored_listings = []
    for item in filtered_listings:
        score = 0
        
        # Check title
        title_lower = item.get("title", "").lower()
        title_score = sum(1 for kw in keywords if kw in title_lower)
        
        # Check description
        desc_lower = item.get("description", "").lower()
        desc_score = sum(1 for kw in keywords if kw in desc_lower) * 0.5  # Half weight for description
        
        # Check style tags (bonus for matching style descriptors)
        style_tags = item.get("style_tags", [])
        style_lower = " ".join(style_tags).lower()
        style_score = sum(1 for kw in keywords if kw in style_lower) * 1.5  # Extra weight for style tags
        
        # Check category
        category_lower = item.get("category", "").lower()
        category_score = sum(1 for kw in keywords if kw in category_lower) * 0.8
        
        # Check colors
        colors = item.get("colors", [])
        colors_lower = " ".join(colors).lower()
        colors_score = sum(1 for kw in keywords if kw in colors_lower) * 0.7
        
        total_score = title_score + desc_score + style_score + category_score + colors_score
        
        if total_score > 0:
            scored_listings.append((total_score, item))
    
    # Step 4: Sort by score, highest first
    scored_listings.sort(key=lambda x: x[0], reverse=True)
    
    # Step 5: Return just the listing dicts (without scores)
    return [item for score, item in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    # Check if wardrobe is empty
    wardrobe_items = wardrobe.get("items", [])
    is_wardrobe_empty = len(wardrobe_items) == 0
    
    # Format new item details for the prompt
    new_item_info = f"""
        Item to style:
        - Title: {new_item.get('title', 'Unknown')}
        - Category: {new_item.get('category', 'Unknown')}
        - Style tags: {', '.join(new_item.get('style_tags', []))}
        - Colors: {', '.join(new_item.get('colors', []))}
        - Condition: {new_item.get('condition', 'Unknown')}
        - Brand: {new_item.get('brand', 'Unknown brand')}
        - Description: {new_item.get('description', 'No description provided')}
        """
    
    if is_wardrobe_empty:
        # Fallback: General styling advice when wardrobe is empty
        prompt = f"""You are a fashion stylist giving buying advice for someone with an empty wardrobe.

        New item: {new_item.get('title', 'Unknown')} ({', '.join(new_item.get('colors', []))}, {new_item.get('category', 'Unknown')})

        Give 1-2 outfit formulas suggesting TYPES of clothing they should buy to go with this item:
        - Write as a single paragraph (no bullet points, no numbered lists)
        - Use "a", "your", or general categories (e.g., "a pair of wide-leg jeans", "some chunky boots")
        - DO NOT pretend they already own specific items
        - Include 1 styling tip per outfit
        - Be direct and concise

        Example: "Get some wide-leg jeans and platform sneakers. French tuck the front."

        Return only the suggestions, nothing else."""
    else:
        # Format wardrobe items for the prompt
        wardrobe_list = []
        for item in wardrobe_items[:15]:  # Limit to 15 items to avoid token overload
            item_info = f"- {item.get('category', 'Unknown')}: {item.get('name', 'Unknown')}"
            if item.get('colors'):
                item_info += f" ({', '.join(item.get('colors', []))})"
            if item.get('style_tags'):
                item_info += f" [{', '.join(item.get('style_tags', []))}]"
            wardrobe_list.append(item_info)
        
        wardrobe_text = "\n".join(wardrobe_list) if wardrobe_list else "No wardrobe items available"
        
        prompt = f"""You are a fashion stylist giving quick, actionable advice.

        New item: {new_item.get('title', 'Unknown')} ({', '.join(new_item.get('colors', []))}, {new_item.get('category', 'Unknown')})

        User's wardrobe includes:
        {wardrobe_text}

        Give 1-2 outfit suggestions following these rules:
        - Write as a single paragraph (no bullet points, no numbered lists)
        - Be direct and concise (like a friend giving advice)
        - Name specific pieces from their wardrobe
        - Include 1 quick styling tip per outfit (tuck, roll, layer, etc.)
        - Use "and" or "or" to separate multiple suggestions
        - NO explanations of why it works
        - NO "I'm excited" or similar commentary
        - NO meta statements
        - NO line breaks

        Example: "Pair with your wide-leg jeans and platform Docs for a classic 90s grunge look. Roll the sleeves once and tuck the front corner slightly for shape. Or try with your black leggings and chunky sneakers for a sportier vibe."

        Return only the suggestions, nothing else."""

    try:
        client = _get_groq_client()

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful, knowledgeable fashion stylist assistant. Provide practical, encouraging outfit advice."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=300,
        )
        
        suggestion = completion.choices[0].message.content
        
        # Ensure we return a non-empty string
        if not suggestion or not suggestion.strip():
            return "I couldn't generate a specific outfit suggestion, but this item would work well with neutral basics and complementary pieces in similar colors."
        
        return suggestion.strip()
        
    except Exception as e:
        # Catch any LLM errors and return a fallback message
        error_msg = f"Unable to generate outfit suggestion due to an error: {str(e)}"
        print(f"Error in suggest_outfit: {error_msg}")  # For debugging
        return "I'm having trouble creating a detailed outfit suggestion right now. Generally, this item would pair well with complementary neutral pieces and items that match its color palette and style vibe."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)
    """
    # Guard against empty or whitespace-only outfit string
    if not outfit or not outfit.strip():
        return "Couldn't generate a fit card because no outfit suggestion was available."
    
    try:
        # Get Groq client
        client = _get_groq_client()
        
        # Extract item details
        item_title = new_item.get('title', 'this find')
        item_price = new_item.get('price', '?')
        item_platform = new_item.get('platform', 'thrift store')
        item_category = new_item.get('category', 'piece')
        item_colors = ', '.join(new_item.get('colors', [])) if new_item.get('colors') else 'neutral'
        
        prompt = f"""You're posting an OOTD (Outfit Of The Day) photo on Instagram/TikTok. 
            You just thrifted this item and styled it according to the suggestion below.

            ITEM DETAILS:
            - Name: {item_title}
            - Category: {item_category}
            - Colors: {item_colors}
            - Price: ${item_price}
            - Platform: {item_platform}

            OUTFIT SUGGESTION:
            {outfit}

            Write a 2-4 sentence caption for your post. Rules:
            - Sound casual and authentic (like a real person posting, not an ad)
            - Mention the item name, price, and platform exactly once each (natural placement)
            - Capture the specific outfit vibe (e.g., "grungy but make it cute", "lazy sunday energy")
            - NO hashtags
            - NO emojis (unless it's 1-2 max and actually fits)
            - NO "I'm obsessed" or influencer clichés
            - Be concise - short punchy sentences

            Example caption: "Threw this vintage tee ($12 on Depop) over my go-to wide-leg jeans. Giving 90s alt energy without trying too hard. Rolled the sleeves once and called it a day."

            Return ONLY the caption, nothing else."""
        # Make LLM call with higher temperature for variety
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You write authentic, non-cringe social media captions for outfit posts. Be casual, specific, and real."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.85,  # Higher temp for different-sounding captions each time
            max_tokens=150,
        )
        
        caption = completion.choices[0].message.content
        
        # Ensure we return a non-empty string
        if not caption or not caption.strip():
            return f"Just styled this {item_title} (${item_price} on {item_platform}) with pieces from my wardrobe. Such a good find!"
        
        return caption.strip()
        
    except Exception as e:
        # Catch any LLM errors and return a fallback caption
        print(f"Error in create_fit_card: {str(e)}")  # For debugging
        item_title = new_item.get('title', 'this piece')
        item_price = new_item.get('price', '?')
        item_platform = new_item.get('platform', 'thrift store')
        return f"Styled this {item_title} (${item_price} on {item_platform}) with my wardrobe. Loving how it came together!"
