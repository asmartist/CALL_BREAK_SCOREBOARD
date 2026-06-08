import uuid
from django.db import models

class Player(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Match(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('READY', 'Ready'),
        ('BIDDING', 'Bidding'),
        ('PLAYING', 'Playing'),
        ('LOCKED', 'Locked'),
        ('SCORING', 'Scoring'),
        ('ROUND_COMPLETE', 'Round Complete'),
        ('MATCH_COMPLETE', 'Match Complete'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    rule_profile_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    trump_suit = models.CharField(max_length=20, default='Spades ♠')
    version = models.IntegerField(default=1)

    def __str__(self):
        return f"Match {self.id} ({self.status})"


class MatchPlayer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, related_name='match_players', on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name='match_participations', on_delete=models.CASCADE)
    seat_no = models.IntegerField()

    class Meta:
        unique_together = [
            ('match', 'player'),
            ('match', 'seat_no')
        ]
        ordering = ['seat_no']

    def __str__(self):
        return f"{self.player.name} in Match {self.match.id} (Seat {self.seat_no})"


class MatchScore(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, related_name='scores', on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name='match_scores', on_delete=models.CASCADE)
    total_score = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ('match', 'player')

    def __str__(self):
        return f"{self.player.name}: {self.total_score} in Match {self.match.id}"
