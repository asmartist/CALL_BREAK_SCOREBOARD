from decimal import Decimal

def calculate_score(bid, tricks_won, is_blind=False):
    """
    Calculate the score for a player in a round based on the house rules:
    - If tricks_won >= bid:
      - score = bid + min(extra_tricks, 2) * 0.1
      - if is_blind: score *= 2
    - If tricks_won < bid:
      - score = -bid
      - if is_blind: score *= 2
    - If tricks_won == 8:
      - score *= 2 (Exact 8 Tricks rule)
    """
    bid_dec = Decimal(str(bid))
    
    if tricks_won >= bid:
        extra_tricks = tricks_won - bid
        # Capped at Max Extra Tricks = 2
        effective_extra = min(extra_tricks, 2)
        score = (bid_dec * Decimal('10.0')) + (Decimal(str(effective_extra)) * Decimal('1.0'))
        
        if is_blind:
            score *= Decimal('2.0')
    else:
        score = -bid_dec * Decimal('10.0')
            
    # Apply "Exact 8 Tricks: Double Score"
    if tricks_won == 8:
        score *= Decimal('2.0')
        
    return score.quantize(Decimal('0.01'))
