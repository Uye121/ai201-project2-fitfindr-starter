# tests/test_tools.py
import pytest
import tools
from unittest.mock import patch

# ── Mock Groq client ─────────────────────────────────────────────────────────

class _MockMessage:
    def __init__(self, content):
        self.content = content

class _MockChoice:
    def __init__(self, content):
        self.message = _MockMessage(content)

class _MockResponse:
    def __init__(self, content):
        self.choices = [_MockChoice(content)]

class _MockClient:    
    def __init__(self, content="mock LLM reply"):
        self._content = content
        self.calls = []
        self.chat = self
        self.completions = self
    
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _MockResponse(self._content)
    
class FailingClient:
    def __init__(self):
        self.chat = self
        self.completions = self
    
    def create(self, **kwargs):
        raise Exception("API connection failed")

def failing_client_factory():
    return FailingClient()

@pytest.fixture
def mock_llm(monkeypatch):
    client = _MockClient()
    monkeypatch.setattr(tools, "_get_groq_client", lambda: client)
    return client


# ── Tool 1: search_listings tests ────────────────────────────────────────────

MOCK_LISTINGS = [
    {
        "id": "lst_001",
        "title": "Y2K Baby Tee Butterfly Print",
        "description": "Cropped baby tee with butterfly print",
        "category": "tops",
        "style_tags": ["y2k", "vintage"],
        "size": "S/M",
        "condition": "good",
        "price": 18.0,
        "colors": ["pink", "white"],
        "brand": None,
        "platform": "depop",
    },
    {
        "id": "lst_002", 
        "title": "Vintage Levi's Jeans",
        "description": "Classic 90s denim jeans",
        "category": "bottoms",
        "style_tags": ["vintage", "denim"],
        "size": "W30 L30",
        "condition": "good",
        "price": 38.0,
        "colors": ["blue"],
        "brand": "Levi's",
        "platform": "depop",
    },
]

SAMPLE_ITEM = MOCK_LISTINGS[0]

WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "White tank top",
            "category": "tops",
            "colors": ["white"],
        },
        {
            "id": "w_002",
            "name": "Black boots",
            "category": "shoes",
            "colors": ["black"],
        },
    ]
}

@pytest.fixture
def mock_listings(monkeypatch):
    """Fixture that replaces load_listings with mock data."""
    monkeypatch.setattr("tools.load_listings", lambda: MOCK_LISTINGS)
    return MOCK_LISTINGS

def test_search_result(mock_listings):
    results = tools.search_listings("pink top", size="m")
    assert len(results) == 1
    assert all(isinstance(item, dict) for item in results)

def test_search_returns_empty_when_no_matches(mock_listings):
    results = tools.search_listings("zzzznomatchquery", max_price=10000)
    assert results == []

def test_search_by_max_price(mock_listings):
    results = tools.search_listings("tee", max_price=20.0)
    assert all(item["price"] <= 20.0 for item in results)

def test_search_by_size(mock_listings):
    results = tools.search_listings("jeans", size="W30 L30")
    assert all(item["size"] == "W30 L30" for item in results)

# ── Tool 2: suggest_outfit tests ────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe(mock_llm):
    """Test suggest_outfit returns a suggestion when wardrobe has items."""
    result = tools.suggest_outfit(SAMPLE_ITEM, WARDROBE)
    
    # Should return a non-empty string
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    
    # Verify LLM was called with wardrobe items in prompt
    assert len(mock_llm.calls) == 1
    prompt = "".join(m["content"] for m in mock_llm.calls[0]["messages"])
    assert "White tank top" in prompt or "Black boots" in prompt

def test_suggest_outfit_empty_wardrobe(mock_llm):
    """Test suggest_outfit handles empty wardrobe gracefully."""
    empty_wardrobe = {"items": []}
    result = tools.suggest_outfit(SAMPLE_ITEM, empty_wardrobe)
    
    # Should return general advice (non-empty string)
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    
    # Verify different prompt was used (no wardrobe items mentioned)
    prompt = "".join(m["content"] for m in mock_llm.calls[0]["messages"])
    assert any(phrase in prompt for phrase in ["Get some", "Get a", "French tuck", "styling tip"])

def test_suggest_outfit_missing_items_key(mock_llm):
    """Test suggest_outfit handles wardrobe dict without 'items' key."""
    result = tools.suggest_outfit(SAMPLE_ITEM, {})
    
    # Should treat as empty wardrobe
    assert isinstance(result, str)
    assert len(result.strip()) > 0

def test_suggest_outfit_api_failure_fallback(monkeypatch):
    """FAILURE CASE: API call fails → returns fallback message, not exception."""    
    # Mock the Groq client to fail
    monkeypatch.setattr(tools, "_get_groq_client", failing_client_factory)
    
    # Should not raise exception
    result = tools.suggest_outfit(SAMPLE_ITEM, WARDROBE)
    
    # Should return a fallback message
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    assert "trouble" in result.lower() or "generally" in result.lower()

# ── Tool 3: create_fit_card tests ────────────────────────────────────────────
def test_create_fit_card_returns_caption(mock_llm):
    """Test create_fit_card returns a non-empty caption."""
    outfit = "Pair the Y2K Baby Tee with your white tank top and black boots. Tuck the front for a relaxed fit."
    result = tools.create_fit_card(outfit, SAMPLE_ITEM)
    
    # Should return a non-empty string
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    
    # Verify LLM was called
    assert len(mock_llm.calls) == 1
    
    # Verify item details were passed to prompt
    prompt = "".join(m["content"] for m in mock_llm.calls[0]["messages"])
    assert "Y2K Baby Tee" in prompt
    assert "18.0" in prompt
    assert "depop" in prompt

def test_create_fit_card_uses_high_temperature(mock_llm):
    """Test create_fit_card uses temperature >= 0.85 for variety."""
    outfit = "Pair with baggy jeans and chunky sneakers."
    tools.create_fit_card(outfit, SAMPLE_ITEM)
    
    # Verify high temperature was set
    assert mock_llm.calls[0]["temperature"] >= 0.85

def test_create_fit_card_passes_outfit_to_prompt(mock_llm):
    """Test the outfit suggestion is included in the prompt."""
    outfit = "Test outfit: wear with red skirt and white sneakers. Roll the sleeves."
    tools.create_fit_card(outfit, SAMPLE_ITEM)
    
    prompt = "".join(m["content"] for m in mock_llm.calls[0]["messages"])
    assert outfit in prompt

def test_create_fit_card_empty_outfit_guard():
    """FAILURE CASE: Empty outfit string returns error message, no API call."""
    # Test with empty string
    result = tools.create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "Couldn't generate" in result or "no outfit" in result.lower()

def test_create_fit_card_api_failure_fallback(monkeypatch):
    """FAILURE CASE: API call fails → returns fallback caption, not exception."""
    # Create a client that raises an exception
    class FailingClient:
        def __init__(self):
            self.chat = self
            self.completions = self
        
        def create(self, **kwargs):
            raise Exception("API connection failed")
    
    def failing_client_factory():
        return FailingClient()
    
    # Mock the Groq client to fail
    monkeypatch.setattr(tools, "_get_groq_client", failing_client_factory)
    
    outfit = "Pair with wide-leg jeans and platform boots."
    result = tools.create_fit_card(outfit, SAMPLE_ITEM)
    
    # Should return a fallback message, not raise exception
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    assert "Styled this" in result or "Just styled" in result
