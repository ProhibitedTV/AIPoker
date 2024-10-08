import requests
import json
import re

OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_LIST_URL = "http://localhost:11434/api/tags"

def get_available_models():
    """
    Retrieves the list of available models from the Ollama API.
    
    Returns:
        list: A list of model names.
    """
    try:
        response = requests.get(OLLAMA_LIST_URL)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [model['name'] for model in models]
            return model_names
        else:
            print(f"Error: Unable to retrieve model list. Status code: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error contacting Ollama API: {e}")
        return []

def get_poker_compatible_model():
    """
    Selects a model that is most suitable for playing poker, based on the available models.
    
    Returns:
        str: The model name that is compatible with poker decisions.
    """
    available_models = get_available_models()
    for model in available_models:
        if "llama3" in model or "command-r" in model or "qwen" in model:
            print(f"Using model: {model} for poker decisions")
            return model

    print("No specific poker model found. Using default model: llama3:latest")
    return "llama3:latest"

def sanitize_decision(decision):
    """
    Filters the AI decision to extract only valid poker actions using regex.
    
    Args:
        decision (str): The raw decision response from the AI.
    
    Returns:
        str: A valid poker action (fold, check, bet, raise) or 'check' as a default.
    """
    valid_actions = ["fold", "check", "bet", "raise"]
    action_match = re.search(r'\b(fold|check|bet|raise)\b', decision.lower())
    
    if action_match:
        action = action_match.group(0)
        print(f"AI chose action: {action}")
        return action
    else:
        print(f"Invalid decision received from model: {decision}. Defaulting to 'check'.")
        return "check"  # Default to 'check' if no valid action is found

def get_ai_decision(player_hand, community_cards, max_retries=2):
    """
    Interacts with the Ollama API to get the AI's decision based on the player's hand and community cards.
    
    Args:
        player_hand (list): A list of tuples representing the player's hand (e.g., [(10, 'hearts'), (9, 'diamonds')]).
        community_cards (list): A list of tuples representing the community cards (e.g., [(2, 'clubs'), (5, 'spades')]).

    Returns:
        str: The AI's decision (e.g., "fold", "check", "bet", "raise").
    """
    hand_str = ', '.join([f"{card[0]} of {card[1]}" for card in player_hand])
    community_str = ', '.join([f"{card[0]} of {card[1]}" for card in community_cards])

    prompt = (
        f"Player's hand: {hand_str}. "
        f"Community cards: {community_str}. "
        "Respond with only one action: fold, check, bet, or raise. No explanation."
    )

    model_name = get_poker_compatible_model()
    data = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    # Retry logic in case of invalid responses
    for attempt in range(max_retries):
        try:
            response = requests.post(OLLAMA_API_URL, data=json.dumps(data))
            response.raise_for_status()

            response_json = response.json()
            decision = response_json.get("message", {}).get("content", "").strip().lower()

            # Sanitize the AI's decision to ensure it's a valid poker action
            valid_action = sanitize_decision(decision)
            if valid_action in ["fold", "check", "bet", "raise"]:
                return valid_action

        except requests.exceptions.RequestException as e:
            print(f"Error contacting Ollama API: {e}")
            return "fold"  # Default to folding if there's an error

    # If no valid action was found after retries, default to folding
    print("No valid decision after retries. Defaulting to 'fold'.")
    return "fold"
