from django.core.exceptions import ValidationError

def validate_match_players(players):
    """
    Ensure exactly 4 players are present in a match.
    """
    if len(players) != 4:
        raise ValidationError("A Call Break match must have exactly 4 players.")

def validate_bid(bid, is_blind=False):
    """
    Validate bids based on minimum requirements.
    - Standard minimum bid: 2
    - Blind minimum bid: 5
    """
    if is_blind:
        if bid < 5:
            raise ValidationError(f"Blind bid must be at least 5. Got: {bid}")
    else:
        if bid < 2:
            raise ValidationError(f"Minimum bid is 2. Got: {bid}")
    
    if bid > 13:
        raise ValidationError(f"Bid cannot exceed 13. Got: {bid}")

def validate_tricks(tricks_dict):
    """
    Validate trick count list.
    tricks_dict: dict of player_id/name -> tricks_won (int)
    - Must be exactly 4 entries.
    - Each entry must be between 0 and 13.
    - Sum of all tricks must be exactly 13.
    """
    if len(tricks_dict) != 4:
        raise ValidationError("Must submit trick results for exactly 4 players.")
        
    total_tricks = 0
    for player, tricks in tricks_dict.items():
        if tricks < 0 or tricks > 13:
            raise ValidationError(f"Tricks won by {player} must be between 0 and 13. Got: {tricks}")
        total_tricks += tricks
        
    if total_tricks != 13:
        raise ValidationError(f"Total tricks won across all players must equal 13. Got: {total_tricks}")
