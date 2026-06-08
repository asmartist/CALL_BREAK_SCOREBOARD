from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.stats.services import get_all_players_stats, get_player_stats
from apps.matches.models import Player

class StatsListView(APIView):
    def get(self, request):
        player_id = request.query_params.get('player_id')
        if player_id:
            try:
                from uuid import UUID
                p_uuid = UUID(player_id)
                player = Player.objects.filter(id=p_uuid).first()
                if not player:
                    return Response({"error": "Player not found"}, status=status.HTTP_404_NOT_FOUND)
                stats_data = get_player_stats(player)
                return Response(stats_data, status=status.HTTP_200_OK)
            except ValueError:
                return Response({"error": "Invalid player_id UUID format"}, status=status.HTTP_400_BAD_REQUEST)
        
        stats_list = get_all_players_stats()
        return Response(stats_list, status=status.HTTP_200_OK)
