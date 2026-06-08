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
