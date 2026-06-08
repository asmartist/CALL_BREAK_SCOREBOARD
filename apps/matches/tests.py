from django.test import TestCase
from rest_framework.test import APIClient
from apps.matches.models import Player, Match, MatchPlayer, MatchScore
from apps.rounds.models import Round

class MatchTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_match_resolves_players(self):
        # Create match by passing player names
        payload = {
            "players": ["Alice", "Bob", "Charlie", "David"]
        }
        response = self.client.post("/api/matches/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "READY")
        
        # Verify players were created in DB
        self.assertEqual(Player.objects.count(), 4)
        self.assertTrue(Player.objects.filter(name="Alice").exists())
        
        # Verify seat numbers
        match_id = response.data["id"]
        match_players = MatchPlayer.objects.filter(match_id=match_id).order_by('seat_no')
        self.assertEqual(len(match_players), 4)
        self.assertEqual(match_players[0].player.name, "Alice")
        self.assertEqual(match_players[0].seat_no, 1)
        self.assertEqual(match_players[3].player.name, "David")
        self.assertEqual(match_players[3].seat_no, 4)
        
        # Verify scores initialized
        scores = MatchScore.objects.filter(match_id=match_id)
        self.assertEqual(scores.count(), 4)
        for s in scores:
            self.assertEqual(float(s.total_score), 0.0)

    def test_start_match_creates_round_one(self):
        # Setup match
        payload = {"players": ["Alice", "Bob", "Charlie", "David"]}
        res = self.client.post("/api/matches/", payload, format="json")
        match_id = res.data["id"]
        
        # Start match
        start_res = self.client.post(f"/api/matches/{match_id}/start/")
        self.assertEqual(start_res.status_code, 200)
        self.assertEqual(start_res.data["match_status"], "BIDDING")
        
        # Verify Round 1 created
        self.assertEqual(Round.objects.filter(match_id=match_id).count(), 1)
        r1 = Round.objects.get(match_id=match_id, round_no=1)
        self.assertEqual(r1.status, "BIDDING")
        self.assertFalse(r1.locked)

    def test_match_trump_suit_lifecycle(self):
        # Setup match
        payload = {"players": ["Alice", "Bob", "Charlie", "David"]}
        res = self.client.post("/api/matches/", payload, format="json")
        match_id = res.data["id"]
        
        # Verify default trump suit
        self.assertEqual(res.data["trump_suit"], "Spades ♠")
        
        # Update trump suit via PATCH
        patch_payload = {"trump_suit": "Hearts ♥"}
        patch_res = self.client.patch(f"/api/matches/{match_id}/", patch_payload, format="json")
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["trump_suit"], "Hearts ♥")
        
        # Verify saved in DB
        match_db = Match.objects.get(id=match_id)
        self.assertEqual(match_db.trump_suit, "Hearts ♥")
