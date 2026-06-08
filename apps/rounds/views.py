import datetime
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.rounds.models import Round, Bid, RoundResult
from apps.rounds.serializers import RoundSerializer
from apps.matches.models import MatchPlayer, MatchScore
from apps.rules.services import validate_bid, validate_tricks
from apps.scoring.services import calculate_score

class RoundViewSet(viewsets.ModelViewSet):
    queryset = Round.objects.all().order_by('round_no')
    serializer_class = RoundSerializer

    @action(detail=True, methods=['put'])
    def bids(self, request, pk=None):
        round_obj = self.get_object()
        
        if round_obj.locked or round_obj.bids_locked:
            return Response(
                {"error": "Bids for this round are locked and cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        payload = request.data
        if isinstance(payload, dict):
            bids_data = payload.get('bids', [])
            should_lock = payload.get('locked', False)
        else:
            bids_data = payload
            should_lock = False

        if not isinstance(bids_data, list) or len(bids_data) != 4:
            return Response(
                {"error": "Must submit bids for exactly 4 players as a list."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Verify players are in this match
        match_player_ids = set(
            MatchPlayer.objects.filter(match=round_obj.match).values_list('player_id', flat=True)
        )
        
        # Validate bids
        bids_to_create = []
        for b_entry in bids_data:
            p_id_str = b_entry.get('player_id')
            bid_val = b_entry.get('bid')
            is_blind = b_entry.get('is_blind', False)
            
            try:
                from uuid import UUID
                p_uuid = UUID(p_id_str)
            except (ValueError, TypeError):
                return Response(
                    {"error": f"Invalid player_id UUID: {p_id_str}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if p_uuid not in match_player_ids:
                return Response(
                    {"error": f"Player {p_id_str} is not registered in this match."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                bid_val = int(bid_val)
                validate_bid(bid_val, is_blind)
            except (ValueError, TypeError, ValidationError) as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            bids_to_create.append((p_uuid, bid_val, is_blind))
            
        # Save bids within a transaction
        with transaction.atomic():
            for p_uuid, bid_val, is_blind in bids_to_create:
                Bid.objects.update_or_create(
                    round=round_obj,
                    player_id=p_uuid,
                    defaults={'bid': bid_val, 'is_blind': is_blind}
                )
            
            # Transition round and match states
            round_obj.status = 'PLAYING'
            if should_lock:
                round_obj.bids_locked = True
            else:
                round_obj.bids_locked = False
            round_obj.save()
            
            match = round_obj.match
            match.status = 'PLAYING'
            match.save()
            
        serializer = self.get_serializer(round_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['put'])
    def results(self, request, pk=None):
        round_obj = self.get_object()
        
        if round_obj.locked:
            return Response(
                {"error": "This round is locked and cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        payload = request.data
        if isinstance(payload, dict):
            results_data = payload.get('results', [])
            should_lock = payload.get('locked', True)
        else:
            results_data = payload
            should_lock = True
            
        if not isinstance(results_data, list) or len(results_data) != 4:
            return Response(
                {"error": "Must submit trick results for exactly 4 players as a list."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Get bids to verify and use in scoring
        bids_map = {b.player_id: b for b in Bid.objects.filter(round=round_obj)}
        if len(bids_map) != 4:
            return Response(
                {"error": "All 4 players must place their bids before submitting results."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Validate tricks won
        tricks_dict = {}
        for r_entry in results_data:
            p_id_str = r_entry.get('player_id')
            tricks = r_entry.get('tricks_won')
            
            try:
                from uuid import UUID
                p_uuid = UUID(p_id_str)
            except (ValueError, TypeError):
                return Response(
                    {"error": f"Invalid player_id UUID: {p_id_str}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if p_uuid not in bids_map:
                return Response(
                    {"error": f"No bid found for player {p_id_str} in this round."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                tricks = int(tricks)
                tricks_dict[p_uuid] = tricks
            except (ValueError, TypeError):
                return Response(
                    {"error": f"Tricks won must be an integer. Got: {tricks}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        try:
            validate_tricks(tricks_dict)
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Save results, calculate scores, update match scores, and handle round/match progression
        with transaction.atomic():
            # 1. Calculate and save round results
            for p_uuid, tricks in tricks_dict.items():
                player_bid = bids_map[p_uuid]
                score = calculate_score(player_bid.bid, tricks, player_bid.is_blind)
                
                RoundResult.objects.update_or_create(
                    round=round_obj,
                    player_id=p_uuid,
                    defaults={'tricks_won': tricks, 'score': score}
                )
                
            # Lock this round if requested
            if should_lock:
                round_obj.status = 'COMPLETE'
                round_obj.locked = True
            else:
                round_obj.status = 'SCORING'
                round_obj.locked = False
            round_obj.save()
            
            # 2. Re-calculate total match score for each player
            match = round_obj.match
            match_players = MatchPlayer.objects.filter(match=match)
            
            for mp in match_players:
                # Sum scores from all rounds with results in this match
                completed_scores = RoundResult.objects.filter(
                    round__match=match,
                    player=mp.player
                ).values_list('score', flat=True)
                
                total = sum(completed_scores)
                
                MatchScore.objects.update_or_create(
                    match=match,
                    player=mp.player,
                    defaults={'total_score': total}
                )
                
            if should_lock:
                # 3. Handle next round creation or match completion
                next_round_no = round_obj.round_no + 1
                if next_round_no <= 13:
                    # Match is ROUND_COMPLETE for the current round, ready for next round
                    match.status = 'ROUND_COMPLETE'
                    match.save()
                    
                    # Auto-create next round in DRAFT state
                    # The user can then start it (transitioning match to BIDDING)
                    Round.objects.get_or_create(
                        match=match,
                        round_no=next_round_no,
                        defaults={
                            'status': 'DRAFT',
                            'trump_card': 'Spades',  # Standard default
                            'locked': False
                        }
                    )
                    
                    # Automatically transition match back to BIDDING so they can enter next bids
                    match.status = 'BIDDING'
                    match.save()
                    
                    next_round = Round.objects.get(match=match, round_no=next_round_no)
                    next_round.status = 'BIDDING'
                    next_round.save()
                    
                else:
                    # 13 rounds completed -> Match Complete!
                    match.status = 'MATCH_COMPLETE'
                    match.completed_at = datetime.datetime.now()
                    match.save()
                    
        serializer = self.get_serializer(round_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)
