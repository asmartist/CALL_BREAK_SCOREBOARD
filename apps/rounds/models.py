import uuid
from django.db import models
from apps.matches.models import Match, Player

class Round(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('BIDDING', 'Bidding'),
        ('PLAYING', 'Playing'),
        ('LOCKED', 'Locked'),
        ('SCORING', 'Scoring'),
        ('COMPLETE', 'Complete'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, related_name='rounds', on_delete=models.CASCADE)
    round_no = models.IntegerField()
    trump_card = models.CharField(max_length=10, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    locked = models.BooleanField(default=False)
    bids_locked = models.BooleanField(default=False)

    class Meta:
        unique_together = ('match', 'round_no')
        ordering = ['round_no']

    def __str__(self):
        return f"Round {self.round_no} of Match {self.match.id}"


class Bid(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(Round, related_name='bids', on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name='bids', on_delete=models.CASCADE)
    bid = models.IntegerField()
    is_blind = models.BooleanField(default=False)

    class Meta:
        unique_together = ('round', 'player')

    def __str__(self):
        return f"Bid {self.bid} by {self.player.name} in Round {self.round.round_no}"


class RoundResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(Round, related_name='results', on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name='round_results', on_delete=models.CASCADE)
    tricks_won = models.IntegerField()
    score = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ('round', 'player')

    def __str__(self):
        return f"Result: {self.player.name} won {self.tricks_won} tricks (Score: {self.score}) in Round {self.round.round_no}"
