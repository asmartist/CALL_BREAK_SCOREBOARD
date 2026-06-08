from django.test import TestCase
from rest_framework.test import APIClient
from apps.matches.models import Player, Match, MatchPlayer, MatchScore
from apps.rounds.models import Round, Bid, RoundResult
from apps.scoring.services import calculate_score
from decimal import Decimal

class RoundAndRulesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Setup players and match
        payload = {"players": ["Alice", "Bob", "Charlie", "David"]}
        res = self.client.post("/api/matches/", payload, format="json")
        self.match_id = res.data["id"]
        
        # Start match (creates round 1)
        self.client.post(f"/api/matches/{self.match_id}/start/")
        self.round_1 = Round.objects.get(match_id=self.match_id, round_no=1)
        
        # Keep track of player objects
        self.players = list(Player.objects.all())

    def test_scoring_logic_direct(self):
        # 1. Standard success, no extra tricks
        self.assertEqual(calculate_score(3, 3), Decimal('30.00'))
        
        # 2. Standard success with 1 extra trick
        self.assertEqual(calculate_score(3, 4), Decimal('31.00'))
        
        # 3. Standard success with 2 extra tricks
        self.assertEqual(calculate_score(3, 5), Decimal('32.00'))
        
        # 4. Standard success with 3 extra tricks (capped at 2 extra tricks -> 32.00)
        self.assertEqual(calculate_score(3, 6), Decimal('32.00'))
        
        # 5. Standard failure
        self.assertEqual(calculate_score(4, 3), Decimal('-40.00'))
        
        # 6. Blind success, no extra tricks (double score)
        self.assertEqual(calculate_score(5, 5, is_blind=True), Decimal('100.00'))
        
        # 7. Blind success, 1 extra trick (double score of base + extra)
        # base=50, extra=1 -> score = 51 -> doubled = 102.00
        self.assertEqual(calculate_score(5, 6, is_blind=True), Decimal('102.00'))
        
        # 8. Blind failure (double penalty)
        self.assertEqual(calculate_score(5, 4, is_blind=True), Decimal('-100.00'))
        
        # 9. Exact 8 tricks rule (double score)
        # success: bid 6, tricks 8 -> normal score 62.00 -> doubled = 124.00
        self.assertEqual(calculate_score(6, 8), Decimal('124.00'))
        # failure: bid 9, tricks 8 -> normal score -90.00 -> doubled = -180.00
        self.assertEqual(calculate_score(9, 8), Decimal('-180.00'))

    def test_bids_validation_and_submission(self):
        r_id = self.round_1.id
        
        # Invalid: bid too low
        payload = [
            {"player_id": str(self.players[0].id), "bid": 1, "is_blind": False},
            {"player_id": str(self.players[1].id), "bid": 3, "is_blind": False},
            {"player_id": str(self.players[2].id), "bid": 4, "is_blind": False},
            {"player_id": str(self.players[3].id), "bid": 2, "is_blind": False},
        ]
        res = self.client.put(f"/api/rounds/{r_id}/bids/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Minimum bid is 2", res.data["error"])

        # Invalid: blind bid too low
        payload = [
            {"player_id": str(self.players[0].id), "bid": 4, "is_blind": True},
            {"player_id": str(self.players[1].id), "bid": 3, "is_blind": False},
            {"player_id": str(self.players[2].id), "bid": 4, "is_blind": False},
            {"player_id": str(self.players[3].id), "bid": 2, "is_blind": False},
        ]
        res = self.client.put(f"/api/rounds/{r_id}/bids/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Blind bid must be at least 5", res.data["error"])

        # Valid bids submission
        payload = [
            {"player_id": str(self.players[0].id), "bid": 3, "is_blind": False},
            {"player_id": str(self.players[1].id), "bid": 5, "is_blind": True},
            {"player_id": str(self.players[2].id), "bid": 4, "is_blind": False},
            {"player_id": str(self.players[3].id), "bid": 2, "is_blind": False},
        ]
        res = self.client.put(f"/api/rounds/{r_id}/bids/", payload, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "PLAYING")
        self.assertEqual(Bid.objects.filter(round_id=r_id).count(), 4)

    def test_results_validation_and_scoring(self):
        r_id = self.round_1.id
        
        # Submit valid bids first
        bids_payload = [
            {"player_id": str(self.players[0].id), "bid": 3, "is_blind": False},
            {"player_id": str(self.players[1].id), "bid": 5, "is_blind": True},
            {"player_id": str(self.players[2].id), "bid": 4, "is_blind": False},
            {"player_id": str(self.players[3].id), "bid": 2, "is_blind": False},
        ]
        self.client.put(f"/api/rounds/{r_id}/bids/", bids_payload, format="json")
        
        # Submit results: tricks sum not 13
        results_payload = [
            {"player_id": str(self.players[0].id), "tricks_won": 3},
            {"player_id": str(self.players[1].id), "tricks_won": 5},
            {"player_id": str(self.players[2].id), "tricks_won": 4},
            {"player_id": str(self.players[3].id), "tricks_won": 0},  # Sum = 12
        ]
        res = self.client.put(f"/api/rounds/{r_id}/results/", results_payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Total tricks won across all players must equal 13", res.data["error"])
        
        # Submit valid tricks: sum = 13
        # Player 0: bid 3, tricks 3 -> score 3.0
        # Player 1: bid 5, tricks 5, blind -> score 10.0
        # Player 2: bid 4, tricks 3 -> score -4.0
        # Player 3: bid 2, tricks 2 -> score 2.0
        results_payload = [
            {"player_id": str(self.players[0].id), "tricks_won": 3},
            {"player_id": str(self.players[1].id), "tricks_won": 5},
            {"player_id": str(self.players[2].id), "tricks_won": 3},
            {"player_id": str(self.players[3].id), "tricks_won": 2},
        ]
        res = self.client.put(f"/api/rounds/{r_id}/results/", results_payload, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "COMPLETE")
        self.assertTrue(res.data["locked"])
        
        # Verify round results in DB
        self.assertEqual(RoundResult.objects.filter(round_id=r_id).count(), 4)
        r0 = RoundResult.objects.get(round_id=r_id, player=self.players[0])
        self.assertEqual(float(r0.score), 30.0)
        
        r1 = RoundResult.objects.get(round_id=r_id, player=self.players[1])
        self.assertEqual(float(r1.score), 100.0)
        
        r2 = RoundResult.objects.get(round_id=r_id, player=self.players[2])
        self.assertEqual(float(r2.score), -40.0)
        
        # Verify match scores updated
        ms0 = MatchScore.objects.get(match_id=self.match_id, player=self.players[0])
        self.assertEqual(float(ms0.total_score), 30.0)
        
        ms2 = MatchScore.objects.get(match_id=self.match_id, player=self.players[2])
        self.assertEqual(float(ms2.total_score), -40.0)

        # Check that Round 2 was auto-created
        self.assertTrue(Round.objects.filter(match_id=self.match_id, round_no=2).exists())
        r2_obj = Round.objects.get(match_id=self.match_id, round_no=2)
        self.assertEqual(r2_obj.status, "BIDDING")

    def test_stats_calculations(self):
        # Setup a completed round so there is data
        r_id = self.round_1.id
        bids_payload = [
            {"player_id": str(self.players[0].id), "bid": 3, "is_blind": False},
            {"player_id": str(self.players[1].id), "bid": 5, "is_blind": True},
            {"player_id": str(self.players[2].id), "bid": 4, "is_blind": False},
            {"player_id": str(self.players[3].id), "bid": 2, "is_blind": False},
        ]
        self.client.put(f"/api/rounds/{r_id}/bids/", bids_payload, format="json")
        results_payload = [
            {"player_id": str(self.players[0].id), "tricks_won": 3},
            {"player_id": str(self.players[1].id), "tricks_won": 5},
            {"player_id": str(self.players[2].id), "tricks_won": 3},
            {"player_id": str(self.players[3].id), "tricks_won": 2},
        ]
        self.client.put(f"/api/rounds/{r_id}/results/", results_payload, format="json")
        
        # Request player stats
        res = self.client.get(f"/api/stats/?player_id={self.players[1].id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["player_name"], self.players[1].name)
        self.assertEqual(res.data["avg_bid"], 5.0)
        self.assertEqual(res.data["total_blind_bids"], 1)
        self.assertEqual(res.data["blind_success_rate"], 100.0)

    def test_exports_endpoints(self):
        # Verify JSON export
        res = self.client.get(f"/api/matches/{self.match_id}/export/?format=json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/json')
        
        # Verify CSV export
        res_csv = self.client.get(f"/api/matches/{self.match_id}/export/?format=csv")
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv['Content-Type'], 'text/csv')

        # Verify PDF export
        res_pdf = self.client.get(f"/api/matches/{self.match_id}/export/?format=pdf")
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')
