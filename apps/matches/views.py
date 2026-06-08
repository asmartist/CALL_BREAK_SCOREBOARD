import datetime
import uuid
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.matches.models import Player, Match, MatchPlayer, MatchScore
from apps.matches.serializers import PlayerSerializer, MatchSerializer
from apps.rounds.models import Round

class PlayerViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.all().order_by('name')
    serializer_class = PlayerSerializer


class MatchViewSet(viewsets.ModelViewSet):
    queryset = Match.objects.all().order_by('-created_at')
    serializer_class = MatchSerializer

    def create(self, request, *args, **kwargs):
        players_data = request.data.get('players', [])
        if len(players_data) != 4:
            return Response(
                {"error": "Exactly 4 players are required to create a match."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        rule_profile_id = request.data.get('rule_profile_id')
        if rule_profile_id:
            try:
                rule_profile_id = uuid.UUID(rule_profile_id)
            except ValueError:
                rule_profile_id = None
                
        # Create Match
        match = Match.objects.create(status='DRAFT', rule_profile_id=rule_profile_id)
        
        # Resolve players and create MatchPlayers
        for idx, p_ident in enumerate(players_data):
            player = None
            # Check if it's a valid UUID
            try:
                uuid.UUID(str(p_ident))
                player = Player.objects.filter(id=p_ident).first()
            except (ValueError, TypeError):
                pass
            
            if not player:
                # Resolve by name
                name_str = str(p_ident).strip()
                if not name_str:
                    name_str = f"Player {idx + 1}"
                player, _ = Player.objects.get_or_create(name=name_str)
                
            MatchPlayer.objects.create(
                match=match,
                player=player,
                seat_no=idx + 1
            )
            
            # Initialize Match Score
            MatchScore.objects.create(
                match=match,
                player=player,
                total_score=0.00
            )
            
        match.status = 'READY'
        match.save()
        
        serializer = self.get_serializer(match)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        match = self.get_object()
        if match.status not in ['DRAFT', 'READY']:
            return Response(
                {"error": f"Cannot start match in status: {match.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        players_count = match.match_players.count()
        if players_count != 4:
            return Response(
                {"error": f"Exactly 4 players required. Currently has: {players_count}"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Start match: transitions status to BIDDING
        match.status = 'BIDDING'
        match.save()
        
        # Create Round 1
        r, created = Round.objects.get_or_create(
            match=match,
            round_no=1,
            defaults={
                'status': 'BIDDING',
                'trump_card': 'Spades',  # Standard Call Break default trump
                'locked': False
            }
        )
        
        return Response({
            "message": "Match started successfully",
            "match_status": match.status,
            "round_id": str(r.id),
            "round_no": r.round_no
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        match = self.get_object()
        if match.status == 'MATCH_COMPLETE':
            return Response(
                {"error": "Match is already completed"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        match.status = 'MATCH_COMPLETE'
        match.completed_at = datetime.datetime.now()
        match.save()
        
        return Response({
            "message": "Match completed",
            "match_status": match.status,
            "completed_at": match.completed_at
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def sync(self, request):
        payload = request.data
        if isinstance(payload, dict):
            matches_data = [payload]
        elif isinstance(payload, list):
            matches_data = payload
        else:
            return Response(
                {"error": "Invalid payload format. Expected object or array."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        synced_ids = []
        errors = []
        
        from django.db import transaction
        from apps.rounds.models import Round, Bid, RoundResult
        from apps.scoring.services import calculate_score
        
        for match_data in matches_data:
            match_id_str = match_data.get('id')
            if not match_id_str:
                errors.append({"error": "Missing match id in payload"})
                continue
                
            try:
                match_id = uuid.UUID(match_id_str)
            except ValueError:
                errors.append({"id": match_id_str, "error": "Invalid match UUID"})
                continue
                
            client_version = match_data.get('version', 1)
            status_val = match_data.get('status', 'DRAFT')
            trump_suit = match_data.get('trump_suit', 'Spades ♠')
            completed_at = match_data.get('completed_at')
            players_data = match_data.get('players', [])
            rounds_data = match_data.get('rounds', [])
            
            try:
                with transaction.atomic():
                    # 1. Lock and fetch or create Match
                    match, created = Match.objects.select_for_update().get_or_create(
                        id=match_id,
                        defaults={
                            'status': status_val,
                            'trump_suit': trump_suit,
                            'version': client_version,
                        }
                    )
                    
                    if not created:
                        if match.version > client_version:
                            synced_ids.append({
                                "id": str(match.id),
                                "status": "skipped",
                                "version": match.version,
                                "message": "Database has a newer version"
                            })
                            continue
                            
                        match.status = status_val
                        match.trump_suit = trump_suit
                        match.version = client_version
                        if completed_at:
                            match.completed_at = completed_at
                        match.save()
                        
                    # 2. Resolve Players
                    player_mapping = {}
                    for idx, p_entry in enumerate(players_data):
                        p_id_str = p_entry.get('id')
                        p_name = p_entry.get('name', '').strip()
                        seat_no = p_entry.get('seat_no', idx + 1)
                        
                        p_uuid = None
                        if p_id_str:
                            try:
                                p_uuid = uuid.UUID(p_id_str)
                            except ValueError:
                                pass
                                
                        player = None
                        if p_uuid:
                            player = Player.objects.filter(id=p_uuid).first()
                            
                        if not player and p_name:
                            player = Player.objects.filter(name=p_name).first()
                            
                        if not player:
                            player = Player.objects.create(
                                id=p_uuid or uuid.uuid4(),
                                name=p_name or f"Player {seat_no}"
                            )
                            
                        player_mapping[p_id_str or str(player.id)] = player
                        
                        MatchPlayer.objects.get_or_create(
                            match=match,
                            player=player,
                            defaults={'seat_no': seat_no}
                        )
                        
                        MatchScore.objects.get_or_create(
                            match=match,
                            player=player,
                            defaults={'total_score': 0.0}
                        )
                        
                    # 3. Sync Rounds
                    for r_entry in rounds_data:
                        r_id_str = r_entry.get('id')
                        r_no = r_entry.get('round_no')
                        r_status = r_entry.get('status', 'DRAFT')
                        r_locked = r_entry.get('locked', False)
                        r_bids_locked = r_entry.get('bids_locked', False)
                        r_trump = r_entry.get('trump_card', 'Spades')
                        r_bids = r_entry.get('bids', [])
                        r_results = r_entry.get('results', [])
                        
                        r_uuid = None
                        if r_id_str:
                            try:
                                r_uuid = uuid.UUID(r_id_str)
                            except ValueError:
                                pass
                                
                        round_obj, r_created = Round.objects.get_or_create(
                            match=match,
                            round_no=r_no,
                            defaults={
                                'id': r_uuid or uuid.uuid4(),
                                'status': r_status,
                                'locked': r_locked,
                                'bids_locked': r_bids_locked,
                                'trump_card': r_trump
                            }
                        )
                        
                        if not r_created and round_obj.locked:
                            continue
                            
                        if not r_created:
                            round_obj.status = r_status
                            round_obj.locked = r_locked
                            round_obj.bids_locked = r_bids_locked
                            round_obj.trump_card = r_trump
                            round_obj.save()
                            
                        # Sync Bids
                        bids_map = {}
                        for b_entry in r_bids:
                            b_p_id = b_entry.get('player_id')
                            b_val = b_entry.get('bid')
                            b_blind = b_entry.get('is_blind', False)
                            
                            player_inst = player_mapping.get(b_p_id)
                            if player_inst and b_val is not None:
                                Bid.objects.update_or_create(
                                    round=round_obj,
                                    player=player_inst,
                                    defaults={'bid': b_val, 'is_blind': b_blind}
                                )
                                bids_map[player_inst.id] = (b_val, b_blind)
                                
                        # Sync Results
                        for res_entry in r_results:
                            res_p_id = res_entry.get('player_id')
                            tricks = res_entry.get('tricks_won')
                            
                            player_inst = player_mapping.get(res_p_id)
                            if player_inst and tricks is not None and player_inst.id in bids_map:
                                bid_val, b_blind = bids_map[player_inst.id]
                                score = calculate_score(bid_val, tricks, b_blind)
                                
                                RoundResult.objects.update_or_create(
                                    round=round_obj,
                                    player=player_inst,
                                    defaults={'tricks_won': tricks, 'score': score}
                                )
                                
                    # 4. Recalculate match scores
                    match_players = MatchPlayer.objects.filter(match=match)
                    for mp in match_players:
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
                        
                synced_ids.append({
                    "id": str(match_id),
                    "status": "success",
                    "version": client_version
                })
            except Exception as e:
                errors.append({"id": str(match_id), "error": str(e)})
                
        return Response({
            "synced": synced_ids,
            "errors": errors
        }, status=status.HTTP_200_OK if not errors else status.HTTP_207_MULTI_STATUS)
