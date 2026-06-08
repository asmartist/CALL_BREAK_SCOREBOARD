from rest_framework import serializers
from apps.matches.models import Player, Match, MatchPlayer, MatchScore

class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ['id', 'name', 'created_at']


class MatchPlayerSerializer(serializers.ModelSerializer):
    player_name = serializers.ReadOnlyField(source='player.name')

    class Meta:
        model = MatchPlayer
        fields = ['id', 'player', 'player_name', 'seat_no']


class MatchScoreSerializer(serializers.ModelSerializer):
    player_name = serializers.ReadOnlyField(source='player.name')

    class Meta:
        model = MatchScore
        fields = ['id', 'player', 'player_name', 'total_score']


class MatchSerializer(serializers.ModelSerializer):
    match_players = MatchPlayerSerializer(many=True, read_only=True)
    scores = MatchScoreSerializer(many=True, read_only=True)
    rounds_count = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            'id', 'status', 'rule_profile_id', 'created_at', 
            'completed_at', 'match_players', 'scores', 'rounds_count',
            'trump_suit'
        ]

    def get_rounds_count(self, obj):
        return obj.rounds.count()
