from django.db.models import Max, Avg
from apps.matches.models import Player, Match, MatchPlayer, MatchScore
from apps.rounds.models import Round, Bid, RoundResult

def get_player_stats(player):
    """
    Calculate stats for a given player:
    - Win %: (completed matches won / completed matches played) * 100
    - Highest Score: Maximum total score achieved in a completed match
    - Avg Bid: Average of all bids placed by the player
    - Blind Success Rate: (successful blind bids / total blind bids) * 100
    """
    # Matches played (completed only)
    participated_matches = MatchPlayer.objects.filter(player=player, match__status='MATCH_COMPLETE').values_list('match_id', flat=True)
    matches_played = len(participated_matches)
    
    # Matches won (highest score in completed match)
    matches_won = 0
    for match_id in participated_matches:
        scores = MatchScore.objects.filter(match_id=match_id)
        if not scores.exists():
            continue
        max_score = scores.aggregate(Max('total_score'))['total_score__max']
        player_score = scores.filter(player=player).first()
        if player_score and player_score.total_score == max_score:
            matches_won += 1
            
    win_rate = (matches_won / matches_played * 100) if matches_played > 0 else 0.0
    
    # Highest match score
    highest_match_score = MatchScore.objects.filter(player=player, match__status='MATCH_COMPLETE').aggregate(Max('total_score'))['total_score__max']
    if highest_match_score is None:
        highest_match_score = 0.0
    else:
        highest_match_score = float(highest_match_score)
        
    # Average bid
    avg_bid = Bid.objects.filter(player=player).aggregate(Avg('bid'))['bid__avg']
    if avg_bid is None:
        avg_bid = 0.0
    else:
        avg_bid = float(avg_bid)
        
    # Blind success rate
    blind_bids = Bid.objects.filter(player=player, is_blind=True)
    total_blind = blind_bids.count()
    successful_blind = 0
    for b in blind_bids:
        # Find result in the same round
        result = RoundResult.objects.filter(round=b.round, player=player).first()
        if result and result.tricks_won >= b.bid:
            successful_blind += 1
            
    blind_success_rate = (successful_blind / total_blind * 100) if total_blind > 0 else 0.0
    
    return {
        'player_id': str(player.id),
        'player_name': player.name,
        'matches_played': matches_played,
        'matches_won': matches_won,
        'win_rate': round(win_rate, 2),
        'highest_match_score': highest_match_score,
        'avg_bid': round(avg_bid, 2),
        'total_blind_bids': total_blind,
        'successful_blind_bids': successful_blind,
        'blind_success_rate': round(blind_success_rate, 2),
    }

def get_all_players_stats():
    """
    Get stats for all players in the system.
    """
    players = Player.objects.all()
    return [get_player_stats(p) for p in players]
