from rest_framework import serializers
from apps.rounds.models import Round, Bid, RoundResult

class BidSerializer(serializers.ModelSerializer):
    player_name = serializers.ReadOnlyField(source='player.name')

    class Meta:
        model = Bid
        fields = ['id', 'round', 'player', 'player_name', 'bid', 'is_blind']


class RoundResultSerializer(serializers.ModelSerializer):
    player_name = serializers.ReadOnlyField(source='player.name')

    class Meta:
        model = RoundResult
        fields = ['id', 'round', 'player', 'player_name', 'tricks_won', 'score']


class RoundSerializer(serializers.ModelSerializer):
    bids = BidSerializer(many=True, read_only=True)
    results = RoundResultSerializer(many=True, read_only=True)

    class Meta:
        model = Round
        fields = [
            'id', 'match', 'round_no', 'trump_card', 
            'status', 'locked', 'bids_locked', 'bids', 'results'
        ]
